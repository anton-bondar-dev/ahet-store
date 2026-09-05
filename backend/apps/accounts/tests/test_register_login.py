"""Register / login / me — the core credential flows (no second factor)."""
import pytest

from apps.accounts.models import Profile

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
ME = "/api/auth/me"
GOOGLE = "/api/auth/google"


# --------------------------------------------------------------------------- #
# register
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_register_happy_path(post_json):
    resp = post_json(
        REGISTER, {"name": "Ivan", "email": "New@Example.Org", "password": "s3cret-pw"}
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "authed"
    assert body["access"] and body["refresh"]
    # Email is normalised to lower-case; display name lands on first_name.
    assert body["user"]["email"] == "new@example.org"
    assert body["user"]["first_name"] == "Ivan"


@pytest.mark.django_db
def test_register_creates_usable_login(post_json):
    post_json(REGISTER, {"name": "Ann", "email": "ann@shop.org", "password": "pw-123456"})
    resp = post_json(LOGIN, {"email": "ann@shop.org", "password": "pw-123456"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "authed"


@pytest.mark.django_db
def test_register_rejects_duplicate_email_case_insensitive(post_json):
    post_json(REGISTER, {"name": "A", "email": "dup@shop.org", "password": "pw-123456"})
    resp = post_json(REGISTER, {"name": "B", "email": "DUP@shop.org", "password": "pw-123456"})
    assert resp.status_code == 400


@pytest.mark.django_db
def test_register_rejects_blank_email(post_json):
    resp = post_json(REGISTER, {"name": "A", "email": "   ", "password": "pw-123456"})
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# login
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_login_happy_path(make_user, post_json):
    make_user("buyer", password="pw", email="buyer@example.com")
    resp = post_json(LOGIN, {"email": "buyer@example.com", "password": "pw"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "authed"
    assert body["access"] and body["refresh"]


@pytest.mark.django_db
def test_login_email_is_case_insensitive(make_user, post_json):
    make_user("cu", password="pw", email="case@example.com")
    resp = post_json(LOGIN, {"email": "CASE@EXAMPLE.COM", "password": "pw"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "authed"


@pytest.mark.django_db
def test_login_wrong_password_is_401(make_user, post_json):
    make_user("wp", password="pw", email="wp@example.com")
    resp = post_json(LOGIN, {"email": "wp@example.com", "password": "nope"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_unknown_email_is_401(post_json):
    resp = post_json(LOGIN, {"email": "ghost@example.com", "password": "pw"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_ignores_2fa_when_no_channel_configured(make_user, post_json):
    # preferred method telegram but no chat linked → must NOT hang on a challenge.
    user = make_user("halfconf", password="pw", email="hc@example.com")
    Profile.objects.create(
        user=user, preferred_2fa_method=Profile.METHOD_TELEGRAM, telegram_chat_id=None
    )
    resp = post_json(LOGIN, {"email": "hc@example.com", "password": "pw"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "authed"


# --------------------------------------------------------------------------- #
# /me
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_me_requires_auth(api):
    assert api.get(ME).status_code == 401


@pytest.mark.django_db
def test_me_returns_current_user(api, bearer, make_user):
    user = make_user("meuser", email="me@example.com")
    resp = api.get(ME, headers=bearer(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == user.id
    assert body["email"] == "me@example.com"
    assert body["is_staff"] is False
    assert body["is_superuser"] is False


@pytest.mark.django_db
def test_me_reports_staff_flag(api, bearer, make_user):
    staff = make_user("op", is_staff=True)
    body = api.get(ME, headers=bearer(staff)).json()
    assert body["is_staff"] is True


@pytest.mark.django_db
def test_me_owner_reports_superuser(api, bearer, make_user):
    owner = make_user("owner", is_superuser=True)
    body = api.get(ME, headers=bearer(owner)).json()
    assert body["is_staff"] is True  # superuser counts as staff for the UI
    assert body["is_superuser"] is True


# --------------------------------------------------------------------------- #
# google endpoint error path (no GOOGLE_CLIENT_ID configured in tests)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_google_auth_rejects_bad_credential(post_json):
    resp = post_json(GOOGLE, {"credential": "not-a-real-token"})
    assert resp.status_code == 401
