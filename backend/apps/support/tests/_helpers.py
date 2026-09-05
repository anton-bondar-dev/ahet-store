"""Shared helpers for the support test-suite (not collected as tests).

Everything here drives the *public* HTTP surface through the Django test
client, exactly like a real client would, so the tests exercise auth, schemas
and view logic end-to-end.
"""
import json

from apps.support.models import ChatMessage, SupportTicket

SUPPORT_BASE = "/api/support"


def jpost(api, path, headers, data=None):
    """POST JSON. `data` may be None for payload-less endpoints."""
    return api.post(
        path,
        data=json.dumps(data or {}),
        content_type="application/json",
        headers=headers,
    )


def jput(api, path, headers, data):
    return api.put(
        path, data=json.dumps(data), content_type="application/json", headers=headers
    )


def jdelete(api, path, headers):
    return api.delete(path, headers=headers)


def send_message(api, bearer, customer, text="Доброго дня", headers=None):
    """Customer posts a chat message (opens the ticket on the first call)."""
    h = headers if headers is not None else bearer(customer)
    return jpost(api, f"{SUPPORT_BASE}/messages", h, {"text": text})


def open_ticket(api, bearer, customer, text="Доброго дня"):
    """Open a ticket for `customer` and return the SupportTicket row."""
    resp = send_message(api, bearer, customer, text)
    assert resp.status_code == 200, resp.content
    return SupportTicket.objects.filter(user=customer).order_by("-created_at").first()


def staff_reply(api, bearer, staff, ticket, text="Вітаю!", is_internal=False):
    return jpost(
        api,
        f"{SUPPORT_BASE}/admin/tickets/{ticket.id}/reply",
        bearer(staff),
        {"text": text, "is_internal": is_internal},
    )


def grant_message(ticket):
    """The most recent grant/cancel system message on a ticket (for cancel tests)."""
    return (
        ChatMessage.objects.filter(ticket=ticket, is_system=True)
        .order_by("-id")
        .first()
    )
