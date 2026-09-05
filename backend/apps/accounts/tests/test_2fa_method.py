"""Choosing/enabling a second factor and the Telegram-link endpoints.

NOTE: /2fa/method returns a UserOut, but that response echoes STALE 2FA fields
(the auth layer caches ``user.profile`` before the handler mutates a separate
Profile instance, so the serialized reverse relation is the pre-change one).
The persisted state is correct, so these tests assert the DB — the source of
truth — and one xfail below documents the stale-response defect.
"""
import pytest

from apps.accounts.models import Profile, TelegramLinkToken

SET_METHOD = "/api/auth/2fa/method"
LINK_START = "/api/auth/telegram/link/start"
LINK_STATUS = "/api/auth/telegram/link/status"


def _set(post_json, headers, method):
    return post_json(SET_METHOD, {"method": method}, headers=headers)


@pytest.mark.django_db
def test_set_method_requires_auth(post_json):
    assert _set(post_json, {}, "email").status_code == 401


@pytest.mark.django_db
def test_enable_email_2fa(post_json, bearer, make_user):
    user = make_user("em", email="em@example.com")
    resp = _set(post_json, bearer(user), "email")
    assert resp.status_code == 200
    prof = Profile.objects.get(user=user)
    assert prof.preferred_2fa_method == Profile.METHOD_EMAIL
    assert prof.is_2fa_enabled is True


@pytest.mark.django_db
def test_enable_email_2fa_without_email_fails(post_json, bearer, make_user):
    user = make_user("noemail", email="")
    resp = _set(post_json, bearer(user), "email")
    assert resp.status_code == 400
    assert Profile.objects.get(user=user).is_2fa_enabled is False


@pytest.mark.django_db
def test_enable_telegram_2fa_without_link_fails(post_json, bearer, make_user):
    user = make_user("notg")
    resp = _set(post_json, bearer(user), "telegram")
    assert resp.status_code == 400
    # Nothing was persisted.
    assert Profile.objects.get(user=user).is_2fa_enabled is False


@pytest.mark.django_db
def test_enable_telegram_2fa_with_link_succeeds(post_json, bearer, make_user):
    user = make_user("tg")
    # bearer() creates the profile; attach a chat id to it.
    headers = bearer(user)
    prof = Profile.objects.get(user=user)
    prof.telegram_chat_id = "555000"
    prof.save(update_fields=["telegram_chat_id"])

    resp = _set(post_json, headers, "telegram")
    assert resp.status_code == 200
    prof.refresh_from_db()
    assert prof.preferred_2fa_method == Profile.METHOD_TELEGRAM
    assert prof.is_2fa_enabled is True


@pytest.mark.django_db
def test_disable_2fa_with_none(post_json, bearer, make_user):
    user = make_user("dis", email="dis@example.com")
    headers = bearer(user)
    _set(post_json, headers, "email")  # first turn it on
    resp = _set(post_json, headers, "none")
    assert resp.status_code == 200
    prof = Profile.objects.get(user=user)
    assert prof.preferred_2fa_method == Profile.METHOD_NONE
    assert prof.is_2fa_enabled is False


@pytest.mark.django_db
def test_unknown_method_rejected(post_json, bearer, make_user):
    user = make_user("unk", email="unk@example.com")
    resp = _set(post_json, bearer(user), "sms")
    assert resp.status_code == 400
    assert Profile.objects.get(user=user).preferred_2fa_method == Profile.METHOD_NONE


@pytest.mark.xfail(
    reason="BUG: /2fa/method returns a stale UserOut — the auth layer caches "
    "user.profile before the handler mutates a separate Profile instance, so the "
    "response echoes the pre-change 2FA fields even though the DB is updated.",
    strict=True,
)
@pytest.mark.django_db
def test_set_method_response_reflects_change(post_json, bearer, make_user):
    user = make_user("echo", email="echo@example.com")
    body = _set(post_json, bearer(user), "email").json()
    assert body["is_2fa_enabled"] is True
    assert body["preferred_2fa_method"] == "email"


# --------------------------------------------------------------------------- #
# telegram link start / status
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_link_start_requires_auth(api):
    assert api.post(LINK_START, content_type="application/json").status_code == 401


@pytest.mark.django_db
def test_link_start_creates_token_and_deep_link(api, bearer, make_user):
    user = make_user("lk")
    resp = api.post(LINK_START, content_type="application/json", headers=bearer(user))
    assert resp.status_code == 200
    body = resp.json()
    token = TelegramLinkToken.objects.get(user=user)
    assert body["token"] == str(token.token)
    assert body["url"].startswith("https://t.me/")
    assert body["token"] in body["url"]


@pytest.mark.django_db
def test_link_status_requires_auth(api):
    assert api.get(LINK_STATUS).status_code == 401


@pytest.mark.django_db
def test_link_status_reflects_binding(api, bearer, make_user):
    user = make_user("ls")
    headers = bearer(user)
    assert api.get(LINK_STATUS, headers=headers).json()["linked"] is False

    prof = Profile.objects.get(user=user)
    prof.telegram_chat_id = "424242"
    prof.save(update_fields=["telegram_chat_id"])
    assert api.get(LINK_STATUS, headers=headers).json()["linked"] is True
