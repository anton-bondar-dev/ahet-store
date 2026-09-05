"""Recently-viewed endpoints (mounted at /api/products).

  GET  /api/products/viewed  — the current user's recently-viewed products
  POST /api/products/viewed  — record that the user viewed a product

Both require authentication. The store keeps at most MAX_VIEWED (12) rows,
one per (user, product), newest first.
"""
import json

import pytest

from apps.catalog.models import RecentlyViewed
from apps.catalog.viewed_api import MAX_VIEWED

URL = "/api/products/viewed"


def _post(api, product_id, headers):
    return api.post(
        URL, data=json.dumps({"product_id": product_id}),
        content_type="application/json", headers=headers,
    )


@pytest.mark.django_db
class TestViewedAuth:
    def test_get_requires_auth(self, api):
        assert api.get(URL).status_code == 401

    def test_post_requires_auth(self, api, product_factory):
        assert _post(api, product_factory().id, headers=None).status_code == 401


@pytest.mark.django_db
class TestViewedTracking:
    def test_post_records_view(self, api, bearer, make_user, product_factory):
        user = make_user("u")
        product = product_factory()
        resp = _post(api, product.id, bearer(user))
        assert resp.status_code == 200
        assert RecentlyViewed.objects.filter(user=user, product=product).count() == 1

    def test_get_returns_tracked_product(self, api, bearer, make_user, product_factory):
        user = make_user("u")
        product = product_factory()
        _post(api, product.id, bearer(user))
        body = api.get(URL, headers=bearer(user)).json()
        assert [p["id"] for p in body] == [product.id]

    def test_post_unknown_product_404(self, api, bearer, make_user):
        assert _post(api, 999999, bearer(make_user("u"))).status_code == 404

    def test_post_is_idempotent_upsert(self, api, bearer, make_user, product_factory):
        user = make_user("u")
        product = product_factory()
        _post(api, product.id, bearer(user))
        _post(api, product.id, bearer(user))
        # One row per (user, product) — re-viewing bumps, never duplicates.
        assert RecentlyViewed.objects.filter(user=user, product=product).count() == 1

    def test_get_orders_by_most_recent_first(self, api, bearer, make_user, product_factory):
        from django.utils import timezone
        from datetime import timedelta

        user = make_user("u")
        p_old = product_factory()
        p_new = product_factory()
        _post(api, p_old.id, bearer(user))
        _post(api, p_new.id, bearer(user))
        # Pin timestamps so the ordering assertion is deterministic.
        now = timezone.now()
        RecentlyViewed.objects.filter(user=user, product=p_old).update(
            viewed_at=now - timedelta(hours=1)
        )
        RecentlyViewed.objects.filter(user=user, product=p_new).update(viewed_at=now)

        body = api.get(URL, headers=bearer(user)).json()
        assert [p["id"] for p in body] == [p_new.id, p_old.id]

    def test_get_caps_at_max_viewed(self, api, bearer, make_user, product_factory):
        user = make_user("u")
        for _ in range(MAX_VIEWED + 3):
            _post(api, product_factory().id, bearer(user))
        body = api.get(URL, headers=bearer(user)).json()
        assert len(body) == MAX_VIEWED

    def test_viewed_is_per_user_isolated(self, api, bearer, make_user, product_factory):
        alice = make_user("alice")
        bob = make_user("bob")
        p_alice = product_factory()
        p_bob = product_factory()
        _post(api, p_alice.id, bearer(alice))
        _post(api, p_bob.id, bearer(bob))

        alice_ids = [p["id"] for p in api.get(URL, headers=bearer(alice)).json()]
        assert alice_ids == [p_alice.id]  # Bob's view is not leaked to Alice.
