"""Actionable chat (bonus gifts) and the Team-Lead approval workflow:
auto-approve threshold, hard ceiling, owner bypass, approve/reject (owner-only),
and reversing a grant. Verifies both the money movement and the audit trail."""
import pytest

from apps.accounts.models import Profile
from apps.support.models import (
    AUTO_APPROVE_BONUSES,
    MAX_GRANT_BONUSES,
    ActionApproval,
    AdminAuditLog,
    ChatMessage,
    SupportTicket,
)

from ._helpers import SUPPORT_BASE, grant_message, jpost


def _ticket_for(customer):
    return SupportTicket.objects.create(user=customer)


def _balance(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.refresh_from_db()
    return profile.bonus_balance


def _grant(api, bearer, staff, ticket, amount):
    return jpost(
        api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/action", bearer(staff),
        {"type": "grant_bonuses", "amount": amount},
    )


@pytest.mark.django_db
class TestGrantBonuses:
    def test_operator_small_grant_auto_approves(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        ticket = _ticket_for(customer)

        resp = _grant(api, bearer, operator, ticket, AUTO_APPROVE_BONUSES)  # at the limit
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "pending": False}
        assert _balance(customer) == AUTO_APPROVE_BONUSES
        # System message + audit entry recorded.
        assert ChatMessage.objects.filter(
            ticket=ticket, is_system=True, meta__action="grant_bonuses"
        ).exists()
        assert AdminAuditLog.objects.filter(
            action_type=AdminAuditLog.ACTION_GRANT_BONUSES, target_user=customer
        ).exists()

    def test_operator_large_grant_requires_approval(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        ticket = _ticket_for(customer)

        resp = _grant(api, bearer, operator, ticket, AUTO_APPROVE_BONUSES + 1)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "pending": True}
        # Nothing credited yet; a pending approval exists.
        assert _balance(customer) == 0
        appr = ActionApproval.objects.get(ticket=ticket, requested_by=operator)
        assert appr.status == ActionApproval.PENDING
        assert appr.amount == AUTO_APPROVE_BONUSES + 1

    def test_owner_large_grant_bypasses_approval(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        customer = make_user("cust")
        ticket = _ticket_for(customer)

        resp = _grant(api, bearer, owner, ticket, AUTO_APPROVE_BONUSES + 500)
        assert resp.status_code == 200
        assert resp.json()["pending"] is False
        assert _balance(customer) == AUTO_APPROVE_BONUSES + 500
        assert not ActionApproval.objects.filter(ticket=ticket).exists()

    def test_over_hard_cap_rejected_for_operator(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _ticket_for(make_user("cust"))
        resp = _grant(api, bearer, operator, ticket, MAX_GRANT_BONUSES + 1)
        assert resp.status_code == 400
        assert not ActionApproval.objects.filter(ticket=ticket).exists()

    def test_over_hard_cap_rejected_even_for_owner(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        customer = make_user("cust")
        ticket = _ticket_for(customer)
        resp = _grant(api, bearer, owner, ticket, MAX_GRANT_BONUSES + 1)
        assert resp.status_code == 400
        assert _balance(customer) == 0

    def test_zero_or_negative_amount_rejected(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _ticket_for(make_user("cust"))
        assert _grant(api, bearer, operator, ticket, 0).status_code == 400
        assert _grant(api, bearer, operator, ticket, -50).status_code == 400

    def test_unknown_action_type_rejected(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        ticket = _ticket_for(make_user("cust"))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/action", bearer(operator),
            {"type": "delete_everything", "amount": 10},
        )
        assert resp.status_code == 400

    def test_action_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        ticket = _ticket_for(customer)
        resp = _grant(api, bearer, customer, ticket, 10)
        assert resp.status_code == 403


@pytest.mark.django_db
class TestApprovalWorkflow:
    def _pending(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        owner = make_user("owner", is_superuser=True, is_staff=True)
        customer = make_user("cust")
        ticket = _ticket_for(customer)
        _grant(api, bearer, operator, ticket, 1000)
        appr = ActionApproval.objects.get(ticket=ticket)
        return operator, owner, customer, ticket, appr

    def test_list_pending_is_owner_only(self, api, bearer, make_user):
        operator, owner, customer, ticket, appr = self._pending(api, bearer, make_user)
        assert api.get(
            f"{SUPPORT_BASE}/admin/approvals", headers=bearer(operator)
        ).status_code == 403
        rows = api.get(f"{SUPPORT_BASE}/admin/approvals", headers=bearer(owner)).json()
        assert appr.id in [r["id"] for r in rows]
        assert rows[0]["amount"] == 1000

    def test_approve_executes_and_credits_requester(self, api, bearer, make_user):
        operator, owner, customer, ticket, appr = self._pending(api, bearer, make_user)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/approvals/{appr.id}/approve", bearer(owner)
        )
        assert resp.status_code == 200
        assert _balance(customer) == 1000
        appr.refresh_from_db()
        assert appr.status == ActionApproval.APPROVED
        assert appr.decided_by == owner
        # The grant is credited to the original requester, not the approver.
        grant = grant_message(ticket)
        assert grant.sender == operator

    def test_approve_twice_rejected(self, api, bearer, make_user):
        operator, owner, customer, ticket, appr = self._pending(api, bearer, make_user)
        jpost(api, f"{SUPPORT_BASE}/admin/approvals/{appr.id}/approve", bearer(owner))
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/approvals/{appr.id}/approve", bearer(owner)
        )
        assert resp.status_code == 400
        assert _balance(customer) == 1000  # not double-credited

    def test_reject_does_not_credit(self, api, bearer, make_user):
        operator, owner, customer, ticket, appr = self._pending(api, bearer, make_user)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/approvals/{appr.id}/reject", bearer(owner)
        )
        assert resp.status_code == 200
        appr.refresh_from_db()
        assert appr.status == ActionApproval.REJECTED
        assert _balance(customer) == 0

    def test_approve_is_owner_only(self, api, bearer, make_user):
        operator, owner, customer, ticket, appr = self._pending(api, bearer, make_user)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/approvals/{appr.id}/approve", bearer(operator)
        )
        assert resp.status_code == 403
        assert _balance(customer) == 0

    def test_reject_is_owner_only(self, api, bearer, make_user):
        operator, owner, customer, ticket, appr = self._pending(api, bearer, make_user)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/approvals/{appr.id}/reject", bearer(operator)
        )
        assert resp.status_code == 403
        appr.refresh_from_db()
        assert appr.status == ActionApproval.PENDING


@pytest.mark.django_db
class TestCancelBonus:
    def _granted_ticket(self, api, bearer, make_user, amount=100):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        ticket = _ticket_for(customer)
        _grant(api, bearer, operator, ticket, amount)
        msg = grant_message(ticket)
        return operator, customer, ticket, msg

    def test_cancel_reverses_the_grant(self, api, bearer, make_user):
        operator, customer, ticket, msg = self._granted_ticket(api, bearer, make_user, 100)
        assert _balance(customer) == 100

        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/cancel-bonus", bearer(operator),
            {"message_id": msg.id},
        )
        assert resp.status_code == 200
        assert _balance(customer) == 0
        msg.refresh_from_db()
        assert msg.meta.get("reversed") is True
        assert ChatMessage.objects.filter(
            ticket=ticket, is_system=True, meta__action="cancel_bonuses"
        ).exists()

    def test_cannot_cancel_twice(self, api, bearer, make_user):
        operator, customer, ticket, msg = self._granted_ticket(api, bearer, make_user, 100)
        jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/cancel-bonus", bearer(operator),
            {"message_id": msg.id},
        )
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/cancel-bonus", bearer(operator),
            {"message_id": msg.id},
        )
        assert resp.status_code == 400
        assert _balance(customer) == 0  # still only reversed once

    def test_cannot_cancel_non_grant_message(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        ticket = _ticket_for(customer)
        plain = ChatMessage.objects.create(
            ticket=ticket, sender=operator, from_staff=True, text="just a reply"
        )
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/cancel-bonus", bearer(operator),
            {"message_id": plain.id},
        )
        assert resp.status_code == 400

    def test_cancel_requires_staff(self, api, bearer, make_user):
        operator, customer, ticket, msg = self._granted_ticket(api, bearer, make_user, 100)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/cancel-bonus", bearer(customer),
            {"message_id": msg.id},
        )
        assert resp.status_code == 403
