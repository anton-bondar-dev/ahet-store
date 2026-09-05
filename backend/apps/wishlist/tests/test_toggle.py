"""Tests for POST /api/wishlist/{product_id}/toggle.

The toggle is the heart of the wishlist: it adds the product if it is missing
and removes it if present, returning the resulting state so an optimistic client
can reconcile. These tests lock down the add/remove semantics, idempotency,
per-user isolation, and the 404 for unknown products.
"""
import pytest

from apps.wishlist.models import Favorite


def _toggle(api, user_headers, product_id):
    return api.post(
        f"/api/wishlist/{product_id}/toggle",
        content_type="application/json",
        headers=user_headers,
    )


@pytest.mark.django_db
def test_toggle_adds_when_missing(api, bearer, make_user, product_factory):
    user = make_user("cust")
    product = product_factory()

    resp = _toggle(api, bearer(user), product.id)

    assert resp.status_code == 200, resp.content
    assert resp.json() == {"is_favorite": True}
    assert Favorite.objects.filter(user=user, product=product).exists()


@pytest.mark.django_db
def test_toggle_removes_when_present(api, bearer, make_user, product_factory):
    user = make_user("cust")
    product = product_factory()
    Favorite.objects.create(user=user, product=product)

    resp = _toggle(api, bearer(user), product.id)

    assert resp.status_code == 200, resp.content
    assert resp.json() == {"is_favorite": False}
    assert not Favorite.objects.filter(user=user, product=product).exists()


@pytest.mark.django_db
def test_toggle_twice_returns_to_original_state(api, bearer, make_user, product_factory):
    """Idempotency: add then remove leaves no trace, and each call reports the
    state it produced."""
    user = make_user("cust")
    product = product_factory()

    first = _toggle(api, bearer(user), product.id)
    assert first.json() == {"is_favorite": True}
    assert Favorite.objects.filter(user=user, product=product).count() == 1

    second = _toggle(api, bearer(user), product.id)
    assert second.json() == {"is_favorite": False}
    assert Favorite.objects.filter(user=user, product=product).count() == 0


@pytest.mark.django_db
def test_toggle_cycles_deterministically(api, bearer, make_user, product_factory):
    """Four toggles alternate True/False/True/False and never duplicate a row."""
    user = make_user("cust")
    product = product_factory()

    states = [_toggle(api, bearer(user), product.id).json()["is_favorite"] for _ in range(4)]
    assert states == [True, False, True, False]
    # A removed favorite must not resurrect as a duplicate on re-add.
    assert Favorite.objects.filter(user=user, product=product).count() == 0


@pytest.mark.django_db
def test_toggle_removing_keeps_the_product(api, bearer, make_user, product_factory):
    """Removing a favorite deletes only the join row, never the catalog product."""
    user = make_user("cust")
    product = product_factory()
    Favorite.objects.create(user=user, product=product)

    _toggle(api, bearer(user), product.id)

    product.refresh_from_db()  # still there
    assert product.id is not None


@pytest.mark.django_db
def test_toggle_unknown_product_returns_404(api, bearer, make_user):
    user = make_user("cust")
    resp = _toggle(api, bearer(user), 999999)
    assert resp.status_code == 404
    assert Favorite.objects.count() == 0


@pytest.mark.django_db
def test_toggle_is_isolated_per_user(api, bearer, make_user, product_factory):
    """One customer's toggle must not touch another customer's wishlist."""
    alice = make_user("alice")
    bob = make_user("bob")
    product = product_factory()

    _toggle(api, bearer(alice), product.id)

    assert Favorite.objects.filter(user=alice, product=product).exists()
    assert not Favorite.objects.filter(user=bob, product=product).exists()

    # Bob toggling the same product creates his own independent row.
    _toggle(api, bearer(bob), product.id)
    assert Favorite.objects.filter(user=bob, product=product).exists()
    # Alice's row is untouched.
    assert Favorite.objects.filter(user=alice, product=product).count() == 1


@pytest.mark.django_db
def test_toggle_off_only_affects_the_targeted_product(api, bearer, make_user, product_factory):
    user = make_user("cust")
    keep = product_factory()
    drop = product_factory()
    Favorite.objects.create(user=user, product=keep)
    Favorite.objects.create(user=user, product=drop)

    _toggle(api, bearer(user), drop.id)

    assert Favorite.objects.filter(user=user, product=keep).exists()
    assert not Favorite.objects.filter(user=user, product=drop).exists()
