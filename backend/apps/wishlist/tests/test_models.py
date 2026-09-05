"""Model-level tests for the Favorite (wishlist entry) model.

Covers the __str__ representation, the (user, product) uniqueness constraint,
the newest-first default ordering, and the cascade deletes that keep the table
free of orphaned rows.
"""
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.wishlist.models import Favorite


@pytest.mark.django_db
def test_str_shows_user_and_product_ids(make_user, product_factory):
    user = make_user("cust")
    product = product_factory()
    fav = Favorite.objects.create(user=user, product=product)
    assert str(fav) == f"{user.id} ♥ {product.id}"


@pytest.mark.django_db
def test_created_at_is_populated_automatically(make_user, product_factory):
    fav = Favorite.objects.create(user=make_user("cust"), product=product_factory())
    assert fav.created_at is not None


@pytest.mark.django_db
def test_unique_together_blocks_duplicate_favorite(make_user, product_factory):
    user = make_user("cust")
    product = product_factory()
    Favorite.objects.create(user=user, product=product)

    # A second (user, product) row must violate the unique_together constraint.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Favorite.objects.create(user=user, product=product)


@pytest.mark.django_db
def test_same_product_favorited_by_two_users_is_allowed(make_user, product_factory):
    product = product_factory()
    a = Favorite.objects.create(user=make_user("a"), product=product)
    b = Favorite.objects.create(user=make_user("b"), product=product)
    assert a.pk != b.pk
    assert product.favorited_by.count() == 2


@pytest.mark.django_db
def test_default_ordering_is_newest_first(make_user, product_factory):
    user = make_user("cust")
    p1, p2, p3 = product_factory(), product_factory(), product_factory()
    older = Favorite.objects.create(user=user, product=p1)
    middle = Favorite.objects.create(user=user, product=p2)
    newer = Favorite.objects.create(user=user, product=p3)

    # auto_now_add stamps can collide in fast tests, so pin them explicitly.
    now = timezone.now()
    Favorite.objects.filter(pk=older.pk).update(created_at=now - timedelta(hours=2))
    Favorite.objects.filter(pk=middle.pk).update(created_at=now - timedelta(hours=1))
    Favorite.objects.filter(pk=newer.pk).update(created_at=now)

    ordered = list(Favorite.objects.filter(user=user).values_list("pk", flat=True))
    assert ordered == [newer.pk, middle.pk, older.pk]


@pytest.mark.django_db
def test_deleting_product_cascades_to_favorite(make_user, product_factory):
    user = make_user("cust")
    product = product_factory()
    Favorite.objects.create(user=user, product=product)
    product.delete()
    assert Favorite.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_deleting_user_cascades_to_favorite(make_user, product_factory):
    user = make_user("cust")
    product = product_factory()
    Favorite.objects.create(user=user, product=product)
    user.delete()
    assert Favorite.objects.filter(product=product).count() == 0
