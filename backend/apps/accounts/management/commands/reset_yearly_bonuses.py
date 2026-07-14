from django.core.management.base import BaseCommand

from apps.accounts.models import Profile


class Command(BaseCommand):
    help = "Reset every profile's bonus_balance to 0 (yearly expiry — run via cron on Jan 1)."

    def handle(self, *args, **options):
        updated = Profile.objects.exclude(bonus_balance=0).update(bonus_balance=0)
        self.stdout.write(
            self.style.SUCCESS(f"Reset bonus_balance for {updated} profile(s).")
        )
