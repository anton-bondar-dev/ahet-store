"""Helpers for the 2FA Telegram bot: the /unlink command and command-menu
registration.

The 2FA flow itself (deep-link /start <token> and the Approve/Deny callbacks)
lives in the long-poll runner (`manage.py run_telegram_bot`).
"""

import logging

from apps.accounts.telegram import call

logger = logging.getLogger("accounts.telegram")

# Registered globally (default scope) so they show up in the app's command menu.
USER_COMMANDS = [
    {"command": "start", "description": "Підключити акаунт до Telegram"},
    {"command": "unlink", "description": "Відключити Telegram від акаунта"},
]


def _send(chat_id, text: str):
    return call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


def handle_unlink(chat_id) -> None:
    """Detach any account(s) bound to this Telegram chat and disable Telegram
    2FA on them."""
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


def register_commands():
    """Register /start and /unlink with Telegram (setMyCommands), globally, so
    they appear in the app's command menu for all users."""
    result = call("setMyCommands", {"commands": USER_COMMANDS})
    logger.info("Registered Telegram user commands (setMyCommands).")
    return result
