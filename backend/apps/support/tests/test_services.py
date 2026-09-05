"""Unit tests for the pure service helpers in apps/support/services.py."""
import pytest

from apps.support.models import AdminAuditLog, SupportTicket
from apps.support.services import log_admin_action, parse_user_agent, render_macro


class TestRenderMacro:
    class _U:
        def __init__(self, first_name="", last_name="", username="john"):
            self.first_name = first_name
            self.last_name = last_name
            self.username = username

    def test_first_name_placeholder(self):
        out = render_macro("Вітаю, {first_name}!", self._U(first_name="Оля"))
        assert out == "Вітаю, Оля!"

    def test_first_name_falls_back_to_username(self):
        out = render_macro("Hi {first_name}", self._U(first_name="", username="bob"))
        assert out == "Hi bob"

    def test_all_whitelisted_keys(self):
        out = render_macro(
            "{first_name} {last_name} ({username})",
            self._U(first_name="A", last_name="B", username="ab"),
        )
        assert out == "A B (ab)"

    def test_unknown_placeholder_is_left_untouched(self):
        # Only the whitelist is interpolated — no arbitrary attribute access.
        out = render_macro("secret={password}", self._U(username="x"))
        assert out == "secret={password}"

    def test_none_customer_yields_blanks(self):
        assert render_macro("[{first_name}]", None) == "[]"


class TestParseUserAgent:
    def test_windows_chrome(self):
        ua = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit Chrome/120 Safari/537"
        assert parse_user_agent(ua) == "Windows Chrome"

    def test_mac_safari(self):
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) Safari/605"
        assert parse_user_agent(ua) == "macOS Safari"

    def test_iphone(self):
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) CriOS/120"
        assert parse_user_agent(ua) == "iOS Chrome"

    def test_edge_wins_over_chrome_token(self):
        ua = "Windows Chrome/120 Edg/120"
        assert parse_user_agent(ua) == "Windows Edge"

    def test_empty_returns_empty(self):
        assert parse_user_agent("") == ""


@pytest.mark.django_db
def test_log_admin_action_writes_row(make_user):
    admin = make_user("owner", is_superuser=True)
    target = make_user("cust")
    ticket = SupportTicket.objects.create(user=target)
    row = log_admin_action(
        admin, AdminAuditLog.ACTION_CLOSE_TICKET, target_user=target,
        ticket=ticket, note="hello",
    )
    row.refresh_from_db()
    assert row.admin_user == admin
    assert row.target_user == target
    assert row.ticket == ticket
    assert row.action_type == AdminAuditLog.ACTION_CLOSE_TICKET
    assert row.meta == {"note": "hello"}
