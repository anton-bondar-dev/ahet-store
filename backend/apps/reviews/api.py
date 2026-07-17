from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router
from apps.accounts.jwt_auth import StampedJWTAuth as JWTAuth

from apps.catalog.models import Product
from apps.core.permissions import forbid_blocked, forbid_staff

from .models import Review, ReviewReply
from .schemas import ReplyIn, ReviewIn, ReviewOut, ReviewReplyOut

router = Router(tags=["reviews"])


def _reviews_qs(product_id: int):
    return (
        Review.objects.filter(product_id=product_id)
        .select_related("user")
        .prefetch_related("replies__user")
    )


# Literal `/reviews/...` route registered before the `/{product_id}/reviews`
# param route so it is never captured by it.
@router.post(
    "/reviews/{review_id}/replies",
    response=ReviewReplyOut,
    auth=JWTAuth(),
    operation_id="create_reply",
)
def create_reply(request, review_id: int, payload: ReplyIn):
    # Staff may reply (support), but blocked customers may not post anything.
    forbid_blocked(request.auth)
    review = get_object_or_404(Review, id=review_id)
    reply = ReviewReply.objects.create(review=review, user=request.auth, text=payload.text)
    return reply


@router.get(
    "/{product_id}/reviews", response=List[ReviewOut], operation_id="get_product_reviews"
)
def get_product_reviews(request, product_id: int):
    return list(_reviews_qs(product_id))


@router.post(
    "/{product_id}/reviews",
    response=ReviewOut,
    auth=JWTAuth(),
    operation_id="create_review",
)
def create_review(request, product_id: int, payload: ReviewIn):
    # Staff can reply to reviews (their job) but never author their own.
    forbid_staff(request.auth)
    forbid_blocked(request.auth)
    product = get_object_or_404(Product, id=product_id)
    rating = max(1, min(payload.rating, 5))
    defaults = {
        "rating": rating,
        "text": payload.text,
        "needs_support": payload.needs_support,
    }
    # (Re)flagging puts the review back into the pending support queue.
    if payload.needs_support:
        defaults["support_status"] = Review.SUPPORT_PENDING
    Review.objects.update_or_create(
        user=request.auth,
        product=product,
        defaults=defaults,
    )
    product.recompute_rating()
    # Return the caller's review with its replies prefetched.
    return _reviews_qs(product_id).get(user=request.auth)
