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
