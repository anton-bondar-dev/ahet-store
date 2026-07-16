import uuid

from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    METHOD_NONE = "none"
    METHOD_TELEGRAM = "telegram"
    METHOD_EMAIL = "email"

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
