"""Authorization tests for the wishlist endpoints.

Who may use the wishlist:
  * anonymous visitors        -> 401 on every endpoint (JWT auth required)
  * a customer with a valid, security-stamped token -> allowed
  * a token whose stamp was rotated ("log out everywhere") -> 401
  * an impersonation token    -> may READ (safe method) but never WRITE

The app also documents (permissions.py) that staff accounts are employees who
"must not be able to shop". The wishlist toggle is a shopping action, yet — unlike
the cart's `add` endpoint — it never calls `forbid_staff`. That gap is captured
as an xfail below.
"""
import json
import uuid

import pytest

from apps.wishlist.models import Favorite

TOGGLE = "/api/wishlist/{}/toggle"
IDS = "/api/wishlist/ids"
LIST = "/api/wishlist"


# --------------------------------------------------------------------------- #
# Anonymous access
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_anonymous_cannot_toggle(api, product_factory):
    product = product_factory()
    resp = api.post(TOGGLE.format(product.id), content_type="application/json")
    assert resp.status_code == 401
    assert Favorite.objects.count() == 0


@pytest.mark.django_db
def test_anonymous_cannot_list_ids(api):
    assert api.get(IDS).status_code == 401


@pytest.mark.django_db
def test_anonymous_cannot_list_wishlist(api):
    assert api.get(LIST).status_code == 401


@pytest.mark.django_db
def test_garbage_token_is_rejected(api, product_factory):
    product = product_factory()
    headers = {"Authorization": "Bearer not-a-real-token", "X-Session-Id": "s"}
    assert api.get(IDS, headers=headers).status_code == 401
    assert api.post(
        TOGGLE.format(product.id), content_type="application/json", headers=headers
    ).status_code == 401


# --------------------------------------------------------------------------- #
# Customer access + security-stamp revocation
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_customer_with_valid_token_is_allowed(api, bearer, make_user, product_factory):
    user = make_user("cust")
    product = product_factory()
    resp = api.post(
        TOGGLE.format(product.id), content_type="application/json", headers=bearer(user)
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_rotated_security_stamp_revokes_token(api, bearer, make_user, product_factory):
    """A token issued before "log out everywhere" must stop working once the
    profile's security stamp is rotated."""
    from apps.accounts.models import Profile

    user = make_user("cust")
    product = product_factory()
    headers = bearer(user)  # stamped with the current security_stamp

    # First request works.
    assert api.get(IDS, headers=headers).status_code == 200

    # Rotate the stamp -> the old token's embedded stamp no longer matches.
    profile = Profile.objects.get(user=user)
    profile.security_stamp = uuid.uuid4()
    profile.save(update_fields=["security_stamp"])

    assert api.get(IDS, headers=headers).status_code == 401
    assert api.post(
        TOGGLE.format(product.id), content_type="application/json", headers=headers
    ).status_code == 401


# --------------------------------------------------------------------------- #
# Staff access
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_staff_may_read_wishlist(api, bearer, make_user):
    """Reading is harmless and mirrors the cart, where staff may view but not
    mutate — a staff wishlist is simply empty."""
    staff = make_user("stf", is_staff=True)
    assert api.get(IDS, headers=bearer(staff)).status_code == 200
    assert api.get(IDS, headers=bearer(staff)).json() == []
    assert api.get(LIST, headers=bearer(staff)).status_code == 200


@pytest.mark.xfail(
    reason="BUG: toggle_wishlist never calls forbid_staff, so staff (employees) "
    "can add products to a wishlist — a shopping action the app forbids for staff "
    "everywhere else (cart.add, reviews, support). Should return 403.",
    strict=False,
)
@pytest.mark.django_db
def test_staff_cannot_toggle_wishlist(api, bearer, make_user, product_factory):
    staff = make_user("stf", is_staff=True)
    product = product_factory()
    resp = api.post(
        TOGGLE.format(product.id), content_type="application/json", headers=bearer(staff)
    )
    assert resp.status_code == 403
    assert Favorite.objects.count() == 0


@pytest.mark.xfail(
    reason="BUG: superuser (is_staff via is_staff_user) is likewise not blocked "
    "from the mutating toggle. Should return 403.",
    strict=False,
)
@pytest.mark.django_db
def test_superuser_cannot_toggle_wishlist(api, bearer, make_user, product_factory):
    owner = make_user("owner", is_superuser=True)
    product = product_factory()
    resp = api.post(
        TOGGLE.format(product.id), content_type="application/json", headers=bearer(owner)
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# Impersonation: read-only "view as customer" tokens
# --------------------------------------------------------------------------- #
def _impersonation_headers(api, bearer, operator, target):
    resp = api.post(
        f"/api/support/admin/impersonate/{target.id}",
        content_type="application/json", headers=bearer(operator),
    )
    assert resp.status_code == 200, resp.content
    token = resp.json()["access"]
    return {"Authorization": f"Bearer {token}", "X-Session-Id": "imp-session"}


@pytest.mark.django_db
def test_impersonation_can_read_victims_wishlist(api, bearer, make_user, product_factory):
    operator = make_user("op", is_staff=True)
    victim = make_user("victim")
    product = product_factory()
    Favorite.objects.create(user=victim, product=product)

    h = _impersonation_headers(api, bearer, operator, victim)
    resp = api.get(IDS, headers=h)
    assert resp.status_code == 200
    assert resp.json() == [product.id]  # sees the victim's saved product


@pytest.mark.django_db
def test_impersonation_cannot_toggle_wishlist(api, bearer, make_user, product_factory):
    """A "view as customer" token is read-only: the POST toggle is a non-safe
    method and must be refused (401), leaving the victim's wishlist untouched."""
    operator = make_user("op", is_staff=True)
    victim = make_user("victim")
    product = product_factory()

    h = _impersonation_headers(api, bearer, operator, victim)
    resp = api.post(TOGGLE.format(product.id), content_type="application/json", headers=h)

    assert resp.status_code == 401
    assert not Favorite.objects.filter(user=victim).exists()
