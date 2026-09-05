from datetime import timedelta

from django.utils import timezone
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import AccessToken

# Only rewrite presence when the last sighting is older than this (avoids a DB
# write on every single request).
_LAST_SEEN_THROTTLE = timedelta(seconds=60)

# Impersonation exists so support staff can SEE the storefront as a customer.
# Anything that changes state is therefore off-limits under such a token.
_IMPERSONATION_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class StampedJWTAuth(JWTAuth):
    """JWTAuth that additionally:
      * validates the per-user security stamp — so "log out everywhere" (which
        rotates the stamp) instantly invalidates every previously issued token;
      * confines impersonation tokens to read-only requests and honours the
        end of an impersonation session;
      * refreshes the user's last-seen presence (throttled).
    """

    def authenticate(self, request, token):
        user = super().authenticate(request, token)
        if user is None:
            return None

        try:
            access = AccessToken(token)
        except Exception:
            return None

        profile = getattr(user, "profile", None)
        if profile is not None:
            # Every issuing path stamps its tokens, so a missing stamp means a
            # token predating the feature: reject it rather than let it dodge
            # "log out everywhere" forever.
            stamp = access.get("stamp")
            if stamp is None or stamp != str(profile.security_stamp):
                return None
            _touch_presence(request, profile)

        if access.get("imp_by") is not None:
            if not _impersonation_allowed(request, access):
                return None
            request.impersonated_by = access.get("imp_by")

        return user


def _impersonation_allowed(request, access) -> bool:
    """A token carrying `imp_by` may only read, and only while its session is
    still open. Without this an impersonation token is an ordinary full-power
    token for the target account: it could change their e-mail, turn off their
    2FA or rate their own support ticket."""
    if request.method not in _IMPERSONATION_SAFE_METHODS:
        return False
    session_id = access.get("imp_sid")
    if session_id is None:
        # Pre-`imp_sid` tokens can't be revoked individually — refuse them.
        return False
    # Imported lazily: apps.support imports this module.
    from apps.support.models import ImpersonationSession

    return ImpersonationSession.objects.filter(
        id=session_id, ended_at__isnull=True
    ).exists()


def _touch_presence(request, profile):
    now = timezone.now()
    if profile.last_seen_at is None or now - profile.last_seen_at > _LAST_SEEN_THROTTLE:
        profile.last_seen_at = now
        profile.last_user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:400]
        profile.save(update_fields=["last_seen_at", "last_user_agent"])
