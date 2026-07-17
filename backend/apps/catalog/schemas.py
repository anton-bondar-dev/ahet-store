from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from ninja import Schema


class CategoryBrief(Schema):
    """A single ancestor node in a breadcrumb trail (no recursion)."""

    id: int
    name: str
    slug: str


class CategoryOut(Schema):
    id: int
    name: str
    slug: str
    description: str
    parent_id: Optional[int]
    depth: int
    # Root → parent, excluding self. Drives breadcrumbs. Populated in bulk by the
    # endpoints (see attach_ancestors) so a product list never triggers N+1.
    ancestors: List[CategoryBrief] = []

    @staticmethod
    def resolve_ancestors(obj):
        cached = getattr(obj, "_ancestors", None)
        if cached is not None:
            return cached
        # Correctness fallback if an endpoint forgot to bulk-attach: resolve the
        # chain from the materialized path in a single query.
        from .models import Category

        ids = getattr(obj, "ancestor_ids", None)
        ids = ids if ids is not None else [
            int(x) for x in (obj.path or "").split("/") if x and int(x) != obj.id
        ]
        if not ids:
            return []
        nodes = {c.id: c for c in Category.objects.filter(id__in=ids)}
        return [nodes[i] for i in ids if i in nodes]


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

    @staticmethod
    def resolve_image(obj):
        return obj.image.url if obj.image else None
