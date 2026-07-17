from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Cart

SESSION_HEADER = "X-Session-Id"


def get_session_id(request) -> Optional[str]:
    sid = request.headers.get(SESSION_HEADER)
    return sid.strip() if sid and sid.strip() else None


def auth_user(request):
    """Decode an optional Bearer token → User, or None. Never raises / never 401s,
    so cart & checkout stay usable anonymously while recognising logged-in users."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    raw = header[7:].strip()
    try:
        # Imported lazily so importing this module doesn't require JWT settings.
        from ninja_jwt.tokens import AccessToken

        token = AccessToken(raw)  # validates signature + expiry
        return get_user_model().objects.filter(id=token["user_id"]).first()
    except Exception:
        return None


def impersonator_id(request):
    """If the request is running under an impersonation token (a staff member
    viewing the app as a customer), return the staff member's id, else None.
    Used to block real checkout/writes while impersonating."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    raw = header[7:].strip()
    try:
        from ninja_jwt.tokens import AccessToken

        return AccessToken(raw).get("imp_by")
    except Exception:
        return None


def _cart_qs():
    return Cart.objects.prefetch_related(
        "items__product__category", "items__product__gallery"
    )


def get_current_cart(request) -> Optional[Cart]:
    """The caller's existing cart (user cart if authed, else session cart)."""
    user = auth_user(request)
    if user is not None:
        return _cart_qs().filter(user=user).order_by("id").first()
    sid = get_session_id(request)
    if not sid:
        return None
    return _cart_qs().filter(session_id=sid, user__isnull=True).order_by("id").first()


def get_or_create_current_cart(request) -> Optional[Cart]:
    """Resolve the caller's cart, creating it if missing. None if no identity at all."""
    cart = get_current_cart(request)
    if cart is not None:
        return cart
    user = auth_user(request)
    if user is not None:
        return Cart.objects.create(user=user)
    sid = get_session_id(request)
    if not sid:
        return None
    return Cart.objects.create(session_id=sid)


@transaction.atomic
def merge_anonymous_cart(user, session_id: Optional[str]) -> None:
    """Fold the anonymous session cart into the user's cart, then remove the anon cart."""
    if not session_id:
        return
    anon = Cart.objects.filter(session_id=session_id, user__isnull=True).first()
    if anon is None:
        return

    user_cart = Cart.objects.filter(user=user).order_by("id").first()
    if user_cart is None:
        # No user cart yet — just claim the anonymous one.
        anon.user = user
        anon.session_id = None
        anon.save(update_fields=["user", "session_id"])
        return

    for item in list(anon.items.all()):
        existing = user_cart.items.filter(product=item.product).first()
        if existing is None:
            item.cart = user_cart
            item.save(update_fields=["cart"])
        else:
            combined = existing.quantity + item.quantity
            existing.quantity = min(combined, item.product.stock)
            existing.save(update_fields=["quantity"])
            item.delete()
    anon.delete()
