from decimal import Decimal
from typing import Optional

from django.db.models import F
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from apps.catalog.models import Product
from apps.catalog.tree import attach_ancestors
from apps.core.permissions import forbid_blocked, forbid_staff
from apps.coupons.models import Coupon

from .models import Cart, CartItem
from .schemas import AddToCartIn, ApplyCouponIn, CartOut, UpdateQuantityIn
from .services import auth_user, get_current_cart, get_or_create_current_cart

router = Router(tags=["cart"])


def _require_customer(request):
    # Staff accounts are employees — they may browse the catalog and view a cart,
    # but every mutating cart action is blocked (403). Blocked customers too.
    user = auth_user(request)
    forbid_staff(user)
    forbid_blocked(user)


def serialize_cart(cart: Optional[Cart]) -> dict:
    # Returns a plain dict with raw Product instances so Ninja serializes the
    # whole tree against CartOut in one pass (applies ProductOut resolvers).
    if cart is None:
        return {
            "items": [], "total_quantity": 0, "total_price": Decimal("0.00"),
            "coupon_code": None, "coupon_discount": Decimal("0.00"),
            "total_after_discount": Decimal("0.00"),
        }

    items = []
    total_quantity = 0
    total_price = Decimal("0.00")
    for item in cart.items.all():
        # All rows are returned (incl. quantity 0 so the drawer can show them),
        # but only quantity > 0 rows count toward the totals / header badge.
        items.append({"id": item.id, "product": item.product, "quantity": item.quantity})
        if item.quantity > 0:
            total_quantity += item.quantity
            total_price += item.product.effective_price * item.quantity

    # Breadcrumb ancestors for each line's product category, in one bulk query.
    attach_ancestors([it["product"].category for it in items])

    # Coupon: apply only if still valid for the current subtotal.
    coupon_code = None
    coupon_discount = Decimal("0.00")
    if cart.coupon and cart.coupon.is_valid(total_price):
        coupon_code = cart.coupon.code
        coupon_discount = cart.coupon.discount_for(total_price)

    return {
        "items": items,
        "total_quantity": total_quantity,
        "total_price": total_price,
        "coupon_code": coupon_code,
        "coupon_discount": coupon_discount,
        "total_after_discount": total_price - coupon_discount,
    }


@router.get("", response=CartOut, operation_id="get_cart")
def get_cart(request):
    return serialize_cart(get_current_cart(request))


@router.post("/add", response=CartOut, operation_id="add_to_cart")
def add_to_cart(request, payload: AddToCartIn):
    _require_customer(request)
    cart = get_or_create_current_cart(request)
    if cart is None:
        raise HttpError(400, "Missing X-Session-Id header")

    product = get_object_or_404(Product, id=payload.product_id)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    item.quantity = (0 if created else item.quantity) + max(1, payload.quantity)
    item.save()

    # Trending engine: count the cart addition (atomic).
    Product.objects.filter(id=product.id).update(cart_adds_count=F("cart_adds_count") + 1)

    return serialize_cart(get_current_cart(request))


def _cart_subtotal(cart: Optional[Cart]) -> Decimal:
    if cart is None:
        return Decimal("0.00")
    total = Decimal("0.00")
    for item in cart.items.all():
        if item.quantity > 0:
            total += item.product.effective_price * item.quantity
    return total


# Literal /coupon routes MUST be registered before the /{item_id} routes so the
# param route doesn't capture them.
@router.post("/coupon", response=CartOut, operation_id="apply_coupon")
def apply_coupon(request, payload: ApplyCouponIn):
    _require_customer(request)
    cart = get_or_create_current_cart(request)
    if cart is None:
        raise HttpError(400, "Missing X-Session-Id header")

    code = payload.code.strip().upper()
    coupon = Coupon.objects.filter(code=code).first()
    if coupon is None:
        raise HttpError(404, "Промокод не знайдено")
    if not coupon.is_valid(_cart_subtotal(cart)):
        raise HttpError(400, "Промокод недійсний або не відповідає умовам")

    cart.coupon = coupon
    cart.save(update_fields=["coupon"])
    return serialize_cart(get_current_cart(request))


@router.delete("/coupon", response=CartOut, operation_id="remove_coupon")
def remove_coupon(request):
    _require_customer(request)
    cart = get_current_cart(request)
    if cart is not None and cart.coupon_id is not None:
        cart.coupon = None
        cart.save(update_fields=["coupon"])
    return serialize_cart(get_current_cart(request))


@router.patch("/{item_id}", response=CartOut, operation_id="update_cart_item")
def update_cart_item(request, item_id: int, payload: UpdateQuantityIn):
    _require_customer(request)
    cart = get_current_cart(request)
    if cart is None:
        raise HttpError(404, "Cart not found")

    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    # 0 is allowed (item stays but drops out of totals); cap at available stock.
    item.quantity = max(0, min(payload.quantity, item.product.stock))
    item.save()

    return serialize_cart(get_current_cart(request))


@router.delete("/{item_id}", response=CartOut, operation_id="delete_cart_item")
def delete_cart_item(request, item_id: int):
    _require_customer(request)
    cart = get_current_cart(request)
    if cart is None:
        raise HttpError(404, "Cart not found")

    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()

    return serialize_cart(get_current_cart(request))
