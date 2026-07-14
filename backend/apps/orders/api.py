from decimal import Decimal
from typing import List

from django.db import models, transaction
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.cart.services import auth_user, get_current_cart, get_session_id
from apps.catalog.models import Product

from .models import Order, OrderItem
from .schemas import CheckoutIn, OrderCreatedOut, OrderOut

router = Router(tags=["orders"])


@router.get("/me", response=List[OrderOut], auth=JWTAuth(), operation_id="get_my_orders")
def get_my_orders(request):
    return list(
        Order.objects.filter(user=request.auth).prefetch_related("items")
    )


@router.post("/checkout", response=OrderCreatedOut, operation_id="checkout")
def checkout(request, payload: CheckoutIn):
    user = auth_user(request)
    sid = get_session_id(request)

    # Everything runs in one atomic block: stock validation, order creation,
    # stock decrement, and cart clearing either all commit or all roll back.
    with transaction.atomic():
        cart = get_current_cart(request)
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
            user=user,
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
    # An order is visible to its owner — the authenticated user, or the session
    # that placed it (so the success page works for anonymous checkout too).
    user = auth_user(request)
    sid = get_session_id(request)
    owner = models.Q()
    if user is not None:
        owner |= models.Q(user=user)
    if sid:
        owner |= models.Q(session_id=sid)
    if not owner:
        raise HttpError(400, "Missing identity")

    order = get_object_or_404(
        Order.objects.prefetch_related("items"), owner, id=order_id
    )
    return order
