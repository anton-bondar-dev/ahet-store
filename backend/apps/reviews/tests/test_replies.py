"""Tests for POST /api/products/reviews/{review_id}/replies (create_reply).

Key rule under test: the `is_admin` staff badge is derived server-side from the
replying user and cannot be spoofed by the client payload. Also covers authz
(anon/blocked) and the not-found path.
"""
import pytest

from apps.reviews.models import Review, ReviewReply


def _review(make_user, product_factory, username="author"):
    return Review.objects.create(
        user=make_user(username), product=product_factory(), rating=4
    )


@pytest.mark.django_db
def test_customer_reply_has_no_admin_badge(api, bearer, make_user, product_factory, review_url, post_json):
    review = _review(make_user, product_factory)
    customer = make_user("cust")
    resp = post_json(review_url.reply(review.id), {"text": "me too"}, bearer(customer))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["is_admin"] is False
    assert body["author_name"] == "cust"
    assert body["text"] == "me too"
    assert ReviewReply.objects.get(id=body["id"]).user_id == customer.id


@pytest.mark.django_db
def test_staff_reply_has_admin_badge(api, bearer, make_user, product_factory, review_url, post_json):
    review = _review(make_user, product_factory)
    staff = make_user("op", is_staff=True)
    resp = post_json(review_url.reply(review.id), {"text": "we're on it"}, bearer(staff))
    assert resp.status_code == 200, resp.content
    assert resp.json()["is_admin"] is True


@pytest.mark.django_db
def test_superuser_reply_has_admin_badge(api, bearer, make_user, product_factory, review_url, post_json):
    review = _review(make_user, product_factory)
    root = make_user("root", is_superuser=True)
    resp = post_json(review_url.reply(review.id), {"text": "handled"}, bearer(root))
    assert resp.status_code == 200, resp.content
    assert resp.json()["is_admin"] is True


@pytest.mark.django_db
def test_admin_badge_cannot_be_spoofed_by_customer(api, bearer, make_user, product_factory, review_url, post_json):
    """A plain customer sending is_admin/user in the body must not be promoted."""
    review = _review(make_user, product_factory)
    customer = make_user("cust")
    staff = make_user("op", is_staff=True)
    resp = post_json(
        review_url.reply(review.id),
        {"text": "trust me", "is_admin": True, "user": staff.id, "user_id": staff.id},
        bearer(customer),
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["is_admin"] is False
    # The reply is owned by the real caller, not the injected staff id.
    reply = ReviewReply.objects.get(id=resp.json()["id"])
    assert reply.user_id == customer.id


@pytest.mark.django_db
def test_reply_requires_auth(api, make_user, product_factory, review_url, post_json):
    review = _review(make_user, product_factory)
    resp = post_json(review_url.reply(review.id), {"text": "hi"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_blocked_customer_cannot_reply(api, bearer, make_user, product_factory, review_url, post_json, block_user):
    review = _review(make_user, product_factory)
    blocked = block_user(make_user("naughty"))
    resp = post_json(review_url.reply(review.id), {"text": "hi"}, bearer(blocked))
    assert resp.status_code == 403
    assert not ReviewReply.objects.filter(user=blocked).exists()


@pytest.mark.django_db
def test_reply_to_missing_review_returns_404(api, bearer, make_user, review_url, post_json):
    resp = post_json(review_url.reply(999999), {"text": "hi"}, bearer(make_user("cust")))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_reply_missing_text_is_422(api, bearer, make_user, product_factory, review_url, post_json):
    review = _review(make_user, product_factory)
    resp = post_json(review_url.reply(review.id), {}, bearer(make_user("cust")))
    assert resp.status_code == 422
