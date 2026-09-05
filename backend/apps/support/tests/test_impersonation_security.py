"""Regression tests for the impersonation privilege-escalation fix.

An impersonation token ("view the store as this customer") must be READ-ONLY
and must stop working once the session ends. Before the fix it was a full
customer token — an operator could change the victim's e-mail, disable their
2FA, or rate their own ticket. These tests lock that shut.
"""
import json

import pytest


def _impersonation_headers(api, bearer, operator, target):
    resp = api.post(
        f"/api/support/admin/impersonate/{target.id}",
        content_type="application/json", headers=bearer(operator),
    )
    assert resp.status_code == 200, resp.content
    token = resp.json()["access"]
    return {"Authorization": f"Bearer {token}", "X-Session-Id": "imp-session"}


@pytest.mark.django_db
def test_read_is_allowed_under_impersonation(api, bearer, make_user):
    operator = make_user("op", is_staff=True)
    victim = make_user("victim")
    h = _impersonation_headers(api, bearer, operator, victim)
    assert api.get("/api/auth/me", headers=h).status_code == 200


@pytest.mark.django_db
def test_profile_write_is_blocked_under_impersonation(api, bearer, make_user):
    operator = make_user("op", is_staff=True)
    victim = make_user("victim", email="victim@example.com")
    h = _impersonation_headers(api, bearer, operator, victim)

    resp = api.put(
        "/api/accounts/profile",
        data=json.dumps({"first_name": "x", "email": "attacker@evil.com"}),
        content_type="application/json", headers=h,
    )
    assert resp.status_code == 401
    victim.refresh_from_db()
    assert victim.email == "victim@example.com"  # the takeover is prevented


@pytest.mark.django_db
def test_cart_write_is_blocked_under_impersonation(api, bearer, make_user, product_factory):
    operator = make_user("op", is_staff=True)
    victim = make_user("victim")
    product = product_factory(stock=5)
    h = _impersonation_headers(api, bearer, operator, victim)

    resp = api.post(
        "/api/cart/add",
        data=json.dumps({"product_id": product.id, "quantity": 1}),
        content_type="application/json", headers=h,
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_impersonation_token_dies_after_session_end(api, bearer, make_user):
    operator = make_user("op", is_staff=True)
    victim = make_user("victim")
    h = _impersonation_headers(api, bearer, operator, victim)
    assert api.get("/api/auth/me", headers=h).status_code == 200

    ended = api.post("/api/support/admin/impersonate/end",
                     content_type="application/json", headers=bearer(operator))
    assert ended.status_code == 200
    assert api.get("/api/auth/me", headers=h).status_code == 401  # revoked


@pytest.mark.django_db
def test_staff_cannot_be_impersonated(api, bearer, make_user):
    operator = make_user("op", is_staff=True)
    other_staff = make_user("op2", is_staff=True)
    resp = api.post(f"/api/support/admin/impersonate/{other_staff.id}",
                    content_type="application/json", headers=bearer(operator))
    assert resp.status_code == 400
