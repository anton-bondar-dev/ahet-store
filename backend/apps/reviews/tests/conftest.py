"""Fixtures local to the reviews test suite.

The shared fixtures (`api`, `bearer`, `make_user`, `product_factory`, ...) live
in the repo-root conftest and are reused as-is. Only helpers specific to reviews
are added here.
"""
import pytest


@pytest.fixture
def block_user(db):
    """Permanently block a customer (so `forbid_blocked` refuses them)."""
    from apps.accounts.models import Profile

    def _block(user):
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.blocked_permanent = True
        profile.save(update_fields=["blocked_permanent"])
        return user

    return _block


@pytest.fixture
def review_url():
    """URL builders for the review endpoints (router mounted at /api/products)."""
    class _Urls:
        @staticmethod
        def list_or_create(product_id):
            return f"/api/products/{product_id}/reviews"

        @staticmethod
        def reply(review_id):
            return f"/api/products/reviews/{review_id}/replies"

        my_reviews = "/api/accounts/reviews"
        support_queue = "/api/support/admin/comments"

        @staticmethod
        def resolve(review_id):
            return f"/api/support/admin/comments/{review_id}/resolve"

    return _Urls
