from typing import List

from ninja import Router
from ninja_jwt.authentication import JWTAuth

from apps.reviews.models import Review
from apps.reviews.schemas import MyReviewOut

from .models import Profile
from .schemas import ProfileIn, ProfileOut

router = Router(tags=["accounts"])


def serialize_profile(user) -> dict:
    profile, _ = Profile.objects.get_or_create(user=user)
    return {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "phone_number": profile.phone_number,
        "city": profile.city,
        "delivery_address": profile.delivery_address,
        "email": user.email or "",
        "bonus_balance": profile.bonus_balance,
    }


@router.get("/profile", response=ProfileOut, auth=JWTAuth(), operation_id="get_profile")
def get_profile(request):
    return serialize_profile(request.auth)


@router.put("/profile", response=ProfileOut, auth=JWTAuth(), operation_id="update_profile")
def update_profile(request, payload: ProfileIn):
    user = request.auth
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.first_name = payload.first_name
    profile.last_name = payload.last_name
    profile.phone_number = payload.phone_number
    profile.city = payload.city
    profile.delivery_address = payload.delivery_address
    profile.save(
        update_fields=["first_name", "last_name", "phone_number", "city", "delivery_address"]
    )
    return serialize_profile(user)


@router.get("/reviews", response=List[MyReviewOut], auth=JWTAuth(), operation_id="get_my_reviews")
def get_my_reviews(request):
    return list(
        Review.objects.filter(user=request.auth).select_related("product")
    )
