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
from apps.core.services.telegram import admin_chat_ids

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
    """True for any of the configured admin/support chats."""
    return str(chat_id) in set(admin_chat_ids())


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


# Explicit slash commands map to the same query handlers as the buttons, so the
# admin can type them regardless of the keyboard's visibility / group privacy.
def _admin_command_handlers():
    return {
        "/stats": _stats_today,
        "/tickets": _open_tickets,
        "/stock": _low_stock,
        "/admin": _admin_panel,
    }


def _button_handlers():
    return {
        BTN_STATS: _stats_today,
        BTN_TICKETS: _open_tickets,
        BTN_LOW_STOCK: _low_stock,
        BTN_ADMIN: _admin_panel,
    }


def _command(text: str) -> str:
    """Normalize a slash command: strip a `@botname` suffix and lowercase.
    Returns '' when the text isn't a command."""
    if not text.startswith("/"):
        return ""
    return text.split()[0].split("@", 1)[0].lower()


# --- Dispatch ----------------------------------------------------------------
def route(chat_id, text: str) -> bool:
    """Shared entry for a (non-linking) incoming message. Handles the universal
    /unlink for anyone, and the admin menu/commands for admin chats only.
    Returns True when it handled the message."""
    text = (text or "").strip()
    if _command(text) == "/unlink":
        handle_unlink(chat_id)
        return True
    if is_admin_chat(chat_id):
        handle_admin_message(chat_id, text)
        return True
    return False


def handle_admin_message(chat_id, text: str) -> None:
    """Route an admin's slash command / button tap to the right reply."""
    text = (text or "").strip()
    cmd = _command(text)
    if cmd in ("/start", "/menu"):
        _send(chat_id, WELCOME, ADMIN_KEYBOARD)
        return
    handler = _admin_command_handlers().get(cmd) or _button_handlers().get(text)
    if handler is not None:
        _send(chat_id, handler())
        return
    # Unknown input — re-show the menu so the keyboard is always available.
    _send(chat_id, "Оберіть дію з меню нижче:", ADMIN_KEYBOARD)


def handle_unlink(chat_id) -> None:
    """Universal /unlink: detach any account(s) bound to this Telegram chat and
    disable Telegram 2FA on them."""
    from apps.accounts.models import Profile

    profiles = list(Profile.objects.filter(telegram_chat_id=str(chat_id)))
    if not profiles:
        _send(chat_id, "ℹ️ До цього чату не прив'язано жодного акаунта.")
        return
    for profile in profiles:
        profile.telegram_chat_id = None
        profile.telegram_username = None
        if profile.preferred_2fa_method == Profile.METHOD_TELEGRAM:
            profile.preferred_2fa_method = Profile.METHOD_NONE
            profile.is_2fa_enabled = False
        profile.save(
            update_fields=[
                "telegram_chat_id",
                "telegram_username",
                "preferred_2fa_method",
                "is_2fa_enabled",
            ]
        )
    _send(
        chat_id,
        f"✅ Telegram відключено від {len(profiles)} акаунт(ів). "
        "Двофакторну автентифікацію через Telegram вимкнено.",
    )


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


# --- Command registration (setMyCommands) ------------------------------------
# Shown for everyone (default scope).
USER_COMMANDS = [
    {"command": "start", "description": "Підключити акаунт / показати меню"},
    {"command": "unlink", "description": "Відключити Telegram від акаунта"},
]
# Shown only inside the configured admin chats (BotCommandScopeChat).
ADMIN_COMMANDS = [
    {"command": "stats", "description": "Статистика дня"},
    {"command": "tickets", "description": "Відкриті тікети"},
    {"command": "stock", "description": "Мало товару (< 5)"},
    {"command": "admin", "description": "Посилання на адмін-панель"},
    {"command": "start", "description": "Показати меню"},
    {"command": "unlink", "description": "Відключити Telegram"},
]


def _as_chat_id(value):
    v = str(value).strip()
    return int(v) if v.lstrip("-").isdigit() else v


def register_commands() -> dict:
    """Register bot commands with Telegram via setMyCommands so they appear in
    the app's command menu. User commands are registered globally (default
    scope); admin commands are registered only for each configured admin chat."""
    results = {"default": call("setMyCommands", {"commands": USER_COMMANDS}), "admins": {}}
    for chat_id in admin_chat_ids():
        results["admins"][chat_id] = call(
            "setMyCommands",
            {
                "commands": ADMIN_COMMANDS,
                "scope": {"type": "chat", "chat_id": _as_chat_id(chat_id)},
            },
        )
    logger.info("Registered Telegram commands (admin chats: %s).", list(results["admins"]))
    return results
