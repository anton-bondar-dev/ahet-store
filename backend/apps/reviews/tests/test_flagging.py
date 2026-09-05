"""Tests for flagging a review for support (the `needs_support` flag on
create_review) and its end-to-end interaction with the support moderation queue
and resolve endpoint.

The flag itself is a reviews-side concern; the queue/resolve endpoints live in
the support app but are the observable effect of flagging, so they are exercised
here to prove the flag actually routes a review to the help desk.
"""
import pytest

from apps.reviews.models import Review


@pytest.mark.django_db
def test_flag_sets_needs_support_pending(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    resp = post_json(
        review_url.list_or_create(product.id),
        {"rating": 1, "text": "arrived broken", "needs_support": True},
        bearer(user),
    )
    assert resp.status_code == 200, resp.content
    review = Review.objects.get(user=user, product=product)
    assert review.needs_support is True
    assert review.support_status == Review.SUPPORT_PENDING


@pytest.mark.django_db
def test_unflagged_review_not_in_support(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    post_json(review_url.list_or_create(product.id), {"rating": 5}, bearer(user))
    review = Review.objects.get(user=user, product=product)
    assert review.needs_support is False


@pytest.mark.django_db
def test_flagged_review_appears_in_support_queue(api, bearer, make_user, product_factory, review_url, post_json):
    flagger = make_user("alice")
    quiet = make_user("bob")
    product = product_factory()
    post_json(review_url.list_or_create(product.id),
              {"rating": 1, "needs_support": True}, bearer(flagger))
    post_json(review_url.list_or_create(product.id),
              {"rating": 5, "needs_support": False}, bearer(quiet))
    flagged = Review.objects.get(user=flagger)

    staff = make_user("op", is_staff=True)
    resp = api.get(review_url.support_queue, headers=bearer(staff))
    assert resp.status_code == 200, resp.content
    ids = [row["id"] for row in resp.json()]
    assert flagged.id in ids
    assert Review.objects.get(user=quiet).id not in ids


@pytest.mark.django_db
def test_support_queue_requires_staff(api, bearer, make_user, review_url):
    assert api.get(review_url.support_queue).status_code == 401
    assert api.get(review_url.support_queue, headers=bearer(make_user("cust"))).status_code == 403


@pytest.mark.django_db
def test_resolve_marks_review_resolved(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    post_json(review_url.list_or_create(product.id),
              {"rating": 1, "needs_support": True}, bearer(user))
    review = Review.objects.get(user=user)

    staff = make_user("op", is_staff=True)
    resp = api.post(review_url.resolve(review.id), content_type="application/json",
                    headers=bearer(staff))
    assert resp.status_code == 200, resp.content

    review.refresh_from_db()
    assert review.support_status == Review.SUPPORT_RESOLVED
    assert review.support_resolved_by_id == staff.id
    assert review.support_resolved_at is not None

    # Resolved reviews drop out of the pending queue.
    queue_ids = [r["id"] for r in api.get(review_url.support_queue, headers=bearer(staff)).json()]
    assert review.id not in queue_ids


@pytest.mark.django_db
def test_resolve_requires_staff(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    post_json(review_url.list_or_create(product.id),
              {"rating": 1, "needs_support": True}, bearer(user))
    review = Review.objects.get(user=user)
    resp = api.post(review_url.resolve(review.id), content_type="application/json",
                    headers=bearer(make_user("cust")))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_reflagging_reopens_after_resolution(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    headers = bearer(user)
    post_json(review_url.list_or_create(product.id),
              {"rating": 1, "needs_support": True}, headers)
    review = Review.objects.get(user=user)

    staff = make_user("op", is_staff=True)
    api.post(review_url.resolve(review.id), content_type="application/json",
             headers=bearer(staff))
    review.refresh_from_db()
    assert review.support_status == Review.SUPPORT_RESOLVED

    # Customer edits their review and re-flags: it must reopen (pending).
    post_json(review_url.list_or_create(product.id),
              {"rating": 1, "text": "still broken", "needs_support": True}, headers)
    review.refresh_from_db()
    assert review.needs_support is True
    assert review.support_status == Review.SUPPORT_PENDING

    queue_ids = [r["id"] for r in api.get(review_url.support_queue, headers=bearer(staff)).json()]
    assert review.id in queue_ids


@pytest.mark.django_db
def test_update_without_reflag_keeps_resolved(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    headers = bearer(user)
    post_json(review_url.list_or_create(product.id),
              {"rating": 1, "needs_support": True}, headers)
    review = Review.objects.get(user=user)

    staff = make_user("op", is_staff=True)
    api.post(review_url.resolve(review.id), content_type="application/json",
             headers=bearer(staff))

    # Re-post WITHOUT the flag: status must not be reset back to pending.
    post_json(review_url.list_or_create(product.id),
              {"rating": 3, "needs_support": False}, headers)
    review.refresh_from_db()
    assert review.needs_support is False
    assert review.support_status == Review.SUPPORT_RESOLVED
