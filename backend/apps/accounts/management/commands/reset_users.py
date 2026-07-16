from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# The one account that must survive a wipe — the Owner (Team Lead).
OWNER_EMAIL = "bondara254@gmail.com"


class Command(BaseCommand):
    help = (
        "DANGER: wipe the user base, keeping only the Owner "
        f"({OWNER_EMAIL}). Also clears ALL orders, carts, and support tickets."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Required. Confirms you intend a full, destructive wipe of non-owner users.",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Skip the interactive confirmation prompt (for scripted use).",
        )

    def handle(self, *args, **options):
        # Safety gate 1: must explicitly opt in with --all.
        if not options["all"]:
            raise CommandError(
                "Refusing to run without --all — this permanently wipes the user base."
            )

        # Safety gate 2: never proceed if the Owner is missing (would delete everyone).
        owner = User.objects.filter(email__iexact=OWNER_EMAIL).first()
        if owner is None:
            raise CommandError(
                f"Owner account ({OWNER_EMAIL}) not found — aborting so nothing is wiped."
            )

        victims = User.objects.exclude(pk=owner.pk)
        count = victims.count()

        self.stdout.write(self.style.WARNING(
            f"About to PERMANENTLY delete {count} user(s), keeping only {owner.email}, "
            "and clear ALL orders, carts, and support tickets. This cannot be undone."
        ))

        # Safety gate 3: interactive confirmation (unless --noinput).
        if not options["noinput"]:
            answer = input('Type "wipe" to proceed, anything else to abort: ')
            if answer.strip().lower() != "wipe":
                self.stdout.write(self.style.NOTICE("Aborted — nothing was deleted."))
                return

        # Imported lazily so the command still loads if an app is unavailable.
        from apps.cart.models import Cart
        from apps.orders.models import Order
        from apps.support.models import SupportTicket

        with transaction.atomic():
            Order.objects.all().delete()          # cascades OrderItems
            Cart.objects.all().delete()           # cascades CartItems
            SupportTicket.objects.all().delete()  # cascades messages / ratings
            victims.delete()                      # cascades profiles, reviews, etc.

        self.stdout.write(self.style.SUCCESS(
            f"Done. Deleted {count} user(s); cleared all orders, carts and tickets. "
            f"Owner {owner.email} preserved."
        ))
