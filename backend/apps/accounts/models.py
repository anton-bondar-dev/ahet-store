import secrets
import uuid

from django.contrib.auth.models import User
from django.db import models

# Unambiguous alphabet for the short customer support id (no 0/O/1/I).
_SUPPORT_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_support_id() -> str:
    return "USR-" + "".join(secrets.choice(_SUPPORT_ID_ALPHABET) for _ in range(4))


class Profile(models.Model):
    METHOD_NONE = "none"
    METHOD_TELEGRAM = "telegram"
    METHOD_EMAIL = "email"

    STATUS_ONLINE = "online"
    STATUS_AWAY = "away"
    OPERATOR_STATUS_CHOICES = [(STATUS_ONLINE, "Online"), (STATUS_AWAY, "Away")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    # Telegram second-factor binding. When telegram_chat_id is set, login
    # requires tap-to-approve via the bot.
    telegram_chat_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    telegram_username = models.CharField(max_length=255, blank=True, null=True)
    # Google account link (the ID token's stable `sub` claim).
    google_sub = models.CharField(max_length=255, blank=True, null=True, unique=True)
    # Chosen second factor — source of truth for the login branch.
    preferred_2fa_method = models.CharField(max_length=10, default=METHOD_NONE)
    is_2fa_enabled = models.BooleanField(default=False)

    # Personal / delivery info — used to pre-fill checkout for logged-in buyers.
    first_name = models.CharField(max_length=255, blank=True, default="")
    last_name = models.CharField(max_length=255, blank=True, default="")
    phone_number = models.CharField(max_length=32, blank=True, default="")
    city = models.CharField(max_length=255, blank=True, default="")
    delivery_address = models.CharField(max_length=255, blank=True, default="")

    # Loyalty bonuses (placeholder — no accrual logic yet).
    bonus_balance = models.IntegerField(default=0)

    # Moderation: the Owner can block a customer temporarily (blocked_until) or
    # permanently (blocked_permanent). Blocked customers are refused buyer/chat
    # actions with 403.
    blocked_until = models.DateTimeField(null=True, blank=True)
    blocked_permanent = models.BooleanField(default=False)

    # Short customer identifier for staff (e.g. USR-7B2X) — hidden from the
    # customer, shown in the Helpdesk sidebar/dossier and searchable there.
    support_id = models.CharField(
        max_length=12, unique=True, null=True, blank=True, db_index=True
    )
    # Operator availability, toggled from the workspace and shown in the dossier.
    operator_status = models.CharField(
        max_length=10, choices=OPERATOR_STATUS_CHOICES, default=STATUS_ONLINE
    )

    # Rotated by "log out everywhere"; embedded in issued JWTs and checked on
    # every request, so old tokens stop working the moment it changes.
    security_stamp = models.UUIDField(default=uuid.uuid4, editable=False)

    # Presence: refreshed (throttled) on authenticated requests.
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_user_agent = models.CharField(max_length=400, blank=True, default="")

    def save(self, *args, **kwargs):
        if not self.support_id:
            for _ in range(20):
                candidate = generate_support_id()
                if not Profile.objects.filter(support_id=candidate).exists():
                    self.support_id = candidate
                    break
        super().save(*args, **kwargs)

    @property
    def is_blocked(self) -> bool:
        from django.utils import timezone

        if self.blocked_permanent:
            return True
        return self.blocked_until is not None and self.blocked_until > timezone.now()

    def __str__(self):
        return f"Profile<{self.user.username}>"


class TelegramLinkToken(models.Model):
    # One-time deep-link token: t.me/<bot>?start=<token> binds the chat to a user.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="link_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"LinkToken<{self.user.username}>"


class LoginChallenge(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"
    STATUS_EXPIRED = "expired"

    METHOD_TELEGRAM = "telegram"
    METHOD_EMAIL = "email"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_challenges")
    challenge_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    method = models.CharField(max_length=10, default=METHOD_TELEGRAM)
    # Telegram: two-digit number-matching code (shown in browser + Telegram) to
    # defeat blind-approval / real-time phishing. Null for email challenges.
    match_code = models.PositiveSmallIntegerField(blank=True, null=True)
    # Email: the 6-digit OTP the user types back (string keeps leading zeros).
    code = models.CharField(max_length=6, blank=True, null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=16, default=STATUS_PENDING)
    # Captured so the anonymous cart can be merged when the challenge is approved.
    session_id = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Challenge<{self.user.username}:{self.method}:{self.status}>"
