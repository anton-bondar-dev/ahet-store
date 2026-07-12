from decimal import Decimal
from typing import List

from ninja import Schema

from apps.catalog.schemas import ProductOut


class AddToCartIn(Schema):
    product_id: int
    quantity: int = 1


class CartItemOut(Schema):
    id: int
    product: ProductOut
    quantity: int


class CartOut(Schema):
    items: List[CartItemOut]
    total_quantity: int
    total_price: Decimal
