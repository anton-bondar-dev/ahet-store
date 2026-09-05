"""Tests for the two read endpoints:

  * GET /api/wishlist       -> full ProductOut objects for the heart page
  * GET /api/wishlist/ids   -> lightweight product-id list for card heart state

Both are scoped to the caller, ordered newest-first, and driven by the same
underlying queryset.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.wishlist.models import Favorite


def _add(user, product):
    return Favorite.objects.create(user=user, product=product)


def _stamp(fav, when):
    Favorite.objects.filter(pk=fav.pk).update(created_at=when)


# --------------------------------------------------------------------------- #
# /api/wishlist/ids
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_ids_empty_for_new_user(api, bearer, make_user):
    resp = api.get("/api/wishlist/ids", headers=bearer(make_user("cust")))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_ids_returns_only_favorited_product_ids(api, bearer, make_user, product_factory):
    user = make_user("cust")
    p1, p2 = product_factory(), product_factory()
    other = product_factory()  # never favorited
    _add(user, p1)
    _add(user, p2)

    resp = api.get("/api/wishlist/ids", headers=bearer(user))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {p1.id, p2.id}
    assert other.id not in body


@pytest.mark.django_db
def test_ids_are_newest_first(api, bearer, make_user, product_factory):
    user = make_user("cust")
    p_old, p_mid, p_new = product_factory(), product_factory(), product_factory()
    now = timezone.now()
    _stamp(_add(user, p_old), now - timedelta(hours=2))
    _stamp(_add(user, p_mid), now - timedelta(hours=1))
    _stamp(_add(user, p_new), now)

    resp = api.get("/api/wishlist/ids", headers=bearer(user))
    assert resp.json() == [p_new.id, p_mid.id, p_old.id]


@pytest.mark.django_db
def test_ids_are_scoped_to_caller(api, bearer, make_user, product_factory):
    alice, bob = make_user("alice"), make_user("bob")
    a_prod, b_prod = product_factory(), product_factory()
    _add(alice, a_prod)
    _add(bob, b_prod)

    resp = api.get("/api/wishlist/ids", headers=bearer(alice))
    assert resp.json() == [a_prod.id]  # never sees Bob's favorite


# --------------------------------------------------------------------------- #
# /api/wishlist
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_list_empty_for_new_user(api, bearer, make_user):
    resp = api.get("/api/wishlist", headers=bearer(make_user("cust")))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_list_returns_full_product_payload(api, bearer, make_user, product_factory):
    user = make_user("cust")
    product = product_factory(price="42.00", stock=7)
    _add(user, product)

    resp = api.get("/api/wishlist", headers=bearer(user))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    item = body[0]
    # Serialized against catalog ProductOut, incl. the nested category.
    assert item["id"] == product.id
    assert item["title"] == product.title
    assert item["slug"] == product.slug
    assert item["price"] == "42.00"
    assert item["stock"] == 7
    assert item["category"]["id"] == product.category_id
    assert "ancestors" in item["category"]  # attach_ancestors ran


@pytest.mark.django_db
def test_list_is_newest_first(api, bearer, make_user, product_factory):
    user = make_user("cust")
    p_old, p_new = product_factory(), product_factory()
    now = timezone.now()
    _stamp(_add(user, p_old), now - timedelta(hours=1))
    _stamp(_add(user, p_new), now)

    resp = api.get("/api/wishlist", headers=bearer(user))
    returned_ids = [item["id"] for item in resp.json()]
    assert returned_ids == [p_new.id, p_old.id]


@pytest.mark.django_db
def test_list_is_scoped_to_caller(api, bearer, make_user, product_factory):
    alice, bob = make_user("alice"), make_user("bob")
    a_prod, b_prod = product_factory(), product_factory()
    _add(alice, a_prod)
    _add(bob, b_prod)

    resp = api.get("/api/wishlist", headers=bearer(alice))
    returned_ids = [item["id"] for item in resp.json()]
    assert returned_ids == [a_prod.id]


@pytest.mark.django_db
def test_list_and_ids_agree_after_toggles(api, bearer, make_user, product_factory):
    """End-to-end: toggling through the API is reflected by both read endpoints."""
    user = make_user("cust")
    p1, p2 = product_factory(), product_factory()

    api.post(f"/api/wishlist/{p1.id}/toggle", content_type="application/json", headers=bearer(user))
    api.post(f"/api/wishlist/{p2.id}/toggle", content_type="application/json", headers=bearer(user))

    ids = api.get("/api/wishlist/ids", headers=bearer(user)).json()
    listed = [it["id"] for it in api.get("/api/wishlist", headers=bearer(user)).json()]
    assert set(ids) == {p1.id, p2.id}
    assert set(listed) == {p1.id, p2.id}

    # Remove one and confirm both endpoints drop it.
    api.post(f"/api/wishlist/{p1.id}/toggle", content_type="application/json", headers=bearer(user))
    ids_after = api.get("/api/wishlist/ids", headers=bearer(user)).json()
    listed_after = [it["id"] for it in api.get("/api/wishlist", headers=bearer(user)).json()]
    assert ids_after == [p2.id]
    assert listed_after == [p2.id]
