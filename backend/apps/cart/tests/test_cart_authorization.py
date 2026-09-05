"""Authorization / permission tests for the cart endpoints.

Rules under test:
  * Anonymous shoppers use an X-Session-Id header; writes without it 400.
  * Staff/superuser accounts are employees: they may VIEW a cart but every
    mutating action is 403.
  * Blocked customers are refused writes (403).
  * Impersonation tokens (staff "viewing as" a customer) are read-only: 403.
  * Cart items are private to their cart — you cannot patch/delete a line that
    belongs to someone else's cart (404, never a cross-cart mutation).
"""
import json

import pytest

from apps.accounts.models import Profile
from apps.cart.models import Cart, CartItem


def _add(api, product_id, headers, quantity=1):
    return api.post("/api/cart/add",
                    data=json.dumps({"product_id": product_id, "quantity": quantity}),
                    content_type="application/json", headers=headers)


def _patch(api, path, data, headers):
    return api.patch(path, data=json.dumps(data),
                     content_type="application/json", headers=headers)


def _impersonation_headers(api, bearer, operator, target):
    resp = api.post(f"/api/support/admin/impersonate/{target.id}",
                    content_type="application/json", headers=bearer(operator))
    assert resp.status_code == 200, resp.content
    token = resp.json()["access"]
    return {"Authorization": f"Bearer {token}", "X-Session-Id": "imp-session"}


# --------------------------------------------------------------------------- #
# Anonymous shoppers (X-Session-Id)
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_anonymous_add_requires_session_id_header(api, product_factory):
    product = product_factory(stock=5)
    resp = _add(api, product.id, headers={})  # no auth, no X-Session-Id
    assert resp.status_code == 400
    assert "X-Session-Id" in resp.json().get("detail", "")


@pytest.mark.django_db
def test_anonymous_add_with_session_id_creates_session_cart(api, product_factory):
    product = product_factory(stock=5)
    resp = _add(api, product.id, headers={"X-Session-Id": "guest-1"}, quantity=2)
    assert resp.status_code == 200, resp.content
    cart = Cart.objects.get(session_id="guest-1")
    assert cart.user_id is None
    assert cart.items.get(product=product).quantity == 2


@pytest.mark.django_db
def test_anonymous_carts_are_isolated_by_session_id(api, product_factory):
    product = product_factory(stock=5)
    _add(api, product.id, headers={"X-Session-Id": "guest-A"}, quantity=1)

    # A different session sees an empty cart.
    body = api.get("/api/cart", headers={"X-Session-Id": "guest-B"}).json()
    assert body["items"] == []
    assert body["total_quantity"] == 0


# --------------------------------------------------------------------------- #
# Staff / superuser: read allowed, writes forbidden
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_staff_may_view_cart(api, bearer, make_user):
    staff = make_user("op", is_staff=True)
    resp = api.get("/api/cart", headers=bearer(staff))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_staff_cannot_add_to_cart(api, bearer, make_user, product_factory):
    staff = make_user("op", is_staff=True)
    product = product_factory(stock=5)
    resp = _add(api, product.id, headers=bearer(staff))
    assert resp.status_code == 403
    assert not CartItem.objects.exists()


@pytest.mark.django_db
def test_superuser_cannot_add_to_cart(api, bearer, make_user, product_factory):
    root = make_user("root", is_superuser=True)
    product = product_factory(stock=5)
    resp = _add(api, product.id, headers=bearer(root))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_staff_cannot_update_or_delete_a_customer_line(api, bearer, make_user, product_factory):
    """Staff is blocked before any item lookup, even on a line that exists."""
    customer = make_user("cust")
    staff = make_user("op", is_staff=True)
    product = product_factory(stock=5)
    _add(api, product.id, headers=bearer(customer), quantity=1)
    item = CartItem.objects.get(product=product)

    assert _patch(api, f"/api/cart/{item.id}", {"quantity": 3}, bearer(staff)).status_code == 403
    assert api.delete(f"/api/cart/{item.id}", headers=bearer(staff)).status_code == 403
    item.refresh_from_db()
    assert item.quantity == 1  # untouched


# --------------------------------------------------------------------------- #
# Blocked customers
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_blocked_customer_cannot_add_to_cart(api, bearer, make_user, product_factory):
    user = make_user("banned")
    Profile.objects.update_or_create(user=user, defaults={"blocked_permanent": True})
    product = product_factory(stock=5)
    resp = _add(api, product.id, headers=bearer(user))
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# Impersonation is read-only
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_impersonation_can_view_but_not_add(api, bearer, make_user, product_factory):
    operator = make_user("op", is_staff=True)
    victim = make_user("victim")
    product = product_factory(stock=5)
    h = _impersonation_headers(api, bearer, operator, victim)

    # Reading the victim's cart is allowed while impersonating...
    assert api.get("/api/cart", headers=h).status_code == 200
    # ...but writing to it is not.
    assert _add(api, product.id, headers=h).status_code == 403
    assert not CartItem.objects.exists()


# --------------------------------------------------------------------------- #
# Cart-item ownership
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_user_cannot_update_another_users_cart_item(api, bearer, make_user, product_factory):
    alice = make_user("alice")
    bob = make_user("bob")
    product_a = product_factory(stock=5)
    product_b = product_factory(stock=5)

    _add(api, product_a.id, headers=bearer(alice), quantity=2)
    alice_item = CartItem.objects.get(product=product_a)
    # Bob must own a cart, so we hit the item-ownership check (not the no-cart branch).
    _add(api, product_b.id, headers=bearer(bob), quantity=1)

    resp = _patch(api, f"/api/cart/{alice_item.id}", {"quantity": 99}, bearer(bob))
    assert resp.status_code == 404
    alice_item.refresh_from_db()
    assert alice_item.quantity == 2  # Alice's line is untouched


@pytest.mark.django_db
def test_user_cannot_delete_another_users_cart_item(api, bearer, make_user, product_factory):
    alice = make_user("alice")
    bob = make_user("bob")
    product_a = product_factory(stock=5)
    product_b = product_factory(stock=5)

    _add(api, product_a.id, headers=bearer(alice), quantity=2)
    alice_item = CartItem.objects.get(product=product_a)
    _add(api, product_b.id, headers=bearer(bob), quantity=1)

    resp = api.delete(f"/api/cart/{alice_item.id}", headers=bearer(bob))
    assert resp.status_code == 404
    assert CartItem.objects.filter(id=alice_item.id).exists()


@pytest.mark.django_db
def test_anonymous_session_cannot_touch_another_sessions_item(api, product_factory):
    product_a = product_factory(stock=5)
    product_b = product_factory(stock=5)
    _add(api, product_a.id, headers={"X-Session-Id": "sess-A"}, quantity=1)
    item_a = CartItem.objects.get(product=product_a)
    _add(api, product_b.id, headers={"X-Session-Id": "sess-B"}, quantity=1)

    resp = api.delete(f"/api/cart/{item_a.id}", headers={"X-Session-Id": "sess-B"})
    assert resp.status_code == 404
    assert CartItem.objects.filter(id=item_a.id).exists()
