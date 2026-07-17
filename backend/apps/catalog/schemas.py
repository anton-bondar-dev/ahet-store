from datetime import datetime
from decimal import Decimal
from typing import Optional

from ninja import Schema


class CategoryOut(Schema):
    id: int
    name: str
    slug: str
    description: str


class SuggestionOut(Schema):
    text: str
    type: str  # "category" | "product"


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
    average_rating: float
    reviews_count: int
    is_new: bool
    bonus_amount: int
    trending_score: float = 0  # populated on the product list (staff-only badges)

    @staticmethod
    def resolve_trending_score(obj):
        return round(getattr(obj, "trending_score", 0) or 0, 4)

    @staticmethod
    def resolve_image(obj):
        return obj.image.url if obj.image else None
