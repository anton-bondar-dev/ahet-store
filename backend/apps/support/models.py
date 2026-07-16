from django.contrib.auth.models import User
from django.db import models

# The single unified identity users see for every staff reply.
SUPPORT_DISPLAY_NAME = "ahetStore"


class SupportTicket(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(STATUS_OPEN, "Open"), (STATUS_CLOSED, "Closed")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="support_tickets")
    subject = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # bumped on each message → sort by activity

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
