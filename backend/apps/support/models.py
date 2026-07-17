from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

# The single unified identity users see for every staff reply.
SUPPORT_DISPLAY_NAME = "ahetStore"

# A ticket with an unanswered customer message older than this is "overdue" (SLA).
SLA_RESPONSE_HOURS = 24

# Actionable-chat limits. Hard ceilings apply to everyone; operators may act
# freely up to the auto-approve thresholds, but larger gifts (up to the hard
# cap) need the Team Lead's approval.
MAX_GRANT_BONUSES = 5000
MAX_COUPON_PERCENT = 100
AUTO_APPROVE_BONUSES = 500
AUTO_APPROVE_COUPON_PERCENT = 20

# Auto-reply posted the moment a user opens a new ticket (i.e. sends their first
# message), so they get an immediate acknowledgement while waiting for a human.
WELCOME_MESSAGE = (
    "Дякуємо за звернення! Будь ласка, зачекайте, спеціаліст підтримки "
    "скоро підключиться до чату."
)


class SupportTicket(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(STATUS_OPEN, "Open"), (STATUS_CLOSED, "Closed")]

    PRIORITY_LOW = "low"
    PRIORITY_NORMAL = "normal"
    PRIORITY_HIGH = "high"
    PRIORITY_URGENT = "urgent"
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_NORMAL, "Normal"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_URGENT, "Urgent"),
    ]
    # Higher weight floats to the top of the queue.
    PRIORITY_RANK = {PRIORITY_URGENT: 0, PRIORITY_HIGH: 1, PRIORITY_NORMAL: 2, PRIORITY_LOW: 3}

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="support_tickets")
    subject = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # bumped on each message → sort by activity
    # Who closed the ticket (and when) — the staff member credited with the
    # resolution and rated by the customer's end-of-chat 👍/👎.
    closed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="closed_tickets",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    # The operator handling this ticket ("Assign to me" / lead assignment).
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_tickets",
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL
    )
    # SLA tracking: stamped as messages arrive, so "overdue" is derived cheaply.
    last_user_message_at = models.DateTimeField(null=True, blank=True)
    last_staff_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Support ticket"
        verbose_name_plural = "Support tickets"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Ticket #{self.pk} ({self.user.username}, {self.status})"

    @property
    def is_overdue(self) -> bool:
        """True when the newest customer message has gone unanswered by staff for
        longer than the SLA window (open tickets only)."""
        if self.status == self.STATUS_CLOSED or not self.last_user_message_at:
            return False
        answered = (
            self.last_staff_message_at is not None
            and self.last_staff_message_at >= self.last_user_message_at
        )
        if answered:
            return False
        return timezone.now() - self.last_user_message_at > timedelta(hours=SLA_RESPONSE_HOURS)


class ChatMessage(models.Model):
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="messages"
    )
    # The REAL author — exposed only to the admin API. On the user side every
    # staff author is masked to the single "support"/ahetStore identity.
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    # Snapshot of the author's staff role at send time, so masking stays correct
    # even if their is_staff flag changes later.
    from_staff = models.BooleanField()
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_by_user = models.BooleanField(default=False)
    read_by_staff = models.BooleanField(default=False)
    # Actionable-chat events (e.g. "granted 50 bonuses"): rendered as a neutral
    # system notice, with `meta` carrying the structured action for the UI.
    is_system = models.BooleanField(default=False)
    meta = models.JSONField(default=dict, blank=True)
    # Internal staff note — visible only in the workspace, never sent to the
    # customer API.
    is_internal = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Chat message"
        verbose_name_plural = "Chat messages"
        ordering = ["created_at"]  # oldest first (conversation order)

    def __str__(self):
        who = "system" if self.is_system else ("staff" if self.from_staff else "user")
        return f"[{who}] msg on ticket {self.ticket_id}"


class SupportRating(models.Model):
    """A single 👍/👎 left by the customer when their ticket is closed. Users
    only ever submit these — the scores are secret, surfaced only to the rated
    staff member (own metrics) and to superusers via the Django admin."""

    ticket = models.OneToOneField(
        SupportTicket, on_delete=models.CASCADE, related_name="rating"
    )
    # The staff member credited (snapshot of ticket.closed_by at rating time, so
    # it stays stable). Metrics (avg rating, resolved count) are derived from
    # these rows on demand — no denormalized counters to drift.
    staff = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="support_ratings"
    )
    is_positive = models.BooleanField()  # 👍 = True, 👎 = False
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Support rating"
        verbose_name_plural = "Support ratings"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{'👍' if self.is_positive else '👎'} ticket {self.ticket_id}"


# --- Phase 1: Customer tags (karma) ------------------------------------------
class CustomerTag(models.Model):
    """The admin-managed vocabulary of tags (VIP, Проблемний, …). Assigned to
    customers via CustomerTagAssignment; visible only to staff."""

    label = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#6b7280")  # hex badge hint
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Customer tag"
        verbose_name_plural = "Customer tags"
        ordering = ["label"]

    def __str__(self):
        return self.label


class CustomerTagAssignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="support_tags")
    tag = models.ForeignKey(CustomerTag, on_delete=models.CASCADE, related_name="assignments")
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="tags_assigned"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Customer tag assignment"
        verbose_name_plural = "Customer tag assignments"
        unique_together = ("user", "tag")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tag.label} → {self.user_id}"


# --- Phase 2: Smart templates (macros) ---------------------------------------
class SupportMacro(models.Model):
    """A reusable reply template. `content` may hold whitelisted placeholders
    such as {first_name}, resolved server-side at insert time."""

    title = models.CharField(max_length=120)
    content = models.TextField()
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="support_macros"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Support macro"
        verbose_name_plural = "Support macros"
        ordering = ["title"]

    def __str__(self):
        return self.title


# --- Phase 4: Impersonation ("login as") -------------------------------------
class ImpersonationSession(models.Model):
    """Record of a staff member viewing the app as a customer. Enforcement is via
    a scoped JWT (imp_by claim) that blocks checkout/writes; this row is the audit
    anchor and lets a session be ended/revoked. Open while ended_at is null."""

    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name="impersonations")
    target_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="impersonated_by"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Impersonation session"
        verbose_name_plural = "Impersonation sessions"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.staff_id} as {self.target_user_id}"


# --- Phase 6: Collision detection (presence) ---------------------------------
class TicketPresence(models.Model):
    """Heartbeat of a staff member viewing/typing on a ticket. Short-polled;
    rows whose `updated_at` is older than the liveness window are treated as
    gone (so two admins don't answer the same ticket)."""

    VIEWING, TYPING = "viewing", "typing"
    STATE_CHOICES = [(VIEWING, "Viewing"), (TYPING, "Typing")]

    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="presence")
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ticket_presence")
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=VIEWING)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "Ticket presence"
        verbose_name_plural = "Ticket presence"
        unique_together = ("ticket", "staff")

    def __str__(self):
        return f"{self.staff_id} {self.state} ticket {self.ticket_id}"


# --- Phase 7: Audit trail ----------------------------------------------------
class AdminAuditLog(models.Model):
    """Append-only log of powerful staff actions (impersonation, tag changes,
    actionable-chat events). Superuser-visible via the Django admin."""

    ACTION_IMPERSONATE_START = "impersonate_start"
    ACTION_IMPERSONATE_END = "impersonate_end"
    ACTION_TAG_ADD = "tag_add"
    ACTION_TAG_REMOVE = "tag_remove"
    ACTION_GRANT_BONUSES = "grant_bonuses"
    ACTION_GENERATE_COUPON = "generate_coupon"
    ACTION_CLOSE_TICKET = "close_ticket"

    admin_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_actions"
    )
    action_type = models.CharField(max_length=32)
    target_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_targeted"
    )
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.SET_NULL, null=True, blank=True
    )
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Admin audit log"
        verbose_name_plural = "Admin audit log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action_type} by {self.admin_user_id} @ {self.created_at:%Y-%m-%d %H:%M}"


class ActionApproval(models.Model):
    """A large bonus/coupon gift requested by an operator that exceeds their
    auto-approve threshold — it waits in the Team Lead's mini-list until they
    approve (executes it) or reject it."""

    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    GRANT_BONUSES = "grant_bonuses"
    GENERATE_COUPON = "generate_coupon"

    requested_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="approval_requests"
    )
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="approvals")
    action_type = models.CharField(max_length=20)
    amount = models.IntegerField(default=0)
    percent = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    decided_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approvals_decided"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Action approval"
        verbose_name_plural = "Action approvals"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action_type} x{self.amount or self.percent} [{self.status}]"
