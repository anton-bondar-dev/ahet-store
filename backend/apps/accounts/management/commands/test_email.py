import traceback

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Diagnose email/SMTP: print the active config and attempt a real send."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            type=str,
            default=None,
            help="Recipient address (defaults to EMAIL_HOST_USER).",
        )

    def handle(self, *args, **options):
        pw = settings.EMAIL_HOST_PASSWORD or ""
        masked = f"{'*' * len(pw)} (length {len(pw)})" if pw else "(EMPTY!)"

        self.stdout.write("=== Active email settings ===")
        self.stdout.write(f"  EMAIL_BACKEND       = {settings.EMAIL_BACKEND}")
        self.stdout.write(f"  EMAIL_HOST          = {settings.EMAIL_HOST}")
        self.stdout.write(f"  EMAIL_PORT          = {settings.EMAIL_PORT}")
        self.stdout.write(f"  EMAIL_USE_TLS       = {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"  EMAIL_HOST_USER     = {settings.EMAIL_HOST_USER or '(EMPTY!)'}")
        self.stdout.write(f"  EMAIL_HOST_PASSWORD = {masked}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL  = {settings.DEFAULT_FROM_EMAIL}")

        # Common misconfigurations, surfaced up front.
        if "console" in settings.EMAIL_BACKEND:
            self.stdout.write(self.style.WARNING(
                "\nBackend is CONSOLE — EMAIL_HOST_USER is empty, so nothing is really sent. "
                "The .env vars aren't loaded (restart the server / check the .env path)."
            ))
        if pw and " " in pw:
            self.stdout.write(self.style.WARNING(
                "\nEMAIL_HOST_PASSWORD contains SPACES — Gmail App Passwords must be pasted "
                "without spaces. This commonly causes 'authentication failed'."
            ))

        recipient = options["to"] or settings.EMAIL_HOST_USER
        if not recipient:
            self.stderr.write("No recipient — pass --to <address> or set EMAIL_HOST_USER.")
            return

        self.stdout.write(f"\nSending a test email to {recipient} …")
        try:
            sent = send_mail(
                subject="Ahet Store — тест SMTP",
                message=(
                    "Це тестовий лист від Ahet Store.\n\n"
                    "Якщо ви його отримали — SMTP налаштовано правильно."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,  # surface the real error instead of hiding it
            )
            self.stdout.write(self.style.SUCCESS(
                f"\nsend_mail() returned {sent}. Check the inbox (and the Spam folder)."
            ))
        except Exception as exc:  # noqa: BLE001 — we want to show any failure
            self.stderr.write(self.style.ERROR(
                f"\nsend_mail() FAILED: {type(exc).__name__}: {exc}\n"
            ))
            self.stderr.write("Full traceback:\n" + traceback.format_exc())
            self.stderr.write(self.style.WARNING(
                "Hints: 535 auth → wrong App Password / 2-Step not enabled; "
                "timeout → port 587 blocked or wrong host; SSL/certificate → local "
                "TLS-inspecting proxy."
            ))
