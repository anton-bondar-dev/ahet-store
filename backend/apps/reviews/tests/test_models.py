"""Model-level tests for Review / ReviewReply: constraints, defaults, ordering,
string representations and the rating validators."""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.reviews.models import Review, ReviewReply


@pytest.mark.django_db
def test_review_str(make_user, product_factory):
    user = make_user("alice")
    product = product_factory()
    review = Review.objects.create(user=user, product=product, rating=5)
    assert str(review) == f"5★ by {user.id} on {product.id}"


@pytest.mark.django_db
def test_reply_str(make_user, product_factory):
    user = make_user("alice")
    product = product_factory()
    review = Review.objects.create(user=user, product=product, rating=3)
    reply = ReviewReply.objects.create(review=review, user=user, text="hi")
    assert str(reply) == f"Reply by {user.id} on review {review.id}"


@pytest.mark.django_db
def test_support_defaults(make_user, product_factory):
    review = Review.objects.create(
        user=make_user("alice"), product=product_factory(), rating=4
    )
    assert review.needs_support is False
    assert review.support_status == Review.SUPPORT_PENDING
    assert review.support_resolved_by is None
    assert review.support_resolved_at is None
    assert review.text == ""


@pytest.mark.django_db
def test_unique_together_one_review_per_user_product(make_user, product_factory):
    user = make_user("alice")
    product = product_factory()
    Review.objects.create(user=user, product=product, rating=5)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Review.objects.create(user=user, product=product, rating=2)


@pytest.mark.django_db
def test_same_user_can_review_different_products(make_user, product_factory):
    user = make_user("alice")
    Review.objects.create(user=user, product=product_factory(), rating=5)
    Review.objects.create(user=user, product=product_factory(), rating=1)
    assert Review.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_different_users_can_review_same_product(make_user, product_factory):
    product = product_factory()
    Review.objects.create(user=make_user("alice"), product=product, rating=5)
    Review.objects.create(user=make_user("bob"), product=product, rating=1)
    assert Review.objects.filter(product=product).count() == 2


@pytest.mark.django_db
def test_reviews_default_ordering_newest_first(make_user, product_factory):
    product = product_factory()
    old = Review.objects.create(user=make_user("alice"), product=product, rating=5)
    new = Review.objects.create(user=make_user("bob"), product=product, rating=1)
    now = timezone.now()
    Review.objects.filter(id=old.id).update(created_at=now - datetime.timedelta(days=2))
    Review.objects.filter(id=new.id).update(created_at=now)
    ordered = list(Review.objects.filter(product=product).values_list("id", flat=True))
    assert ordered == [new.id, old.id]


@pytest.mark.django_db
def test_replies_default_ordering_oldest_first(make_user, product_factory):
    review = Review.objects.create(
        user=make_user("alice"), product=product_factory(), rating=4
    )
    first = ReviewReply.objects.create(review=review, user=review.user, text="first")
    second = ReviewReply.objects.create(review=review, user=review.user, text="second")
    now = timezone.now()
    ReviewReply.objects.filter(id=first.id).update(
        created_at=now - datetime.timedelta(hours=1)
    )
    ReviewReply.objects.filter(id=second.id).update(created_at=now)
    ordered = list(review.replies.values_list("id", flat=True))
    assert ordered == [first.id, second.id]


@pytest.mark.django_db
@pytest.mark.parametrize("bad_rating", [0, 6, 99])
def test_rating_validators_reject_out_of_range(make_user, product_factory, bad_rating):
    review = Review(user=make_user("alice"), product=product_factory(), rating=bad_rating)
    with pytest.raises(ValidationError):
        review.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize("ok_rating", [1, 3, 5])
def test_rating_validators_accept_in_range(make_user, product_factory, ok_rating):
    review = Review(user=make_user("alice"), product=product_factory(), rating=ok_rating)
    review.full_clean()  # must not raise
