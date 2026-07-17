from decimal import Decimal
from typing import List, Optional

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.accounts.jwt_auth import StampedJWTAuth as JWTAuth

from .models import Product

router = Router(tags=["catalog-admin"])


def _require_staff(request):
    user = request.auth
    if not (user.is_staff or user.is_superuser):
        raise HttpError(403, "Доступ лише для персоналу")
    if not user.is_active:
        raise HttpError(403, "Ваш акаунт заблоковано")
    return user


class StaffProductOut(Schema):
    id: int
    title: str
    price: Decimal
    stock: int
    is_active: bool
    views_count: int
    cart_adds_count: int
    purchases_count: int
    trending_score: float = 0

    @staticmethod
    def resolve_trending_score(obj):
        return round(getattr(obj, "trending_score", 0) or 0, 4)


class ProductEditIn(Schema):
    price: Optional[Decimal] = None
    stock: Optional[int] = None


@router.get(
    "/products", response=List[StaffProductOut], auth=JWTAuth(), operation_id="staff_list_products"
)
def staff_list_products(request):
    _require_staff(request)
    return list(
        Product.objects.with_trending_score().select_related("category").order_by("title")
    )


@router.patch(
    "/products/{product_id}",
    response=StaffProductOut,
    auth=JWTAuth(),
    operation_id="staff_update_product",
)
def staff_update_product(request, product_id: int, payload: ProductEditIn):
    # Quick inventory edit: stock is open to all operators, but price changes
    # (financial) are restricted to the Team Lead (least privilege).
    user = _require_staff(request)
    product = get_object_or_404(Product, id=product_id)
    fields = []
    if payload.price is not None:
        if not user.is_superuser:
            raise HttpError(403, "Ціну може змінювати лише тімлід")
        if payload.price < 0:
            raise HttpError(400, "Ціна не може бути від'ємною")
        product.price = payload.price
        fields.append("price")
    if payload.stock is not None:
        if payload.stock < 0:
            raise HttpError(400, "Кількість не може бути від'ємною")
        product.stock = payload.stock
        fields.append("stock")
    if fields:
        product.save(update_fields=fields)
    return Product.objects.with_trending_score().get(id=product.id)
