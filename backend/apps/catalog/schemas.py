from decimal import Decimal

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
