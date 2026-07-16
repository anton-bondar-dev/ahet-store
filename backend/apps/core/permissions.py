"""Role-based access helpers shared across the API.

Support/admin accounts (is_staff) are employees, not customers: they must not be
able to shop, open their own support tickets, or leave product reviews. These
helpers enforce that at the endpoint level.
"""

from ninja.errors import HttpError

STAFF_FORBIDDEN_MSG = "Службовим акаунтам ця дія недоступна"


def is_staff_user(user) -> bool:
    return bool(
        user
        and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    )


def forbid_staff(user):
    """Raise 403 when `user` is a staff/support account. `user` may be None
    (anonymous), which is always allowed through."""
    if is_staff_user(user):
        raise HttpError(403, STAFF_FORBIDDEN_MSG)
