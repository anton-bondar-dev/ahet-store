from datetime import datetime
from decimal import Decimal
from typing import Optional

from ninja import Schema


class CategoryOut(Schema):
    id: int
    name: str
    slug: str
    description: str


class ProductOut(Schema):
    id: int
    title: str
    slug: str
    price: Decimal
    description: str
    category: CategoryOut
    sku: Optional[str]
    stock: int
    is_active: bool
    discount_price: Optional[Decimal]
    discount_end_date: Optional[datetime]
    image: Optional[str]

    @staticmethod
    def resolve_image(obj):
        return obj.image.url if obj.image else None
