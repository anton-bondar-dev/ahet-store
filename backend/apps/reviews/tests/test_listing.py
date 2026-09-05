"""Tests for the read endpoints:
  * GET /api/products/{product_id}/reviews (public product review list)
  * GET /api/accounts/reviews (the caller's own reviews)
"""
import datetime

import pytest
from django.utils import timezone

from apps.reviews.models import Review, ReviewReply


@pytest.mark.django_db
def test_list_reviews_is_public(api, make_user, product_factory, review_url):
    product = product_factory()
    Review.objects.create(user=make_user("alice"), product=product, rating=5, text="great")
    resp = api.get(review_url.list_or_create(product.id))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["rating"] == 5 and body[0]["text"] == "great"


@pytest.mark.django_db
def test_list_reviews_empty_for_unreviewed_product(api, product_factory, review_url):
    product = product_factory()
    resp = api.get(review_url.list_or_create(product.id))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_list_reviews_scoped_to_product(api, make_user, product_factory, review_url):
    p1, p2 = product_factory(), product_factory()
    Review.objects.create(user=make_user("alice"), product=p1, rating=5)
    Review.objects.create(user=make_user("bob"), product=p2, rating=1)
    body = api.get(review_url.list_or_create(p1.id)).json()
    assert len(body) == 1 and body[0]["rating"] == 5


@pytest.mark.django_db
def test_list_reviews_newest_first(api, make_user, product_factory, review_url):
    product = product_factory()
    old = Review.objects.create(user=make_user("alice"), product=product, rating=5)
    new = Review.objects.create(user=make_user("bob"), product=product, rating=1)
    now = timezone.now()
    Review.objects.filter(id=old.id).update(created_at=now - datetime.timedelta(days=1))
    Review.objects.filter(id=new.id).update(created_at=now)
    body = api.get(review_url.list_or_create(product.id)).json()
    assert [r["id"] for r in body] == [new.id, old.id]


@pytest.mark.django_db
def test_list_reviews_nest_replies_oldest_first(api, make_user, product_factory, review_url):
    product = product_factory()
    author = make_user("alice")
    review = Review.objects.create(user=author, product=product, rating=4)
    staff = make_user("op", is_staff=True)
    r1 = ReviewReply.objects.create(review=review, user=staff, text="first")
    r2 = ReviewReply.objects.create(review=review, user=author, text="second")
    now = timezone.now()
    ReviewReply.objects.filter(id=r1.id).update(created_at=now - datetime.timedelta(hours=1))
    ReviewReply.objects.filter(id=r2.id).update(created_at=now)

    body = api.get(review_url.list_or_create(product.id)).json()
    replies = body[0]["replies"]
    assert [rep["text"] for rep in replies] == ["first", "second"]
    assert replies[0]["is_admin"] is True   # staff reply
    assert replies[1]["is_admin"] is False  # author reply


@pytest.mark.django_db
def test_my_reviews_requires_auth(api, review_url):
    resp = api.get(review_url.my_reviews)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_my_reviews_returns_only_own(api, bearer, make_user, product_factory, review_url):
    alice, bob = make_user("alice"), make_user("bob")
    pa, pb = product_factory(), product_factory()
    Review.objects.create(user=alice, product=pa, rating=5, text="mine")
    Review.objects.create(user=bob, product=pb, rating=1, text="theirs")

    body = api.get(review_url.my_reviews, headers=bearer(alice)).json()
    assert len(body) == 1
    row = body[0]
    assert row["text"] == "mine"
    assert row["product_title"] == pa.title
    assert row["product_slug"] == pa.slug


@pytest.mark.django_db
def test_my_reviews_empty_when_none(api, bearer, make_user, review_url):
    body = api.get(review_url.my_reviews, headers=bearer(make_user("alice"))).json()
    assert body == []
