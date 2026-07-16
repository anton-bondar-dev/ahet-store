import secrets
from datetime import timedelta
from typing import List

from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import AccessToken

from apps.accounts.models import Profile
from apps.core.permissions import forbid_blocked, forbid_staff, is_staff_user
from apps.coupons.models import Coupon
from apps.orders.models import Order
from apps.reviews.models import Review

from .models import (
    AUTO_APPROVE_BONUSES,
    AUTO_APPROVE_COUPON_PERCENT,
    MAX_COUPON_PERCENT,
    MAX_GRANT_BONUSES,
    WELCOME_MESSAGE,
    ActionApproval,
    AdminAuditLog,
    ChatMessage,
    CustomerTag,
    CustomerTagAssignment,
    ImpersonationSession,
    SupportMacro,
    SupportRating,
    SupportTicket,
    TicketPresence,
)
from .schemas import (
    AdminTicketDetailOut,
    AdminTicketOut,
    ActionResultOut,
    ApprovalOut,
    AssignTagIn,
    AuditLogOut,
    BlockUserIn,
    CancelBonusIn,
    ChatActionIn,
    ChatMessageIn,
    CustomerOrderOut,
    CustomerTagOut,
    ImpersonateOut,
    MacroIn,
    MacroOut,
    MacroRenderIn,
    OkOut,
    PresenceIn,
    RatingIn,
    RenderedTextOut,
    StaffDossierOut,
    StaffMetricsOut,
    TagCreateIn,
    TaggedCommentOut,
    UserChatMessageOut,
    UserChatOut,
)
from .services import PRESENCE_TTL_SECONDS, log_admin_action, render_macro

router = Router(tags=["support"])


def _require_staff(request):
    user = request.auth
    if not (user.is_staff or user.is_superuser):
        raise HttpError(403, "Доступ лише для персоналу")
    if not user.is_active:  # blocked operators lose access immediately
        raise HttpError(403, "Ваш акаунт заблоковано")
    return user


def _require_owner(request):
    # Owner-only (superuser) — e.g. the audit log. Support Admins are excluded.
    user = request.auth
    if not user.is_superuser:
        raise HttpError(403, "Доступ лише для власника")
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
    forbid_blocked(request.auth)  # blocked customers can't open tickets
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
        # help-desk-branded acknowledgement while a human gets involved. The
        # automated reply does NOT count as a staff response for SLA purposes.
        ChatMessage.objects.create(
            ticket=ticket,
            sender=_support_admin(),
            from_staff=True,
            text=WELCOME_MESSAGE,
            read_by_staff=True,  # automated — never counts as an unread staff task
        )

    # SLA clock: the newest unanswered customer message starts the timer.
    ticket.last_user_message_at = timezone.now()
    ticket.save(update_fields=["updated_at", "last_user_message_at"])
    return msg


# --- Admin side (real identities, staff only) --------------------------------
def _heartbeat_and_viewers(ticket, caller):
    """Register the caller as viewing this ticket (collision detection) and
    attach the other staff whose heartbeat is still fresh."""
    TicketPresence.objects.update_or_create(ticket=ticket, staff=caller, defaults={})
    cutoff = timezone.now() - timedelta(seconds=PRESENCE_TTL_SECONDS)
    ticket._viewers = list(
        TicketPresence.objects.filter(ticket=ticket, updated_at__gte=cutoff)
        .exclude(staff=caller)
        .select_related("staff")
    )
    return ticket


@router.get(
    "/admin/tickets", response=List[AdminTicketOut], auth=JWTAuth(), operation_id="list_tickets"
)
def list_tickets(request, archived: bool = False):
    # By default the queue shows only active (open) tickets; closed ones are
    # archived and surfaced only when explicitly requested (?archived=true).
    _require_staff(request)
    status = SupportTicket.STATUS_CLOSED if archived else SupportTicket.STATUS_OPEN
    tickets = list(
        SupportTicket.objects.filter(status=status).select_related("user").annotate(
            unread_count=Count(
                "messages", filter=Q(messages__from_staff=False, messages__read_by_staff=False)
            )
        ).order_by("-updated_at")
    )
    # Overdue tickets float to the top (stable sort keeps recency within groups).
    tickets.sort(key=lambda t: not t.is_overdue)
    return tickets


@router.get(
    "/admin/tickets/{ticket_id}",
    response=AdminTicketDetailOut,
    auth=JWTAuth(),
    operation_id="get_ticket",
)
def get_ticket(request, ticket_id: int):
    staff = _require_staff(request)
    ticket = get_object_or_404(
        SupportTicket.objects.select_related("user"), id=ticket_id
    )
    # Viewing marks the user's messages as read by staff.
    ticket.messages.filter(from_staff=False, read_by_staff=False).update(read_by_staff=True)
    return _heartbeat_and_viewers(ticket, staff)


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
    # A real staff reply answers the SLA clock.
    ticket.last_staff_message_at = timezone.now()
    ticket.save(update_fields=["updated_at", "last_staff_message_at"])
    return _heartbeat_and_viewers(ticket, staff)


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
        log_admin_action(
            staff, AdminAuditLog.ACTION_CLOSE_TICKET, target_user=ticket.user, ticket=ticket
        )
    return _heartbeat_and_viewers(ticket, staff)


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


def _staff_metrics(staff) -> dict:
    """Derive a staff member's performance snapshot from rating/ticket rows."""
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


@router.get(
    "/admin/metrics", response=StaffMetricsOut, auth=JWTAuth(), operation_id="my_support_metrics"
)
def my_support_metrics(request):
    # The caller's own (secret) performance metrics, derived from rating rows.
    staff = _require_staff(request)
    return _staff_metrics(staff)


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


# --- Phase 1: customer tags --------------------------------------------------
@router.get("/admin/tags", response=List[CustomerTagOut], auth=JWTAuth(), operation_id="list_tags")
def list_tags(request):
    _require_staff(request)
    return list(CustomerTag.objects.all())


@router.post("/admin/tags", response=CustomerTagOut, auth=JWTAuth(), operation_id="create_tag")
def create_tag(request, payload: TagCreateIn):
    _require_staff(request)
    label = payload.label.strip()
    if not label:
        raise HttpError(400, "Порожня назва тегу")
    tag, _ = CustomerTag.objects.get_or_create(
        label=label, defaults={"color": payload.color or "#6b7280"}
    )
    return tag


@router.post(
    "/admin/users/{user_id}/tags",
    response=List[CustomerTagOut],
    auth=JWTAuth(),
    operation_id="assign_tag",
)
def assign_tag(request, user_id: int, payload: AssignTagIn):
    staff = _require_staff(request)
    target = get_object_or_404(User, id=user_id)
    tag = get_object_or_404(CustomerTag, id=payload.tag_id)
    _, created = CustomerTagAssignment.objects.get_or_create(
        user=target, tag=tag, defaults={"assigned_by": staff}
    )
    if created:
        log_admin_action(
            staff, AdminAuditLog.ACTION_TAG_ADD, target_user=target, meta={"tag": tag.label}
        )
    return [a.tag for a in target.support_tags.select_related("tag").all()]


@router.delete(
    "/admin/users/{user_id}/tags/{tag_id}",
    response=List[CustomerTagOut],
    auth=JWTAuth(),
    operation_id="remove_tag",
)
def remove_tag(request, user_id: int, tag_id: int):
    staff = _require_staff(request)
    target = get_object_or_404(User, id=user_id)
    assignment = CustomerTagAssignment.objects.filter(user=target, tag_id=tag_id).first()
    if assignment:
        label = assignment.tag.label
        assignment.delete()
        log_admin_action(
            staff, AdminAuditLog.ACTION_TAG_REMOVE, target_user=target, meta={"tag": label}
        )
    return [a.tag for a in target.support_tags.select_related("tag").all()]


# --- Phase 2: macros ---------------------------------------------------------
@router.get("/admin/macros", response=List[MacroOut], auth=JWTAuth(), operation_id="list_macros")
def list_macros(request):
    _require_staff(request)
    return list(SupportMacro.objects.all())


@router.post("/admin/macros", response=MacroOut, auth=JWTAuth(), operation_id="create_macro")
def create_macro(request, payload: MacroIn):
    staff = _require_staff(request)
    if not payload.title.strip() or not payload.content.strip():
        raise HttpError(400, "Заповніть назву та текст")
    return SupportMacro.objects.create(
        title=payload.title.strip(), content=payload.content, created_by=staff
    )


@router.put(
    "/admin/macros/{macro_id}", response=MacroOut, auth=JWTAuth(), operation_id="update_macro"
)
def update_macro(request, macro_id: int, payload: MacroIn):
    _require_staff(request)
    macro = get_object_or_404(SupportMacro, id=macro_id)
    macro.title = payload.title.strip()
    macro.content = payload.content
    macro.save(update_fields=["title", "content", "updated_at"])
    return macro


@router.delete("/admin/macros/{macro_id}", response=OkOut, auth=JWTAuth(), operation_id="delete_macro")
def delete_macro(request, macro_id: int):
    _require_staff(request)
    SupportMacro.objects.filter(id=macro_id).delete()
    return {"ok": True}


@router.post(
    "/admin/macros/{macro_id}/render",
    response=RenderedTextOut,
    auth=JWTAuth(),
    operation_id="render_macro_for_ticket",
)
def render_macro_for_ticket(request, macro_id: int, payload: MacroRenderIn):
    # Resolve {placeholders} against the ticket's customer, server-side.
    _require_staff(request)
    macro = get_object_or_404(SupportMacro, id=macro_id)
    ticket = get_object_or_404(SupportTicket.objects.select_related("user"), id=payload.ticket_id)
    return {"content": render_macro(macro.content, ticket.user)}


# --- Phase 6: collision detection (presence heartbeat) -----------------------
@router.post(
    "/admin/tickets/{ticket_id}/presence",
    response=OkOut,
    auth=JWTAuth(),
    operation_id="ticket_presence",
)
def ticket_presence(request, ticket_id: int, payload: PresenceIn):
    staff = _require_staff(request)
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    state = payload.state if payload.state in (TicketPresence.VIEWING, TicketPresence.TYPING) else TicketPresence.VIEWING
    TicketPresence.objects.update_or_create(
        ticket=ticket, staff=staff, defaults={"state": state}
    )
    return {"ok": True}


# --- Phase 5: actionable chat ------------------------------------------------
def _execute_chat_action(staff, ticket, action_type, amount, percent):
    """Apply a bonus/coupon gift: mutate state, drop a system message, audit."""
    customer = ticket.user
    if action_type == ActionApproval.GRANT_BONUSES:
        profile, _ = Profile.objects.get_or_create(user=customer)
        profile.bonus_balance += amount
        profile.save(update_fields=["bonus_balance"])
        text = f"Адміністратор подарував вам {amount} бонусів."
        meta = {"action": "grant_bonuses", "amount": amount}
        log_admin_action(
            staff, AdminAuditLog.ACTION_GRANT_BONUSES, target_user=customer, ticket=ticket,
            amount=amount,
        )
    else:  # generate_coupon
        code = f"SUP{secrets.token_hex(3).upper()}"
        Coupon.objects.create(
            code=code, discount_type=Coupon.PERCENTAGE, discount_value=percent,
        )
        text = f"Адміністратор згенерував для вас промокод {code} на знижку {percent}%."
        meta = {"action": "generate_coupon", "code": code, "percent": percent}
        log_admin_action(
            staff, AdminAuditLog.ACTION_GENERATE_COUPON, target_user=customer, ticket=ticket,
            code=code, percent=percent,
        )
    ChatMessage.objects.create(
        ticket=ticket, sender=staff, from_staff=True, is_system=True, text=text, meta=meta,
    )
    ticket.last_staff_message_at = timezone.now()
    ticket.save(update_fields=["updated_at", "last_staff_message_at"])


@router.post(
    "/admin/tickets/{ticket_id}/action",
    response=ActionResultOut,
    auth=JWTAuth(),
    operation_id="ticket_action",
)
def ticket_action(request, ticket_id: int, payload: ChatActionIn):
    staff = _require_staff(request)
    ticket = get_object_or_404(SupportTicket.objects.select_related("user"), id=ticket_id)

    # Validate against the hard ceilings, then decide whether the Team Lead's
    # approval is required (operators only, above their auto-approve threshold).
    if payload.type == "grant_bonuses":
        amount = payload.amount
        if amount <= 0:
            raise HttpError(400, "Вкажіть кількість бонусів")
        if amount > MAX_GRANT_BONUSES:
            raise HttpError(400, f"Максимум {MAX_GRANT_BONUSES} бонусів на клієнта")
        needs_approval = not staff.is_superuser and amount > AUTO_APPROVE_BONUSES
        percent = 0
    elif payload.type == "generate_coupon":
        percent = payload.percent
        if percent < 1 or percent > MAX_COUPON_PERCENT:
            raise HttpError(400, f"Знижка від 1% до {MAX_COUPON_PERCENT}%")
        needs_approval = not staff.is_superuser and percent > AUTO_APPROVE_COUPON_PERCENT
        amount = 0
    else:
        raise HttpError(400, "Невідома дія")

    if needs_approval:
        ActionApproval.objects.create(
            requested_by=staff, ticket=ticket, action_type=payload.type,
            amount=amount, percent=percent,
        )
        return {"ok": True, "pending": True}

    _execute_chat_action(staff, ticket, payload.type, amount, percent)
    return {"ok": True, "pending": False}


# --- Team-lead approval mini-list (owner-only) -------------------------------
@router.get(
    "/admin/approvals", response=List[ApprovalOut], auth=JWTAuth(), operation_id="list_approvals"
)
def list_approvals(request):
    _require_owner(request)
    return list(
        ActionApproval.objects.filter(status=ActionApproval.PENDING)
        .select_related("requested_by", "ticket__user")
    )


@router.post(
    "/admin/approvals/{approval_id}/approve",
    response=OkOut,
    auth=JWTAuth(),
    operation_id="approve_action",
)
def approve_action(request, approval_id: int):
    owner = _require_owner(request)
    appr = get_object_or_404(
        ActionApproval.objects.select_related("ticket__user", "requested_by"), id=approval_id
    )
    if appr.status != ActionApproval.PENDING:
        raise HttpError(400, "Запит вже опрацьовано")
    # Execute crediting the original requester (their action, lead-approved).
    _execute_chat_action(appr.requested_by, appr.ticket, appr.action_type, appr.amount, appr.percent)
    appr.status = ActionApproval.APPROVED
    appr.decided_by = owner
    appr.decided_at = timezone.now()
    appr.save(update_fields=["status", "decided_by", "decided_at"])
    log_admin_action(owner, "approve_action", target_user=appr.ticket.user, ticket=appr.ticket)
    return {"ok": True}


@router.post(
    "/admin/approvals/{approval_id}/reject",
    response=OkOut,
    auth=JWTAuth(),
    operation_id="reject_action",
)
def reject_action(request, approval_id: int):
    owner = _require_owner(request)
    appr = get_object_or_404(ActionApproval, id=approval_id)
    if appr.status != ActionApproval.PENDING:
        raise HttpError(400, "Запит вже опрацьовано")
    appr.status = ActionApproval.REJECTED
    appr.decided_by = owner
    appr.decided_at = timezone.now()
    appr.save(update_fields=["status", "decided_by", "decided_at"])
    log_admin_action(owner, "reject_action", ticket=appr.ticket)
    return {"ok": True}


# --- Phase 4: impersonation --------------------------------------------------
@router.post(
    "/admin/impersonate/{user_id}",
    response=ImpersonateOut,
    auth=JWTAuth(),
    operation_id="impersonate_user",
)
def impersonate_user(request, user_id: int):
    staff = _require_staff(request)
    target = get_object_or_404(User, id=user_id)
    if is_staff_user(target):
        raise HttpError(400, "Не можна імперсонувати службовий акаунт")

    session = ImpersonationSession.objects.create(staff=staff, target_user=target)
    # Short-lived storefront token carrying the impersonation claim; the checkout
    # guard reads imp_by and blocks real orders.
    token = AccessToken.for_user(target)
    token.set_exp(lifetime=timedelta(minutes=30))
    token["imp_by"] = staff.id
    token["imp_sid"] = session.id
    log_admin_action(
        staff, AdminAuditLog.ACTION_IMPERSONATE_START, target_user=target,
        session_id=session.id,
    )
    return {
        "access": str(token),
        "target_username": target.username,
        "target_name": target.first_name or target.username,
    }


@router.post(
    "/admin/impersonate/end", response=OkOut, auth=JWTAuth(), operation_id="end_impersonation"
)
def end_impersonation(request):
    staff = _require_staff(request)
    sessions = ImpersonationSession.objects.filter(staff=staff, ended_at__isnull=True)
    for s in sessions:
        s.ended_at = timezone.now()
        s.save(update_fields=["ended_at"])
        log_admin_action(
            staff, AdminAuditLog.ACTION_IMPERSONATE_END, target_user=s.target_user,
            session_id=s.id,
        )
    return {"ok": True}


# --- Phase 7: audit trail (owner-only) ---------------------------------------
@router.get("/admin/audit", response=List[AuditLogOut], auth=JWTAuth(), operation_id="list_audit_log")
def list_audit_log(request):
    _require_owner(request)
    return list(
        AdminAuditLog.objects.select_related("admin_user", "target_user")[:200]
    )


# --- Cancel a bonus grant (staff can reverse their own gifts) ----------------
@router.post(
    "/admin/tickets/{ticket_id}/cancel-bonus",
    response=AdminTicketDetailOut,
    auth=JWTAuth(),
    operation_id="cancel_bonus",
)
def cancel_bonus(request, ticket_id: int, payload: CancelBonusIn):
    staff = _require_staff(request)
    ticket = get_object_or_404(SupportTicket.objects.select_related("user"), id=ticket_id)
    msg = get_object_or_404(ChatMessage, id=payload.message_id, ticket=ticket)
    meta = msg.meta or {}
    if meta.get("action") != "grant_bonuses" or meta.get("reversed"):
        raise HttpError(400, "Немає що скасовувати")

    amount = int(meta.get("amount", 0))
    profile, _ = Profile.objects.get_or_create(user=ticket.user)
    profile.bonus_balance = max(0, profile.bonus_balance - amount)
    profile.save(update_fields=["bonus_balance"])

    meta["reversed"] = True
    msg.meta = meta
    msg.save(update_fields=["meta"])
    ChatMessage.objects.create(
        ticket=ticket, sender=staff, from_staff=True, is_system=True,
        text=f"Нарахування {amount} бонусів скасовано.",
        meta={"action": "cancel_bonuses", "amount": amount},
    )
    log_admin_action(
        staff, "cancel_bonuses", target_user=ticket.user, ticket=ticket, amount=amount
    )
    ticket.save(update_fields=["updated_at"])
    return _heartbeat_and_viewers(ticket, staff)


# --- Owner: staff dossiers + moderation --------------------------------------
@router.get(
    "/admin/staff", response=List[StaffDossierOut], auth=JWTAuth(), operation_id="list_staff"
)
def list_staff(request):
    _require_owner(request)
    rows = []
    for u in User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).order_by("id"):
        m = _staff_metrics(u)
        rows.append({
            "id": u.id,
            "username": u.username,
            "name": u.first_name or u.username,
            "role": "owner" if u.is_superuser else "operator",
            "is_active": u.is_active,
            **m,
        })
    return rows


@router.post(
    "/admin/staff/{user_id}/block", response=OkOut, auth=JWTAuth(), operation_id="block_staff"
)
def block_staff(request, user_id: int):
    owner = _require_owner(request)
    target = get_object_or_404(User, id=user_id)
    if target.is_superuser or target.id == owner.id:
        raise HttpError(400, "Не можна заблокувати власника")
    target.is_active = False
    target.save(update_fields=["is_active"])
    log_admin_action(owner, "block_staff", target_user=target)
    return {"ok": True}


@router.post(
    "/admin/staff/{user_id}/unblock", response=OkOut, auth=JWTAuth(), operation_id="unblock_staff"
)
def unblock_staff(request, user_id: int):
    owner = _require_owner(request)
    target = get_object_or_404(User, id=user_id)
    target.is_active = True
    target.save(update_fields=["is_active"])
    log_admin_action(owner, "unblock_staff", target_user=target)
    return {"ok": True}


@router.post(
    "/admin/users/{user_id}/block", response=OkOut, auth=JWTAuth(), operation_id="block_user"
)
def block_user(request, user_id: int, payload: BlockUserIn):
    owner = _require_owner(request)
    target = get_object_or_404(User, id=user_id)
    if is_staff_user(target):
        raise HttpError(400, "Не можна заблокувати службовий акаунт")
    profile, _ = Profile.objects.get_or_create(user=target)
    profile.blocked_permanent = payload.permanent
    profile.blocked_until = (
        None if payload.permanent
        else timezone.now() + timedelta(days=max(1, payload.days or 7))
    )
    profile.save(update_fields=["blocked_permanent", "blocked_until"])
    log_admin_action(
        owner, "block_user", target_user=target,
        permanent=payload.permanent, days=payload.days,
    )
    return {"ok": True}


@router.post(
    "/admin/users/{user_id}/unblock", response=OkOut, auth=JWTAuth(), operation_id="unblock_user"
)
def unblock_user(request, user_id: int):
    owner = _require_owner(request)
    target = get_object_or_404(User, id=user_id)
    profile, _ = Profile.objects.get_or_create(user=target)
    profile.blocked_permanent = False
    profile.blocked_until = None
    profile.save(update_fields=["blocked_permanent", "blocked_until"])
    log_admin_action(owner, "unblock_user", target_user=target)
    return {"ok": True}
