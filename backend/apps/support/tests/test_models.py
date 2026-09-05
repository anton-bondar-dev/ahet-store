"""Model-level tests: SupportTicket.is_overdue SLA logic, constraints, and the
__str__ helpers. These touch the ORM directly (no HTTP), so they lock the data
layer independently of the API."""
from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.support.models import (
    SLA_RESPONSE_HOURS,
    ActionApproval,
    ChatMessage,
    CustomerTag,
    CustomerTagAssignment,
    SupportRating,
    SupportTicket,
    TicketPresence,
)


def _hours_ago(h):
    return timezone.now() - timedelta(hours=h)


@pytest.mark.django_db
class TestIsOverdue:
    def test_open_unanswered_past_sla_is_overdue(self, make_user):
        t = SupportTicket.objects.create(user=make_user("c1"))
        t.last_user_message_at = _hours_ago(SLA_RESPONSE_HOURS + 1)
        t.save(update_fields=["last_user_message_at"])
        assert t.is_overdue is True

    def test_open_unanswered_within_sla_is_not_overdue(self, make_user):
        t = SupportTicket.objects.create(user=make_user("c2"))
        t.last_user_message_at = _hours_ago(1)
        t.save(update_fields=["last_user_message_at"])
        assert t.is_overdue is False

    def test_answered_ticket_is_not_overdue(self, make_user):
        t = SupportTicket.objects.create(user=make_user("c3"))
        t.last_user_message_at = _hours_ago(SLA_RESPONSE_HOURS + 5)
        t.last_staff_message_at = _hours_ago(1)  # staff replied after the customer
        t.save(update_fields=["last_user_message_at", "last_staff_message_at"])
        assert t.is_overdue is False

    def test_stale_staff_reply_still_overdue(self, make_user):
        # Staff replied, but the customer wrote again afterwards and got no answer.
        t = SupportTicket.objects.create(user=make_user("c4"))
        t.last_staff_message_at = _hours_ago(SLA_RESPONSE_HOURS + 3)
        t.last_user_message_at = _hours_ago(SLA_RESPONSE_HOURS + 1)
        t.save(update_fields=["last_user_message_at", "last_staff_message_at"])
        assert t.is_overdue is True

    def test_closed_ticket_is_never_overdue(self, make_user):
        t = SupportTicket.objects.create(
            user=make_user("c5"), status=SupportTicket.STATUS_CLOSED
        )
        t.last_user_message_at = _hours_ago(SLA_RESPONSE_HOURS + 10)
        t.save(update_fields=["last_user_message_at"])
        assert t.is_overdue is False

    def test_no_customer_message_is_not_overdue(self, make_user):
        t = SupportTicket.objects.create(user=make_user("c6"))
        assert t.last_user_message_at is None
        assert t.is_overdue is False


@pytest.mark.django_db
class TestConstraints:
    def test_rating_is_one_to_one_with_ticket(self, make_user):
        t = SupportTicket.objects.create(user=make_user("r1"))
        SupportRating.objects.create(ticket=t, staff=None, is_positive=True)
        with pytest.raises(IntegrityError):
            SupportRating.objects.create(ticket=t, staff=None, is_positive=False)

    def test_tag_assignment_is_unique_per_user_and_tag(self, make_user):
        user = make_user("t1")
        tag = CustomerTag.objects.create(label="Unique-VIP")
        CustomerTagAssignment.objects.create(user=user, tag=tag)
        with pytest.raises(IntegrityError):
            CustomerTagAssignment.objects.create(user=user, tag=tag)

    def test_customer_tag_label_is_unique(self, make_user):
        CustomerTag.objects.create(label="Dupe")
        with pytest.raises(IntegrityError):
            CustomerTag.objects.create(label="Dupe")

    def test_presence_is_unique_per_ticket_and_staff(self, make_user):
        t = SupportTicket.objects.create(user=make_user("p1"))
        op = make_user("op1", is_staff=True)
        TicketPresence.objects.create(ticket=t, staff=op)
        with pytest.raises(IntegrityError):
            TicketPresence.objects.create(ticket=t, staff=op)


@pytest.mark.django_db
class TestDunderStr:
    def test_ticket_str(self, make_user):
        t = SupportTicket.objects.create(user=make_user("s1"))
        assert f"#{t.pk}" in str(t)
        assert "s1" in str(t)

    def test_chat_message_str_labels_author(self, make_user):
        t = SupportTicket.objects.create(user=make_user("s2"))
        m = ChatMessage.objects.create(ticket=t, sender=t.user, from_staff=False, text="hi")
        assert "user" in str(m)
        sysm = ChatMessage.objects.create(
            ticket=t, sender=None, from_staff=False, text="x", is_system=True
        )
        assert "system" in str(sysm)

    def test_action_approval_str_with_amount(self, make_user):
        # A grant with a real amount renders fine (`amount` short-circuits).
        t = SupportTicket.objects.create(user=make_user("s3"))
        appr = ActionApproval.objects.create(
            requested_by=t.user, ticket=t,
            action_type=ActionApproval.GRANT_BONUSES, amount=750,
        )
        assert "750" in str(appr)

    @pytest.mark.xfail(
        reason="BUG: ActionApproval.__str__ references self.percent, a field "
        "removed in migration 0010. When amount is falsy the `amount or "
        "self.percent` fallback raises AttributeError.",
        raises=AttributeError,
        strict=True,
    )
    def test_action_approval_str_with_zero_amount(self, make_user):
        t = SupportTicket.objects.create(user=make_user("s4"))
        appr = ActionApproval.objects.create(
            requested_by=t.user, ticket=t,
            action_type=ActionApproval.GRANT_BONUSES, amount=0,
        )
        str(appr)  # must not raise
