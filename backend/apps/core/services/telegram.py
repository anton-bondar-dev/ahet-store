"""Fire-and-forget Telegram alerts to the Team Lead / support chat.

Distinct from `apps.accounts.telegram` (the 2FA login bot): this is a tiny,
best-effort notifier. It never blocks the request/response cycle (the HTTP call
runs on a background daemon thread with a strict timeout) and never raises —
missing config or network errors are logged and swallowed.
"""

import logging
import threading

import requests
from django.conf import settings

logger = logging.getLogger("core.telegram")

_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT_SECONDS = 3


def admin_chat_ids() -> list[str]:
    """Configured admin chat id(s). TELEGRAM_ADMIN_CHAT_ID may be a single id or
    a comma-separated list, so one bot can serve several staff / a group."""
    raw = getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", "") or ""
    return [c.strip() for c in str(raw).split(",") if c.strip()]


def _deliver(token: str, chat_ids: list[str], message: str) -> None:
    """Runs on a background thread — must not raise. Fans the alert out to every
    configured admin chat."""
    for chat_id in chat_ids:
        try:
            resp = requests.post(
                _SEND_MESSAGE_URL.format(token=token),
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=_TIMEOUT_SECONDS,
            )
            if resp.status_code != 200:
                logger.error(
                    "Telegram admin alert to %s failed: HTTP %s — %s",
                    chat_id,
                    resp.status_code,
                    resp.text[:300],
                )
        except requests.RequestException as exc:
            logger.error("Telegram admin alert to %s network error: %s", chat_id, exc)
        except Exception as exc:  # never let a notifier take down anything
            logger.error("Telegram admin alert to %s unexpected error: %s", chat_id, exc)


def send_admin_alert(message: str) -> None:
    """Send an HTML-formatted alert to the admin chat(s), off the request thread.

    No-ops (with a logged warning) when the bot token or admin chat id is not
    configured, so the app runs fine without Telegram set up.
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_ids = admin_chat_ids()
    if not token or not chat_ids:
        logger.warning(
            "Admin alert skipped: TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_CHAT_ID not set."
        )
        return
    # Daemon thread so a hung request never blocks shutdown, and the response
    # returns immediately.
    threading.Thread(
        target=_deliver,
        args=(token, chat_ids, message),
        daemon=True,
    ).start()
