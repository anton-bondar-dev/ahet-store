from decimal import Decimal
from typing import Optional

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from apps.catalog.models import Product

from .models import Cart, CartItem
from .schemas import AddToCartIn, CartOut, UpdateQuantityIn

router = Router(tags=["cart"])

SESSION_HEADER = "X-Session-Id"


def get_session_id(request) -> Optional[str]:
    sid = request.headers.get(SESSION_HEADER)
    return sid.strip() if sid and sid.strip() else None


def serialize_cart(cart: Optional[Cart]) -> dict:
    # Returns a plain dict with raw Product instances so Ninja serializes the
    # whole tree against CartOut in one pass (applies ProductOut resolvers).
    if cart is None:
        return {"items": [], "total_quantity": 0, "total_price": Decimal("0.00")}

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

    return {"items": items, "total_quantity": total_quantity, "total_price": total_price}


def load_cart(session_id: str) -> Optional[Cart]:
    return (
        Cart.objects.prefetch_related("items__product__category")
        .filter(session_id=session_id)
        .first()
    )


@router.get("", response=CartOut, operation_id="get_cart")
def get_cart(request):
    sid = get_session_id(request)
    if not sid:
        return serialize_cart(None)
    return serialize_cart(load_cart(sid))


@router.post("/add", response=CartOut, operation_id="add_to_cart")
def add_to_cart(request, payload: AddToCartIn):
    sid = get_session_id(request)
    if not sid:
        raise HttpError(400, "Missing X-Session-Id header")

    product = get_object_or_404(Product, id=payload.product_id)
    cart, _ = Cart.objects.get_or_create(session_id=sid)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    item.quantity = (0 if created else item.quantity) + max(1, payload.quantity)
    item.save()

    return serialize_cart(load_cart(sid))


@router.patch("/{item_id}", response=CartOut, operation_id="update_cart_item")
def update_cart_item(request, item_id: int, payload: UpdateQuantityIn):
    sid = get_session_id(request)
    if not sid:
        raise HttpError(400, "Missing X-Session-Id header")

    item = get_object_or_404(CartItem, id=item_id, cart__session_id=sid)
    # 0 is allowed (item stays but drops out of totals); cap at available stock.
    item.quantity = max(0, min(payload.quantity, item.product.stock))
    item.save()

    return serialize_cart(load_cart(sid))


@router.delete("/{item_id}", response=CartOut, operation_id="delete_cart_item")
def delete_cart_item(request, item_id: int):
    sid = get_session_id(request)
    if not sid:
        raise HttpError(400, "Missing X-Session-Id header")

    item = get_object_or_404(CartItem, id=item_id, cart__session_id=sid)
    item.delete()

    return serialize_cart(load_cart(sid))
