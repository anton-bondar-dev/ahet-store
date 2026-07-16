from typing import List

from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.core.permissions import forbid_staff
from apps.orders.models import Order
from apps.reviews.models import Review

from .models import WELCOME_MESSAGE, ChatMessage, SupportRating, SupportTicket
from .schemas import (
    AdminTicketDetailOut,
    AdminTicketOut,
    ChatMessageIn,
    CustomerOrderOut,
    OkOut,
    RatingIn,
    StaffMetricsOut,
    TaggedCommentOut,
    UserChatMessageOut,
    UserChatOut,
)

router = Router(tags=["support"])


def _require_staff(request):
    user = request.auth
    if not (user.is_staff or user.is_superuser):
        raise HttpError(403, "Доступ лише для персоналу")
    return user


def _user_open_ticket(user):
    return (
        SupportTicket.objects.filter(user=user, status=SupportTicket.STATUS_OPEN)
        .order_by("-updated_at")
        .first()
    )


def _user_latest_ticket(user):
    # The most recent ticket of any status — so the user can still see (and rate)
    # a just-closed conversation until they start a new one.
    return SupportTicket.objects.filter(user=user).order_by("-updated_at").first()


def _support_admin():
    """The unified help-desk account; welcome auto-replies are attributed to it
    so the admin side shows a real author (users only ever see 'ahetStore')."""
    return User.objects.filter(username="support").first()


# --- User side (masked) -------------------------------------------------------
@router.get("/messages", response=UserChatOut, auth=JWTAuth(), operation_id="get_my_chat")
def get_my_chat(request):
    ticket = _user_latest_ticket(request.auth)
    if ticket is None:
        # No conversation yet. Returning an empty thread (instead of creating a
        # ticket here) keeps this endpoint side-effect free, so the widget can
        # poll it for notifications without spawning empty tickets — the ticket
        # is created only when the user actually sends their first message.
        return {"ticket_id": 0, "status": "none", "messages": [], "can_rate": False}
    # Seeing the thread marks staff messages as read by the user.
    ticket.messages.filter(from_staff=True, read_by_user=False).update(read_by_user=True)
    can_rate = (
        ticket.status == SupportTicket.STATUS_CLOSED
        and not SupportRating.objects.filter(ticket_id=ticket.id).exists()
    )
    return {
        "ticket_id": ticket.id,
        "status": ticket.status,
        "messages": list(ticket.messages.select_related("sender").all()),
        "can_rate": can_rate,
    }


@router.post("/rating", response=OkOut, auth=JWTAuth(), operation_id="rate_support")
def rate_support(request, payload: RatingIn):
    forbid_staff(request.auth)  # only customers rate the support they received
    # Rate the user's most recent closed, not-yet-rated ticket. The score is
    # credited to whoever closed it and is never shown back to the user.
    ticket = (
        SupportTicket.objects.filter(
            user=request.auth, status=SupportTicket.STATUS_CLOSED, rating__isnull=True
        )
        .order_by("-closed_at", "-updated_at")
        .first()
    )
    if ticket is None:
        raise HttpError(400, "Немає закритих звернень для оцінки")
    SupportRating.objects.create(
        ticket=ticket, staff=ticket.closed_by, is_positive=payload.is_positive
    )
    return {"ok": True}


@router.post("/messages", response=UserChatMessageOut, auth=JWTAuth(), operation_id="send_my_message")
def send_my_message(request, payload: ChatMessageIn):
    forbid_staff(request.auth)  # staff use the admin console, not customer chat
    text = payload.text.strip()
    if not text:
        raise HttpError(400, "Повідомлення порожнє")

    ticket = _user_open_ticket(request.auth)
    is_new_ticket = ticket is None
    if is_new_ticket:
        ticket = SupportTicket.objects.create(user=request.auth)

    msg = ChatMessage.objects.create(
        ticket=ticket, sender=request.auth, from_staff=False, text=text
    )

    if is_new_ticket:
        # Auto-reply right after the user's first message: an immediate,
        # help-desk-branded acknowledgement while a human gets involved.
        ChatMessage.objects.create(
            ticket=ticket,
            sender=_support_admin(),
            from_staff=True,
            text=WELCOME_MESSAGE,
            read_by_staff=True,  # automated — never counts as an unread staff task
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


@router.post(
    "/admin/tickets/{ticket_id}/close",
    response=AdminTicketDetailOut,
    auth=JWTAuth(),
    operation_id="close_ticket",
)
def close_ticket(request, ticket_id: int):
    staff = _require_staff(request)
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if ticket.status != SupportTicket.STATUS_CLOSED:
        ticket.status = SupportTicket.STATUS_CLOSED
        ticket.closed_by = staff  # credited with the resolution + the user's rating
        ticket.closed_at = timezone.now()
        ticket.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
    return ticket


@router.get(
    "/admin/tickets/{ticket_id}/orders",
    response=List[CustomerOrderOut],
    auth=JWTAuth(),
    operation_id="ticket_customer_orders",
)
def ticket_customer_orders(request, ticket_id: int):
    # Customer context for the admin: the ticket author's recent orders, so the
    # agent doesn't have to ask "what's your order number?".
    _require_staff(request)
    ticket = get_object_or_404(SupportTicket.objects.select_related("user"), id=ticket_id)
    return list(
        Order.objects.filter(user=ticket.user)
        .prefetch_related("items")
        .order_by("-created_at")[:5]
    )


@router.get(
    "/admin/metrics", response=StaffMetricsOut, auth=JWTAuth(), operation_id="my_support_metrics"
)
def my_support_metrics(request):
    # The caller's own (secret) performance metrics, derived from rating rows.
    staff = _require_staff(request)
    ratings = SupportRating.objects.filter(staff=staff)
    total = ratings.count()
    positive = ratings.filter(is_positive=True).count()
    return {
        "resolved_tickets": SupportTicket.objects.filter(
            closed_by=staff, status=SupportTicket.STATUS_CLOSED
        ).count(),
        "comments_resolved": Review.objects.filter(support_resolved_by=staff).count(),
        "ratings_total": total,
        "ratings_positive": positive,
        "positive_rate": round(positive / total * 100) if total else None,
    }


# --- Support workspace: tagged product comments ------------------------------
@router.get(
    "/admin/comments",
    response=List[TaggedCommentOut],
    auth=JWTAuth(),
    operation_id="list_tagged_comments",
)
def list_tagged_comments(request):
    _require_staff(request)
    return list(
        Review.objects.filter(
            needs_support=True, support_status=Review.SUPPORT_PENDING
        )
        .select_related("user", "product")
        .prefetch_related("replies__user")
        .order_by("-created_at")
    )


@router.post(
    "/admin/comments/{review_id}/resolve",
    response=TaggedCommentOut,
    auth=JWTAuth(),
    operation_id="resolve_tagged_comment",
)
def resolve_tagged_comment(request, review_id: int):
    staff = _require_staff(request)
    review = get_object_or_404(
        Review.objects.select_related("user", "product"), id=review_id
    )
    review.support_status = Review.SUPPORT_RESOLVED
    review.support_resolved_by = staff
    review.support_resolved_at = timezone.now()
    review.save(
        update_fields=["support_status", "support_resolved_by", "support_resolved_at"]
    )
    return review
