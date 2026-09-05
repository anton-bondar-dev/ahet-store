"""Password change (authenticated) and the forgot-password reset flow.

Both paths validate the new password, rotate the security stamp (so all other
sessions die), and hand back a fresh token pair.
"""
import pytest
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

CHANGE = "/api/auth/password/change"
RESET_REQUEST = "/api/auth/password/reset/request"
RESET_CONFIRM = "/api/auth/password/reset/confirm"
LOGIN = "/api/auth/login"
ME = "/api/auth/me"

STRONG = "Gx9-qwzP2m!"
WEAK = "1234"


def _reset_link(user):
    return {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    }


# --------------------------------------------------------------------------- #
# change password (authenticated)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_change_password_requires_auth(post_json):
    resp = post_json(CHANGE, {"current_password": "pw", "new_password": STRONG})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_change_password_wrong_current_is_400(post_json, bearer, make_user):
    user = make_user("cp", password="pw", email="cp@example.com")
    resp = post_json(CHANGE, {"current_password": "WRONG", "new_password": STRONG}, headers=bearer(user))
    assert resp.status_code == 400


@pytest.mark.django_db
def test_change_password_weak_new_is_400(post_json, bearer, make_user):
    user = make_user("cpw", password="pw", email="cpw@example.com")
    resp = post_json(CHANGE, {"current_password": "pw", "new_password": WEAK}, headers=bearer(user))
    assert resp.status_code == 400


@pytest.mark.django_db
def test_change_password_success_rotates_sessions(api, post_json, bearer, make_user):
    user = make_user("cpok", password="pw", email="cpok@example.com")
    old = bearer(user)
    assert api.get(ME, headers=old).status_code == 200

    resp = post_json(CHANGE, {"current_password": "pw", "new_password": STRONG}, headers=old)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access"] and body["refresh"]

    # Every previously issued token is now dead (stamp rotated)...
    assert api.get(ME, headers=old).status_code == 401
    # ...the returned one works...
    fresh = {"Authorization": f"Bearer {body['access']}", "X-Session-Id": "s"}
    assert api.get(ME, headers=fresh).status_code == 200
    # ...and the new password is the one that logs in.
    assert post_json(LOGIN, {"email": "cpok@example.com", "password": STRONG}).status_code == 200
    assert post_json(LOGIN, {"email": "cpok@example.com", "password": "pw"}).status_code == 401


# --------------------------------------------------------------------------- #
# reset request (enumeration protection)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_reset_request_existing_email_ok(post_json, make_user):
    make_user("rr", email="rr@example.com")
    resp = post_json(RESET_REQUEST, {"email": "rr@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.django_db
def test_reset_request_unknown_email_still_ok(post_json):
    # Never reveal which addresses are registered.
    resp = post_json(RESET_REQUEST, {"email": "nobody@nowhere.org"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# --------------------------------------------------------------------------- #
# reset confirm
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_reset_confirm_success(api, post_json, make_user):
    user = make_user("rc", password="old-pw", email="rc@example.com")
    link = _reset_link(user)
    resp = post_json(RESET_CONFIRM, {**link, "new_password": STRONG})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access"] and body["refresh"]
    # The new password logs in; the old one does not.
    assert post_json(LOGIN, {"email": "rc@example.com", "password": STRONG}).status_code == 200
    assert post_json(LOGIN, {"email": "rc@example.com", "password": "old-pw"}).status_code == 401


@pytest.mark.django_db
def test_reset_confirm_bad_uid_is_400(post_json, make_user):
    user = make_user("rcu", email="rcu@example.com")
    resp = post_json(
        RESET_CONFIRM,
        {"uid": "!!!not-base64!!!", "token": default_token_generator.make_token(user), "new_password": STRONG},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_reset_confirm_bad_token_is_400(post_json, make_user):
    user = make_user("rct", email="rct@example.com")
    resp = post_json(
        RESET_CONFIRM,
        {"uid": urlsafe_base64_encode(force_bytes(user.pk)), "token": "bogus-token", "new_password": STRONG},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_reset_confirm_token_is_single_use(post_json, make_user):
    user = make_user("rcs", email="rcs@example.com")
    link = _reset_link(user)
    assert post_json(RESET_CONFIRM, {**link, "new_password": STRONG}).status_code == 200
    # Reusing the same link fails — setting the password invalidated the token.
    again = post_json(RESET_CONFIRM, {**link, "new_password": "An0ther-Pass!"})
    assert again.status_code == 400


@pytest.mark.django_db
def test_reset_confirm_weak_password_is_400(post_json, make_user):
    user = make_user("rcw", email="rcw@example.com")
    link = _reset_link(user)
    resp = post_json(RESET_CONFIRM, {**link, "new_password": WEAK})
    assert resp.status_code == 400
