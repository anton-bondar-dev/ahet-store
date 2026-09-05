"""Analytics-specific factories, layered on top of the shared root conftest.

These build the domain objects the two dashboard endpoints aggregate over —
orders + line items (lead financials), support tickets + ratings (SLA /
operator metrics) and support-flagged reviews. They deliberately keep the
required-but-irrelevant fields (customer name, address, …) filled with sane
defaults so each test only spells out the figures it actually asserts on.
"""
from decimal import Decimal

import pytest

from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review
from apps.support.models import SupportRating, SupportTicket


def dec(value) -> Decimal:
    """Normalise a JSON-decoded money value (django-ninja renders Decimals as
    strings) to a Decimal for exact numeric comparison."""
    return Decimal(str(value))


@pytest.fixture
def order_factory(db):
    def _make(total_price="100.00", status=Order._meta.get_field("status").default,
              user=None, created_at=None, **kwargs):
        defaults = dict(
            first_name="John", last_name="Doe", phone="+380501112233",
            email="john@example.com", city="Kyiv", address="Main St 1",
        )
        defaults.update(kwargs)
        order = Order.objects.create(
            user=user, status=status, total_price=total_price, **defaults
        )
        if created_at is not None:
            # created_at is auto_now_add, so it can only be forced via an UPDATE.
            Order.objects.filter(pk=order.pk).update(created_at=created_at)
            order.refresh_from_db()
        return order

    return _make


@pytest.fixture
def order_item_factory(db):
    def _make(order, product, quantity=1, price=None):
        return OrderItem.objects.create(
            order=order,
            product=product,
            product_title=product.title,
            quantity=quantity,
            price=product.price if price is None else price,
        )

    return _make


@pytest.fixture
def ticket_factory(db):
    def _make(user, status=SupportTicket.STATUS_OPEN, closed_by=None,
              closed_at=None, last_user_message_at=None, last_staff_message_at=None,
              **kwargs):
        return SupportTicket.objects.create(
            user=user,
            status=status,
            closed_by=closed_by,
            closed_at=closed_at,
            last_user_message_at=last_user_message_at,
            last_staff_message_at=last_staff_message_at,
            **kwargs,
        )

    return _make


@pytest.fixture
def rating_factory(db):
    def _make(ticket, staff, is_positive=True):
        return SupportRating.objects.create(
            ticket=ticket, staff=staff, is_positive=is_positive
        )

    return _make


@pytest.fixture
def resolved_review_factory(db, make_user, product_factory):
    """A support-flagged review marked resolved by `staff` (feeds the operator
    endpoint's `comments_resolved`). Each call gets a fresh reviewer + product so
    the (user, product) uniqueness constraint is never hit."""
    counter = {"n": 0}

    def _make(staff, resolved=True, user=None, product=None):
        counter["n"] += 1
        user = user or make_user(f"reviewer{counter['n']}")
        product = product or product_factory()
        return Review.objects.create(
            user=user,
            product=product,
            rating=5,
            needs_support=True,
            support_status=(
                Review.SUPPORT_RESOLVED if resolved else Review.SUPPORT_PENDING
            ),
            support_resolved_by=staff if resolved else None,
        )

    return _make
