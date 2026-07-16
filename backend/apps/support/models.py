from django.contrib.auth.models import User
from django.db import models

# The single unified identity users see for every staff reply.
SUPPORT_DISPLAY_NAME = "ahetStore"

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

    class Meta:
        verbose_name = "Support ticket"
        verbose_name_plural = "Support tickets"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Ticket #{self.pk} ({self.user.username}, {self.status})"


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

    class Meta:
        verbose_name = "Chat message"
        verbose_name_plural = "Chat messages"
        ordering = ["created_at"]  # oldest first (conversation order)

    def __str__(self):
        who = "staff" if self.from_staff else "user"
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
