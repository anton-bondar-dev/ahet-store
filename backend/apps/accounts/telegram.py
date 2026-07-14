import json
import logging
import ssl
import urllib.error
import urllib.request

from django.conf import settings

API_URL = "https://api.telegram.org/bot{token}/{method}"

logger = logging.getLogger("accounts.telegram")


def _ssl_context():
    # DEBUG-only: skip verification behind a TLS-inspecting proxy / broken CA store.
    if settings.DEBUG and getattr(settings, "TELEGRAM_INSECURE_SKIP_TLS_VERIFY", False):
        logger.warning("TLS verification DISABLED for Telegram calls (dev only).")
        return ssl._create_unverified_context()
    return None


def call(method: str, payload: dict, timeout: int = 60):
    """Call a Telegram Bot API method. Returns the parsed JSON, or None on any
    error (logged). No-ops when no token is set, so local dev works without a
    bot (use the DEBUG dev-approve endpoint instead).

    `timeout` must exceed getUpdates long-poll `timeout` or the socket closes
    before Telegram replies."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN is not set; skipping %s", method)
        return None
    url = API_URL.format(token=token, method=method)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        logger.error("Telegram %s failed: HTTP %s — %s", method, e.code, body)
        return None
    except Exception as e:  # network / timeout / decode
        logger.error("Telegram %s failed: %s", method, e)
        return None


def send_login_prompt(chat_id: str, match_code: int, challenge_id: str):
    text = (
        "🔐 Спроба входу в Ahet Store\n\n"
        f"Код підтвердження: *{match_code}*\n"
        "Переконайтесь, що це число збігається з тим, що показано на сайті, "
        "і підтвердіть вхід."
    )
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Підтвердити", "callback_data": f"approve:{challenge_id}"},
                {"text": "❌ Відхилити", "callback_data": f"deny:{challenge_id}"},
            ]
        ]
    }
    return call(
        "sendMessage",
        {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard},
    )
