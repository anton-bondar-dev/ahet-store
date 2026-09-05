"""The 2FA login challenge: Telegram tap-to-approve and e-mail OTP.

Login with a second factor configured returns a `pending` result and issues NO
tokens until the challenge is satisfied. These tests drive both branches and
lock down the abuse guards (expiry, attempt cap, single-use) and the DEBUG-only
dev-approve shim.

Note: pytest/Django force settings.DEBUG=False during tests, which is exactly
the production posture — so the dev-approve shim is off by default and is
exercised explicitly with override_settings(DEBUG=True). Telegram approval in
production comes from the bot flipping the challenge to APPROVED; the tests
simulate that by setting the status directly.
"""
import uuid
from datetime import timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.accounts.api import MAX_OTP_ATTEMPTS
from apps.accounts.models import LoginChallenge, Profile

LOGIN = "/api/auth/login"


def _challenge_url(cid, suffix=""):
    return f"/api/auth/login/challenge/{cid}{suffix}"


def _telegram_user(make_user, name):
    user = make_user(name, password="pw", email=f"{name}@example.com")
    Profile.objects.create(
        user=user,
        preferred_2fa_method=Profile.METHOD_TELEGRAM,
        telegram_chat_id="9001",
        is_2fa_enabled=True,
    )
    return user


# --------------------------------------------------------------------------- #
# Telegram branch
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_telegram_login_returns_pending_without_tokens(post_json, make_user):
    _telegram_user(make_user, "tgpend")
    resp = post_json(LOGIN, {"email": "tgpend@example.com", "password": "pw"})
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "pending"
    assert body["method"] == "telegram"
    assert body["access"] is None and body["refresh"] is None
    assert isinstance(body["match_code"], int) and 10 <= body["match_code"] <= 99

    ch = LoginChallenge.objects.get(challenge_id=body["challenge_id"])
    assert ch.method == LoginChallenge.METHOD_TELEGRAM
    assert ch.status == LoginChallenge.STATUS_PENDING


@pytest.mark.django_db
def test_approved_challenge_issues_tokens_and_is_single_use(api, make_user):
    # Simulates the bot having approved the tap: status flips to APPROVED, then
    # the polling GET exchanges it for real tokens and consumes it.
    user = make_user("tgapp", email="tgapp@example.com")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_TELEGRAM,
        match_code=42,
        status=LoginChallenge.STATUS_APPROVED,
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    resp = api.get(_challenge_url(ch.challenge_id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "authed"
    assert body["access"] and body["refresh"]
    assert body["user"]["email"] == "tgapp@example.com"

    # Consumed — polling again 404s.
    assert not LoginChallenge.objects.filter(challenge_id=ch.challenge_id).exists()
    assert api.get(_challenge_url(ch.challenge_id)).status_code == 404


@pytest.mark.django_db
def test_get_challenge_pending_hides_tokens(api, make_user):
    user = make_user("pend")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_TELEGRAM,
        match_code=42,
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    body = api.get(_challenge_url(ch.challenge_id)).json()
    assert body["status"] == "pending"
    assert body["access"] is None
    assert body["refresh"] is None
    assert body["user"] is None


@pytest.mark.django_db
def test_get_challenge_denied_is_403(api, make_user):
    user = make_user("den")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_TELEGRAM,
        status=LoginChallenge.STATUS_DENIED,
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    assert api.get(_challenge_url(ch.challenge_id)).status_code == 403


@pytest.mark.django_db
def test_get_challenge_expired_is_403_and_marks_expired(api, make_user):
    user = make_user("exp")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_TELEGRAM,
        status=LoginChallenge.STATUS_PENDING,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert api.get(_challenge_url(ch.challenge_id)).status_code == 403
    ch.refresh_from_db()
    assert ch.status == LoginChallenge.STATUS_EXPIRED


@pytest.mark.django_db
def test_get_challenge_unknown_is_404(api):
    assert api.get(_challenge_url(uuid.uuid4())).status_code == 404


# --------------------------------------------------------------------------- #
# dev-approve shim — gated on DEBUG
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_dev_approve_disabled_without_debug(api, make_user):
    # DEBUG is False under the test runner (== production), so the shim is off.
    user = make_user("nodebug")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_TELEGRAM,
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    resp = api.post(_challenge_url(ch.challenge_id, "/dev-approve"), content_type="application/json")
    assert resp.status_code == 404
    ch.refresh_from_db()
    assert ch.status == LoginChallenge.STATUS_PENDING  # not approved


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_dev_approve_enabled_in_debug(api, make_user):
    user = make_user("yesdebug")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_TELEGRAM,
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    resp = api.post(_challenge_url(ch.challenge_id, "/dev-approve"), content_type="application/json")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    ch.refresh_from_db()
    assert ch.status == LoginChallenge.STATUS_APPROVED


# --------------------------------------------------------------------------- #
# Email OTP branch
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_email_otp_login_flow(api, post_json, make_user):
    user = make_user("otp", password="pw", email="otpuser@gmail.com")
    Profile.objects.create(
        user=user, preferred_2fa_method=Profile.METHOD_EMAIL, is_2fa_enabled=True
    )

    before = len(mail.outbox)
    resp = post_json(LOGIN, {"email": "otpuser@gmail.com", "password": "pw"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["method"] == "email"
    assert body["match_code"] is None  # no number-matching on the email path
    cid = body["challenge_id"]

    # The OTP is emailed (synchronously) and never returned in the response.
    assert len(mail.outbox) == before + 1
    assert "otpuser@gmail.com" in mail.outbox[-1].to

    ch = LoginChallenge.objects.get(challenge_id=cid)
    assert ch.code and len(ch.code) == 6
    assert body.get("code") is None

    verify = post_json(_challenge_url(cid, "/verify"), {"code": ch.code})
    assert verify.status_code == 200
    b2 = verify.json()
    assert b2["status"] == "authed"
    assert b2["access"] and b2["refresh"]

    # single use
    assert not LoginChallenge.objects.filter(challenge_id=cid).exists()
    assert post_json(_challenge_url(cid, "/verify"), {"code": ch.code}).status_code == 404


@pytest.mark.django_db
def test_verify_wrong_code_increments_attempts(post_json, make_user):
    user = make_user("otpw", password="pw", email="otpw@gmail.com")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_EMAIL,
        code="654321",
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    resp = post_json(_challenge_url(ch.challenge_id, "/verify"), {"code": "000000"})
    assert resp.status_code == 400
    ch.refresh_from_db()
    assert ch.attempts == 1
    assert ch.status == LoginChallenge.STATUS_PENDING  # still usable


@pytest.mark.django_db
def test_verify_expired_code_is_403(post_json, make_user):
    user = make_user("otpe", email="otpe@gmail.com")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_EMAIL,
        code="123456",
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    resp = post_json(_challenge_url(ch.challenge_id, "/verify"), {"code": "123456"})
    assert resp.status_code == 403
    ch.refresh_from_db()
    assert ch.status == LoginChallenge.STATUS_EXPIRED


@pytest.mark.django_db
def test_verify_too_many_attempts_is_403(post_json, make_user):
    user = make_user("otpa", email="otpa@gmail.com")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_EMAIL,
        code="123456",
        attempts=MAX_OTP_ATTEMPTS,
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    # Even with the correct code, the attempt cap locks it out.
    resp = post_json(_challenge_url(ch.challenge_id, "/verify"), {"code": "123456"})
    assert resp.status_code == 403
    ch.refresh_from_db()
    assert ch.status == LoginChallenge.STATUS_EXPIRED


@pytest.mark.django_db
def test_verify_rejects_non_email_challenge(post_json, make_user):
    # The verify endpoint is email-only; a telegram challenge id must 404.
    user = make_user("otpt")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_TELEGRAM,
        match_code=55,
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    resp = post_json(_challenge_url(ch.challenge_id, "/verify"), {"code": "123456"})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_verify_already_consumed_challenge_is_403(post_json, make_user):
    user = make_user("otpc", email="otpc@gmail.com")
    ch = LoginChallenge.objects.create(
        user=user,
        method=LoginChallenge.METHOD_EMAIL,
        code="123456",
        status=LoginChallenge.STATUS_APPROVED,
        expires_at=timezone.now() + timedelta(minutes=2),
    )
    resp = post_json(_challenge_url(ch.challenge_id, "/verify"), {"code": "123456"})
    assert resp.status_code == 403
