"""Customer-facing helpdesk API: opening a ticket, messaging, unread badge,
closing, rating — and the security-critical guarantee that internal staff notes
never reach the customer thread."""
import pytest
from django.utils import timezone

from apps.support.models import (
    ChatMessage,
    SupportRating,
    SupportTicket,
    WELCOME_MESSAGE,
)

from ._helpers import SUPPORT_BASE, jpost, open_ticket, send_message, staff_reply


@pytest.mark.django_db
class TestGetMyChat:
    def test_empty_when_no_ticket(self, api, bearer, make_user):
        customer = make_user("cust")
        resp = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer))
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticket_id"] == 0
        assert body["status"] == "none"
        assert body["messages"] == []
        assert body["can_rate"] is False
        assert body["unread_count"] == 0

    def test_get_requires_auth(self, api):
        assert api.get(f"{SUPPORT_BASE}/messages").status_code == 401

    def test_reading_chat_has_no_side_effects(self, api, bearer, make_user):
        # Polling the widget must not create a ticket.
        customer = make_user("cust")
        api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer))
        assert SupportTicket.objects.filter(user=customer).count() == 0


@pytest.mark.django_db
class TestSendMessage:
    def test_first_message_creates_ticket_and_welcome(self, api, bearer, make_user):
        customer = make_user("cust")
        resp = send_message(api, bearer, customer, "Мій пароль не працює")
        assert resp.status_code == 200, resp.content

        tickets = SupportTicket.objects.filter(user=customer)
        assert tickets.count() == 1
        ticket = tickets.first()
        assert ticket.status == SupportTicket.STATUS_OPEN

        msgs = list(ticket.messages.order_by("id"))
        assert len(msgs) == 2  # the customer message + the auto welcome reply
        assert msgs[0].text == "Мій пароль не працює"
        assert msgs[0].from_staff is False
        assert msgs[1].text == WELCOME_MESSAGE
        assert msgs[1].from_staff is True

        # SLA clock started; the automated welcome does NOT answer it.
        ticket.refresh_from_db()
        assert ticket.last_user_message_at is not None
        assert ticket.last_staff_message_at is None

    def test_second_message_reuses_open_ticket_no_new_welcome(self, api, bearer, make_user):
        customer = make_user("cust")
        send_message(api, bearer, customer, "перше")
        send_message(api, bearer, customer, "друге")
        assert SupportTicket.objects.filter(user=customer).count() == 1
        ticket = SupportTicket.objects.get(user=customer)
        welcomes = ticket.messages.filter(text=WELCOME_MESSAGE)
        assert welcomes.count() == 1  # welcome only fires on ticket creation

    def test_send_requires_auth(self, api, make_user):
        assert send_message(api, None, make_user("c"), headers={}).status_code == 401

    def test_staff_cannot_open_customer_ticket(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        resp = send_message(api, bearer, operator, "hi")
        assert resp.status_code == 403
        assert SupportTicket.objects.filter(user=operator).count() == 0

    def test_blocked_customer_cannot_send(self, api, bearer, make_user):
        from apps.accounts.models import Profile

        customer = make_user("blocked")
        profile, _ = Profile.objects.get_or_create(user=customer)
        profile.blocked_permanent = True
        profile.save(update_fields=["blocked_permanent"])
        resp = send_message(api, bearer, customer, "let me in")
        assert resp.status_code == 403
        assert SupportTicket.objects.filter(user=customer).count() == 0

    def test_empty_message_rejected(self, api, bearer, make_user):
        customer = make_user("cust")
        resp = send_message(api, bearer, customer, "   ")
        assert resp.status_code == 400
        assert SupportTicket.objects.filter(user=customer).count() == 0


@pytest.mark.django_db
class TestUnreadAndRead:
    def test_staff_reply_increments_unread(self, api, bearer, make_user):
        customer = make_user("cust")
        operator = make_user("op", is_staff=True)
        ticket = open_ticket(api, bearer, customer)

        before = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer)).json()
        assert before["unread_count"] == 1  # the welcome auto-reply is unread for the user
        staff_reply(api, bearer, operator, ticket, "Дивлюсь")
        after = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer)).json()
        assert after["unread_count"] == 2  # welcome + the new operator reply

    def test_mark_read_clears_unread(self, api, bearer, make_user):
        customer = make_user("cust")
        operator = make_user("op", is_staff=True)
        ticket = open_ticket(api, bearer, customer)
        staff_reply(api, bearer, operator, ticket, "Дивлюсь")

        resp = jpost(api, f"{SUPPORT_BASE}/messages/read", bearer(customer))
        assert resp.status_code == 200
        body = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer)).json()
        assert body["unread_count"] == 0

    def test_mark_read_forbidden_for_staff(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        resp = jpost(api, f"{SUPPORT_BASE}/messages/read", bearer(operator))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestInternalNotesNeverLeak:
    """The security-critical invariant: is_internal notes are workspace-only."""

    def test_internal_note_absent_from_customer_thread(self, api, bearer, make_user):
        customer = make_user("cust")
        operator = make_user("op", is_staff=True)
        ticket = open_ticket(api, bearer, customer)

        staff_reply(api, bearer, operator, ticket, "СЕКРЕТНА нотатка", is_internal=True)
        staff_reply(api, bearer, operator, ticket, "Публічна відповідь", is_internal=False)

        body = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer)).json()
        texts = [m["text"] for m in body["messages"]]
        assert "СЕКРЕТНА нотатка" not in texts
        assert "Публічна відповідь" in texts

    def test_internal_note_not_counted_as_unread(self, api, bearer, make_user):
        customer = make_user("cust")
        operator = make_user("op", is_staff=True)
        ticket = open_ticket(api, bearer, customer)

        before = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer)).json()
        staff_reply(api, bearer, operator, ticket, "internal only", is_internal=True)
        after = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer)).json()
        # The internal note is invisible to the customer, so it adds nothing to
        # the unread badge (only the pre-existing welcome remains).
        assert after["unread_count"] == before["unread_count"] == 1

    def test_marking_read_ignores_internal_notes(self, api, bearer, make_user):
        # The row exists but stays out of the customer's view entirely.
        customer = make_user("cust")
        operator = make_user("op", is_staff=True)
        ticket = open_ticket(api, bearer, customer)
        staff_reply(api, bearer, operator, ticket, "hidden", is_internal=True)

        note = ChatMessage.objects.get(ticket=ticket, is_internal=True)
        assert note.text == "hidden"
        body = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer)).json()
        assert all(m["text"] != "hidden" for m in body["messages"])


@pytest.mark.django_db
class TestCloseChat:
    def test_customer_closes_and_credits_last_staff(self, api, bearer, make_user):
        customer = make_user("cust")
        operator = make_user("op", is_staff=True)
        ticket = open_ticket(api, bearer, customer)
        staff_reply(api, bearer, operator, ticket, "Готово")

        resp = jpost(api, f"{SUPPORT_BASE}/close", bearer(customer))
        assert resp.status_code == 200
        ticket.refresh_from_db()
        assert ticket.status == SupportTicket.STATUS_CLOSED
        assert ticket.closed_by == operator
        assert ticket.closed_at is not None
        # A neutral system notice records that the customer ended it.
        assert ticket.messages.filter(is_system=True, from_staff=False).exists()

    def test_close_without_open_ticket_400(self, api, bearer, make_user):
        customer = make_user("cust")
        resp = jpost(api, f"{SUPPORT_BASE}/close", bearer(customer))
        assert resp.status_code == 400

    def test_close_forbidden_for_staff(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        resp = jpost(api, f"{SUPPORT_BASE}/close", bearer(operator))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestRating:
    def _close_ticket(self, ticket, staff):
        ticket.status = SupportTicket.STATUS_CLOSED
        ticket.closed_by = staff
        ticket.closed_at = timezone.now()
        ticket.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])

    def test_rate_closed_ticket_credits_closer(self, api, bearer, make_user):
        customer = make_user("cust")
        operator = make_user("op", is_staff=True)
        ticket = open_ticket(api, bearer, customer)
        self._close_ticket(ticket, operator)

        resp = jpost(api, f"{SUPPORT_BASE}/rating", bearer(customer), {"is_positive": True})
        assert resp.status_code == 200
        rating = SupportRating.objects.get(ticket=ticket)
        assert rating.is_positive is True
        assert rating.staff == operator

    def test_can_rate_flag_flips_after_rating(self, api, bearer, make_user):
        customer = make_user("cust")
        operator = make_user("op", is_staff=True)
        ticket = open_ticket(api, bearer, customer)
        self._close_ticket(ticket, operator)

        before = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer)).json()
        assert before["can_rate"] is True
        jpost(api, f"{SUPPORT_BASE}/rating", bearer(customer), {"is_positive": False})
        after = api.get(f"{SUPPORT_BASE}/messages", headers=bearer(customer)).json()
        assert after["can_rate"] is False

    def test_rating_without_closed_ticket_400(self, api, bearer, make_user):
        customer = make_user("cust")
        open_ticket(api, bearer, customer)  # ticket is still open
        resp = jpost(api, f"{SUPPORT_BASE}/rating", bearer(customer), {"is_positive": True})
        assert resp.status_code == 400

    def test_rating_forbidden_for_staff(self, api, bearer, make_user):
        operator = make_user("op", is_staff=True)
        resp = jpost(api, f"{SUPPORT_BASE}/rating", bearer(operator), {"is_positive": True})
        assert resp.status_code == 403

    def test_cannot_rate_same_ticket_twice(self, api, bearer, make_user):
        customer = make_user("cust")
        operator = make_user("op", is_staff=True)
        ticket = open_ticket(api, bearer, customer)
        self._close_ticket(ticket, operator)
        first = jpost(api, f"{SUPPORT_BASE}/rating", bearer(customer), {"is_positive": True})
        assert first.status_code == 200
        # No other closed, unrated ticket → the second attempt is rejected.
        second = jpost(api, f"{SUPPORT_BASE}/rating", bearer(customer), {"is_positive": True})
        assert second.status_code == 400
        assert SupportRating.objects.filter(ticket=ticket).count() == 1
