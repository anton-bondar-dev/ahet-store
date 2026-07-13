from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from apps.cart.models import Cart
from apps.catalog.models import Product

from .models import Order, OrderItem
from .schemas import CheckoutIn, OrderCreatedOut, OrderOut

router = Router(tags=["orders"])

SESSION_HEADER = "X-Session-Id"


def get_session_id(request) -> Optional[str]:
    sid = request.headers.get(SESSION_HEADER)
    return sid.strip() if sid and sid.strip() else None


@router.post("/checkout", response=OrderCreatedOut, operation_id="checkout")
def checkout(request, payload: CheckoutIn):
    sid = get_session_id(request)
    if not sid:
        raise HttpError(400, "Missing X-Session-Id header")

    # Everything runs in one atomic block: stock validation, order creation,
    # stock decrement, and cart clearing either all commit or all roll back.
    with transaction.atomic():
        cart = Cart.objects.filter(session_id=sid).first()
        items = (
            list(cart.items.filter(quantity__gt=0).select_related("product"))
            if cart
            else []
        )
        if not items:
            raise HttpError(400, "Кошик порожній")

        # Lock the product rows (sorted ids → stable order, no deadlocks) so a
        # concurrent checkout can't oversell: the second waits, then re-reads the
        # decremented stock and correctly fails the check below.
        product_ids = sorted({item.product_id for item in items})
        locked = {
            p.id: p
            for p in Product.objects.select_for_update().filter(id__in=product_ids)
        }

        for item in items:
            product = locked[item.product_id]
            if product.stock < item.quantity:
                raise HttpError(409, f"Недостатньо товару: {product.title}")

        order = Order.objects.create(
            session_id=sid,
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone=payload.phone,
            email=payload.email,
            city=payload.city,
            address=payload.address,
        )

        total_price = Decimal("0.00")
        order_items = []
        for item in items:
            product = locked[item.product_id]
            unit_price = product.effective_price
            order_items.append(
                OrderItem(
                    order=order,
                    product=product,
                    product_title=product.title,
                    quantity=item.quantity,
                    price=unit_price,
                )
            )
            product.stock -= item.quantity
            total_price += unit_price * item.quantity

        OrderItem.objects.bulk_create(order_items)
        Product.objects.bulk_update(locked.values(), ["stock"])

        order.total_price = total_price
        order.save(update_fields=["total_price"])

        cart.items.all().delete()

    return {"id": order.id}


@router.get("/{order_id}", response=OrderOut, operation_id="get_order")
def get_order(request, order_id: int):
    sid = get_session_id(request)
    if not sid:
        raise HttpError(400, "Missing X-Session-Id header")
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), id=order_id, session_id=sid
    )
    return order
