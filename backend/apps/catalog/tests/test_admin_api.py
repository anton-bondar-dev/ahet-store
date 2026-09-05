"""Staff catalog endpoints (mounted at /api/staff/catalog).

  GET   /api/staff/catalog/products          — staff inventory list
  PATCH /api/staff/catalog/products/{id}      — quick stock/price edit

Authorization ladder (least privilege):
  * unauthenticated            -> 401
  * authenticated non-staff    -> 403
  * staff                      -> may edit stock
  * only superuser (team lead) -> may edit price

NOTE: every SUCCESS path serializes through with_trending_score()
(Extract-epoch / DurationField), which is Postgres-only and raises on the
sqlite test DB. Those happy paths are skipped with a reason; all the
authorization/validation guards run *before* that query and are asserted here.
"""
import json
from decimal import Decimal

import pytest

LIST = "/api/staff/catalog/products"


def _patch(api, product_id, data, headers):
    return api.patch(
        f"{LIST}/{product_id}", data=json.dumps(data),
        content_type="application/json", headers=headers,
    )


@pytest.mark.django_db
class TestStaffListAuth:
    def test_requires_auth(self, api):
        assert api.get(LIST).status_code == 401

    def test_non_staff_forbidden(self, api, bearer, make_user):
        assert api.get(LIST, headers=bearer(make_user("cust"))).status_code == 403

    @pytest.mark.skip(
        reason="Success serializes with_trending_score() (Extract-epoch/DurationField), "
        "Postgres-only; raises on the sqlite test DB."
    )
    def test_staff_list_happy_path(self, api, bearer, make_user, product_factory):
        product_factory()
        api.get(LIST, headers=bearer(make_user("st", is_staff=True)))


@pytest.mark.django_db
class TestStaffUpdateAuth:
    def test_requires_auth(self, api, product_factory):
        assert _patch(api, product_factory().id, {"stock": 5}, headers=None).status_code == 401

    def test_non_staff_forbidden(self, api, bearer, make_user, product_factory):
        p = product_factory(stock=10)
        resp = _patch(api, p.id, {"stock": 5}, bearer(make_user("cust")))
        assert resp.status_code == 403
        p.refresh_from_db()
        assert p.stock == 10  # unchanged

    def test_unknown_product_404(self, api, bearer, make_user):
        resp = _patch(api, 999999, {"stock": 5}, bearer(make_user("st", is_staff=True)))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestStaffUpdateValidation:
    def test_staff_cannot_change_price(self, api, bearer, make_user, product_factory):
        p = product_factory(price="100.00")
        staff = make_user("st", is_staff=True)  # not superuser
        resp = _patch(api, p.id, {"price": "5.00"}, bearer(staff))
        assert resp.status_code == 403  # price is team-lead only
        p.refresh_from_db()
        assert p.price == Decimal("100.00")

    def test_superuser_rejects_negative_price(self, api, bearer, make_user, product_factory):
        p = product_factory(price="100.00")
        owner = make_user("owner", is_staff=True, is_superuser=True)
        resp = _patch(api, p.id, {"price": "-1.00"}, bearer(owner))
        assert resp.status_code == 400
        p.refresh_from_db()
        assert p.price == Decimal("100.00")  # not persisted

    def test_rejects_negative_stock(self, api, bearer, make_user, product_factory):
        p = product_factory(stock=10)
        staff = make_user("st", is_staff=True)
        resp = _patch(api, p.id, {"stock": -1}, bearer(staff))
        assert resp.status_code == 400
        p.refresh_from_db()
        assert p.stock == 10  # not persisted

    @pytest.mark.skip(
        reason="A successful edit returns Product.objects.with_trending_score().get(...), "
        "Postgres-only; raises on the sqlite test DB."
    )
    def test_staff_stock_update_happy_path(self, api, bearer, make_user, product_factory):
        p = product_factory(stock=1)
        _patch(api, p.id, {"stock": 7}, bearer(make_user("st", is_staff=True)))
