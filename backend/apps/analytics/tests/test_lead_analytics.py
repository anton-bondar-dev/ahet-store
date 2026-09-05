"""GET /analytics/lead — the Team-Lead financial dashboard.

Every figure is derived on demand from the live tables (no denormalised
counters), so these tests seed known orders / tickets / ratings / stock and
assert the endpoint reproduces the arithmetic exactly.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.support.models import SupportTicket

from .conftest import dec

LEAD = "/api/analytics/lead"


@pytest.fixture
def lead(make_user):
    return make_user("lead", is_staff=True, is_superuser=True)


def _body(api, bearer, lead):
    resp = api.get(LEAD, headers=bearer(lead))
    assert resp.status_code == 200, resp.content
    return resp.json()


# --- Empty state -------------------------------------------------------------
@pytest.mark.django_db
def test_empty_dashboard_is_all_zeroes(api, bearer, lead):
    body = _body(api, bearer, lead)
    assert dec(body["total_revenue"]) == Decimal("0")
    assert dec(body["month_revenue"]) == Decimal("0")
    assert dec(body["average_order_value"]) == Decimal("0")
    assert body["orders_count"] == 0
    assert body["top_products"] == []
    assert body["low_stock"] == []
    assert body["sla"] == {
        "open_tickets": 0,
        "closed_tickets": 0,
        "overdue_tickets": 0,
        "satisfaction_rate": None,
    }


# --- Revenue / order aggregates ---------------------------------------------
@pytest.mark.django_db
def test_revenue_count_and_average(api, bearer, lead, order_factory):
    order_factory(total_price="100.00")
    order_factory(total_price="200.00")
    order_factory(total_price="300.00")

    body = _body(api, bearer, lead)
    assert dec(body["total_revenue"]) == Decimal("600.00")
    assert body["orders_count"] == 3
    assert dec(body["average_order_value"]) == Decimal("200.00")


@pytest.mark.django_db
def test_average_order_value_is_rounded_to_two_places(api, bearer, lead, order_factory):
    # 100 + 100 + 101 = 301 / 3 = 100.333... -> 100.33
    for price in ("100.00", "100.00", "101.00"):
        order_factory(total_price=price)
    body = _body(api, bearer, lead)
    assert dec(body["average_order_value"]) == Decimal("100.33")


@pytest.mark.django_db
def test_cancelled_orders_still_count_toward_revenue(api, bearer, lead, order_factory):
    # The endpoint aggregates Order.objects.all() with no status filter, so even
    # a cancelled order contributes to gross revenue / count. Lock that in.
    order_factory(total_price="100.00", status="new")
    order_factory(total_price="50.00", status="cancelled")
    body = _body(api, bearer, lead)
    assert dec(body["total_revenue"]) == Decimal("150.00")
    assert body["orders_count"] == 2


# --- Month-to-date filter ----------------------------------------------------
@pytest.mark.django_db
def test_month_revenue_excludes_prior_months(api, bearer, lead, order_factory):
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    order_factory(total_price="500.00")  # this month (created_at = now)
    order_factory(total_price="700.00", created_at=month_start - timedelta(seconds=1))

    body = _body(api, bearer, lead)
    assert dec(body["total_revenue"]) == Decimal("1200.00")  # both counted
    assert dec(body["month_revenue"]) == Decimal("500.00")   # only this month
    assert body["orders_count"] == 2


# --- Top products ------------------------------------------------------------
@pytest.mark.django_db
def test_top_products_quantity_and_revenue(api, bearer, lead,
                                           order_factory, order_item_factory,
                                           product_factory):
    widget = product_factory(price="10.00")
    gadget = product_factory(price="25.00")
    order = order_factory()
    order_item_factory(order, widget, quantity=4, price="10.00")   # rev 40
    order_item_factory(order, gadget, quantity=2, price="25.00")   # rev 50

    body = _body(api, bearer, lead)
    by_id = {p["id"]: p for p in body["top_products"]}
    assert by_id[widget.id]["quantity_sold"] == 4
    assert dec(by_id[widget.id]["revenue"]) == Decimal("40.00")
    assert by_id[gadget.id]["quantity_sold"] == 2
    assert dec(by_id[gadget.id]["revenue"]) == Decimal("50.00")
    assert by_id[widget.id]["title"] == widget.title


@pytest.mark.django_db
def test_top_products_sums_across_orders_and_orders_by_quantity(
    api, bearer, lead, order_factory, order_item_factory, product_factory
):
    hot = product_factory(price="10.00")
    cold = product_factory(price="10.00")
    # `hot` sold across two separate orders -> quantities must sum to 7.
    order_item_factory(order_factory(), hot, quantity=5, price="10.00")
    order_item_factory(order_factory(), hot, quantity=2, price="10.00")
    order_item_factory(order_factory(), cold, quantity=1, price="10.00")

    body = _body(api, bearer, lead)
    rows = body["top_products"]
    assert [r["id"] for r in rows] == [hot.id, cold.id]  # sorted by qty desc
    assert rows[0]["quantity_sold"] == 7
    assert dec(rows[0]["revenue"]) == Decimal("70.00")


@pytest.mark.django_db
def test_top_products_is_capped_at_five(api, bearer, lead,
                                        order_factory, order_item_factory,
                                        product_factory):
    # Six products, each sold in a distinct quantity; only the top five surface.
    products = []
    for qty in range(1, 7):  # 1..6
        p = product_factory(price="10.00")
        order_item_factory(order_factory(), p, quantity=qty, price="10.00")
        products.append((qty, p.id))

    body = _body(api, bearer, lead)
    ids = [r["id"] for r in body["top_products"]]
    assert len(ids) == 5
    # The qty=1 product (the least-sold) is the one dropped.
    dropped_id = min(products)[1]
    assert dropped_id not in ids
    assert ids[0] == max(products)[1]  # qty=6 leads


@pytest.mark.django_db
def test_top_products_uses_live_product_title_not_snapshot(
    api, bearer, lead, order_factory, order_item_factory, product_factory
):
    product = product_factory(price="10.00")
    order_item_factory(order_factory(), product, quantity=1, price="10.00")
    # Rename the product after the sale; the snapshot on the OrderItem keeps the
    # old title, but the dashboard joins through to the live product title.
    product.title = "Renamed Live Title"
    product.save(update_fields=["title"])

    body = _body(api, bearer, lead)
    assert body["top_products"][0]["title"] == "Renamed Live Title"


@pytest.mark.django_db
def test_top_products_revenue_uses_line_item_price_not_live_price(
    api, bearer, lead, order_factory, order_item_factory, product_factory
):
    product = product_factory(price="10.00")
    # Sold at 8.00 (e.g. a past sale); the line item snapshots that price.
    order_item_factory(order_factory(), product, quantity=3, price="8.00")
    # Later the catalogue price changes — revenue must reflect the sale price.
    product.price = Decimal("99.00")
    product.save(update_fields=["price"])

    row = _body(api, bearer, lead)["top_products"][0]
    assert dec(row["revenue"]) == Decimal("24.00")  # 3 * 8.00, not 3 * 99.00


# --- SLA block ---------------------------------------------------------------
@pytest.mark.django_db
def test_sla_open_and_closed_ticket_counts(api, bearer, lead, make_user, ticket_factory):
    customer = make_user("customer")
    ticket_factory(customer, status=SupportTicket.STATUS_OPEN)
    ticket_factory(customer, status=SupportTicket.STATUS_OPEN)
    ticket_factory(customer, status=SupportTicket.STATUS_CLOSED)

    sla = _body(api, bearer, lead)["sla"]
    assert sla["open_tickets"] == 2
    assert sla["closed_tickets"] == 1


@pytest.mark.django_db
def test_sla_overdue_only_counts_unanswered_open_tickets(
    api, bearer, lead, make_user, ticket_factory
):
    customer = make_user("customer")
    now = timezone.now()
    stale = now - timedelta(hours=25)  # past the 24h SLA window
    fresh = now - timedelta(hours=1)

    # Overdue: open, customer wrote 25h ago, no staff reply since.
    ticket_factory(customer, status=SupportTicket.STATUS_OPEN, last_user_message_at=stale)
    # Not overdue: customer wrote 25h ago BUT staff replied afterwards.
    ticket_factory(
        customer, status=SupportTicket.STATUS_OPEN,
        last_user_message_at=stale, last_staff_message_at=now,
    )
    # Not overdue: recent customer message, still inside the window.
    ticket_factory(customer, status=SupportTicket.STATUS_OPEN, last_user_message_at=fresh)
    # Closed tickets are never overdue even if the last message is ancient.
    ticket_factory(customer, status=SupportTicket.STATUS_CLOSED, last_user_message_at=stale)

    sla = _body(api, bearer, lead)["sla"]
    assert sla["open_tickets"] == 3
    assert sla["overdue_tickets"] == 1


@pytest.mark.django_db
def test_sla_satisfaction_rate_is_percent_positive(
    api, bearer, lead, make_user, ticket_factory, rating_factory
):
    customer = make_user("customer")
    agent = make_user("agent", is_staff=True)
    # 3 👍 / 1 👎 across four closed tickets -> 75%.
    outcomes = [True, True, True, False]
    for positive in outcomes:
        t = ticket_factory(customer, status=SupportTicket.STATUS_CLOSED, closed_by=agent)
        rating_factory(t, staff=agent, is_positive=positive)

    sla = _body(api, bearer, lead)["sla"]
    assert sla["satisfaction_rate"] == 75


@pytest.mark.django_db
def test_sla_satisfaction_rounds_to_nearest_percent(
    api, bearer, lead, make_user, ticket_factory, rating_factory
):
    customer = make_user("customer")
    agent = make_user("agent", is_staff=True)
    # 2 👍 / 1 👎 -> 66.66.. -> rounds to 67.
    for positive in (True, True, False):
        t = ticket_factory(customer, status=SupportTicket.STATUS_CLOSED, closed_by=agent)
        rating_factory(t, staff=agent, is_positive=positive)

    assert _body(api, bearer, lead)["sla"]["satisfaction_rate"] == 67


@pytest.mark.django_db
def test_sla_satisfaction_is_null_without_ratings(api, bearer, lead, make_user, ticket_factory):
    customer = make_user("customer")
    ticket_factory(customer, status=SupportTicket.STATUS_CLOSED)  # closed but unrated
    assert _body(api, bearer, lead)["sla"]["satisfaction_rate"] is None


@pytest.mark.django_db
def test_sla_satisfaction_aggregates_across_all_staff(
    api, bearer, lead, make_user, ticket_factory, rating_factory
):
    # The lead SLA satisfaction spans EVERY rating, regardless of which agent
    # earned it (unlike the operator dashboard's per-agent figure).
    customer = make_user("customer")
    a1 = make_user("agent1", is_staff=True)
    a2 = make_user("agent2", is_staff=True)
    rating_factory(ticket_factory(customer, closed_by=a1), staff=a1, is_positive=True)
    rating_factory(ticket_factory(customer, closed_by=a2), staff=a2, is_positive=False)
    assert _body(api, bearer, lead)["sla"]["satisfaction_rate"] == 50


# --- Low stock ---------------------------------------------------------------
@pytest.mark.django_db
def test_low_stock_lists_products_below_threshold_ordered_ascending(
    api, bearer, lead, product_factory
):
    p0 = product_factory(stock=0)
    p4 = product_factory(stock=4)
    p3 = product_factory(stock=3)
    product_factory(stock=5)   # exactly 5 -> not low (threshold is stock < 5)
    product_factory(stock=20)  # plenty

    low = _body(api, bearer, lead)["low_stock"]
    assert [row["id"] for row in low] == [p0.id, p3.id, p4.id]  # ascending stock
    assert low[0] == {"id": p0.id, "title": p0.title, "stock": 0}


@pytest.mark.django_db
def test_low_stock_empty_when_all_well_stocked(api, bearer, lead, product_factory):
    product_factory(stock=5)
    product_factory(stock=99)
    assert _body(api, bearer, lead)["low_stock"] == []
