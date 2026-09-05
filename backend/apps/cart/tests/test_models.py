"""Model-level tests for the cart app: defaults, __str__, and the
per-cart/per-product uniqueness constraint that makes re-adding increment
instead of duplicating a line.
"""
import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from apps.cart.models import Cart, CartItem


@pytest.mark.django_db
def test_anonymous_cart_is_keyed_by_session_id():
    cart = Cart.objects.create(session_id="sess-123")
    assert cart.user_id is None
    assert cart.session_id == "sess-123"
    # created_at / updated_at auto-populate.
    assert cart.created_at is not None
    assert cart.updated_at is not None


@pytest.mark.django_db
def test_user_cart_has_no_session_id():
    user = User.objects.create_user(username="buyer", password="pw")
    cart = Cart.objects.create(user=user)
    assert cart.session_id is None
    assert cart.user_id == user.id


@pytest.mark.django_db
def test_cart_str_prefers_user_then_session(product_factory):
    user = User.objects.create_user(username="buyer", password="pw")
    user_cart = Cart.objects.create(user=user)
    anon_cart = Cart.objects.create(session_id="abc")

    assert str(user_cart) == f"Cart {user.id}"
    assert str(anon_cart) == "Cart abc"


@pytest.mark.django_db
def test_cart_item_defaults_to_quantity_one(product_factory):
    cart = Cart.objects.create(session_id="s1")
    product = product_factory()
    item = CartItem.objects.create(cart=cart, product=product)
    assert item.quantity == 1


@pytest.mark.django_db
def test_cart_item_str(product_factory):
    cart = Cart.objects.create(session_id="s1")
    product = product_factory()
    item = CartItem.objects.create(cart=cart, product=product, quantity=4)
    assert str(item) == f"4 × {product.id} in cart {cart.id}"


@pytest.mark.django_db
def test_same_product_twice_in_one_cart_is_rejected(product_factory):
    """unique_together(cart, product): the API increments an existing line
    rather than creating a second row — the DB constraint backs that up."""
    cart = Cart.objects.create(session_id="s1")
    product = product_factory()
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CartItem.objects.create(cart=cart, product=product, quantity=2)


@pytest.mark.django_db
def test_same_product_in_different_carts_is_allowed(product_factory):
    product = product_factory()
    cart_a = Cart.objects.create(session_id="a")
    cart_b = Cart.objects.create(session_id="b")
    CartItem.objects.create(cart=cart_a, product=product, quantity=1)
    # No constraint violation across carts.
    CartItem.objects.create(cart=cart_b, product=product, quantity=1)
    assert CartItem.objects.filter(product=product).count() == 2


@pytest.mark.django_db
def test_deleting_cart_cascades_to_items(product_factory):
    cart = Cart.objects.create(session_id="s1")
    product = product_factory()
    CartItem.objects.create(cart=cart, product=product)
    cart.delete()
    assert CartItem.objects.count() == 0


@pytest.mark.django_db
def test_product_is_protected_while_referenced_by_a_cart_item(product_factory):
    """CartItem.product uses on_delete=PROTECT — a product in someone's cart
    cannot be hard-deleted out from under them."""
    from django.db.models import ProtectedError

    cart = Cart.objects.create(session_id="s1")
    product = product_factory()
    CartItem.objects.create(cart=cart, product=product)
    with pytest.raises(ProtectedError):
        product.delete()
