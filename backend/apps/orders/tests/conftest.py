"""Local fixtures for the orders test suite.

These build the pre-conditions checkout/order endpoints need — a cart with
items, a profile carrying a bonus balance, a ready-made order — on top of the
shared fixtures in the repo-root conftest (api, bearer, make_user,
product_factory, post_json, ...).
"""
import pytest

# A complete, valid CheckoutIn body. Individual tests override single fields.
_CHECKOUT_FIELDS = dict(
    first_name="Ivan",
    last_name="Petrenko",
    phone="+380501234567",
    email="ivan@example.com",
    city="Kyiv",
    address="Khreshchatyk 1",
)


@pytest.fixture
def checkout_payload():
    """Return a valid checkout body; pass overrides (or applied_bonuses=...)."""
    def _make(**overrides):
        data = dict(_CHECKOUT_FIELDS)
        data.update(overrides)
        return data
    return _make


@pytest.fixture
def make_cart(db):
    """Create a cart (user cart or anonymous session cart) with line items.

    items is an iterable of (product, quantity) pairs.
    """
    from apps.cart.models import Cart, CartItem

    def _make(user=None, session_id=None, items=()):
        cart = Cart.objects.create(user=user, session_id=session_id)
        for product, quantity in items:
            CartItem.objects.create(cart=cart, product=product, quantity=quantity)
        return cart

    return _make


@pytest.fixture
def set_bonus_balance(db):
    """Ensure the user has a Profile with the given bonus balance, return it."""
    from apps.accounts.models import Profile

    def _set(user, balance):
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.bonus_balance = balance
        profile.save(update_fields=["bonus_balance"])
        return profile

    return _set


@pytest.fixture
def block_user(db):
    """Permanently block a user (set profile.blocked_permanent)."""
    from apps.accounts.models import Profile

    def _block(user):
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.blocked_permanent = True
        profile.save(update_fields=["blocked_permanent"])
        return profile

    return _block


@pytest.fixture
def order_factory(db):
    """Create an Order (optionally with OrderItems) directly, bypassing checkout.

    items is an iterable of (product, quantity, price) tuples.
    """
    from apps.orders.models import Order, OrderItem

    def _make(user=None, session_id=None, items=None, **kw):
        fields = dict(
            first_name="Ivan",
            last_name="Petrenko",
            phone="+380501234567",
            email="ivan@example.com",
            city="Kyiv",
            address="Khreshchatyk 1",
        )
        fields.update(kw)
        order = Order.objects.create(user=user, session_id=session_id, **fields)
        for product, quantity, price in (items or []):
            OrderItem.objects.create(
                order=order,
                product=product,
                product_title=product.title,
                quantity=quantity,
                price=price,
            )
        return order

    return _make


@pytest.fixture
def impersonation_headers():
    """Headers carrying a storefront token with an `imp_by` claim — the same
    shape the support 'view as customer' flow issues. The token authenticates
    as `target`, but the checkout guard reads `imp_by` and blocks real orders."""
    from ninja_jwt.tokens import RefreshToken

    def _headers(target, operator, session_id="imp-session"):
        access = RefreshToken.for_user(target).access_token
        access["imp_by"] = operator.id
        access["imp_sid"] = 1
        return {"Authorization": f"Bearer {access}", "X-Session-Id": session_id}

    return _headers
