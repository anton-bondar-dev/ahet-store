from datetime import datetime
from decimal import Decimal
from typing import List

from ninja import Schema


class CheckoutIn(Schema):
    first_name: str
    last_name: str
    phone: str
    email: str
    city: str
    address: str
    applied_bonuses: int = 0


class OrderCreatedOut(Schema):
    id: int


class OrderItemOut(Schema):
    product_title: str
    quantity: int
    price: Decimal


class OrderOut(Schema):
    id: int
    status: str
    status_label: str
    total_price: Decimal
    bonus_earned: int
    applied_bonuses: int
    created_at: datetime
    items: List[OrderItemOut]

    @staticmethod
    def resolve_status_label(obj):
        from .models import STATUS_LABELS_UK

        status = obj["status"] if isinstance(obj, dict) else obj.status
        return STATUS_LABELS_UK.get(status, status)
