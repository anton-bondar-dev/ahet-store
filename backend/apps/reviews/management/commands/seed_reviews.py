from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.reviews.models import Review, ReviewReply

SEED_PREFIX = "seed_"

# Mock reviewers (username, first name) — created if missing, cleaned on re-run.
MOCK_USERS = [
    ("seed_oksana", "Оксана"),
    ("seed_petro", "Петро"),
    ("seed_ihor", "Ігор"),
    ("seed_maryna", "Марина"),
    ("seed_andriy", "Андрій"),
]


class Command(BaseCommand):
    help = "Seed realistic Ukrainian reviews + replies covering every UI state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            help="Username of YOUR main account (gets reviews for the dashboard test).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete ALL existing reviews first for a pristine demo state.",
        )

    def handle(self, *args, **options):
        products = list(Product.objects.order_by("id"))
        if len(products) < 4:
            self.stderr.write("Need at least 4 products to seed all scenarios.")
            return

        if options["clear"]:
            deleted = Review.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing review rows."))

        mock = self._ensure_mock_users()
        admin = self._ensure_admin()
        main = self._resolve_main_user(options["user"])
        if main is None:
            return

        # Scenario products (4) + two products for the main user's dashboard.
        p_standard, p_critical, p_community, p_mixed = products[:4]
        main_products = products[4:6] if len(products) >= 6 else products[:2]

        # Idempotency: drop previously-seeded data (cascades to replies).
        Review.objects.filter(user__username__startswith=SEED_PREFIX).delete()
        Review.objects.filter(user=main, product__in=main_products).delete()

        touched = set()

        # 1) Standard — a clean 5★ review, no replies.
        self._review(
            mock["seed_oksana"], p_standard, 5,
            "Чудовий вибір! Пристрій працює швидко, батарея тримає цілий день. "
            "Доставка Новою поштою зайняла лише один день. Дуже задоволена покупкою!",
        )
        touched.add(p_standard.id)

        # 2) Admin interaction — critical review + apologetic admin reply.
        r_crit = self._review(
            mock["seed_petro"], p_critical, 1,
            "Дуже розчарований. Товар прийшов із подряпинами на корпусі, а на екрані "
            "помітні биті пікселі. За такі гроші очікував значно кращої якості.",
        )
        self._reply(
            r_crit, admin,
            "Вітаємо! Щиро перепрошуємо за цю ситуацію. Будь ласка, зверніться до нашої "
            "підтримки — ми оперативно замінимо товар або повернемо кошти. Дякуємо, що "
            "повідомили, і ще раз вибачте за незручності.",
        )
        touched.add(p_critical.id)

        # 3) Community discussion — 3 regular-user replies (tests the toggle).
        r_comm = self._review(
            mock["seed_ihor"], p_community, 4,
            "Загалом задоволений, але хотілося б більше портів USB. Хтось знає, чи "
            "підтримує пристрій швидку зарядку через Type-C?",
        )
        self._reply(r_comm, mock["seed_oksana"], "Так, підтримує! Заряджається від павербанка без проблем.")
        self._reply(r_comm, mock["seed_maryna"], "Погоджуюсь щодо портів — доводиться носити з собою USB-хаб.")
        self._reply(r_comm, mock["seed_andriy"], "Користуюсь уже пів року, жодних нарікань. Раджу докупити хаб і буде ідеально.")
        touched.add(p_community.id)

        # 4) Mixed thread — BOTH an admin reply and regular-user replies.
        r_mix = self._review(
            mock["seed_maryna"], p_mixed, 2,
            "Пристрій непоганий, але вентилятор дуже шумить під навантаженням. "
            "Трохи шкодую про покупку.",
        )
        self._reply(
            r_mix, admin,
            "Дякуємо за відгук! Спробуйте оновити BIOS до останньої версії — це часто "
            "вирішує проблему з шумом. Якщо не допоможе, ми безкоштовно проведемо "
            "діагностику в сервісному центрі.",
        )
        self._reply(r_mix, mock["seed_petro"], "У мене та сама проблема з шумом вентилятора.")
        self._reply(r_mix, mock["seed_andriy"], "Спробуйте перемкнути режим живлення на «тихий» — мені допомогло.")
        touched.add(p_mixed.id)

        # 5) Dashboard — 2 reviews on the main account (+ an admin reply on one,
        #    so you also see admin styling on your own review's page).
        self._review(
            main, main_products[0], 5,
            "Відмінна покупка! Ціна повністю відповідає якості, усе працює як заявлено. "
            "Рекомендую цей магазин.",
        )
        touched.add(main_products[0].id)
        r_main2 = self._review(
            main, main_products[1], 3,
            "Сам товар без нарікань, але доставка затрималася на три дні. "
            "Сподіваюсь, наступного разу буде швидше.",
        )
        self._reply(
            r_main2, admin,
            "Дякуємо за ваш відгук і вибачте за затримку! Ми вже працюємо над "
            "покращенням логістики. Гарного користування покупкою!",
        )
        touched.add(main_products[1].id)

        # Refresh denormalized rating aggregates on every touched product.
        for product in Product.objects.filter(id__in=touched):
            product.recompute_rating()

        self.stdout.write(self.style.SUCCESS(
            f"Seeded reviews on {len(touched)} products. "
            f"Dashboard reviews assigned to '{main.username}' "
            f"({main_products[0].title[:30]}…, {main_products[1].title[:30]}…)."
        ))

    # --- helpers -------------------------------------------------------------

    def _ensure_mock_users(self):
        mock = {}
        for uname, first in MOCK_USERS:
            u, _ = User.objects.get_or_create(
                username=uname,
                defaults={"first_name": first, "email": f"{uname}@example.com"},
            )
            if u.first_name != first:
                u.first_name = first
                u.save(update_fields=["first_name"])
            mock[uname] = u
        return mock

    def _ensure_admin(self):
        admin = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(is_staff=True).first()
        )
        if admin is None:
            admin, _ = User.objects.get_or_create(
                username="seed_admin",
                defaults={"first_name": "Адміністратор", "email": "admin@ahet.store"},
            )
            admin.is_staff = True
            admin.save(update_fields=["is_staff"])
        self.stdout.write(f"Admin replies authored by: '{admin.username}' (is_staff={admin.is_staff}).")
        return admin

    def _resolve_main_user(self, username):
        if username:
            u = User.objects.filter(username=username).first()
            if u is None:
                self.stderr.write(f"User '{username}' not found. Register/login once, then retry.")
            return u
        u = (
            User.objects.exclude(username__startswith=SEED_PREFIX)
            .order_by("-date_joined")
            .first()
        )
        if u is None:
            self.stderr.write("No account found. Register/login once, then re-run with --user=<username>.")
            return None
        self.stdout.write(self.style.WARNING(
            f"No --user given; using most recent account: '{u.username}'. "
            f"Re-run with --user=<your username> to target your real account."
        ))
        return u

    def _review(self, user, product, rating, text):
        review, _ = Review.objects.update_or_create(
            user=user, product=product, defaults={"rating": rating, "text": text}
        )
        return review

    def _reply(self, review, user, text):
        return ReviewReply.objects.create(review=review, user=user, text=text)
