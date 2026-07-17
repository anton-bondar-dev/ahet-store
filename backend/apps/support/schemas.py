from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from ninja import Schema

from apps.reviews.schemas import ReviewReplyOut

from .models import SUPPORT_DISPLAY_NAME


class ChatMessageIn(Schema):
    text: str
    is_internal: bool = False  # staff-only note (ignored on the customer endpoint)


class RatingIn(Schema):
    is_positive: bool  # 👍 = True, 👎 = False


class OkOut(Schema):
    ok: bool


# --- User-facing (staff identity masked to a single "support" entity) ---------
class UserChatMessageOut(Schema):
    id: int
    sender: str        # "support" | "user" | "system"
    author_name: str   # SUPPORT_DISPLAY_NAME for staff, else the user's own name
    text: str
    is_system: bool = False
    created_at: datetime

    @staticmethod
    def resolve_sender(obj):
        if obj.is_system:
            return "system"
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
    # True when the latest ticket is closed and hasn't been rated yet → the
    # frontend shows the end-of-chat 👍/👎 prompt.
    can_rate: bool = False


# --- Admin-facing (real staff identities) ------------------------------------
class AdminChatMessageOut(Schema):
    id: int
    sender_username: str
    sender_name: str
    from_staff: bool
    is_system: bool = False
    is_internal: bool = False
    meta: dict = {}
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


class CustomerTagOut(Schema):
    id: int
    label: str
    color: str


class TicketPresenceOut(Schema):
    staff_username: str
    staff_name: str
    state: str  # "viewing" | "typing"

    @staticmethod
    def resolve_staff_username(obj):
        return obj.staff.username if obj.staff else "?"

    @staticmethod
    def resolve_staff_name(obj):
        return (obj.staff.first_name or obj.staff.username) if obj.staff else "?"


class AdminTicketOut(Schema):
    id: int
    user_username: str
    support_id: Optional[str] = None      # customer's hidden support id (staff-only)
    assigned_to: Optional[str] = None     # operator handling it
    priority: str = "normal"
    status: str
    subject: str
    updated_at: datetime
    unread_count: int = 0
    is_overdue: bool = False  # SLA breach → 🚨 + floats to top

    @staticmethod
    def resolve_user_username(obj):
        return obj.user.username

    @staticmethod
    def resolve_support_id(obj):
        profile = getattr(obj.user, "profile", None)
        return profile.support_id if profile else None

    @staticmethod
    def resolve_assigned_to(obj):
        u = obj.assigned_to
        return (u.first_name or u.username) if u else None


class AdminTicketDetailOut(Schema):
    id: int
    user_id: int
    user_username: str
    customer_name: str
    customer_support_id: Optional[str] = None
    customer_blocked: bool = False
    status: str
    priority: str = "normal"
    is_overdue: bool = False
    assigned_to_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    customer_last_seen: Optional[datetime] = None
    customer_device: str = ""
    customer_online: bool = False
    messages: List[AdminChatMessageOut]
    tags: List[CustomerTagOut]
    viewers: List[TicketPresenceOut]  # other staff currently on this ticket

    @staticmethod
    def resolve_user_id(obj):
        return obj.user_id

    @staticmethod
    def resolve_customer_last_seen(obj):
        profile = getattr(obj.user, "profile", None)
        return profile.last_seen_at if profile else None

    @staticmethod
    def resolve_customer_device(obj):
        from .services import parse_user_agent

        profile = getattr(obj.user, "profile", None)
        return parse_user_agent(profile.last_user_agent) if profile else ""

    @staticmethod
    def resolve_customer_online(obj):
        from datetime import timedelta

        from django.utils import timezone

        profile = getattr(obj.user, "profile", None)
        if not profile or not profile.last_seen_at:
            return False
        return timezone.now() - profile.last_seen_at < timedelta(minutes=2)

    @staticmethod
    def resolve_customer_support_id(obj):
        profile = getattr(obj.user, "profile", None)
        return profile.support_id if profile else None

    @staticmethod
    def resolve_assigned_to_id(obj):
        return obj.assigned_to_id

    @staticmethod
    def resolve_assigned_to_name(obj):
        u = obj.assigned_to
        return (u.first_name or u.username) if u else None

    @staticmethod
    def resolve_customer_blocked(obj):
        profile = getattr(obj.user, "profile", None)
        return bool(profile and profile.is_blocked)

    @staticmethod
    def resolve_user_username(obj):
        return obj.user.username

    @staticmethod
    def resolve_customer_name(obj):
        return obj.user.first_name or obj.user.username

    @staticmethod
    def resolve_messages(obj):
        return list(obj.messages.select_related("sender").all())

    @staticmethod
    def resolve_tags(obj):
        return [a.tag for a in obj.user.support_tags.select_related("tag").all()]

    @staticmethod
    def resolve_viewers(obj):
        # Populated by the view (fresh heartbeats, excluding the caller).
        return getattr(obj, "_viewers", [])


# --- Support workspace: metrics, customer context, tagged comments -----------
class StaffMetricsOut(Schema):
    resolved_tickets: int
    comments_resolved: int
    ratings_total: int
    ratings_positive: int
    positive_rate: Optional[int] = None  # % positive, None when no ratings yet


class CustomerOrderOut(Schema):
    id: int
    status: str
    total_price: Decimal
    item_count: int
    created_at: datetime

    @staticmethod
    def resolve_item_count(obj):
        return obj.items.count()


class TaggedCommentOut(Schema):
    id: int
    product_title: str
    product_slug: str
    author_name: str
    rating: int
    text: str
    support_status: str
    created_at: datetime
    replies: List[ReviewReplyOut]

    @staticmethod
    def resolve_product_title(obj):
        return obj.product.title

    @staticmethod
    def resolve_product_slug(obj):
        return obj.product.slug

    @staticmethod
    def resolve_author_name(obj):
        return obj.user.first_name or obj.user.username


# --- Phase 1: tags -----------------------------------------------------------
class TagCreateIn(Schema):
    label: str
    color: str = "#6b7280"


class AssignTagIn(Schema):
    tag_id: int


# --- Phase 2: macros ---------------------------------------------------------
class MacroOut(Schema):
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class MacroIn(Schema):
    title: str
    content: str


class MacroRenderIn(Schema):
    ticket_id: int


class RenderedTextOut(Schema):
    content: str


# --- Phase 4: impersonation --------------------------------------------------
class ImpersonateOut(Schema):
    access: str            # scoped JWT to run the storefront as the customer
    target_username: str
    target_name: str


# --- Phase 5: actionable chat ------------------------------------------------
class ChatActionIn(Schema):
    type: str              # "grant_bonuses" | "generate_coupon"
    amount: int = 0        # bonuses to grant
    percent: int = 0       # coupon discount %


class ActionResultOut(Schema):
    ok: bool
    pending: bool = False  # True → sent to the Team Lead for approval


class ApprovalOut(Schema):
    id: int
    requested_by: str
    ticket_id: int
    customer_name: str
    action_type: str
    amount: int
    percent: int
    created_at: datetime

    @staticmethod
    def resolve_requested_by(obj):
        u = obj.requested_by
        return (u.first_name or u.username) if u else "?"

    @staticmethod
    def resolve_customer_name(obj):
        u = obj.ticket.user
        return u.first_name or u.username


# --- Phase 6: presence -------------------------------------------------------
class PresenceIn(Schema):
    state: str = "viewing"  # "viewing" | "typing"


# --- Phase 7: audit ----------------------------------------------------------
class AuditLogOut(Schema):
    id: int
    admin_username: str
    action_type: str
    target_username: Optional[str] = None
    ticket_id: Optional[int] = None
    meta: dict
    created_at: datetime

    @staticmethod
    def resolve_admin_username(obj):
        return obj.admin_user.username if obj.admin_user else "(видалений)"

    @staticmethod
    def resolve_target_username(obj):
        return obj.target_user.username if obj.target_user else None


# --- Owner: staff dossiers + moderation --------------------------------------
class StaffDossierOut(Schema):
    id: int
    username: str
    name: str
    role: str              # "owner" | "operator"
    status: str = "online"  # operator availability (online | away)
    is_active: bool        # False = blocked operator
    resolved_tickets: int
    comments_resolved: int
    ratings_total: int
    positive_rate: Optional[int] = None


class OperatorStatusIn(Schema):
    status: str            # "online" | "away"


class AssignTicketIn(Schema):
    operator_id: Optional[int] = None  # None → assign to self ("Assign to me")


class PriorityIn(Schema):
    priority: str  # low | normal | high | urgent


class BlockUserIn(Schema):
    permanent: bool = False
    days: int = 0          # temporary block length when not permanent


class CancelBonusIn(Schema):
    message_id: int        # the grant system-message to reverse
