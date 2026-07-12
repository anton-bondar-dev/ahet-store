from decimal import Decimal
from typing import Optional

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from apps.catalog.models import Product

from .models import Cart, CartItem
from .schemas import AddToCartIn, CartOut

router = Router(tags=["cart"])

SESSION_HEADER = "X-Session-Id"


def get_session_id(request) -> Optional[str]:
    sid = request.headers.get(SESSION_HEADER)
    return sid.strip() if sid and sid.strip() else None


def effective_price(product) -> Decimal:
    if product.discount_price is not None and product.is_active:
        return product.discount_price
    return product.price


def serialize_cart(cart: Optional[Cart]) -> dict:
    # Returns a plain dict with raw Product instances so Ninja serializes the
    # whole tree against CartOut in one pass (applies ProductOut resolvers).
    if cart is None:
        return {"items": [], "total_quantity": 0, "total_price": Decimal("0.00")}

    items = []
    total_quantity = 0
    total_price = Decimal("0.00")
    for item in cart.items.all():
        items.append({"id": item.id, "product": item.product, "quantity": item.quantity})
        total_quantity += item.quantity
        total_price += effective_price(item.product) * item.quantity

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
