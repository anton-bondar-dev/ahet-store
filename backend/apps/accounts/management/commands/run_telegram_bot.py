import logging
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts import telegram_bot
from apps.accounts.models import LoginChallenge, Profile, TelegramLinkToken
from apps.accounts.telegram import call

POLL_TIMEOUT = 25  # seconds of long-polling per getUpdates request


class Command(BaseCommand):
    help = "Long-poll Telegram getUpdates to handle account linking and 2FA approvals (dev)."

    def log(self, msg):
        self.stdout.write(f"[telegram-bot] {msg}")

    def handle(self, *args, **options):
        # Surface telegram.call() errors (HTTP 409/timeouts/etc.) in this terminal.
        tlog = logging.getLogger("accounts.telegram")
        if not tlog.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("[telegram] %(levelname)s %(message)s"))
            tlog.addHandler(handler)
            tlog.setLevel(logging.INFO)

        if not settings.TELEGRAM_BOT_TOKEN:
            self.stderr.write(
                "TELEGRAM_BOT_TOKEN is not set. Add it to backend/.env and restart."
            )
            return

        # Self-check: confirm the token, then clear any webhook (getUpdates and a
        # webhook are mutually exclusive — a webhook makes getUpdates return 409).
        me = call("getMe", {})
        if not me or not me.get("ok"):
            self.stderr.write(
                "getMe failed — the bot token looks invalid or the network is unreachable. "
                "See the logged error above."
            )
            return
        bot = me["result"]
        self.log(f"Authenticated as @{bot.get('username')} (id {bot.get('id')}).")
        call("deleteWebhook", {"drop_pending_updates": False})
        telegram_bot.register_commands()
        self.log("Registered bot commands (setMyCommands).")
        self.log("Cleared any existing webhook. Polling for updates… (Ctrl-C to stop)")

        offset = None
        while True:
            params = {"timeout": POLL_TIMEOUT}
            if offset is not None:
                params["offset"] = offset
            result = call("getUpdates", params, timeout=POLL_TIMEOUT + 15)
            if not result or not result.get("ok"):
                # Error already logged by telegram.call(); back off briefly.
                time.sleep(2)
                continue
            updates = result.get("result", [])
            if updates:
                self.log(f"Received {len(updates)} update(s).")
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    self._handle(update)
                except Exception as e:  # never let one bad update kill the loop
                    self.stderr.write(f"[telegram-bot] error handling update: {e}")

    def _handle(self, update):
        callback = update.get("callback_query")
        if callback:
            self._handle_callback(callback)
            return
        message = update.get("message")
        if not message:
            self.log(f"Ignored update keys: {list(update.keys())}")
            return
        text = (message.get("text") or "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))
        parts = text.split(maxsplit=1)
        cmd0 = parts[0].split("@", 1)[0].lower() if parts else ""
        # 2FA account linking: /start <token>.
        if cmd0 == "/start" and len(parts) > 1:
            self._handle_start(message)
            return
        # Let users detach their account.
        if cmd0 == "/unlink":
            self.log(f"/unlink from chat {chat_id}")
            telegram_bot.handle_unlink(chat_id)
            return
        # Plain /start with no token → the account-linking hint.
        if cmd0 == "/start":
            self._handle_start(message)
            return
        self.log(f"Ignored message text={text!r} from chat {chat_id}")

    def _handle_start(self, message):
        chat = message["chat"]
        parts = message["text"].split(maxsplit=1)
        if len(parts) < 2:
            self.log(f"/start with no token from chat {chat['id']} — ignoring.")
            call("sendMessage", {"chat_id": chat["id"], "text": "Відкрийте посилання зі сторінки акаунта, щоб підключити Telegram."})
            return
        raw_token = parts[1].strip()
        self.log(f"/start token={raw_token} from chat {chat['id']} (@{chat.get('username')})")
        link = TelegramLinkToken.objects.filter(
            token=raw_token, used_at__isnull=True, expires_at__gte=timezone.now()
        ).first()
        if not link:
            self.log("  → token invalid/expired/used.")
            call("sendMessage", {"chat_id": chat["id"], "text": "Посилання недійсне або протерміноване."})
            return
        profile, _ = Profile.objects.get_or_create(user=link.user)
        profile.telegram_chat_id = str(chat["id"])
        profile.telegram_username = chat.get("username")
        profile.preferred_2fa_method = Profile.METHOD_TELEGRAM
        profile.is_2fa_enabled = True
        profile.save()
        link.used_at = timezone.now()
        link.save(update_fields=["used_at"])
        self.log(f"  → linked user '{link.user.username}' to chat {chat['id']}; 2FA enabled.")
        call("sendMessage", {"chat_id": chat["id"], "text": "✅ Telegram підключено до Ahet Store. Двофакторну автентифікацію увімкнено."})

    def _handle_callback(self, callback):
        data = callback.get("data", "")
        self.log(f"callback data={data!r}")
        if ":" not in data:
            return
        action, challenge_id = data.split(":", 1)
        challenge = LoginChallenge.objects.filter(challenge_id=challenge_id).first()
        if challenge and challenge.status == LoginChallenge.STATUS_PENDING:
            challenge.status = (
                LoginChallenge.STATUS_APPROVED if action == "approve" else LoginChallenge.STATUS_DENIED
            )
            challenge.save(update_fields=["status"])
            self.log(f"  → challenge {challenge_id} set to {challenge.status}.")
        else:
            self.log(f"  → challenge {challenge_id} not pending / not found.")
        answer = "Підтверджено ✅" if action == "approve" else "Відхилено ❌"
        call("answerCallbackQuery", {"callback_query_id": callback["id"], "text": answer})
