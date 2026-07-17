import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.telegram import call

WEBHOOK_PATH = "/api/telegram/webhook"


class Command(BaseCommand):
    help = (
        "Register (or delete) the Telegram webhook for the admin bot. "
        "A webhook replaces long-polling — do not run run_telegram_bot at the "
        "same time.\n\n"
        "  python manage.py set_telegram_webhook https://store.example.com\n"
        "  python manage.py set_telegram_webhook --delete"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "base_url",
            nargs="?",
            help="Public HTTPS base URL of the site (e.g. https://store.example.com).",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Remove the webhook (revert to long-polling).",
        )

    def handle(self, *args, **opts):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set (see backend/.env).")

        if opts["delete"]:
            res = call("deleteWebhook", {"drop_pending_updates": False})
            self.stdout.write(self.style.SUCCESS(f"deleteWebhook → {res}"))
            return

        base = (
            opts["base_url"]
            or os.environ.get("PUBLIC_BASE_URL")
            or getattr(settings, "PUBLIC_BASE_URL", "")
        )
        if not base:
            raise CommandError(
                "Provide the public HTTPS base URL as an argument "
                "(or set PUBLIC_BASE_URL)."
            )
        if not base.startswith("https://"):
            raise CommandError("Telegram requires an HTTPS webhook URL.")

        url = base.rstrip("/") + WEBHOOK_PATH
        payload = {"url": url, "allowed_updates": ["message", "callback_query"]}
        secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        if secret:
            payload["secret_token"] = secret

        res = call("setWebhook", payload)
        if not res or not res.get("ok"):
            raise CommandError(f"setWebhook failed: {res}")
        self.stdout.write(self.style.SUCCESS(f"Webhook registered → {url}"))
        if secret:
            self.stdout.write("Secret token enabled (X-Telegram-Bot-Api-Secret-Token).")
        self.stdout.write(
            self.style.WARNING(
                "A webhook disables long-polling — stop run_telegram_bot if it's running."
            )
        )
