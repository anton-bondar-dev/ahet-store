from typing import List

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from .models import ChatMessage, SupportTicket
from .schemas import (
    AdminTicketDetailOut,
    AdminTicketOut,
    ChatMessageIn,
    UserChatMessageOut,
    UserChatOut,
)

router = Router(tags=["support"])


def _require_staff(request):
    user = request.auth
    if not (user.is_staff or user.is_superuser):
        raise HttpError(403, "Доступ лише для персоналу")
    return user


def _user_open_ticket(user, create=False):
    ticket = (
        SupportTicket.objects.filter(user=user, status=SupportTicket.STATUS_OPEN)
        .order_by("-updated_at")
        .first()
    )
    if ticket is None and create:
        ticket = SupportTicket.objects.create(user=user)
    return ticket


# --- User side (masked) -------------------------------------------------------
@router.get("/messages", response=UserChatOut, auth=JWTAuth(), operation_id="get_my_chat")
def get_my_chat(request):
    ticket = _user_open_ticket(request.auth, create=True)
    # Seeing the thread marks staff messages as read by the user.
    ticket.messages.filter(from_staff=True, read_by_user=False).update(read_by_user=True)
    return {
        "ticket_id": ticket.id,
        "status": ticket.status,
        "messages": list(ticket.messages.select_related("sender").all()),
    }


@router.post("/messages", response=UserChatMessageOut, auth=JWTAuth(), operation_id="send_my_message")
def send_my_message(request, payload: ChatMessageIn):
    if not payload.text.strip():
        raise HttpError(400, "Повідомлення порожнє")
    ticket = _user_open_ticket(request.auth, create=True)
    msg = ChatMessage.objects.create(
        ticket=ticket, sender=request.auth, from_staff=False, text=payload.text
    )
    ticket.save(update_fields=["updated_at"])  # bump activity
    return msg


# --- Admin side (real identities, staff only) --------------------------------
@router.get(
    "/admin/tickets", response=List[AdminTicketOut], auth=JWTAuth(), operation_id="list_tickets"
)
def list_tickets(request):
    _require_staff(request)
    tickets = SupportTicket.objects.select_related("user").annotate(
        unread_count=Count(
            "messages", filter=Q(messages__from_staff=False, messages__read_by_staff=False)
        )
    ).order_by("-updated_at")
    return list(tickets)


@router.get(
    "/admin/tickets/{ticket_id}",
    response=AdminTicketDetailOut,
    auth=JWTAuth(),
    operation_id="get_ticket",
)
def get_ticket(request, ticket_id: int):
    _require_staff(request)
    ticket = get_object_or_404(
        SupportTicket.objects.select_related("user"), id=ticket_id
    )
    # Viewing marks the user's messages as read by staff.
    ticket.messages.filter(from_staff=False, read_by_staff=False).update(read_by_staff=True)
    return ticket


@router.post(
    "/admin/tickets/{ticket_id}/reply",
    response=AdminTicketDetailOut,
    auth=JWTAuth(),
    operation_id="reply_ticket",
)
def reply_ticket(request, ticket_id: int, payload: ChatMessageIn):
    staff = _require_staff(request)
    if not payload.text.strip():
        raise HttpError(400, "Повідомлення порожнє")
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    ChatMessage.objects.create(
        ticket=ticket, sender=staff, from_staff=True, text=payload.text
    )
    ticket.save(update_fields=["updated_at"])
    return ticket
