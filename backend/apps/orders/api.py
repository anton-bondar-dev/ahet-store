from decimal import Decimal
from typing import List

from django.db import models, transaction
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from apps.accounts.jwt_auth import StampedJWTAuth as JWTAuth

from apps.accounts.models import Profile
from apps.cart.services import (
    auth_user,
    get_current_cart,
    get_session_id,
    impersonator_id,
)
from apps.catalog.models import Product
from apps.core.permissions import forbid_blocked, forbid_staff
from apps.coupons.models import Coupon

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
    forbid_staff(user)  # employees can't place orders
    forbid_blocked(user)  # blocked customers can't order
    if impersonator_id(request) is not None:
        # A staff member viewing as this customer — debugging only, no real orders.
        raise HttpError(403, "Оформлення недоступне в режимі перегляду від імені клієнта")
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
            product.purchases_count += item.quantity  # trending engine
            total_price += unit_price * item.quantity

        OrderItem.objects.bulk_create(order_items)
        Product.objects.bulk_update(locked.values(), ["stock", "purchases_count"])

        # Money order: subtotal → coupon discount → bonus cap on the remainder.
        subtotal = total_price  # Σ effective_price × qty
        # Lock the coupon row so two concurrent checkouts can't both pass the
        # max_uses check and over-increment used_count (SET_NULL guarantees a
        # set coupon_id still points at a live row).
        coupon = None
        if cart.coupon_id is not None:
            coupon = (
                Coupon.objects.select_for_update().filter(id=cart.coupon_id).first()
            )
        coupon_discount = Decimal("0.00")
        if coupon and coupon.is_valid(subtotal):
            coupon_discount = coupon.discount_for(subtotal)
            coupon.used_count += 1
            coupon.save(update_fields=["used_count"])
        else:
            coupon = None
        after_coupon = subtotal - coupon_discount

        bonus_earned = sum(
            locked[item.product_id].bonus_amount * item.quantity for item in items
        )
        applied = 0
        if user is not None:
            profile, _ = Profile.objects.get_or_create(user=user)
            # Cap: 75% of the post-coupon amount at ≥500 UAH, else 50%; and by the balance.
            pct = Decimal("0.75") if after_coupon >= 500 else Decimal("0.50")
            max_applicable = int(after_coupon * pct)  # floor → integer UAH
            applied = max(
                0, min(payload.applied_bonuses, max_applicable, profile.bonus_balance)
            )
            # No bonuses are earned on an order that spends bonuses.
            if applied > 0:
                bonus_earned = 0
            profile.bonus_balance = profile.bonus_balance - applied + bonus_earned
            profile.save(update_fields=["bonus_balance"])
        else:
            bonus_earned = 0

        order.total_price = after_coupon - applied  # amount actually due
        order.bonus_earned = bonus_earned
        order.applied_bonuses = applied
        order.coupon = coupon
        order.coupon_discount = coupon_discount
        order.save(update_fields=[
            "total_price", "bonus_earned", "applied_bonuses", "coupon", "coupon_discount",
        ])

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
