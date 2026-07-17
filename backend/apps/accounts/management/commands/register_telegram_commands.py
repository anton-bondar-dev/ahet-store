from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import telegram_bot


class Command(BaseCommand):
    help = (
        "Register the bot's /start and /unlink commands with Telegram "
        "(setMyCommands) so they show up in the app's command menu."
    )

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set (see backend/.env).")

        res = telegram_bot.register_commands()
        ok = bool(res and res.get("ok"))
        self.stdout.write(
            self.style.SUCCESS(f"Registered /start and /unlink (ok={ok}).")
        )
