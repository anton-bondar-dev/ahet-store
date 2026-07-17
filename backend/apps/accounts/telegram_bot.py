"""Interactive admin bot: a persistent navigation menu (ReplyKeyboardMarkup) for
the Team Lead / support staff.

Pure logic, shared by both transports:
  * the long-poll runner (`manage.py run_telegram_bot`) — used in dev, and
  * the webhook endpoint (`POST /api/telegram/webhook`) — used in prod.

All replies use HTML parse_mode. Only the configured admin chat can drive the
menu (`is_admin_chat`), so the DB summaries are never exposed to other users.
"""

import html
import logging

from django.conf import settings
from django.utils import timezone

from apps.accounts.telegram import call

logger = logging.getLogger("accounts.telegram")

LOW_STOCK_THRESHOLD = 5
MAX_LIST = 20  # cap list replies so a huge catalog/queue can't overflow a message

# Menu button captions — must match byte-for-byte what Telegram sends back when
# the admin taps a Reply-keyboard button.
BTN_STATS = "📊 Статистика дня"
BTN_TICKETS = "💬 Відкриті тікети"
BTN_LOW_STOCK = "📦 Мало товару (< 5)"
BTN_ADMIN = "🌐 Адмін-панель"

ADMIN_KEYBOARD = {
    "keyboard": [
        [{"text": BTN_STATS}, {"text": BTN_TICKETS}],
        [{"text": BTN_LOW_STOCK}, {"text": BTN_ADMIN}],
    ],
    "resize_keyboard": True,
}

WELCOME = (
    "👋 <b>Вітаю в адмін-панелі Ahet Store!</b>\n"
    "Оберіть дію з меню нижче."
)


def is_admin_chat(chat_id) -> bool:
    """True only for the configured admin/support chat."""
    admin = str(getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", "") or "")
    return bool(admin) and str(chat_id) == admin


def _send(chat_id, text: str, keyboard: dict | None = None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if keyboard is not None:
        payload["reply_markup"] = keyboard
    return call("sendMessage", payload)


# --- Dispatch ----------------------------------------------------------------
def handle_admin_message(chat_id, text: str) -> None:
    """Route an admin's text/button tap to the right reply."""
    text = (text or "").strip()
    if text in ("/start", "/menu", "menu"):
        _send(chat_id, WELCOME, ADMIN_KEYBOARD)
        return
    handler = {
        BTN_STATS: _stats_today,
        BTN_TICKETS: _open_tickets,
        BTN_LOW_STOCK: _low_stock,
        BTN_ADMIN: _admin_panel,
    }.get(text)
    if handler is not None:
        _send(chat_id, handler())
        return
    # Unknown input — re-show the menu so the keyboard is always available.
    _send(chat_id, "Оберіть дію з меню нижче:", ADMIN_KEYBOARD)


# --- Query handlers (return HTML strings) ------------------------------------
def _stats_today() -> str:
    from apps.catalog.models import Product
    from apps.support.models import SupportTicket

    today = timezone.localdate()
    new_tickets = SupportTicket.objects.filter(created_at__date=today).count()
    low_stock = Product.objects.filter(stock__lt=LOW_STOCK_THRESHOLD).count()
    return (
        "📊 <b>Статистика за сьогодні</b>\n"
        f"Сьогодні: <b>{new_tickets}</b> нових тікетів, "
        f"<b>{low_stock}</b> товарів закінчуються."
    )


def _open_tickets() -> str:
    from django.db.models import Count, Q

    from apps.support.models import SupportTicket

    qs = (
        SupportTicket.objects.filter(status=SupportTicket.STATUS_OPEN)
        .annotate(
            unread=Count(
                "messages",
                filter=Q(messages__from_staff=False, messages__read_by_staff=False),
            )
        )
        .filter(unread__gt=0)
        .select_related("user")
        .order_by("-updated_at")
    )
    count = qs.count()
    if count == 0:
        return "💬 <b>Відкриті тікети</b>\nНемає чатів з непрочитаними повідомленнями. 🎉"
    if count > MAX_LIST:
        return (
            f"💬 <b>Відкриті тікети</b>\n"
            f"Активних чатів з непрочитаними: <b>{count}</b> "
            f"(забагато, щоб показати списком)."
        )
    lines = []
    for ticket in qs[:MAX_LIST]:
        user = ticket.user
        name = user.first_name or user.email or user.username
        lines.append(
            f"• {html.escape(name, quote=False)} — "
            f"{ticket.unread} непрочит. (тікет #{ticket.id})"
        )
    return f"💬 <b>Відкриті тікети</b> ({count})\n" + "\n".join(lines)


def _low_stock() -> str:
    from apps.catalog.models import Product

    low = Product.objects.filter(stock__lt=LOW_STOCK_THRESHOLD).order_by("stock", "title")
    count = low.count()
    if count == 0:
        return "📦 <b>Мало товару (&lt; 5)</b>\nНемає товарів, що закінчуються. 👍"
    lines = [
        f"- {html.escape(p.title, quote=False)}: {p.stock} шт."
        for p in low[:MAX_LIST]
    ]
    body = "\n".join(lines)
    if count > MAX_LIST:
        body += f"\n… та ще {count - MAX_LIST}."
    return f"📦 <b>Мало товару (&lt; 5)</b> — {count}\n{body}"


def _admin_panel() -> str:
    base = str(getattr(settings, "FRONTEND_URL", "http://localhost:5173")).rstrip("/")
    return f"🌐 <b>Адмін-панель</b>\n{base}/support/admin"
