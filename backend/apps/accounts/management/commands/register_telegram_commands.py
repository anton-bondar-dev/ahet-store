from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import telegram_bot


class Command(BaseCommand):
    help = (
        "Register the bot's commands with Telegram (setMyCommands) so they show "
        "up in the app's command menu. User commands are global; the admin "
        "commands (/stats, /tickets, /stock, /admin) are scoped to each "
        "TELEGRAM_ADMIN_CHAT_ID."
    )

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set (see backend/.env).")

        results = telegram_bot.register_commands()
        default_ok = bool(results.get("default") and results["default"].get("ok"))
        self.stdout.write(
            self.style.SUCCESS(f"User commands (default scope): ok={default_ok}")
        )
        admins = results.get("admins", {})
        if not admins:
            self.stdout.write(
                self.style.WARNING(
                    "No admin chats configured — set TELEGRAM_ADMIN_CHAT_ID "
                    "(comma-separated for several)."
                )
            )
        for chat_id, res in admins.items():
            ok = bool(res and res.get("ok"))
            self.stdout.write(
                self.style.SUCCESS(f"Admin commands for chat {chat_id}: ok={ok}")
            )
