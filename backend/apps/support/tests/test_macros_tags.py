"""Macros (reply templates) CRUD + rendering, and customer tags (karma):
create / assign / remove with audit logging. All staff-gated."""
import pytest

from apps.support.models import (
    AdminAuditLog,
    CustomerTag,
    CustomerTagAssignment,
    SupportMacro,
    SupportTicket,
)

from ._helpers import SUPPORT_BASE, jdelete, jpost, jput


# --- Macros ------------------------------------------------------------------
@pytest.mark.django_db
class TestMacros:
    def test_list_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        assert api.get(
            f"{SUPPORT_BASE}/admin/macros", headers=bearer(customer)
        ).status_code == 403
        assert api.get(f"{SUPPORT_BASE}/admin/macros").status_code == 401

    def test_list_includes_seeded_macros(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        rows = api.get(f"{SUPPORT_BASE}/admin/macros", headers=bearer(operator)).json()
        # Migration 0005 seeds four default macros.
        assert len(rows) >= 4

    def test_create_macro(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/macros", bearer(operator),
            {"title": " Привітання ", "content": "Вітаю, {first_name}!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Привітання"  # trimmed
        macro = SupportMacro.objects.get(id=body["id"])
        assert macro.created_by == operator

    def test_create_rejects_blank(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        assert jpost(
            api, f"{SUPPORT_BASE}/admin/macros", bearer(operator),
            {"title": "  ", "content": "x"},
        ).status_code == 400
        assert jpost(
            api, f"{SUPPORT_BASE}/admin/macros", bearer(operator),
            {"title": "t", "content": "   "},
        ).status_code == 400

    def test_update_macro(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        macro = SupportMacro.objects.create(title="old", content="old body")
        resp = jput(
            api, f"{SUPPORT_BASE}/admin/macros/{macro.id}", bearer(operator),
            {"title": "new", "content": "new body"},
        )
        assert resp.status_code == 200
        macro.refresh_from_db()
        assert macro.title == "new"
        assert macro.content == "new body"

    def test_update_missing_404(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        assert jput(
            api, f"{SUPPORT_BASE}/admin/macros/999999", bearer(operator),
            {"title": "x", "content": "y"},
        ).status_code == 404

    def test_delete_macro(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        macro = SupportMacro.objects.create(title="temp", content="body")
        resp = jdelete(api, f"{SUPPORT_BASE}/admin/macros/{macro.id}", bearer(operator))
        assert resp.status_code == 200
        assert not SupportMacro.objects.filter(id=macro.id).exists()

    def test_render_resolves_placeholders_against_ticket_customer(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust", email="c@e.com")
        customer.first_name = "Оля"
        customer.save(update_fields=["first_name"])
        ticket = SupportTicket.objects.create(user=customer)
        macro = SupportMacro.objects.create(title="hi", content="Вітаю, {first_name}!")

        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/macros/{macro.id}/render", bearer(operator),
            {"ticket_id": ticket.id},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Вітаю, Оля!"

    def test_render_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        ticket = SupportTicket.objects.create(user=customer)
        macro = SupportMacro.objects.create(title="hi", content="hello")
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/macros/{macro.id}/render", bearer(customer),
            {"ticket_id": ticket.id},
        )
        assert resp.status_code == 403


# --- Customer tags -----------------------------------------------------------
@pytest.mark.django_db
class TestTags:
    def test_list_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        assert api.get(
            f"{SUPPORT_BASE}/admin/tags", headers=bearer(customer)
        ).status_code == 403
        assert api.get(f"{SUPPORT_BASE}/admin/tags").status_code == 401

    def test_list_includes_seeded_tags(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        rows = api.get(f"{SUPPORT_BASE}/admin/tags", headers=bearer(operator)).json()
        labels = {r["label"] for r in rows}
        assert "VIP" in labels  # seeded by migration 0004

    def test_create_tag(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tags", bearer(operator),
            {"label": " Boycott ", "color": "#111111"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["label"] == "Boycott"
        assert body["color"] == "#111111"

    def test_create_blank_label_400(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        assert jpost(
            api, f"{SUPPORT_BASE}/admin/tags", bearer(operator), {"label": "   "}
        ).status_code == 400

    def test_create_existing_label_returns_existing(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        existing = CustomerTag.objects.create(label="Repeat", color="#abcdef")
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/tags", bearer(operator),
            {"label": "Repeat", "color": "#000000"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == existing.id
        assert CustomerTag.objects.filter(label="Repeat").count() == 1

    def test_assign_tag_and_audit(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        tag = CustomerTag.objects.create(label="Flagged")
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/users/{customer.id}/tags", bearer(operator),
            {"tag_id": tag.id},
        )
        assert resp.status_code == 200
        labels = {t["label"] for t in resp.json()}
        assert "Flagged" in labels
        assignment = CustomerTagAssignment.objects.get(user=customer, tag=tag)
        assert assignment.assigned_by == operator
        assert AdminAuditLog.objects.filter(
            action_type=AdminAuditLog.ACTION_TAG_ADD, target_user=customer
        ).exists()

    def test_assign_tag_is_idempotent(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        tag = CustomerTag.objects.create(label="Flagged")
        for _ in range(2):
            jpost(
                api, f"{SUPPORT_BASE}/admin/users/{customer.id}/tags", bearer(operator),
                {"tag_id": tag.id},
            )
        assert CustomerTagAssignment.objects.filter(user=customer, tag=tag).count() == 1
        # Only the first (creating) assignment is audited.
        assert AdminAuditLog.objects.filter(
            action_type=AdminAuditLog.ACTION_TAG_ADD, target_user=customer
        ).count() == 1

    def test_remove_tag_and_audit(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        customer = make_user("cust")
        tag = CustomerTag.objects.create(label="Flagged")
        CustomerTagAssignment.objects.create(user=customer, tag=tag, assigned_by=operator)

        resp = jdelete(
            api, f"{SUPPORT_BASE}/admin/users/{customer.id}/tags/{tag.id}", bearer(operator)
        )
        assert resp.status_code == 200
        assert not CustomerTagAssignment.objects.filter(user=customer, tag=tag).exists()
        assert AdminAuditLog.objects.filter(
            action_type=AdminAuditLog.ACTION_TAG_REMOVE, target_user=customer
        ).exists()

    def test_assign_requires_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        tag = CustomerTag.objects.create(label="Flagged")
        resp = jpost(
            api, f"{SUPPORT_BASE}/admin/users/{customer.id}/tags", bearer(customer),
            {"tag_id": tag.id},
        )
        assert resp.status_code == 403
