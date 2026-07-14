from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth

from .models import Product, RecentlyViewed
from .schemas import ProductOut

router = Router(tags=["products"])

MAX_VIEWED = 12


class ViewIn(Schema):
    product_id: int


@router.get("/viewed", response=List[ProductOut], auth=JWTAuth(), operation_id="get_viewed")
def get_viewed(request):
    rows = (
        RecentlyViewed.objects.filter(user=request.auth)
        .select_related("product__category")
        .order_by("-viewed_at")[:MAX_VIEWED]
    )
    return [row.product for row in rows]


@router.post("/viewed", response={200: None}, auth=JWTAuth(), operation_id="track_viewed")
def track_viewed(request, payload: ViewIn):
    product = get_object_or_404(Product, id=payload.product_id)
    # Upsert: one row per (user, product); re-viewing bumps viewed_at (auto_now).
    RecentlyViewed.objects.update_or_create(user=request.auth, product=product)
    return 200, None
