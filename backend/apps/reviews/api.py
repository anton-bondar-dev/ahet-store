from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from apps.catalog.models import Product

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
    product = get_object_or_404(Product, id=product_id)
    rating = max(1, min(payload.rating, 5))
    Review.objects.update_or_create(
        user=request.auth,
        product=product,
        defaults={"rating": rating, "text": payload.text},
    )
    product.recompute_rating()
    # Return the caller's review with its replies prefetched.
    return _reviews_qs(product_id).get(user=request.auth)
