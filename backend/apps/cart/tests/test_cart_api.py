"""API tests for the cart endpoints (mounted at /api/cart):

    GET    /api/cart            -> view cart (always 200, even anonymous)
    POST   /api/cart/add        -> add / increment a line
    PATCH  /api/cart/{item_id}  -> set quantity (clamped 0..stock)
    DELETE /api/cart/{item_id}  -> remove a line

These cover happy paths, totals, the quantity-clamp rules, and error/404
responses. Authorization rules live in test_cart_authorization.py.
"""
import json
from decimal import Decimal

import pytest

from apps.cart.models import Cart, CartItem


def _patch(api, path, data, headers):
    return api.patch(path, data=json.dumps(data),
                     content_type="application/json", headers=headers)


def _price(body):
    # total_price may serialize as a JSON string or number; normalize.
    return Decimal(str(body["total_price"]))


# --------------------------------------------------------------------------- #
# GET /api/cart
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_get_empty_cart_for_anonymous_without_session(api):
    resp = api.get("/api/cart")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["items"] == []
    assert body["total_quantity"] == 0
    assert _price(body) == Decimal("0.00")


@pytest.mark.django_db
def test_get_cart_reflects_items_and_totals(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(price="100.00", stock=10)
    api.post("/api/cart/add",
             data=json.dumps({"product_id": product.id, "quantity": 2}),
             content_type="application/json", headers=bearer(user))

    resp = api.get("/api/cart", headers=bearer(user))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 2
    assert body["items"][0]["product"]["id"] == product.id
    assert body["total_quantity"] == 2
    assert _price(body) == Decimal("200.00")


@pytest.mark.django_db
def test_totals_use_discounted_effective_price(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    # effective_price = discount_price while the product is active.
    product = product_factory(price="100.00", discount_price="80.00", stock=10)
    api.post("/api/cart/add",
             data=json.dumps({"product_id": product.id, "quantity": 3}),
             content_type="application/json", headers=bearer(user))

    body = api.get("/api/cart", headers=bearer(user)).json()
    assert _price(body) == Decimal("240.00")  # 3 * 80.00


# --------------------------------------------------------------------------- #
# POST /api/cart/add
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_add_creates_line_with_requested_quantity(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=10)
    resp = api.post("/api/cart/add",
                    data=json.dumps({"product_id": product.id, "quantity": 3}),
                    content_type="application/json", headers=bearer(user))
    assert resp.status_code == 200, resp.content
    assert resp.json()["total_quantity"] == 3
    assert CartItem.objects.get(product=product).quantity == 3


@pytest.mark.django_db
def test_add_defaults_quantity_to_one(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=10)
    resp = api.post("/api/cart/add",
                    data=json.dumps({"product_id": product.id}),
                    content_type="application/json", headers=bearer(user))
    assert resp.status_code == 200, resp.content
    assert CartItem.objects.get(product=product).quantity == 1


@pytest.mark.django_db
def test_re_adding_increments_existing_line(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=10)
    h = bearer(user)
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 2}),
             content_type="application/json", headers=h)
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 3}),
             content_type="application/json", headers=h)
    # One row, quantities summed.
    assert CartItem.objects.filter(product=product).count() == 1
    assert CartItem.objects.get(product=product).quantity == 5


@pytest.mark.django_db
def test_add_floors_non_positive_quantity_to_one(api, bearer, make_user, product_factory):
    """add uses max(1, quantity): 0 or negative still adds a single unit."""
    user = make_user("buyer")
    product = product_factory(stock=10)
    resp = api.post("/api/cart/add",
                    data=json.dumps({"product_id": product.id, "quantity": 0}),
                    content_type="application/json", headers=bearer(user))
    assert resp.status_code == 200, resp.content
    assert CartItem.objects.get(product=product).quantity == 1


@pytest.mark.django_db
def test_add_does_not_clamp_to_stock(api, bearer, make_user, product_factory):
    """Documented behavior: /add increments without a stock cap; the clamp is
    applied by PATCH (and, ultimately, checkout). Asserting the real behavior."""
    user = make_user("buyer")
    product = product_factory(stock=3)
    api.post("/api/cart/add",
             data=json.dumps({"product_id": product.id, "quantity": 10}),
             content_type="application/json", headers=bearer(user))
    assert CartItem.objects.get(product=product).quantity == 10


@pytest.mark.django_db
def test_add_unknown_product_returns_404(api, bearer, make_user):
    user = make_user("buyer")
    resp = api.post("/api/cart/add",
                    data=json.dumps({"product_id": 999999, "quantity": 1}),
                    content_type="application/json", headers=bearer(user))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_add_increments_product_cart_adds_counter(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=10)
    assert product.cart_adds_count == 0
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 1}),
             content_type="application/json", headers=bearer(user))
    product.refresh_from_db()
    assert product.cart_adds_count == 1


# --------------------------------------------------------------------------- #
# PATCH /api/cart/{item_id}
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_update_sets_exact_quantity(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=10)
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 1}),
             content_type="application/json", headers=bearer(user))
    item = CartItem.objects.get(product=product)

    resp = _patch(api, f"/api/cart/{item.id}", {"quantity": 4}, bearer(user))
    assert resp.status_code == 200, resp.content
    assert resp.json()["total_quantity"] == 4
    item.refresh_from_db()
    assert item.quantity == 4


@pytest.mark.django_db
def test_update_clamps_quantity_to_available_stock(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=5)
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 1}),
             content_type="application/json", headers=bearer(user))
    item = CartItem.objects.get(product=product)

    resp = _patch(api, f"/api/cart/{item.id}", {"quantity": 100}, bearer(user))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["total_quantity"] == 5  # capped at stock
    item.refresh_from_db()
    assert item.quantity == 5


@pytest.mark.django_db
def test_update_to_zero_keeps_line_but_drops_it_from_totals(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=5)
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 2}),
             content_type="application/json", headers=bearer(user))
    item = CartItem.objects.get(product=product)

    resp = _patch(api, f"/api/cart/{item.id}", {"quantity": 0}, bearer(user))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    # Line stays present (drawer can still show it) but contributes nothing.
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 0
    assert body["total_quantity"] == 0
    assert _price(body) == Decimal("0.00")
    assert CartItem.objects.filter(id=item.id).exists()


@pytest.mark.django_db
def test_update_negative_quantity_clamps_to_zero(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=5)
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 2}),
             content_type="application/json", headers=bearer(user))
    item = CartItem.objects.get(product=product)

    _patch(api, f"/api/cart/{item.id}", {"quantity": -7}, bearer(user))
    item.refresh_from_db()
    assert item.quantity == 0


@pytest.mark.django_db
def test_update_unknown_item_returns_404(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    # Give the user a cart so we reach the item lookup (not the "no cart" branch).
    product = product_factory(stock=5)
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 1}),
             content_type="application/json", headers=bearer(user))
    resp = _patch(api, "/api/cart/999999", {"quantity": 1}, bearer(user))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_update_when_caller_has_no_cart_returns_404(api, bearer, make_user):
    user = make_user("buyer")  # never added anything -> no cart
    resp = _patch(api, "/api/cart/1", {"quantity": 1}, bearer(user))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# DELETE /api/cart/{item_id}
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_delete_removes_the_line(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=5)
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 2}),
             content_type="application/json", headers=bearer(user))
    item = CartItem.objects.get(product=product)

    resp = api.delete(f"/api/cart/{item.id}", headers=bearer(user))
    assert resp.status_code == 200, resp.content
    assert resp.json()["items"] == []
    assert not CartItem.objects.filter(id=item.id).exists()


@pytest.mark.django_db
def test_delete_unknown_item_returns_404(api, bearer, make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=5)
    api.post("/api/cart/add", data=json.dumps({"product_id": product.id, "quantity": 1}),
             content_type="application/json", headers=bearer(user))
    resp = api.delete("/api/cart/999999", headers=bearer(user))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_delete_when_caller_has_no_cart_returns_404(api, bearer, make_user):
    user = make_user("buyer")
    resp = api.delete("/api/cart/1", headers=bearer(user))
    assert resp.status_code == 404
