"""Guest -> user cart merge.

When an anonymous shopper logs in (or resets their password), their session
cart is folded into their user cart. Direct service-level tests exercise every
branch of merge_anonymous_cart(); an end-to-end test drives it through the real
/api/auth/login endpoint.
"""
import json

import pytest

from apps.cart.models import Cart, CartItem
from apps.cart.services import merge_anonymous_cart


def _anon_cart_with(product, quantity, session_id="guest-1"):
    cart = Cart.objects.create(session_id=session_id)
    CartItem.objects.create(cart=cart, product=product, quantity=quantity)
    return cart


# --------------------------------------------------------------------------- #
# Service-level branches
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_merge_no_session_id_is_a_noop(make_user, product_factory):
    user = make_user("buyer")
    user_cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=user_cart, product=product_factory(), quantity=1)

    merge_anonymous_cart(user, None)

    assert Cart.objects.filter(user=user).count() == 1
    assert user_cart.items.count() == 1


@pytest.mark.django_db
def test_merge_with_no_matching_anon_cart_is_a_noop(make_user):
    user = make_user("buyer")
    merge_anonymous_cart(user, "does-not-exist")
    assert Cart.objects.count() == 0


@pytest.mark.django_db
def test_merge_claims_anon_cart_when_user_has_none(make_user, product_factory):
    """No existing user cart: the anon cart is simply reassigned to the user."""
    user = make_user("buyer")
    product = product_factory(stock=5)
    anon = _anon_cart_with(product, quantity=2, session_id="guest-1")

    merge_anonymous_cart(user, "guest-1")

    anon.refresh_from_db()
    assert anon.user_id == user.id
    assert anon.session_id is None
    assert anon.items.get(product=product).quantity == 2
    # No stray anonymous session cart remains.
    assert not Cart.objects.filter(session_id="guest-1", user__isnull=True).exists()


@pytest.mark.django_db
def test_merge_moves_distinct_products_into_user_cart(make_user, product_factory):
    user = make_user("buyer")
    product_u = product_factory(stock=5)
    product_a = product_factory(stock=5)

    user_cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=user_cart, product=product_u, quantity=1)
    _anon_cart_with(product_a, quantity=3, session_id="guest-1")

    merge_anonymous_cart(user, "guest-1")

    assert Cart.objects.filter(user=user).count() == 1
    assert not Cart.objects.filter(session_id="guest-1", user__isnull=True).exists()
    quantities = {ci.product_id: ci.quantity for ci in user_cart.items.all()}
    assert quantities == {product_u.id: 1, product_a.id: 3}


@pytest.mark.django_db
def test_merge_combines_same_product_and_clamps_to_stock(make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=5)

    user_cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=user_cart, product=product, quantity=3)
    _anon_cart_with(product, quantity=4, session_id="guest-1")  # 3 + 4 = 7 -> clamp 5

    merge_anonymous_cart(user, "guest-1")

    assert user_cart.items.count() == 1
    assert user_cart.items.get(product=product).quantity == 5
    # Anon cart and its item are gone.
    assert not Cart.objects.filter(session_id="guest-1", user__isnull=True).exists()
    assert CartItem.objects.filter(product=product).count() == 1


@pytest.mark.django_db
def test_merge_combines_under_stock_without_clamping(make_user, product_factory):
    user = make_user("buyer")
    product = product_factory(stock=10)

    user_cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=user_cart, product=product, quantity=2)
    _anon_cart_with(product, quantity=3, session_id="guest-1")

    merge_anonymous_cart(user, "guest-1")

    assert user_cart.items.get(product=product).quantity == 5


# --------------------------------------------------------------------------- #
# End-to-end through the login endpoint
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_login_merges_guest_cart(api, make_user, product_factory):
    """A guest fills a cart under X-Session-Id, then logs in with that same
    session id — the guest cart becomes the user's cart."""
    user = make_user("buyer", email="buyer@example.com", password="s3cret-pw")
    product = product_factory(stock=5)

    # Guest add.
    r = api.post("/api/cart/add",
                 data=json.dumps({"product_id": product.id, "quantity": 2}),
                 content_type="application/json",
                 headers={"X-Session-Id": "guest-xyz"})
    assert r.status_code == 200, r.content
    assert Cart.objects.filter(session_id="guest-xyz", user__isnull=True).exists()

    # Log in carrying the same session id.
    login = api.post("/api/auth/login",
                     data=json.dumps({"email": "buyer@example.com", "password": "s3cret-pw"}),
                     content_type="application/json",
                     headers={"X-Session-Id": "guest-xyz"})
    assert login.status_code == 200, login.content
    assert login.json()["status"] == "authed"

    # The guest cart is now owned by the user and no anon cart remains.
    assert not Cart.objects.filter(session_id="guest-xyz", user__isnull=True).exists()
    user_cart = Cart.objects.get(user=user)
    assert user_cart.items.get(product=product).quantity == 2


@pytest.mark.django_db
def test_login_merges_into_existing_user_cart(api, bearer, make_user, product_factory):
    user = make_user("buyer", email="buyer@example.com", password="s3cret-pw")
    product = product_factory(stock=10)

    # Existing authenticated cart with 2 units.
    api.post("/api/cart/add",
             data=json.dumps({"product_id": product.id, "quantity": 2}),
             content_type="application/json", headers=bearer(user))
    # Same product added anonymously with 3 units.
    api.post("/api/cart/add",
             data=json.dumps({"product_id": product.id, "quantity": 3}),
             content_type="application/json",
             headers={"X-Session-Id": "guest-xyz"})

    login = api.post("/api/auth/login",
                     data=json.dumps({"email": "buyer@example.com", "password": "s3cret-pw"}),
                     content_type="application/json",
                     headers={"X-Session-Id": "guest-xyz"})
    assert login.status_code == 200, login.content

    user_cart = Cart.objects.get(user=user)
    assert user_cart.items.get(product=product).quantity == 5  # 2 + 3, within stock
    assert not Cart.objects.filter(session_id="guest-xyz", user__isnull=True).exists()
