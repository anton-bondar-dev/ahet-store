"""Loyalty bonuses at checkout: earning, applying, and the clamping rules.

Earned = Σ product.bonus_amount × qty (bonus_amount = custom_bonus, else 1% of
the effective price). Applied bonuses (1 bonus = 1 UAH) are clamped by three
ceilings: the requested amount, a percentage cap on the subtotal (75% at
≥500 UAH else 50%), and the account balance. Spending bonuses earns none.
"""
from decimal import Decimal

import pytest

from apps.orders.models import Order

CHECKOUT_URL = "/api/orders/checkout"


def _order_from(resp):
    assert resp.status_code == 200, resp.content
    return Order.objects.get(id=resp.json()["id"])


# --- earning --------------------------------------------------------------

@pytest.mark.django_db
def test_authenticated_user_earns_bonuses_credited_to_balance(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json,
    set_bonus_balance,
):
    user = make_user("buyer")
    profile = set_bonus_balance(user, 0)
    product = product_factory(price="300.00", stock=10)  # bonus_amount = 3
    make_cart(user=user, items=[(product, 2)])

    order = _order_from(
        post_json(CHECKOUT_URL, checkout_payload(applied_bonuses=0), headers=bearer(user))
    )
    assert order.bonus_earned == 6  # 3 * 2
    assert order.applied_bonuses == 0
    assert order.total_price == Decimal("600.00")

    profile.refresh_from_db()
    assert profile.bonus_balance == 6


@pytest.mark.django_db
def test_custom_bonus_overrides_percentage(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json,
    set_bonus_balance,
):
    user = make_user("buyer")
    profile = set_bonus_balance(user, 0)
    product = product_factory(price="100.00", stock=10, custom_bonus=50)
    make_cart(user=user, items=[(product, 2)])

    order = _order_from(
        post_json(CHECKOUT_URL, checkout_payload(), headers=bearer(user))
    )
    assert order.bonus_earned == 100  # 50 * 2, ignoring the 1%-of-price default
    profile.refresh_from_db()
    assert profile.bonus_balance == 100


# --- applying + clamping --------------------------------------------------

@pytest.mark.django_db
def test_applied_bonuses_capped_at_50pct_below_500(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json,
    set_bonus_balance,
):
    user = make_user("buyer")
    profile = set_bonus_balance(user, 1000)
    product = product_factory(price="100.00", stock=10)
    make_cart(user=user, items=[(product, 4)])  # subtotal 400 (< 500) -> 50% cap

    order = _order_from(
        post_json(CHECKOUT_URL, checkout_payload(applied_bonuses=300), headers=bearer(user))
    )
    assert order.applied_bonuses == 200  # int(400 * 0.50)
    assert order.total_price == Decimal("200.00")  # 400 - 200
    assert order.bonus_earned == 0  # spending earns nothing
    profile.refresh_from_db()
    assert profile.bonus_balance == 800  # 1000 - 200


@pytest.mark.django_db
def test_applied_bonuses_capped_at_75pct_at_or_above_500(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json,
    set_bonus_balance,
):
    user = make_user("buyer")
    profile = set_bonus_balance(user, 1000)
    product = product_factory(price="100.00", stock=10)
    make_cart(user=user, items=[(product, 6)])  # subtotal 600 (>= 500) -> 75% cap

    order = _order_from(
        post_json(CHECKOUT_URL, checkout_payload(applied_bonuses=500), headers=bearer(user))
    )
    assert order.applied_bonuses == 450  # int(600 * 0.75)
    assert order.total_price == Decimal("150.00")
    assert order.bonus_earned == 0
    profile.refresh_from_db()
    assert profile.bonus_balance == 550


@pytest.mark.django_db
def test_75pct_tier_applies_exactly_at_500_boundary(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json,
    set_bonus_balance,
):
    user = make_user("buyer")
    set_bonus_balance(user, 1000)
    product = product_factory(price="100.00", stock=10)
    make_cart(user=user, items=[(product, 5)])  # subtotal exactly 500

    order = _order_from(
        post_json(CHECKOUT_URL, checkout_payload(applied_bonuses=500), headers=bearer(user))
    )
    assert order.applied_bonuses == 375  # int(500 * 0.75), not 0.50


@pytest.mark.django_db
def test_applied_bonuses_capped_by_balance(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json,
    set_bonus_balance,
):
    user = make_user("buyer")
    profile = set_bonus_balance(user, 50)
    product = product_factory(price="100.00", stock=10)
    make_cart(user=user, items=[(product, 4)])  # subtotal 400, 50% cap = 200

    order = _order_from(
        post_json(CHECKOUT_URL, checkout_payload(applied_bonuses=100), headers=bearer(user))
    )
    assert order.applied_bonuses == 50  # balance is the binding limit
    assert order.total_price == Decimal("350.00")
    profile.refresh_from_db()
    assert profile.bonus_balance == 0


@pytest.mark.django_db
def test_applying_bonuses_earns_none_even_when_products_grant_bonus(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json,
    set_bonus_balance,
):
    user = make_user("buyer")
    profile = set_bonus_balance(user, 1000)
    product = product_factory(price="100.00", stock=10)  # bonus_amount = 1
    make_cart(user=user, items=[(product, 4)])  # would earn 4 if not spending

    order = _order_from(
        post_json(CHECKOUT_URL, checkout_payload(applied_bonuses=100), headers=bearer(user))
    )
    assert order.applied_bonuses == 100
    assert order.bonus_earned == 0
    assert order.total_price == Decimal("300.00")
    profile.refresh_from_db()
    assert profile.bonus_balance == 900  # 1000 - 100 + 0


@pytest.mark.django_db
def test_negative_applied_bonuses_clamped_to_zero_and_still_earns(
    bearer, make_user, product_factory, make_cart, checkout_payload, post_json,
    set_bonus_balance,
):
    user = make_user("buyer")
    profile = set_bonus_balance(user, 1000)
    product = product_factory(price="100.00", stock=10)  # bonus_amount = 1
    make_cart(user=user, items=[(product, 4)])

    order = _order_from(
        post_json(CHECKOUT_URL, checkout_payload(applied_bonuses=-50), headers=bearer(user))
    )
    assert order.applied_bonuses == 0  # negatives clamp to 0, never credit money
    assert order.total_price == Decimal("400.00")
    assert order.bonus_earned == 4  # applied == 0, so earning is NOT suppressed
    profile.refresh_from_db()
    assert profile.bonus_balance == 1004  # 1000 - 0 + 4


@pytest.mark.django_db
def test_anonymous_checkout_cannot_apply_bonuses(
    product_factory, make_cart, checkout_payload, post_json
):
    product = product_factory(price="100.00", stock=10)
    make_cart(session_id="anon-b", items=[(product, 4)])

    resp = post_json(
        CHECKOUT_URL,
        checkout_payload(applied_bonuses=100),
        headers={"X-Session-Id": "anon-b"},
    )
    order = _order_from(resp)
    assert order.applied_bonuses == 0
    assert order.bonus_earned == 0
    assert order.total_price == Decimal("400.00")  # full price, no discount
