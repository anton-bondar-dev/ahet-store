"""Tests for POST /api/products/{product_id}/reviews (create_review).

Covers the happy path, the one-review-per-user semantics (update-in-place),
rating clamping, product-rating recomputation, authz (staff/blocked/anon) and
input validation.
"""
import pytest

from apps.reviews.models import Review


@pytest.mark.django_db
def test_create_review_happy_path(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    resp = post_json(
        review_url.list_or_create(product.id),
        {"rating": 4, "text": "solid"},
        bearer(user),
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["rating"] == 4
    assert body["text"] == "solid"
    assert body["author_name"] == "alice"
    assert body["replies"] == []

    review = Review.objects.get(user=user, product=product)
    assert review.rating == 4 and review.text == "solid"


@pytest.mark.django_db
def test_create_review_requires_auth(api, make_user, product_factory, review_url, post_json):
    product = product_factory()
    resp = post_json(review_url.list_or_create(product.id), {"rating": 4})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_text_optional_defaults_to_empty(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    resp = post_json(review_url.list_or_create(product.id), {"rating": 5}, bearer(user))
    assert resp.status_code == 200, resp.content
    assert resp.json()["text"] == ""


@pytest.mark.django_db
def test_author_name_prefers_first_name(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    user.first_name = "Alicia"
    user.save(update_fields=["first_name"])
    product = product_factory()
    resp = post_json(review_url.list_or_create(product.id), {"rating": 5}, bearer(user))
    assert resp.status_code == 200, resp.content
    assert resp.json()["author_name"] == "Alicia"


@pytest.mark.django_db
@pytest.mark.parametrize("sent,stored", [(9, 5), (6, 5), (0, 1), (-4, 1)])
def test_rating_is_clamped_to_1_5(api, bearer, make_user, product_factory, review_url, post_json, sent, stored):
    user = make_user("alice")
    product = product_factory()
    resp = post_json(review_url.list_or_create(product.id), {"rating": sent}, bearer(user))
    assert resp.status_code == 200, resp.content
    assert resp.json()["rating"] == stored
    assert Review.objects.get(user=user, product=product).rating == stored


@pytest.mark.django_db
def test_second_post_updates_in_place_not_duplicate(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    headers = bearer(user)
    first = post_json(review_url.list_or_create(product.id), {"rating": 3, "text": "meh"}, headers)
    review_id = first.json()["id"]

    second = post_json(review_url.list_or_create(product.id), {"rating": 5, "text": "great"}, headers)
    assert second.status_code == 200, second.content
    # Same review row, updated content — not a second review.
    assert second.json()["id"] == review_id
    assert Review.objects.filter(user=user, product=product).count() == 1
    review = Review.objects.get(user=user, product=product)
    assert review.rating == 5 and review.text == "great"


@pytest.mark.django_db
def test_create_review_recomputes_product_rating(api, bearer, make_user, product_factory, review_url, post_json):
    product = product_factory()
    post_json(review_url.list_or_create(product.id), {"rating": 4}, bearer(make_user("alice")))
    product.refresh_from_db()
    assert product.reviews_count == 1
    assert product.average_rating == 4.0

    post_json(review_url.list_or_create(product.id), {"rating": 2}, bearer(make_user("bob")))
    product.refresh_from_db()
    assert product.reviews_count == 2
    assert product.average_rating == 3.0


@pytest.mark.django_db
def test_staff_cannot_create_review(api, bearer, make_user, product_factory, review_url, post_json):
    staff = make_user("op", is_staff=True)
    product = product_factory()
    resp = post_json(review_url.list_or_create(product.id), {"rating": 5}, bearer(staff))
    assert resp.status_code == 403
    assert not Review.objects.filter(user=staff).exists()


@pytest.mark.django_db
def test_superuser_cannot_create_review(api, bearer, make_user, product_factory, review_url, post_json):
    root = make_user("root", is_superuser=True)
    product = product_factory()
    resp = post_json(review_url.list_or_create(product.id), {"rating": 5}, bearer(root))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_blocked_customer_cannot_create_review(api, bearer, make_user, product_factory, review_url, post_json, block_user):
    user = block_user(make_user("naughty"))
    product = product_factory()
    resp = post_json(review_url.list_or_create(product.id), {"rating": 5}, bearer(user))
    assert resp.status_code == 403
    assert not Review.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_create_review_for_missing_product_returns_404(api, bearer, make_user, review_url, post_json):
    user = make_user("alice")
    resp = post_json(review_url.list_or_create(999999), {"rating": 5}, bearer(user))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_create_review_missing_rating_is_422(api, bearer, make_user, product_factory, review_url, post_json):
    user = make_user("alice")
    product = product_factory()
    resp = post_json(review_url.list_or_create(product.id), {"text": "no rating"}, bearer(user))
    assert resp.status_code == 422
