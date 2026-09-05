"""Admin-side ticket workspace: the queue (priority + SLA ordering, archive
filter), ticket detail (read receipts, presence/viewers), replies (internal vs
public, SLA), closing, assignment and priority — plus the staff-only guard on
every endpoint."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.orders.models import Order
from apps.support.models import (
    SLA_RESPONSE_HOURS,
    AdminAuditLog,
    ChatMessage,
    SupportTicket,
    TicketPresence,
)

from ._helpers import SUPPORT_BASE, jpost, open_ticket, staff_reply


def _mk_ticket(user, **kw):
    return SupportTicket.objects.create(user=user, **kw)


@pytest.mark.django_db
class TestListTicketsAuth:
    def test_customer_gets_403(self, api, bearer, make_user):
        customer = make_user("cust")
        resp = api.get(f"{SUPPORT_BASE}/admin/tickets", headers=bearer(customer))
        assert resp.status_code == 403

    def test_anonymous_gets_401(self, api):
        assert api.get(f"{SUPPORT_BASE}/admin/tickets").status_code == 401

    def test_staff_allowed(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        resp = api.get(f"{SUPPORT_BASE}/admin/tickets", headers=bearer(operator))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestQueueContents:
    def test_open_by_default_archived_on_request(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        open_t = _mk_ticket(make_user("c1"))
        closed_t = _mk_ticket(make_user("c2"), status=SupportTicket.STATUS_CLOSED)

        active = api.get(f"{SUPPORT_BASE}/admin/tickets", headers=bearer(operator)).json()
        ids = [t["id"] for t in active]
        assert open_t.id in ids and closed_t.id not in ids

        arch = api.get(
            f"{SUPPORT_BASE}/admin/tickets?archived=true", headers=bearer(operator)
        ).json()
        arch_ids = [t["id"] for t in arch]
        assert closed_t.id in arch_ids and open_t.id not in arch_ids

    def test_priority_ordering(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        low = _mk_ticket(make_user("c1"), priority=SupportTicket.PRIORITY_LOW)
        urgent = _mk_ticket(make_user("c2"), priority=SupportTicket.PRIORITY_URGENT)
        normal = _mk_ticket(make_user("c3"), priority=SupportTicket.PRIORITY_NORMAL)

        rows = api.get(f"{SUPPORT_BASE}/admin/tickets", headers=bearer(operator)).json()
        ids = [t["id"] for t in rows]
        assert ids.index(urgent.id) < ids.index(normal.id) < ids.index(low.id)

    def test_overdue_floats_within_same_priority(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        fresh = _mk_ticket(make_user("c1"))
        overdue = _mk_ticket(make_user("c2"))
        overdue.last_user_message_at = timezone.now() - timedelta(hours=SLA_RESPONSE_HOURS + 2)
        overdue.save(update_fields=["last_user_message_at"])

        rows = api.get(f"{SUPPORT_BASE}/admin/tickets", headers=bearer(operator)).json()
        ids = [t["id"] for t in rows]
        assert ids.index(overdue.id) < ids.index(fresh.id)
        overdue_row = next(t for t in rows if t["id"] == overdue.id)
        assert overdue_row["is_overdue"] is True

    def test_unread_count_annotation(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        open_ticket(api, bearer, customer)  # 1 unread customer message (welcome is staff)
        rows = api.get(f"{SUPPORT_BASE}/admin/tickets", headers=bearer(operator)).json()
        row = rows[0]
        assert row["unread_count"] == 1


@pytest.mark.django_db
class TestTicketDetail:
    def test_get_marks_customer_messages_read(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        ticket = open_ticket(api, bearer, customer)

        detail = api.get(
            f"{SUPPORT_BASE}/admin/tickets/{ticket.id}", headers=bearer(operator)
        )
        assert detail.status_code == 200
        # After viewing, the customer's messages are flagged read_by_staff.
        assert not ChatMessage.objects.filter(
            ticket=ticket, from_staff=False, read_by_staff=False
        ).exists()
        rows = api.get(f"{SUPPORT_BASE}/admin/tickets", headers=bearer(operator)).json()
        assert next(t for t in rows if t["id"] == ticket.id)["unread_count"] == 0

    def test_detail_exposes_internal_notes_to_staff(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        ticket = open_ticket(api, bearer, customer)
        staff_reply(api, bearer, operator, ticket, "внутрішня", is_internal=True)

        detail = api.get(
            f"{SUPPORT_BASE}/admin/tickets/{ticket.id}", headers=bearer(operator)
        ).json()
        internal = [m for m in detail["messages"] if m["is_internal"]]
        assert len(internal) == 1
        assert internal[0]["text"] == "внутрішня"
        # The real staff author is exposed on the admin side (not masked).
        assert internal[0]["sender_username"] == "op"

    def test_get_missing_ticket_404(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        assert api.get(
            f"{SUPPORT_BASE}/admin/tickets/999999", headers=bearer(operator)
        ).status_code == 404

    def test_detail_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        ticket = _mk_ticket(customer)
        assert api.get(
            f"{SUPPORT_BASE}/admin/tickets/{ticket.id}", headers=bearer(customer)
        ).status_code == 403


@pytest.mark.django_db
class TestReply:
    def test_public_reply_appended_and_answers_sla(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        ticket = open_ticket(api, bearer, customer)
        # make the ticket overdue first
        ticket.last_user_message_at = timezone.now() - timedelta(hours=SLA_RESPONSE_HOURS + 2)
        ticket.save(update_fields=["last_user_message_at"])

        resp = staff_reply(api, bearer, operator, ticket, "Ось відповідь")
        assert resp.status_code == 200
        ticket.refresh_from_db()
        assert ticket.last_staff_message_at is not None
        assert ticket.is_overdue is False
        assert ChatMessage.objects.filter(
            ticket=ticket, from_staff=True, text="Ось відповідь", is_internal=False
        ).exists()

    def test_internal_note_does_not_answer_sla(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        ticket = open_ticket(api, bearer, customer)
        ticket.last_user_message_at = timezone.now() - timedelta(hours=SLA_RESPONSE_HOURS + 2)
        ticket.save(update_fields=["last_user_message_at"])

        staff_reply(api, bearer, operator, ticket, "note to self", is_internal=True)
        ticket.refresh_from_db()
        assert ticket.last_staff_message_at is None  # SLA clock untouched
        assert ticket.is_overdue is True

    def test_empty_reply_400(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/reply",
            bearer(operator), {"text": "   "},
        )
        assert resp.status_code == 400

    def test_reply_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        ticket = _mk_ticket(customer)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/reply",
            bearer(customer), {"text": "hi"},
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestCloseTicket:
    def test_close_sets_closer_and_audits(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        resp = jpost(api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/close", bearer(operator))
        assert resp.status_code == 200
        ticket.refresh_from_db()
        assert ticket.status == SupportTicket.STATUS_CLOSED
        assert ticket.closed_by == operator
        assert ticket.closed_at is not None
        assert AdminAuditLog.objects.filter(
            admin_user=operator, action_type=AdminAuditLog.ACTION_CLOSE_TICKET, ticket=ticket
        ).exists()

    def test_close_is_idempotent_no_double_audit(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        jpost(api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/close", bearer(operator))
        jpost(api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/close", bearer(operator))
        assert AdminAuditLog.objects.filter(
            action_type=AdminAuditLog.ACTION_CLOSE_TICKET, ticket=ticket
        ).count() == 1

    def test_close_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        ticket = _mk_ticket(customer)
        resp = jpost(api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/close", bearer(customer))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestAssignment:
    def test_assign_to_me(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/assign",
            bearer(operator), {"operator_id": None},
        )
        assert resp.status_code == 200
        ticket.refresh_from_db()
        assert ticket.assigned_to == operator

    def test_operator_cannot_assign_to_another_operator(self, api, bearer, make_user):
        op1 = make_user("op1", is_staff=True)
        op2 = make_user("op2", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/assign",
            bearer(op1), {"operator_id": op2.id},
        )
        assert resp.status_code == 403
        ticket.refresh_from_db()
        assert ticket.assigned_to is None

    def test_owner_can_assign_to_another_operator(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        op2 = make_user("op2", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/assign",
            bearer(owner), {"operator_id": op2.id},
        )
        assert resp.status_code == 200
        ticket.refresh_from_db()
        assert ticket.assigned_to == op2

    def test_cannot_assign_ticket_to_a_customer(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        customer2 = make_user("cust2")
        ticket = _mk_ticket(make_user("cust"))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/assign",
            bearer(owner), {"operator_id": customer2.id},
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestPriority:
    def test_set_priority(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/priority",
            bearer(operator), {"priority": SupportTicket.PRIORITY_URGENT},
        )
        assert resp.status_code == 200
        ticket.refresh_from_db()
        assert ticket.priority == SupportTicket.PRIORITY_URGENT

    def test_invalid_priority_400(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/priority",
            bearer(operator), {"priority": "banana"},
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestPresence:
    def test_heartbeat_records_presence(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/presence",
            bearer(operator), {"state": "typing"},
        )
        assert resp.status_code == 200
        pres = TicketPresence.objects.get(ticket=ticket, staff=operator)
        assert pres.state == "typing"

    def test_other_viewers_surface_in_detail(self, api, bearer, make_user):
        op1 = make_user("op1", is_staff=True)
        op2 = make_user("op2", is_staff=True)
        ticket = _mk_ticket(make_user("cust"))
        # op2 announces they are typing on the ticket ...
        jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/presence",
            bearer(op2), {"state": "typing"},
        )
        # ... op1 opens it and should see op2 listed as a live viewer.
        detail = api.get(
            f"{SUPPORT_BASE}/admin/tickets/{ticket.id}", headers=bearer(op1)
        ).json()
        viewers = {v["staff_username"]: v for v in detail["viewers"]}
        assert "op2" in viewers
        assert viewers["op2"]["state"] == "typing"
        assert "op1" not in viewers  # the caller excludes themselves


@pytest.mark.django_db
class TestCustomerOrders:
    def test_lists_recent_orders(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        ticket = _mk_ticket(customer)
        Order.objects.create(user=customer, total_price="42.00")

        resp = api.get(
            f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/orders", headers=bearer(operator)
        )
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["item_count"] == 0

    def test_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        ticket = _mk_ticket(customer)
        assert api.get(
            f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/orders", headers=bearer(customer)
        ).status_code == 403
