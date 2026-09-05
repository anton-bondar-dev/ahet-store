"""Unit coverage for SupportTicket.is_overdue.

The lead dashboard's `sla.overdue_tickets` is computed by iterating open tickets
and counting `t.is_overdue`, so the branch logic of that property is part of the
analytics contract. Each branch is exercised here directly (no HTTP).
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.support.models import SLA_RESPONSE_HOURS, SupportTicket


@pytest.fixture
def customer(make_user):
    return make_user("customer")


@pytest.mark.django_db
def test_closed_ticket_is_never_overdue(customer, ticket_factory):
    stale = timezone.now() - timedelta(hours=SLA_RESPONSE_HOURS + 1)
    t = ticket_factory(customer, status=SupportTicket.STATUS_CLOSED, last_user_message_at=stale)
    assert t.is_overdue is False


@pytest.mark.django_db
def test_open_ticket_without_user_message_is_not_overdue(customer, ticket_factory):
    t = ticket_factory(customer, status=SupportTicket.STATUS_OPEN, last_user_message_at=None)
    assert t.is_overdue is False


@pytest.mark.django_db
def test_recent_unanswered_message_is_not_overdue(customer, ticket_factory):
    recent = timezone.now() - timedelta(hours=SLA_RESPONSE_HOURS - 1)
    t = ticket_factory(customer, status=SupportTicket.STATUS_OPEN, last_user_message_at=recent)
    assert t.is_overdue is False


@pytest.mark.django_db
def test_stale_unanswered_message_is_overdue(customer, ticket_factory):
    stale = timezone.now() - timedelta(hours=SLA_RESPONSE_HOURS + 1)
    t = ticket_factory(customer, status=SupportTicket.STATUS_OPEN, last_user_message_at=stale)
    assert t.is_overdue is True


@pytest.mark.django_db
def test_staff_reply_after_user_clears_overdue(customer, ticket_factory):
    now = timezone.now()
    stale = now - timedelta(hours=SLA_RESPONSE_HOURS + 1)
    t = ticket_factory(
        customer, status=SupportTicket.STATUS_OPEN,
        last_user_message_at=stale, last_staff_message_at=now,  # staff answered since
    )
    assert t.is_overdue is False


@pytest.mark.django_db
def test_stale_staff_reply_before_newer_user_message_is_overdue(customer, ticket_factory):
    now = timezone.now()
    # Staff replied, THEN the customer wrote again and has waited past the SLA.
    staff_reply = now - timedelta(hours=SLA_RESPONSE_HOURS + 2)
    user_followup = now - timedelta(hours=SLA_RESPONSE_HOURS + 1)
    t = ticket_factory(
        customer, status=SupportTicket.STATUS_OPEN,
        last_user_message_at=user_followup, last_staff_message_at=staff_reply,
    )
    assert t.is_overdue is True
