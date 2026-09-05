"""Authorization matrix for the two analytics dashboards.

Two privilege tiers, enforced per endpoint:

  * /analytics/lead      — financial data, **superuser (Team Lead) only**.
  * /analytics/operator  — any active staff member (or superuser).

A plain customer must never see either dashboard, an anonymous request is
rejected before any handler runs, and an account that has been deactivated
loses access even while holding a still-unexpired token.
"""
import pytest

LEAD = "/api/analytics/lead"
OPERATOR = "/api/analytics/operator"


# --- Anonymous ---------------------------------------------------------------
@pytest.mark.django_db
@pytest.mark.parametrize("path", [LEAD, OPERATOR])
def test_anonymous_is_unauthorized(api, path):
    assert api.get(path).status_code == 401


# --- Plain customer ----------------------------------------------------------
@pytest.mark.django_db
@pytest.mark.parametrize("path", [LEAD, OPERATOR])
def test_customer_is_forbidden(api, bearer, make_user, path):
    customer = make_user("customer")
    assert api.get(path, headers=bearer(customer)).status_code == 403


# --- Lead dashboard: superuser gate -----------------------------------------
@pytest.mark.django_db
def test_lead_forbidden_for_plain_staff(api, bearer, make_user):
    # A regular operator is staff but NOT a superuser: financials stay hidden.
    operator = make_user("operator", is_staff=True)
    resp = api.get(LEAD, headers=bearer(operator))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_lead_allowed_for_superuser(api, bearer, make_user):
    lead = make_user("lead", is_staff=True, is_superuser=True)
    resp = api.get(LEAD, headers=bearer(lead))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_lead_superuser_without_staff_flag_still_allowed(api, bearer, make_user):
    # The gate keys off is_superuser alone, independent of the is_staff flag.
    lead = make_user("lead", is_staff=False, is_superuser=True)
    resp = api.get(LEAD, headers=bearer(lead))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_lead_deactivated_superuser_rejected(api, bearer, make_user):
    lead = make_user("lead", is_staff=True, is_superuser=True)
    lead.is_active = False
    lead.save()
    # An inactive account is refused at the JWT layer (401), never reaching the
    # 200 handler — "log out everywhere" / ban takes effect immediately.
    assert api.get(LEAD, headers=bearer(lead)).status_code == 401


# --- Operator dashboard: staff gate -----------------------------------------
@pytest.mark.django_db
def test_operator_deactivated_staff_rejected(api, bearer, make_user):
    operator = make_user("operator", is_staff=True)
    operator.is_active = False
    operator.save()
    assert api.get(OPERATOR, headers=bearer(operator)).status_code == 401


@pytest.mark.django_db
def test_operator_staff_passes_permission_gate(api, bearer, make_user):
    # Active staff clear _require_staff and go on to build the (Postgres-only)
    # trending query, which raises on the sqlite test DB. Reaching that query —
    # rather than getting a 403 — is proof the operator was authorized.
    operator = make_user("operator", is_staff=True)
    with pytest.raises(ValueError):
        api.get(OPERATOR, headers=bearer(operator))


@pytest.mark.django_db
def test_operator_superuser_passes_permission_gate(api, bearer, make_user):
    # A superuser is also staff-privileged for the operator dashboard.
    lead = make_user("lead", is_staff=True, is_superuser=True)
    with pytest.raises(ValueError):
        api.get(OPERATOR, headers=bearer(lead))
