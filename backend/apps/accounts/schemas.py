from typing import Optional

from ninja import Schema


class RegisterIn(Schema):
    username: str
    email: str
    password: str


class LoginIn(Schema):
    username: str
    password: str


class UserOut(Schema):
    id: int
    username: str
    email: str
    is_2fa_enabled: bool = False
    preferred_2fa_method: str = "none"
    telegram_linked: bool = False
    bonus_balance: int = 0
    is_staff: bool = False

    @staticmethod
    def resolve_is_staff(obj):
        return bool(obj.is_staff or obj.is_superuser)

    @staticmethod
    def resolve_is_2fa_enabled(obj):
        profile = getattr(obj, "profile", None)
        return bool(profile and profile.is_2fa_enabled)

    @staticmethod
    def resolve_bonus_balance(obj):
        profile = getattr(obj, "profile", None)
        return profile.bonus_balance if profile else 0

    @staticmethod
    def resolve_preferred_2fa_method(obj):
        profile = getattr(obj, "profile", None)
        return profile.preferred_2fa_method if profile else "none"

    @staticmethod
    def resolve_telegram_linked(obj):
        profile = getattr(obj, "profile", None)
        return bool(profile and profile.telegram_chat_id)


class TokenPair(Schema):
    access: str
    refresh: str


class AuthResult(Schema):
    # status == "authed": tokens + user are present.
    # status == "pending": second factor required. `method` picks the UI:
    #   "telegram" → poll for tap approval (match_code shown); "email" → enter OTP.
    status: str
    method: Optional[str] = None
    access: Optional[str] = None
    refresh: Optional[str] = None
    user: Optional[UserOut] = None
    challenge_id: Optional[str] = None
    match_code: Optional[int] = None


class GoogleAuthIn(Schema):
    credential: str  # Google ID token (JWT) from GIS


class ProfileIn(Schema):
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    phone_number: str = ""
    city: str = ""
    delivery_address: str = ""


class ProfileOut(Schema):
    username: str
    first_name: str
    last_name: str
    phone_number: str
    city: str
    delivery_address: str
    email: str
    bonus_balance: int


class VerifyOtpIn(Schema):
    code: str


class Set2faMethodIn(Schema):
    method: str  # "none" | "telegram" | "email"


class RefreshIn(Schema):
    refresh: str


class AccessOut(Schema):
    access: str


class TelegramLinkOut(Schema):
    url: str
    token: str


class LinkStatusOut(Schema):
    linked: bool
