"""Profile read/update, email-change rules, and the my-reviews endpoint."""
import pytest

from apps.accounts.models import Profile

PROFILE = "/api/accounts/profile"
REVIEWS = "/api/accounts/reviews"


def _full_payload(**over):
    base = {
        "first_name": "Ivan",
        "last_name": "Petrov",
        "email": "",
        "phone_number": "+380000000000",
        "city": "Kyiv",
        "delivery_address": "Main St 1",
    }
    base.update(over)
    return base


# --------------------------------------------------------------------------- #
# read
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_get_profile_requires_auth(api):
    assert api.get(PROFILE).status_code == 401


@pytest.mark.django_db
def test_get_profile_returns_fields(api, bearer, make_user):
    user = make_user("pr", email="pr@example.com")
    Profile.objects.create(user=user, first_name="Ann", city="Lviv", bonus_balance=15)
    body = api.get(PROFILE, headers=bearer(user)).json()
    assert body["username"] == user.username
    assert body["first_name"] == "Ann"
    assert body["city"] == "Lviv"
    assert body["email"] == "pr@example.com"
    assert body["bonus_balance"] == 15


# --------------------------------------------------------------------------- #
# update
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_update_profile_requires_auth(put_json):
    assert put_json(PROFILE, _full_payload()).status_code == 401


@pytest.mark.django_db
def test_update_profile_persists_and_syncs_user_name(api, put_json, bearer, make_user):
    user = make_user("up", email="up@example.com")
    resp = put_json(PROFILE, _full_payload(), headers=bearer(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["first_name"] == "Ivan"
    assert body["city"] == "Kyiv"

    prof = Profile.objects.get(user=user)
    assert prof.phone_number == "+380000000000"
    assert prof.delivery_address == "Main St 1"
    # The auth User's display name is kept in sync.
    user.refresh_from_db()
    assert user.first_name == "Ivan"
    assert user.last_name == "Petrov"


@pytest.mark.django_db
def test_update_profile_changes_email(api, put_json, bearer, make_user):
    user = make_user("ue", email="ue@example.com")
    resp = put_json(PROFILE, _full_payload(email="New.Address@Example.com"), headers=bearer(user))
    assert resp.status_code == 200
    assert resp.json()["email"] == "new.address@example.com"
    user.refresh_from_db()
    assert user.email == "new.address@example.com"


@pytest.mark.django_db
def test_update_profile_same_email_is_noop(api, put_json, bearer, make_user):
    user = make_user("us", email="us@example.com")
    resp = put_json(PROFILE, _full_payload(email="US@Example.com"), headers=bearer(user))
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.email == "us@example.com"


@pytest.mark.django_db
def test_update_profile_duplicate_email_is_400(api, put_json, bearer, make_user):
    make_user("owner_of_email", email="taken@example.com")
    user = make_user("ud", email="ud@example.com")
    resp = put_json(PROFILE, _full_payload(email="taken@example.com"), headers=bearer(user))
    assert resp.status_code == 400
    user.refresh_from_db()
    assert user.email == "ud@example.com"  # unchanged


# --------------------------------------------------------------------------- #
# staff email is locked
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_staff_cannot_change_email(api, put_json, bearer, make_user):
    staff = make_user("op", is_staff=True, email="op@example.com")
    resp = put_json(PROFILE, _full_payload(email="new-op@example.com"), headers=bearer(staff))
    assert resp.status_code == 403
    staff.refresh_from_db()
    assert staff.email == "op@example.com"


@pytest.mark.django_db
def test_staff_can_update_other_fields(api, put_json, bearer, make_user):
    # Same email (case-insensitive) → the email guard is skipped, other fields save.
    staff = make_user("op2", is_staff=True, email="op2@example.com")
    resp = put_json(
        PROFILE, _full_payload(email="op2@example.com", first_name="Helpdesk"), headers=bearer(staff)
    )
    assert resp.status_code == 200
    assert Profile.objects.get(user=staff).first_name == "Helpdesk"


# --------------------------------------------------------------------------- #
# my reviews
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_reviews_requires_auth(api):
    assert api.get(REVIEWS).status_code == 401


@pytest.mark.django_db
def test_reviews_empty_for_new_user(api, bearer, make_user):
    user = make_user("rv", email="rv@example.com")
    resp = api.get(REVIEWS, headers=bearer(user))
    assert resp.status_code == 200
    assert resp.json() == []
