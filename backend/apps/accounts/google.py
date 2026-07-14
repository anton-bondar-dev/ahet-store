import logging

from django.conf import settings
from django.contrib.auth.models import User

from .models import Profile

logger = logging.getLogger("accounts.google")


def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token and return its claims. Raises ValueError if the
    token is invalid, the audience/issuer is wrong, or verification is not
    configured. Imported lazily so the app loads without google-auth present."""
    if not settings.GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID is not configured (backend/.env)")

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    # verify_oauth2_token checks signature, expiry, issuer and audience.
    try:
        claims = id_token.verify_oauth2_token(
            credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError as e:
        # google-auth raises ValueError for bad audience / signature / expiry.
        logger.error("verify_oauth2_token rejected the token: %s", e)
        raise
    except Exception as e:
        # e.g. network / SSL (CERTIFICATE_VERIFY_FAILED) while fetching Google certs.
        logger.error("Could not reach Google to verify token: %s: %s", type(e).__name__, e)
        raise

    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        logger.error("Wrong issuer: %s", claims.get("iss"))
        raise ValueError("Wrong issuer")

    logger.info(
        "Google token OK: sub=%s email=%s aud_ok=True", claims.get("sub"), claims.get("email")
    )
    return claims


def get_or_create_google_user(claims: dict) -> User:
    """Resolve a User from verified Google claims: match by google_sub, then by
    verified email (linking it), else create a new account."""
    sub = claims.get("sub")
    email = claims.get("email") or ""
    email_verified = claims.get("email_verified", False)
    if not sub:
        raise ValueError("Missing subject claim")

    # 1) Already linked by Google subject.
    profile = Profile.objects.filter(google_sub=sub).select_related("user").first()
    if profile:
        return profile.user

    # 2) Existing account with the same verified email → link it.
    if email and email_verified:
        user = User.objects.filter(email__iexact=email).first()
        if user:
            prof, _ = Profile.objects.get_or_create(user=user)
            prof.google_sub = sub
            prof.save(update_fields=["google_sub"])
            return user

    # 3) New account. Username derived from email, made unique; unusable password
    # (this account signs in via Google, not a local password).
    base = (email.split("@")[0] if email else f"google_{sub}")[:150] or f"google_{sub}"
    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        i += 1
        username = f"{base}{i}"[:150]

    user = User.objects.create_user(username=username, email=email)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    Profile.objects.create(user=user, google_sub=sub)
    return user
