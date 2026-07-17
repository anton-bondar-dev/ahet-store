"""Support-workspace helpers shared by the API views."""

from .models import AdminAuditLog

# Liveness window for collision detection: presence heartbeats older than this
# are treated as "gone".
PRESENCE_TTL_SECONDS = 12


def log_admin_action(admin_user, action_type, *, target_user=None, ticket=None, **meta):
    """Append an entry to the audit trail. Called from every sensitive staff
    action (impersonation, tag changes, actionable-chat events, ticket close)."""
    return AdminAuditLog.objects.create(
        admin_user=admin_user,
        action_type=action_type,
        target_user=target_user,
        ticket=ticket,
        meta=meta or {},
    )


def parse_user_agent(ua: str) -> str:
    """Very small UA → 'OS Browser' summary for the staff sidebar (no deps)."""
    if not ua:
        return ""
    low = ua.lower()
    if "windows" in low:
        os_name = "Windows"
    elif "iphone" in low or "ipad" in low or "ios " in low:
        os_name = "iOS"
    elif "mac os" in low or "macintosh" in low:
        os_name = "macOS"
    elif "android" in low:
        os_name = "Android"
    elif "linux" in low:
        os_name = "Linux"
    else:
        os_name = ""
    if "edg" in low:
        browser = "Edge"
    elif "opr" in low or "opera" in low:
        browser = "Opera"
    elif "chrome" in low or "crios" in low:
        browser = "Chrome"
    elif "firefox" in low or "fxios" in low:
        browser = "Firefox"
    elif "safari" in low:
        browser = "Safari"
    else:
        browser = ""
    return " ".join(p for p in (os_name, browser) if p)


def render_macro(content: str, customer) -> str:
    """Substitute whitelisted {placeholders} in a macro against the ticket's
    customer. Only these keys are ever interpolated — no arbitrary attributes."""
    first = (customer.first_name or customer.username) if customer else ""
    values = {
        "first_name": first,
        "last_name": (customer.last_name if customer else "") or "",
        "username": customer.username if customer else "",
    }
    out = content
    for key, value in values.items():
        out = out.replace("{" + key + "}", value)
    return out
