"""Checkout: order creation, stock decrement, oversell protection, and the
authorization rules that gate it (staff / blocked / impersonation)."""
from decimal import Decimal

import pytest

from apps.cart.models import CartItem
from apps.orders.models import Order, OrderItem

CHECKOUT_URL = "/api/orders/checkout"


# --- happy paths ----------------------------------------------------------

@pytest.mark.django_db
def test_checkout_authenticated_creates_order_and_decrements_stock(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    user = make_user("buyer")
    p1 = product_factory(price="100.00", stock=10)
    p2 = product_factory(price="250.00", stock=5)
    make_cart(user=user, items=[(p1, 2), (p2, 1)])

    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 200, resp.content

    order = Order.objects.get(id=resp.json()["id"])
    assert order.user_id == user.id
    assert order.status == "new"
    assert order.total_price == Decimal("450.00")  # 100*2 + 250*1
    assert order.items.count() == 2
    # customer details are copied onto the order.
    assert order.first_name == "Ivan"
    assert order.email == "ivan@example.com"

    p1.refresh_from_db()
    p2.refresh_from_db()
    assert p1.stock == 8
    assert p2.stock == 4
    # trending engine counters advance by the purchased quantity.
    assert p1.purchases_count == 2
    assert p2.purchases_count == 1

    # cart line items are cleared once the order commits.
    assert CartItem.objects.filter(cart__user=user).count() == 0


@pytest.mark.django_db
def test_checkout_snapshots_title_and_price_immune_to_later_edits(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    user = make_user("buyer")
    product = product_factory(price="199.99", stock=3)
    original_title = product.title
    make_cart(user=user, items=[(product, 2)])

    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 200, resp.content

    item = OrderItem.objects.get(order_id=resp.json()["id"])
    assert item.product_title == original_title
    assert item.price == Decimal("199.99")
    assert item.quantity == 2

    # Editing the product afterwards must not rewrite the historical snapshot.
    product.title = "Renamed"
    product.price = Decimal("1.00")
    product.save(update_fields=["title", "price"])
    item.refresh_from_db()
    assert item.product_title == original_title
    assert item.price == Decimal("199.99")


@pytest.mark.django_db
def test_checkout_uses_effective_discount_price(
    product_factory, make_cart, checkout_payload, post_json
):
    # An active discount is the price actually charged and snapshotted.
    product = product_factory(price="1000.00", discount_price="200.00", stock=5)
    make_cart(session_id="anon-disc", items=[(product, 2)])

    resp = post_json(
        CHECKOUT_URL, checkout_payload(), headers={"X-Session-Id": "anon-disc"}
    )
    assert resp.status_code == 200, resp.content

    order = Order.objects.get(id=resp.json()["id"])
    assert order.total_price == Decimal("400.00")  # 200 * 2, not 1000 * 2
    item = order.items.get()
    assert item.price == Decimal("200.00")


@pytest.mark.django_db
def test_checkout_anonymous_uses_session_cart_and_no_bonuses(
    product_factory, make_cart, checkout_payload, post_json
):
    product = product_factory(price="100.00", stock=10)
    make_cart(session_id="anon-1", items=[(product, 3)])

    resp = post_json(
        CHECKOUT_URL, checkout_payload(), headers={"X-Session-Id": "anon-1"}
    )
    assert resp.status_code == 200, resp.content

    order = Order.objects.get(id=resp.json()["id"])
    assert order.user_id is None
    assert order.session_id == "anon-1"
    assert order.total_price == Decimal("300.00")
    assert order.bonus_earned == 0
    assert order.applied_bonuses == 0

    product.refresh_from_db()
    assert product.stock == 7


@pytest.mark.django_db
def test_checkout_excludes_zero_quantity_lines(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    user = make_user("buyer")
    bought = product_factory(price="100.00", stock=10)
    skipped = product_factory(price="500.00", stock=10)
    make_cart(user=user, items=[(bought, 2), (skipped, 0)])

    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 200, resp.content

    order = Order.objects.get(id=resp.json()["id"])
    assert order.items.count() == 1
    assert order.total_price == Decimal("200.00")
    skipped.refresh_from_db()
    assert skipped.stock == 10  # untouched


@pytest.mark.django_db
def test_checkout_exact_stock_succeeds_and_zeroes_stock(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    user = make_user("buyer")
    product = product_factory(price="100.00", stock=3)
    make_cart(user=user, items=[(product, 3)])

    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 200, resp.content

    product.refresh_from_db()
    assert product.stock == 0


# --- empty cart -----------------------------------------------------------

@pytest.mark.django_db
def test_checkout_no_cart_returns_400(
    bearer, make_user, checkout_payload, post_json
):
    user = make_user("buyer")  # never built a cart
    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 400


@pytest.mark.django_db
def test_checkout_empty_cart_returns_400(
    bearer, make_user, make_cart, checkout_payload, post_json
):
    user = make_user("buyer")
    make_cart(user=user, items=[])
    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 400
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_only_zero_quantity_items_returns_400(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    user = make_user("buyer")
    product = product_factory(stock=10)
    make_cart(user=user, items=[(product, 0)])
    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 400
    assert Order.objects.count() == 0


# --- oversell protection (correctness, not concurrency) -------------------

@pytest.mark.django_db
def test_checkout_cannot_oversell_returns_409_and_rolls_back(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    user = make_user("buyer")
    product = product_factory(price="100.00", stock=2)
    make_cart(user=user, items=[(product, 5)])

    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 409

    # Nothing was committed: no order, stock and counters untouched.
    assert Order.objects.count() == 0
    product.refresh_from_db()
    assert product.stock == 2
    assert product.purchases_count == 0


@pytest.mark.django_db
def test_checkout_is_all_or_nothing_when_one_line_is_short(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    user = make_user("buyer")
    plenty = product_factory(price="100.00", stock=10)
    short = product_factory(price="100.00", stock=1)
    make_cart(user=user, items=[(plenty, 2), (short, 3)])

    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 409

    assert Order.objects.count() == 0
    plenty.refresh_from_db()
    short.refresh_from_db()
    # The sufficient product must not have been decremented either.
    assert plenty.stock == 10
    assert short.stock == 1


# --- authorization --------------------------------------------------------

@pytest.mark.django_db
def test_staff_cannot_checkout_403(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    staff = make_user("employee", is_staff=True)
    product = product_factory(stock=5)
    make_cart(user=staff, items=[(product, 1)])

    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(staff))
    assert resp.status_code == 403

    assert Order.objects.count() == 0
    product.refresh_from_db()
    assert product.stock == 5  # guard fires before any stock change


@pytest.mark.django_db
def test_superuser_cannot_checkout_403(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    admin = make_user("root", is_superuser=True)
    product = product_factory(stock=5)
    make_cart(user=admin, items=[(product, 1)])

    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(admin))
    assert resp.status_code == 403
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_blocked_customer_cannot_checkout_403(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json,
    block_user,
):
    user = make_user("blocked")
    block_user(user)
    product = product_factory(stock=5)
    make_cart(user=user, items=[(product, 1)])

    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    assert resp.status_code == 403
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_impersonation_token_cannot_checkout_403(
    make_user, product_factory, make_cart, checkout_payload, post_json,
    impersonation_headers,
):
    operator = make_user("op", is_staff=True)
    victim = make_user("victim")
    product = product_factory(stock=5)
    make_cart(user=victim, items=[(product, 1)])

    headers = impersonation_headers(victim, operator)
    resp = post_json(CHECKOUT_URL, checkout_payload(), headers=headers)
    assert resp.status_code == 403

    # No real order is placed while an operator is "viewing as" the customer.
    assert Order.objects.count() == 0
    product.refresh_from_db()
    assert product.stock == 5


# --- input validation -----------------------------------------------------

@pytest.mark.django_db
def test_checkout_missing_required_field_returns_422(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json
):
    user = make_user("buyer")
    make_cart(user=user, items=[(product_factory(stock=5), 1)])
    payload = checkout_payload()
    del payload["first_name"]  # required by CheckoutIn

    resp = post_json(CHECKOUT_URL, payload, headers=bearer(user))
    assert resp.status_code == 422
    assert Order.objects.count() == 0
