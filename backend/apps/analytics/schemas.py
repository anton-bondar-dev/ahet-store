from decimal import Decimal
from typing import List, Optional

from ninja import Schema


# --- Team Lead (financial — superuser only) ----------------------------------
class TopProductOut(Schema):
    id: int
    title: str
    quantity_sold: int
    revenue: Decimal


class SlaOut(Schema):
    open_tickets: int
    closed_tickets: int
    overdue_tickets: int
    satisfaction_rate: Optional[int] = None  # % positive ratings


class LowStockOut(Schema):
    id: int
    title: str
    stock: int


class LeadAnalyticsOut(Schema):
    total_revenue: Decimal
    month_revenue: Decimal
    average_order_value: Decimal
    orders_count: int
    top_products: List[TopProductOut]
    sla: SlaOut
    low_stock: List[LowStockOut]


# --- Operator (no financials) ------------------------------------------------
class TrendingProductOut(Schema):
    id: int
    title: str
    slug: str
    trending_score: float
    views_count: int
    cart_adds_count: int
    purchases_count: int


class OperatorAnalyticsOut(Schema):
    closed_tickets: int
    comments_resolved: int
    avg_resolution_hours: Optional[float] = None
    satisfaction_rate: Optional[int] = None
    trending_products: List[TrendingProductOut]
