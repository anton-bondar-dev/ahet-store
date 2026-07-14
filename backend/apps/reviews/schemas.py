from datetime import datetime
from typing import List

from ninja import Schema


def _author_name(user) -> str:
    return user.first_name or user.username


class ReviewReplyOut(Schema):
    id: int
    author_name: str
    is_admin: bool
    text: str
    created_at: datetime

    @staticmethod
    def resolve_author_name(obj):
        return _author_name(obj.user)

    @staticmethod
    def resolve_is_admin(obj):
        return bool(obj.user.is_staff or obj.user.is_superuser)


class ReviewOut(Schema):
    id: int
    author_name: str
    rating: int
    text: str
    created_at: datetime
    replies: List[ReviewReplyOut]

    @staticmethod
    def resolve_author_name(obj):
        return _author_name(obj.user)


class ReviewIn(Schema):
    rating: int
    text: str = ""


class ReplyIn(Schema):
    text: str


class MyReviewOut(Schema):
    id: int
    product_title: str
    product_slug: str
    rating: int
    text: str
    created_at: datetime

    @staticmethod
    def resolve_product_title(obj):
        return obj.product.title

    @staticmethod
    def resolve_product_slug(obj):
        return obj.product.slug
