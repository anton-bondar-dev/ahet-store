import uuid

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Seeded team created after the wipe. (email → display name, password, is_owner)
SEED = [
    ("lead@ahetstore.com", "Тімлід", "admin1234", True),
    ("op1@ahetstore.com", "Оператор 1", "operator1234", False),
    ("op2@ahetstore.com", "Оператор 2", "operator1234", False),
    ("op3@ahetstore.com", "Оператор 3", "operator1234", False),
]


class Command(BaseCommand):
    help = (
        "DANGER: permanently delete EVERY user (plus all orders, carts and "
        "support tickets), then seed 1 Team Lead + 3 Operators."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Required. Confirms a full wipe of ALL users (no exceptions).",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Skip the interactive confirmation prompt (for scripted use).",
        )

    def handle(self, *args, **options):
        if not options["all"]:
            raise CommandError("Refusing to run without --all — this wipes EVERY user.")

        total = User.objects.count()
        self.stdout.write(self.style.WARNING(
            f"About to PERMANENTLY delete ALL {total} user(s) and clear all orders, "
            "carts and support tickets, then seed 1 Team Lead + 3 Operators. "
            "This cannot be undone."
        ))
        if not options["noinput"]:
            if input('Type "wipe" to proceed, anything else to abort: ').strip().lower() != "wipe":
                self.stdout.write(self.style.NOTICE("Aborted — nothing changed."))
                return

        from apps.accounts.models import Profile
        from apps.cart.models import Cart
        from apps.orders.models import Order
        from apps.support.models import SupportTicket

        with transaction.atomic():
            Order.objects.all().delete()
            Cart.objects.all().delete()
            SupportTicket.objects.all().delete()
            User.objects.all().delete()  # no exceptions this time

            for email, name, password, is_owner in SEED:
                username = f"u-{uuid.uuid4().hex[:20]}"
                if is_owner:
                    user = User.objects.create_superuser(
                        username=username, email=email, password=password
                    )
                    user.first_name = name
                    user.save(update_fields=["first_name"])
                else:
                    user = User.objects.create_user(
                        username=username, email=email, password=password, first_name=name
                    )
                    user.is_staff = True
                    user.save(update_fields=["is_staff"])
                Profile.objects.create(user=user, first_name=name)

        self.stdout.write(self.style.SUCCESS(f"Done. Wiped {total} user(s); seeded team:"))
        for email, name, _pw, is_owner in SEED:
            self.stdout.write(f"  {'Team Lead ' if is_owner else 'Operator  '} {name} <{email}>")
