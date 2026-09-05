"""Security-stamp enforcement: the mechanism behind "log out everywhere".

Every issued JWT embeds the profile's `security_stamp`; the auth layer rejects
any token whose stamp no longer matches the DB. Rotating the stamp (log out
everywhere, password change/reset) therefore kills every previously issued
token instantly. Tokens with no stamp at all are refused outright.
"""
import pytest
from ninja_jwt.tokens import RefreshToken

from apps.accounts.models import Profile

ME = "/api/auth/me"
LOGOUT_OTHERS = "/api/auth/logout-others"
REFRESH = "/api/auth/refresh"

_UNSET = object()


def _profile(user):
    p, _ = Profile.objects.get_or_create(user=user)
    return p


def _headers(token, session_id="test-session"):
    return {"Authorization": f"Bearer {token}", "X-Session-Id": session_id}


def _access(user, stamp=_UNSET):
    """Build an access token; stamp defaults to the profile's current stamp,
    pass stamp=None to omit it, or a string to force a value."""
    p = _profile(user)
    access = RefreshToken.for_user(user).access_token
    if stamp is _UNSET:
        access["stamp"] = str(p.security_stamp)
    elif stamp is not None:
        access["stamp"] = stamp
    return str(access)


def _refresh(user, stamp=_UNSET):
    p = _profile(user)
    refresh = RefreshToken.for_user(user)
    if stamp is _UNSET:
        refresh["stamp"] = str(p.security_stamp)
    elif stamp is not None:
        refresh["stamp"] = stamp
    return str(refresh)


# --------------------------------------------------------------------------- #
# access-token stamp enforcement
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_stamped_token_is_accepted(api, make_user):
    user = make_user()
    assert api.get(ME, headers=_headers(_access(user))).status_code == 200


@pytest.mark.django_db
def test_token_without_stamp_is_rejected(api, make_user):
    user = make_user()
    assert api.get(ME, headers=_headers(_access(user, stamp=None))).status_code == 401


@pytest.mark.django_db
def test_token_with_wrong_stamp_is_rejected(api, make_user):
    user = make_user()
    bad = "00000000-0000-0000-0000-000000000000"
    assert api.get(ME, headers=_headers(_access(user, stamp=bad))).status_code == 401


@pytest.mark.django_db
def test_garbage_bearer_is_rejected(api):
    assert api.get(ME, headers=_headers("not.a.jwt")).status_code == 401


# --------------------------------------------------------------------------- #
# logout-others = rotate stamp
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_logout_others_requires_auth(api):
    assert api.post(LOGOUT_OTHERS, content_type="application/json").status_code == 401


@pytest.mark.django_db
def test_logout_others_invalidates_old_token_and_returns_working_ones(api, bearer, make_user):
    user = make_user()
    old = bearer(user)
    assert api.get(ME, headers=old).status_code == 200

    resp = api.post(LOGOUT_OTHERS, content_type="application/json", headers=old)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access"] and body["refresh"]

    # The old token is now dead everywhere...
    assert api.get(ME, headers=old).status_code == 401
    # ...but the freshly issued one works.
    fresh = _headers(body["access"])
    assert api.get(ME, headers=fresh).status_code == 200


# --------------------------------------------------------------------------- #
# refresh endpoint stamp enforcement
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_refresh_with_valid_stamp_returns_access(api, post_json, make_user):
    user = make_user()
    resp = post_json(REFRESH, {"refresh": _refresh(user)})
    assert resp.status_code == 200
    assert resp.json()["access"]


@pytest.mark.django_db
def test_refresh_without_stamp_is_rejected(api, post_json, make_user):
    user = make_user()
    resp = post_json(REFRESH, {"refresh": _refresh(user, stamp=None)})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_refresh_with_wrong_stamp_is_rejected(api, post_json, make_user):
    user = make_user()
    resp = post_json(REFRESH, {"refresh": _refresh(user, stamp="deadbeef")})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_refresh_with_garbage_token_is_rejected(post_json):
    resp = post_json(REFRESH, {"refresh": "totally-invalid"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_refresh_is_dead_after_logout_others(api, post_json, make_user):
    user = make_user()
    token = _refresh(user)          # stamped with the current value
    # sanity: it works now
    assert post_json(REFRESH, {"refresh": token}).status_code == 200
    # rotate the stamp via logout-others
    api.post(LOGOUT_OTHERS, content_type="application/json", headers=_headers(_access(user)))
    # the pre-rotation refresh can no longer launder itself into an access token
    assert post_json(REFRESH, {"refresh": token}).status_code == 401
