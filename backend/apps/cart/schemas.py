from decimal import Decimal
from typing import List, Optional

from ninja import Schema

from apps.catalog.schemas import ProductOut


class AddToCartIn(Schema):
    product_id: int
    quantity: int = 1


class UpdateQuantityIn(Schema):
    quantity: int


class ApplyCouponIn(Schema):
    code: str


class CartItemOut(Schema):
    id: int
    product: ProductOut
    quantity: int


class CartOut(Schema):
    items: List[CartItemOut]
    total_quantity: int
    total_price: Decimal  # subtotal, before coupon
    coupon_code: Optional[str] = None
    coupon_discount: Decimal = Decimal("0.00")
    total_after_discount: Decimal = Decimal("0.00")
