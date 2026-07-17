from django.db.models import (
    Avg,
    Count,
    DecimalField,
    DurationField,
    ExpressionWrapper,
    F,
    Sum,
)
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from apps.accounts.jwt_auth import StampedJWTAuth as JWTAuth
from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review
from apps.support.models import SupportRating, SupportTicket

from .schemas import LeadAnalyticsOut, OperatorAnalyticsOut

router = Router(tags=["analytics"])


def _require_owner(request):
    # Financial data is Team-Lead-only (Principle of Least Privilege).
    if not request.auth.is_superuser:
        raise HttpError(403, "Доступ лише для тімліда")
    return request.auth


def _require_staff(request):
    user = request.auth
    if not (user.is_staff or user.is_superuser):
        raise HttpError(403, "Доступ лише для персоналу")
    if not user.is_active:
        raise HttpError(403, "Ваш акаунт заблоковано")
    return user


def _satisfaction_rate(ratings_qs) -> "int | None":
    total = ratings_qs.count()
    if not total:
        return None
    positive = ratings_qs.filter(is_positive=True).count()
    return round(positive / total * 100)


@router.get("/lead", response=LeadAnalyticsOut, auth=JWTAuth(), operation_id="lead_analytics")
def lead_analytics(request):
    _require_owner(request)
    orders = Order.objects.all()
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    agg = orders.aggregate(total=Sum("total_price"), count=Count("id"), aov=Avg("total_price"))
    month_total = orders.filter(created_at__gte=month_start).aggregate(s=Sum("total_price"))["s"]

    top = (
        OrderItem.objects.values("product_id", "product__title")
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum(
                ExpressionWrapper(F("price") * F("quantity"), output_field=DecimalField())
            ),
        )
        .order_by("-quantity_sold")[:5]
    )
    top_products = [
        {
            "id": r["product_id"],
            "title": r["product__title"],
            "quantity_sold": r["quantity_sold"] or 0,
            "revenue": r["revenue"] or 0,
        }
        for r in top
    ]

    open_qs = SupportTicket.objects.filter(status=SupportTicket.STATUS_OPEN)
    overdue = sum(1 for t in open_qs if t.is_overdue)
    sla = {
        "open_tickets": open_qs.count(),
        "closed_tickets": SupportTicket.objects.filter(status=SupportTicket.STATUS_CLOSED).count(),
        "overdue_tickets": overdue,
        "satisfaction_rate": _satisfaction_rate(SupportRating.objects.all()),
    }

    low_stock = list(
        Product.objects.filter(stock__lt=5).order_by("stock").values("id", "title", "stock")
    )

    return {
        "total_revenue": agg["total"] or 0,
        "month_revenue": month_total or 0,
        "average_order_value": round(agg["aov"] or 0, 2),
        "orders_count": agg["count"],
        "top_products": top_products,
        "sla": sla,
        "low_stock": low_stock,
    }


@router.get(
    "/operator", response=OperatorAnalyticsOut, auth=JWTAuth(), operation_id="operator_analytics"
)
def operator_analytics(request):
    # Standard staff. Deliberately excludes ALL revenue/financial data.
    staff = _require_staff(request)

    closed_qs = SupportTicket.objects.filter(
        closed_by=staff, status=SupportTicket.STATUS_CLOSED
    )
    resolution = closed_qs.filter(closed_at__isnull=False).aggregate(
        avg=Avg(ExpressionWrapper(F("closed_at") - F("created_at"), output_field=DurationField()))
    )["avg"]
    avg_hours = round(resolution.total_seconds() / 3600, 1) if resolution else None

    trending = (
        Product.objects.with_trending_score().order_by("-trending_score", "title")[:5]
    )
    trending_products = [
        {
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "trending_score": round(p.trending_score or 0, 4),
            "views_count": p.views_count,
            "cart_adds_count": p.cart_adds_count,
            "purchases_count": p.purchases_count,
        }
        for p in trending
    ]

    return {
        "closed_tickets": closed_qs.count(),
        "comments_resolved": Review.objects.filter(support_resolved_by=staff).count(),
        "avg_resolution_hours": avg_hours,
        "satisfaction_rate": _satisfaction_rate(SupportRating.objects.filter(staff=staff)),
        "trending_products": trending_products,
    }
