import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

USERNAME = "support"
EMAIL = "noreply.ahetstore@gmail.com"
FIRST_NAME = "ahetStore"
DEFAULT_PASSWORD = "changeme-support-admin"  # override via SUPPORT_ADMIN_PASSWORD


class Command(BaseCommand):
    help = (
        "Create (or update) the unified 'support' help-desk account. Idempotent. "
        "This is a STAFF account, not a superuser — the Owner (superuser) is a "
        "separate account and is the only role that can read the audit log."
    )

    def handle(self, *args, **options):
        password = os.environ.get("SUPPORT_ADMIN_PASSWORD", DEFAULT_PASSWORD)
        if password == DEFAULT_PASSWORD:
            self.stdout.write(self.style.WARNING(
                "Using the default password — set SUPPORT_ADMIN_PASSWORD in the environment "
                "and re-run for a secure one."
            ))

        user, created = User.objects.get_or_create(
            username=USERNAME,
            defaults={"email": EMAIL, "first_name": FIRST_NAME},
        )
        user.email = EMAIL
        user.first_name = FIRST_NAME
        user.is_staff = True
        user.is_superuser = False  # Support Admin ≠ Owner; no superuser powers.
        user.set_password(password)
        user.save()

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} support-admin (staff) '{USERNAME}' <{EMAIL}> (display name '{FIRST_NAME}')."
        ))
