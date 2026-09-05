"""Owner-only surfaces (audit log, staff dossier, staff/customer moderation),
staff performance metrics, operator status, and the tagged-comment queue.

The recurring theme: audit log / approvals / dossier / moderation are the Team
Lead's (superuser) tools — a plain operator must get 403."""
import pytest
from django.utils import timezone

from apps.accounts.models import Profile
from apps.reviews.models import Review
from apps.support.models import (
    AdminAuditLog,
    SupportRating,
    SupportTicket,
)

from ._helpers import SUPPORT_BASE, jpost


# --- Owner-only access gate --------------------------------------------------
@pytest.mark.django_db
class TestOwnerOnlyGate:
    @pytest.mark.parametrize("path", [
        "/admin/audit",
        "/admin/approvals",
        "/admin/staff",
    ])
    def test_operator_forbidden_owner_allowed(self, api, bearer, make_user, path):
        operator = make_user("op", is_staff=True)
        owner = make_user("owner", is_superuser=True, is_staff=True)
        assert api.get(
            f"{SUPPORT_BASE}{path}", headers=bearer(operator)
        ).status_code == 403
        assert api.get(
            f"{SUPPORT_BASE}{path}", headers=bearer(owner)
        ).status_code == 200

    @pytest.mark.parametrize("path", [
        "/admin/audit",
        "/admin/approvals",
        "/admin/staff",
    ])
    def test_anonymous_unauthorized(self, api, path):
        assert api.get(f"{SUPPORT_BASE}{path}").status_code == 401


@pytest.mark.django_db
class TestAuditLog:
    def test_audit_log_lists_recorded_actions(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        operator = make_user("op", is_staff=True)
        ticket = SupportTicket.objects.create(user=make_user("cust"))
        # An operator closing a ticket writes an audit entry ...
        jpost(api, f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/close", bearer(operator))

        rows = api.get(f"{SUPPORT_BASE}/admin/audit", headers=bearer(owner)).json()
        actions = {r["action_type"] for r in rows}
        assert AdminAuditLog.ACTION_CLOSE_TICKET in actions


# --- Metrics -----------------------------------------------------------------
@pytest.mark.django_db
class TestMetrics:
    def test_metrics_require_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        assert api.get(
            f"{SUPPORT_BASE}/admin/metrics", headers=bearer(customer)
        ).status_code == 403
        assert api.get(f"{SUPPORT_BASE}/admin/metrics").status_code == 401

    def test_metrics_are_derived_from_ratings(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        # Two resolved tickets: one 👍, one 👎.
        for i, positive in enumerate([True, False]):
            t = SupportTicket.objects.create(
                user=make_user(f"c{i}"),
                status=SupportTicket.STATUS_CLOSED,
                closed_by=operator,
                closed_at=timezone.now(),
            )
            SupportRating.objects.create(ticket=t, staff=operator, is_positive=positive)

        body = api.get(f"{SUPPORT_BASE}/admin/metrics", headers=bearer(operator)).json()
        assert body["resolved_tickets"] == 2
        assert body["ratings_total"] == 2
        assert body["ratings_positive"] == 1
        assert body["positive_rate"] == 50

    def test_positive_rate_none_without_ratings(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        body = api.get(f"{SUPPORT_BASE}/admin/metrics", headers=bearer(operator)).json()
        assert body["ratings_total"] == 0
        assert body["positive_rate"] is None


# --- Staff dossier -----------------------------------------------------------
@pytest.mark.django_db
class TestStaffDossier:
    def test_lists_staff_with_roles(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        operator = make_user("op", is_staff=True)
        rows = api.get(f"{SUPPORT_BASE}/admin/staff", headers=bearer(owner)).json()
        by_username = {r["username"]: r for r in rows}
        assert by_username["owner"]["role"] == "owner"
        assert by_username["op"]["role"] == "operator"
        assert by_username["op"]["is_active"] is True


# --- Operator status ---------------------------------------------------------
@pytest.mark.django_db
class TestOperatorStatus:
    def test_set_status_away(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/me/status", bearer(operator),
            {"status": Profile.STATUS_AWAY},
        )
        assert resp.status_code == 200
        profile = Profile.objects.get(user=operator)
        assert profile.operator_status == Profile.STATUS_AWAY

    def test_invalid_status_defaults_online(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        jpost(
            api, f"{SUPPORT_BASE}/admin/me/status", bearer(operator),
            {"status": "invisible"},
        )
        profile = Profile.objects.get(user=operator)
        assert profile.operator_status == Profile.STATUS_ONLINE

    def test_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/me/status", bearer(customer),
            {"status": Profile.STATUS_AWAY},
        )
        assert resp.status_code == 403


# --- Staff moderation (block / unblock operators) ----------------------------
@pytest.mark.django_db
class TestStaffModeration:
    def test_owner_blocks_operator_who_then_loses_access(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        operator = make_user("op", is_staff=True)

        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/staff/{operator.id}/block", bearer(owner)
        )
        assert resp.status_code == 200
        operator.refresh_from_db()
        assert operator.is_active is False
        # A blocked operator can no longer reach staff endpoints (access revoked).
        denied = api.get(f"{SUPPORT_BASE}/admin/tickets", headers=bearer(operator))
        assert denied.status_code in (401, 403)

    def test_unblock_restores_access(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        operator = make_user("op", is_staff=True)
        jpost(api, f"{SUPPORT_BASE}/admin/staff/{operator.id}/block", bearer(owner))
        jpost(api, f"{SUPPORT_BASE}/admin/staff/{operator.id}/unblock", bearer(owner))
        operator.refresh_from_db()
        assert operator.is_active is True
        assert api.get(
            f"{SUPPORT_BASE}/admin/tickets", headers=bearer(operator)
        ).status_code == 200

    def test_cannot_block_owner(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        other_owner = make_user("owner2", is_superuser=True, is_staff=True)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/staff/{other_owner.id}/block", bearer(owner)
        )
        assert resp.status_code == 400
        other_owner.refresh_from_db()
        assert other_owner.is_active is True

    def test_block_staff_is_owner_only(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        victim = make_user("op2", is_staff=True)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/staff/{victim.id}/block", bearer(operator)
        )
        assert resp.status_code == 403


# --- Customer moderation (block / unblock buyers) ----------------------------
@pytest.mark.django_db
class TestCustomerModeration:
    def test_owner_blocks_customer(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        customer = make_user("cust")
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/users/{customer.id}/block", bearer(owner),
            {"permanent": True},
        )
        assert resp.status_code == 200
        profile = Profile.objects.get(user=customer)
        assert profile.is_blocked is True

    def test_temporary_block_sets_expiry(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        customer = make_user("cust")
        jpost(
            api, f"{SUPPORT_BASE}/admin/users/{customer.id}/block", bearer(owner),
            {"permanent": False, "days": 3},
        )
        profile = Profile.objects.get(user=customer)
        assert profile.blocked_permanent is False
        assert profile.blocked_until is not None and profile.blocked_until > timezone.now()

    def test_unblock_customer(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        customer = make_user("cust")
        jpost(
            api, f"{SUPPORT_BASE}/admin/users/{customer.id}/block", bearer(owner),
            {"permanent": True},
        )
        jpost(api, f"{SUPPORT_BASE}/admin/users/{customer.id}/unblock", bearer(owner))
        profile = Profile.objects.get(user=customer)
        assert profile.is_blocked is False

    def test_cannot_block_staff_account_as_customer(self, api, bearer, make_user):
        owner = make_user("owner", is_superuser=True, is_staff=True)
        operator = make_user("op", is_staff=True)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/users/{operator.id}/block", bearer(owner),
            {"permanent": True},
        )
        assert resp.status_code == 400

    def test_block_user_is_owner_only(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/users/{customer.id}/block", bearer(operator),
            {"permanent": True},
        )
        assert resp.status_code == 403


# --- Tagged product comments queue -------------------------------------------
@pytest.mark.django_db
class TestTaggedComments:
    def _make_review(self, make_user, product_factory, **kw):
        author = make_user(f"rev{Review.objects.count()}")
        product = product_factory()
        return Review.objects.create(
            user=author, product=product, rating=2, text="defective",
            needs_support=True, **kw,
        )

    def test_list_pending_tagged_comments(self, api, bearer, make_user, product_factory):
        operator = make_user("op", is_staff=True)
        review = self._make_review(make_user, product_factory)
        rows = api.get(f"{SUPPORT_BASE}/admin/comments", headers=bearer(operator)).json()
        assert review.id in [r["id"] for r in rows]

    def test_resolved_comments_excluded(self, api, bearer, make_user, product_factory):
        operator = make_user("op", is_staff=True)
        review = self._make_review(
            make_user, product_factory, support_status=Review.SUPPORT_RESOLVED
        )
        rows = api.get(f"{SUPPORT_BASE}/admin/comments", headers=bearer(operator)).json()
        assert review.id not in [r["id"] for r in rows]

    def test_resolve_marks_resolver(self, api, bearer, make_user, product_factory):
        operator = make_user("op", is_staff=True)
        review = self._make_review(make_user, product_factory)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/comments/{review.id}/resolve", bearer(operator)
        )
        assert resp.status_code == 200
        review.refresh_from_db()
        assert review.support_status == Review.SUPPORT_RESOLVED
        assert review.support_resolved_by == operator
        assert review.support_resolved_at is not None

    def test_list_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        assert api.get(
            f"{SUPPORT_BASE}/admin/comments", headers=bearer(customer)
        ).status_code == 403
