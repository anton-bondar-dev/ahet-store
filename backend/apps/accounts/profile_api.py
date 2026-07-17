from typing import List

from django.contrib.auth.models import User
from ninja import Router
from ninja.errors import HttpError
from apps.accounts.jwt_auth import StampedJWTAuth as JWTAuth

from apps.core.permissions import is_staff_user
from apps.reviews.models import Review
from apps.reviews.schemas import MyReviewOut

from .models import Profile
from .schemas import ProfileIn, ProfileOut

router = Router(tags=["accounts"])


def serialize_profile(user) -> dict:
    profile, _ = Profile.objects.get_or_create(user=user)
    return {
        "username": user.username,
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

    # Email is the login identifier now — editable, with a uniqueness check.
    # (Staff email is locked to protect the fixed help-desk identity.)
    new_email = payload.email.strip().lower()
    if new_email and new_email != (user.email or "").lower():
        if is_staff_user(user):
            raise HttpError(403, "Email службового акаунта змінити не можна")
        if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
            raise HttpError(400, "Цей email вже використовується")
        user.email = new_email
        user.save(update_fields=["email"])

    profile, _ = Profile.objects.get_or_create(user=user)
    profile.first_name = payload.first_name
    profile.last_name = payload.last_name
    profile.phone_number = payload.phone_number
    profile.city = payload.city
    profile.delivery_address = payload.delivery_address
    profile.save(
        update_fields=["first_name", "last_name", "phone_number", "city", "delivery_address"]
    )
    # Keep the auth User's display name in sync so it updates everywhere it is
    # shown (header, chat author names, staff dossier) — not just at checkout.
    user.first_name = payload.first_name
    user.last_name = payload.last_name
    user.save(update_fields=["first_name", "last_name"])
    return serialize_profile(user)


@router.get("/reviews", response=List[MyReviewOut], auth=JWTAuth(), operation_id="get_my_reviews")
def get_my_reviews(request):
    return list(
        Review.objects.filter(user=request.auth).select_related("product")
    )
