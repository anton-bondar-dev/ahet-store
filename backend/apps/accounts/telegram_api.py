"""Telegram webhook receiver for the interactive admin bot.

Mounted at POST /api/telegram/webhook. Telegram POSTs updates here (prod). For
security we (a) optionally verify a shared secret sent by Telegram, and (b) only
act on messages from the configured admin chat. Always returns 200 so Telegram
does not retry.

In dev, `manage.py run_telegram_bot` long-polls instead and shares the same
handler (`telegram_bot.handle_admin_message`).
"""

import json
import logging

from django.conf import settings
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.accounts import telegram_bot

router = Router(tags=["telegram"])
logger = logging.getLogger("accounts.telegram")


class OkOut(Schema):
    ok: bool


@router.post("/webhook", response=OkOut, auth=None)
def telegram_webhook(request):
    # Reject forged calls: when TELEGRAM_WEBHOOK_SECRET is set we register it with
    # Telegram, which then echoes it back in this header on every update.
    secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
    if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
        raise HttpError(403, "forbidden")

    try:
        update = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return {"ok": True}

    message = update.get("message") or update.get("edited_message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    text = message.get("text") or ""

    # Security: only the admin chat drives the menu / sees DB summaries.
    if text and telegram_bot.is_admin_chat(chat_id):
        try:
            telegram_bot.handle_admin_message(chat_id, text)
        except Exception as exc:  # never fail the webhook (Telegram would retry)
            logger.error("Telegram webhook handler error: %s", exc)

    return {"ok": True}
