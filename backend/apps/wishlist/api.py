from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from apps.accounts.jwt_auth import StampedJWTAuth as JWTAuth
from apps.catalog.models import Product
from apps.catalog.schemas import ProductOut

from .models import Favorite

router = Router(tags=["wishlist"])


class ToggleOut(Schema):
    is_favorite: bool


def _favorites_qs(user):
    return (
        Favorite.objects.filter(user=user)
        .select_related("product__category")
        .order_by("-created_at")
    )


# Literal `/ids` route registered before the `/{product_id}/...` param route so
# it is never captured by it.
@router.get(
    "/ids", response=List[int], auth=JWTAuth(), operation_id="list_wishlist_ids"
)
def list_wishlist_ids(request):
    # Lightweight id-only list used to render the heart state across every
    # product card without embedding a flag in the public ProductOut.
    return list(_favorites_qs(request.auth).values_list("product_id", flat=True))


@router.get(
    "", response=List[ProductOut], auth=JWTAuth(), operation_id="list_wishlist"
)
def list_wishlist(request):
    # Return raw Product instances so Ninja serializes them against ProductOut
    # (same approach as the cart / recently-viewed endpoints).
    return [fav.product for fav in _favorites_qs(request.auth)]


@router.post(
    "/{product_id}/toggle",
    response=ToggleOut,
    auth=JWTAuth(),
    operation_id="toggle_wishlist",
)
def toggle_wishlist(request, product_id: int):
    # Idempotent toggle: add if missing, remove if present. Returns the new state
    # so the client can reconcile its optimistic update.
    product = get_object_or_404(Product, id=product_id)
    favorite, created = Favorite.objects.get_or_create(
        user=request.auth, product=product
    )
    if not created:
        favorite.delete()
        return {"is_favorite": False}
    return {"is_favorite": True}
