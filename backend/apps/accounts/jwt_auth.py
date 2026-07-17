from datetime import timedelta

from django.utils import timezone
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import AccessToken

# Only rewrite presence when the last sighting is older than this (avoids a DB
# write on every single request).
_LAST_SEEN_THROTTLE = timedelta(seconds=60)


class StampedJWTAuth(JWTAuth):
    """JWTAuth that additionally:
      * validates the per-user security stamp — so "log out everywhere" (which
        rotates the stamp) instantly invalidates every previously issued token;
      * refreshes the user's last-seen presence (throttled).
    """

    def authenticate(self, request, token):
        user = super().authenticate(request, token)
        if user is None:
            return None

        profile = getattr(user, "profile", None)
        if profile is not None:
            try:
                stamp = AccessToken(token).get("stamp")
            except Exception:
                return None
            # Tokens issued before the security-stamp feature carry no stamp —
            # allow them (backward compat; they get re-stamped on next refresh).
            # A token that DOES carry a stamp must match, so "log out everywhere"
            # still invalidates it.
            if stamp is not None and stamp != str(profile.security_stamp):
                return None
            _touch_presence(request, profile)
        return user


def _touch_presence(request, profile):
    now = timezone.now()
    if profile.last_seen_at is None or now - profile.last_seen_at > _LAST_SEEN_THROTTLE:
        profile.last_seen_at = now
        profile.last_user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:400]
        profile.save(update_fields=["last_seen_at", "last_user_agent"])
