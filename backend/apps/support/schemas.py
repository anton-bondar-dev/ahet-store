from datetime import datetime
from typing import List

from ninja import Schema

from .models import SUPPORT_DISPLAY_NAME


class ChatMessageIn(Schema):
    text: str


# --- User-facing (staff identity masked to a single "support" entity) ---------
class UserChatMessageOut(Schema):
    id: int
    sender: str        # "support" | "user"
    author_name: str   # SUPPORT_DISPLAY_NAME for staff, else the user's own name
    text: str
    created_at: datetime

    @staticmethod
    def resolve_sender(obj):
        return "support" if obj.from_staff else "user"

    @staticmethod
    def resolve_author_name(obj):
        if obj.from_staff:
            return SUPPORT_DISPLAY_NAME
        user = obj.sender
        if user is None:
            return "Користувач"
        return user.first_name or user.username


class UserChatOut(Schema):
    ticket_id: int
    status: str
    messages: List[UserChatMessageOut]


# --- Admin-facing (real staff identities) ------------------------------------
class AdminChatMessageOut(Schema):
    id: int
    sender_username: str
    sender_name: str
    from_staff: bool
    text: str
    created_at: datetime

    @staticmethod
    def resolve_sender_username(obj):
        return obj.sender.username if obj.sender else "(видалений)"

    @staticmethod
    def resolve_sender_name(obj):
        user = obj.sender
        if user is None:
            return "(видалений)"
        return user.first_name or user.username


class AdminTicketOut(Schema):
    id: int
    user_username: str
    status: str
    subject: str
    updated_at: datetime
    unread_count: int = 0

    @staticmethod
    def resolve_user_username(obj):
        return obj.user.username


class AdminTicketDetailOut(Schema):
    id: int
    user_username: str
    status: str
    messages: List[AdminChatMessageOut]

    @staticmethod
    def resolve_user_username(obj):
        return obj.user.username

    @staticmethod
    def resolve_messages(obj):
        return list(obj.messages.select_related("sender").all())
