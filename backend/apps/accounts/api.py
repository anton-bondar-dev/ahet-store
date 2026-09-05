import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from ninja import Router
from ninja.errors import HttpError
from apps.accounts.jwt_auth import StampedJWTAuth as JWTAuth
from ninja_jwt.tokens import RefreshToken

from apps.cart.services import get_session_id, merge_anonymous_cart

from .email import (
    send_email_otp,
    send_login_alert_async,
    send_password_reset_async,
)
from .google import get_or_create_google_user, verify_google_token
from .models import LoginChallenge, Profile, TelegramLinkToken
from .schemas import (
    AccessOut,
    AuthResult,
    ChangePasswordIn,
    GoogleAuthIn,
    LinkStatusOut,
    LoginIn,
    OkOut,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    RefreshIn,
    RegisterIn,
    Set2faMethodIn,
    TelegramLinkOut,
    TokenPair,
    UserOut,
    VerifyOtpIn,
)
from .telegram import send_login_prompt

MAX_OTP_ATTEMPTS = 5

logger = logging.getLogger("accounts.google")

router = Router(tags=["auth"])

CHALLENGE_TTL = timedelta(minutes=2)
LINK_TTL = timedelta(minutes=30)


def _issue_tokens(user: User):
    # Embed the user's security stamp so tokens can be mass-invalidated by
    # rotating it ("log out everywhere").
    profile, _ = Profile.objects.get_or_create(user=user)
    stamp = str(profile.security_stamp)
    refresh = RefreshToken.for_user(user)
    refresh["stamp"] = stamp
    access = refresh.access_token
    access["stamp"] = stamp
    return str(access), str(refresh)


def _authed(request, user: User, session_id, notify: bool = True):
    # Fold any anonymous cart into the user's cart at the moment tokens are issued.
    merge_anonymous_cart(user, session_id)
    access, refresh = _issue_tokens(user)
    # Security "new login" alert — sent in the background so it never delays the
    # response. Covers password login, Google, and post-2FA (Telegram / email OTP);
    # skipped on register (that's a new account, not a new login).
    if notify:
        send_login_alert_async(user.email, user.username)
    return {"status": "authed", "access": access, "refresh": refresh, "user": user}


def _set_new_password(user: User, new_password: str) -> dict:
    """Validate + set a new password, rotate the security stamp (invalidates every
    other session), and issue fresh tokens so the caller stays / becomes logged in."""
    try:
        validate_password(new_password, user)
    except DjangoValidationError as exc:
        raise HttpError(400, " ".join(exc.messages))
    user.set_password(new_password)
    user.save(update_fields=["password"])
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.security_stamp = uuid.uuid4()
    profile.save(update_fields=["security_stamp"])
    access, refresh = _issue_tokens(user)
    return {"access": access, "refresh": refresh}


@router.post("/register", response=AuthResult, operation_id="register")
def register(request, payload: RegisterIn):
    email = payload.email.strip().lower()
    name = payload.name.strip()
    if not email:
        raise HttpError(400, "Вкажіть email")
    if User.objects.filter(email__iexact=email).exists():
        raise HttpError(400, "Обліковий запис із таким email вже існує")
    # The username is required by Django but hidden from users — generate a
    # random, collision-free value they never see.
    username = f"u-{uuid.uuid4().hex[:20]}"
    user = User.objects.create_user(
        username=username, email=email, password=payload.password, first_name=name
    )
    Profile.objects.create(user=user, first_name=name)
    return _authed(request, user, get_session_id(request), notify=False)


@router.post("/login", response=AuthResult, operation_id="login")
def login(request, payload: LoginIn):
    user = authenticate(request, username=payload.email.strip(), password=payload.password)
    if user is None:
        raise HttpError(401, "Невірний email або пароль")

    profile = getattr(user, "profile", None)
    method = profile.preferred_2fa_method if profile else Profile.METHOD_NONE
    sid = get_session_id(request)

    if method == Profile.METHOD_TELEGRAM and profile.telegram_chat_id:
        # Intermediate state: no tokens until the Telegram tap approves.
        code = secrets.randbelow(90) + 10  # two-digit 10..99
        challenge = LoginChallenge.objects.create(
            user=user,
            method=LoginChallenge.METHOD_TELEGRAM,
            match_code=code,
            session_id=sid,
            expires_at=timezone.now() + CHALLENGE_TTL,
        )
        send_login_prompt(profile.telegram_chat_id, code, str(challenge.challenge_id))
        return {
            "status": "pending",
            "method": "telegram",
            "challenge_id": str(challenge.challenge_id),
            "match_code": code,
        }

    if method == Profile.METHOD_EMAIL and user.email:
        # Intermediate state: no tokens until the emailed 6-digit code is entered.
        code = f"{secrets.randbelow(10 ** 6):06d}"
        challenge = LoginChallenge.objects.create(
            user=user,
            method=LoginChallenge.METHOD_EMAIL,
            code=code,
            session_id=sid,
            expires_at=timezone.now() + CHALLENGE_TTL,
        )
        send_email_otp(user, code)  # code is emailed, never returned in the response
        return {
            "status": "pending",
            "method": "email",
            "challenge_id": str(challenge.challenge_id),
        }

    return _authed(request, user, sid)


@router.post("/google", response=AuthResult, operation_id="google_auth")
def google_auth(request, payload: GoogleAuthIn):
    # Google Sign-In → verify ID token → link/create user → reuse the shared
    # _authed path (JWT issuance + anonymous-cart merge). Google accounts are
    # password-less; they satisfy the first factor directly.
    try:
        claims = verify_google_token(payload.credential)
    except Exception as e:
        # Surface the exact rejection reason (audience/signature/SSL/expiry).
        logger.error("Google auth failed: %s: %s", type(e).__name__, e)
        raise HttpError(401, "Недійсний токен Google")
    user = get_or_create_google_user(claims)
    return _authed(request, user, get_session_id(request))


@router.get(
    "/login/challenge/{challenge_id}",
    response=AuthResult,
    operation_id="get_login_challenge",
)
def get_login_challenge(request, challenge_id: str):
    challenge = get_object_or_404(LoginChallenge, challenge_id=challenge_id)

    if challenge.status == LoginChallenge.STATUS_PENDING and challenge.expires_at < timezone.now():
        challenge.status = LoginChallenge.STATUS_EXPIRED
        challenge.save(update_fields=["status"])

    if challenge.status == LoginChallenge.STATUS_PENDING:
        return {"status": "pending"}

    if challenge.status == LoginChallenge.STATUS_APPROVED:
        user = challenge.user
        sid = challenge.session_id or get_session_id(request)
        result = _authed(request, user, sid)
        challenge.delete()  # single-use
        return result

    raise HttpError(403, "Запит відхилено або протерміновано")


@router.post(
    "/login/challenge/{challenge_id}/dev-approve",
    response=AuthResult,
    operation_id="dev_approve_challenge",
)
def dev_approve_challenge(request, challenge_id: str):
    # DEBUG-only shim so the 2FA flow is E2E-testable without a Telegram bot.
    if not settings.DEBUG:
        raise HttpError(404, "Not found")
    challenge = get_object_or_404(LoginChallenge, challenge_id=challenge_id)
    if challenge.status == LoginChallenge.STATUS_PENDING:
        challenge.status = LoginChallenge.STATUS_APPROVED
        challenge.save(update_fields=["status"])
    return {"status": challenge.status}


@router.post(
    "/login/challenge/{challenge_id}/verify",
    response=AuthResult,
    operation_id="verify_login_challenge",
)
def verify_login_challenge(request, challenge_id: str, payload: VerifyOtpIn):
    challenge = get_object_or_404(
        LoginChallenge, challenge_id=challenge_id, method=LoginChallenge.METHOD_EMAIL
    )

    if challenge.status != LoginChallenge.STATUS_PENDING:
        raise HttpError(403, "Код більше недійсний. Спробуйте увійти ще раз.")
    if challenge.expires_at < timezone.now():
        challenge.status = LoginChallenge.STATUS_EXPIRED
        challenge.save(update_fields=["status"])
        raise HttpError(403, "Код протерміновано. Спробуйте увійти ще раз.")
    if challenge.attempts >= MAX_OTP_ATTEMPTS:
        challenge.status = LoginChallenge.STATUS_EXPIRED
        challenge.save(update_fields=["status"])
        raise HttpError(403, "Забагато спроб. Спробуйте увійти ще раз.")

    if payload.code.strip() != challenge.code:
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        raise HttpError(400, "Невірний код")

    user = challenge.user
    sid = challenge.session_id or get_session_id(request)
    result = _authed(request, user, sid)
    challenge.delete()  # single-use
    return result


@router.post("/2fa/method", response=UserOut, auth=JWTAuth(), operation_id="set_2fa_method")
def set_2fa_method(request, payload: Set2faMethodIn):
    user = request.auth
    profile, _ = Profile.objects.get_or_create(user=user)
    method = payload.method

    if method == Profile.METHOD_TELEGRAM:
        if not profile.telegram_chat_id:
            raise HttpError(400, "Спочатку підключіть Telegram")
    elif method == Profile.METHOD_EMAIL:
        if not user.email:
            raise HttpError(400, "До акаунта не прив'язано email")
    elif method != Profile.METHOD_NONE:
        raise HttpError(400, "Невідомий метод")

    profile.preferred_2fa_method = method
    profile.is_2fa_enabled = method != Profile.METHOD_NONE
    profile.save(update_fields=["preferred_2fa_method", "is_2fa_enabled"])
    return user


@router.post("/refresh", response=AccessOut, operation_id="refresh_token")
def refresh_token(request, payload: RefreshIn):
    try:
        refresh = RefreshToken(payload.refresh)
    except Exception:
        raise HttpError(401, "Недійсний токен оновлення")
    profile = Profile.objects.filter(user_id=refresh.get("user_id")).first()
    if profile is None:
        raise HttpError(401, "Сесію завершено")
    # A refresh token must carry the current stamp. Unstamped tokens predate the
    # feature and would otherwise survive "log out everywhere" indefinitely,
    # laundering themselves into fresh access tokens on every refresh.
    stamp = refresh.get("stamp")
    if stamp is None or stamp != str(profile.security_stamp):
        raise HttpError(401, "Сесію завершено")
    access = refresh.access_token
    access["stamp"] = str(profile.security_stamp)
    return {"access": str(access)}


@router.post(
    "/logout-others", response=TokenPair, auth=JWTAuth(), operation_id="logout_other_sessions"
)
def logout_other_sessions(request):
    # Rotate the security stamp → every previously issued token (on all devices)
    # stops validating. Return fresh tokens so THIS session stays logged in.
    user = request.auth
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.security_stamp = uuid.uuid4()
    profile.save(update_fields=["security_stamp"])
    access, refresh = _issue_tokens(user)
    return {"access": access, "refresh": refresh}


@router.post(
    "/password/change", response=TokenPair, auth=JWTAuth(), operation_id="change_password"
)
def change_password(request, payload: ChangePasswordIn):
    # Logged-in user changing their own password — must prove the current one.
    user = request.auth
    if not user.check_password(payload.current_password):
        raise HttpError(400, "Невірний поточний пароль")
    return _set_new_password(user, payload.new_password)


@router.post(
    "/password/reset/request", response=OkOut, operation_id="request_password_reset"
)
def request_password_reset(request, payload: PasswordResetRequestIn):
    # "Forgot password": email a one-time reset link to any registered account,
    # including Google-login accounts (completing the reset lets them SET a
    # password and use email login too). Always returns ok so we never reveal
    # which emails are registered.
    email = payload.email.strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = (
            f"{str(settings.FRONTEND_URL).rstrip('/')}"
            f"/reset-password?uid={uid}&token={token}"
        )
        send_password_reset_async(
            user.email, user.first_name or user.username, reset_url
        )
    return {"ok": True}


@router.post(
    "/password/reset/confirm", response=TokenPair, operation_id="confirm_password_reset"
)
def confirm_password_reset(request, payload: PasswordResetConfirmIn):
    # Verify the emailed link and set the new password. Setting it changes the
    # password hash, which invalidates this (single-use) token. Returns fresh
    # tokens so the user is logged straight in.
    try:
        uid = force_str(urlsafe_base64_decode(payload.uid))
        user = User.objects.get(pk=uid)
    except (ValueError, TypeError, OverflowError, User.DoesNotExist):
        raise HttpError(400, "Недійсне посилання для відновлення пароля")
    if not default_token_generator.check_token(user, payload.token):
        raise HttpError(400, "Посилання недійсне або протерміноване")
    # Anonymous → authed transition: fold any guest cart in, like the normal
    # login paths (_authed) do.
    merge_anonymous_cart(user, get_session_id(request))
    return _set_new_password(user, payload.new_password)


@router.get("/me", response=UserOut, auth=JWTAuth(), operation_id="me")
def me(request):
    return request.auth


@router.post(
    "/telegram/link/start",
    response=TelegramLinkOut,
    auth=JWTAuth(),
    operation_id="telegram_link_start",
)
def telegram_link_start(request):
    token = TelegramLinkToken.objects.create(
        user=request.auth, expires_at=timezone.now() + LINK_TTL
    )
    bot = settings.TELEGRAM_BOT_USERNAME
    return {"url": f"https://t.me/{bot}?start={token.token}", "token": str(token.token)}


@router.get(
    "/telegram/link/status",
    response=LinkStatusOut,
    auth=JWTAuth(),
    operation_id="telegram_link_status",
)
def telegram_link_status(request):
    profile = getattr(request.auth, "profile", None)
    return {"linked": bool(profile and profile.telegram_chat_id)}
