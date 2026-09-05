"""Seed the public portfolio demo: sign-in-ready accounts plus a helpdesk that
looks like a desk somebody actually works at.

Idempotent and self-healing — every run deletes and rebuilds each demo-owned
row, so a visitor who blocks a customer or closes every ticket cannot leave the
demo broken. Safe to run from cron.

    python manage.py seed_demo

Roles:
    customer  — ordinary buyer (order history, bonuses, support chat)
    operator  — is_staff: ticket queue, macros, tags, impersonation
    owner     — is_superuser but NOT is_staff, so the account gets full helpdesk
                and audit-log access while Django's /admin/ stays closed to it.

Dashboard counters are derived from real rows (closed tickets, rating records,
resolved review flags), so the numbers on screen are true, not painted on.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Profile
from apps.cart.models import Cart
from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review, ReviewReply
from apps.support.models import (
    ActionApproval,
    AdminAuditLog,
    ChatMessage,
    CustomerTag,
    CustomerTagAssignment,
    ImpersonationSession,
    SupportMacro,
    SupportRating,
    SupportTicket,
)

PASSWORD = "demo2026"

# The account a visitor signs in as; the rest populate the queue with real names.
PRIMARY = ("demo-customer", "demo.customer@ahet.store", "Олена", "Ковальчук")
EXTRA_CUSTOMERS = [
    ("demo-c2", "demo.c2@ahet.store", "Андрій", "Мельник"),
    ("demo-c3", "demo.c3@ahet.store", "Ірина", "Шевченко"),
    ("demo-c4", "demo.c4@ahet.store", "Максим", "Бондаренко"),
    ("demo-c5", "demo.c5@ahet.store", "Наталія", "Ткаченко"),
    ("demo-c6", "demo.c6@ahet.store", "Сергій", "Лисенко"),
]
OPERATOR = ("demo-operator", "demo.operator@ahet.store", "ahetStore", "")
OWNER = ("demo-owner", "demo.owner@ahet.store", "Demo Owner", "")

TAGS = [("VIP", "#7c3aed"), ("Постійний клієнт", "#0ea5e9"), ("Проблемний", "#ef4444")]

MACROS = [
    ("Вітання", "Доброго дня, {first_name}! Дякую за звернення — вже дивлюся ваше питання."),
    ("Уточнення замовлення", "Підкажіть, будь ласка, номер замовлення — так я швидше знайду його в системі."),
    ("Доставка Новою поштою", "Замовлення передано в Нову пошту. ТТН надійде вам на пошту протягом години."),
    ("Повернення товару", "Оформити повернення можна протягом 14 днів. Надішліть, будь ласка, фото товару та чек."),
    ("Гарантійний випадок", "Це гарантійний випадок. Привезіть товар у сервісний центр або оформіть виїзд кур'єра — ми покриємо доставку."),
    ("Вибачення за затримку", "Перепрошуємо за затримку. Я вже передав ваше замовлення на пріоритетну обробку."),
]

# Closed-ticket material: (subject, customer line, staff line).
RESOLVED = [
    ("Не приходить чек на пошту", "Оплатив, але чек не надійшов.", "Надіслав чек повторно — перевірте, будь ласка, теку «Спам»."),
    ("Помилка при оплаті карткою", "Платіж відхиляється, хоча кошти на карті є.", "Банк відхиляв 3-D Secure. Спробуйте ще раз — зараз усе проходить."),
    ("Змінити адресу доставки", "Помилилася у відділенні Нової пошти.", "Адресу змінив на відділення №12. Замовлення вже їде туди."),
    ("Коли буде в наявності?", "Товар зник із сайту, коли завезете?", "Постачання очікуємо в четвер, поставив вам сповіщення про наявність."),
    ("Не застосовуються бонуси", "На оформленні бонуси не списуються.", "Це була помилка в кошику, вже виправили. Бонуси застосовуються."),
    ("Питання по гарантії", "Скільки гарантії на цю модель?", "24 місяці офіційної гарантії виробника, талон у коробці."),
    ("Дублікат замовлення", "Випадково оформив двічі.", "Другий дублікат скасував, кошти повернуться протягом 3 днів."),
    ("Не приходить SMS з кодом", "Код підтвердження не надходить.", "Перевів вашу двофакторну автентифікацію на Telegram — тепер працює."),
    ("Товар не той, що на фото", "Прийшов інший колір.", "Оформив обмін, кур'єр забере товар завтра, без доплат."),
    ("Рахунок для ФОП", "Потрібен рахунок на юридичну особу.", "Рахунок сформовано і надіслано на вашу пошту."),
    ("Повернення коштів", "Коли повернете гроші за скасоване?", "Кошти вже відправлені, зазвичай банк зараховує за 1-3 дні."),
    ("Змінити спосіб оплати", "Хочу оплатити при отриманні.", "Змінив на накладений платіж, доплат немає."),
]

# Product reviews that the buyer flagged as needing a reply.
FLAGGED = [
    (2, "Пропрацював два тижні і почав вимикатися сам. Дуже прикро."),
    (3, "Комплектація не збігається з описом — немає кабелю в коробці."),
    (2, "Прийшов з подряпиною на корпусі, хоча коробка ціла."),
]
RESOLVED_REVIEWS = [
    (4, "Спершу не вдавалося під'єднати, підтримка допомогла — все працює."),
    (5, "Була проблема з доставкою, вирішили за день. Дякую!"),
    (3, "Довго їхало, але товар справний."),
    (4, "Замінили бракований екземпляр без питань."),
    (5, "Оперативно відповіли і повернули кошти за другий товар."),
    (4, "Гарантійний ремонт зробили швидше, ніж обіцяли."),
]


def _upsert(username, email, first, last, *, staff=False, superuser=False):
    user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
    user.email, user.first_name, user.last_name = email, first, last
    user.is_active, user.is_staff, user.is_superuser = True, staff, superuser
    user.set_password(PASSWORD)
    user.save()
    Profile.objects.get_or_create(user=user)
    return user


def _stamp(model, pk, **fields):
    model.objects.filter(pk=pk).update(**fields)


def _msg(ticket, sender, from_staff, text, *, minutes_ago, internal=False):
    m = ChatMessage.objects.create(
        ticket=ticket, sender=sender, from_staff=from_staff, text=text,
        is_internal=internal, read_by_user=True, read_by_staff=True,
    )
    _stamp(ChatMessage, m.pk, created_at=timezone.now() - timedelta(minutes=minutes_ago))


def _ticket(user, subject, *, priority="normal", status="open", assigned=None, hours_ago=1):
    t = SupportTicket.objects.create(
        user=user, subject=subject, priority=priority, status=status, assigned_to=assigned
    )
    _stamp(SupportTicket, t.pk, created_at=timezone.now() - timedelta(hours=hours_ago))
    return t


class Command(BaseCommand):
    help = "Rebuild the public demo dataset (accounts, queue, metrics, audit trail)."

    @transaction.atomic
    def handle(self, *args, **options):
        primary = _upsert(*PRIMARY)
        extras = [_upsert(*c) for c in EXTRA_CUSTOMERS]
        customers = [primary] + extras
        operator = _upsert(*OPERATOR, staff=True)
        # superuser without is_staff: full helpdesk + audit, no Django /admin/.
        owner = _upsert(*OWNER, superuser=True)

        # --- wipe every demo-owned row so the demo self-heals ---------------
        SupportTicket.objects.filter(user__in=customers).delete()
        Review.objects.filter(user__in=customers).delete()
        Order.objects.filter(user__in=customers).delete()
        Cart.objects.filter(user__in=customers).delete()   # drop carts left by visitors
        AdminAuditLog.objects.filter(admin_user__in=[operator, owner]).delete()
        ImpersonationSession.objects.filter(staff__in=[operator, owner]).delete()
        CustomerTagAssignment.objects.filter(user__in=customers).delete()

        for u in customers:
            p = u.profile
            p.first_name, p.last_name = u.first_name, u.last_name
            p.city = "Київ"
            p.blocked_until, p.blocked_permanent = None, False
            p.save()

        p = primary.profile
        p.phone_number = "+380 67 000 00 00"
        p.delivery_address = "вул. Хрещатик, 22, відділення №5"
        p.bonus_balance = 1250
        p.save()

        op = operator.profile
        op.operator_status = Profile.STATUS_ONLINE
        op.save()

        # --- vocabulary -----------------------------------------------------
        tags = {}
        for label, color in TAGS:
            tag, _ = CustomerTag.objects.get_or_create(label=label, defaults={"color": color})
            tags[label] = tag
        CustomerTagAssignment.objects.create(user=primary, tag=tags["VIP"], assigned_by=operator)
        CustomerTagAssignment.objects.create(user=extras[0], tag=tags["Постійний клієнт"], assigned_by=operator)
        CustomerTagAssignment.objects.create(user=extras[2], tag=tags["Проблемний"], assigned_by=owner)
        for title, content in MACROS:
            SupportMacro.objects.update_or_create(
                title=title, defaults={"content": content, "created_by": owner}
            )

        # --- order history for the account visitors sign in as --------------
        products = list(Product.objects.filter(is_active=True)[:12])
        if products:
            order = Order.objects.create(
                user=primary, first_name="Олена", last_name="Ковальчук",
                phone="+380 67 000 00 00", email=primary.email, city="Київ",
                address="вул. Хрещатик, 22, відділення №5", status="delivered",
                bonus_earned=346, applied_bonuses=0, total_price=Decimal("0.00"),
            )
            total = Decimal("0.00")
            for prod in products[:2]:
                OrderItem.objects.create(
                    order=order, product=prod, product_title=prod.title,
                    quantity=1, price=prod.price,
                )
                total += prod.price
            order.total_price = total
            order.save()
            _stamp(Order, order.pk, created_at=timezone.now() - timedelta(days=9))

        # --- open queue -----------------------------------------------------
        t1 = _ticket(primary, "Не приходить код підтвердження", priority="high", hours_ago=40)
        _msg(t1, primary, False, "Доброго дня! Намагаюся увійти, але код на пошту не приходить уже другий день.", minutes_ago=2400)
        _stamp(SupportTicket, t1.pk,
               last_user_message_at=timezone.now() - timedelta(hours=40),
               updated_at=timezone.now() - timedelta(hours=40))

        t2 = _ticket(primary, "Замовлення №1042 — коли буде доставка?", assigned=operator, hours_ago=5)
        _msg(t2, primary, False, "Вітаю! Замовлення оформила три дні тому, статус досі «Обробка». Коли відправите?", minutes_ago=300)
        _msg(t2, operator, True, "Доброго дня, Олено! Перевіряю ваше замовлення, хвилинку.", minutes_ago=280)
        _msg(t2, operator, True, "Клієнтка VIP — відправити пріоритетно.", minutes_ago=275, internal=True)
        _msg(t2, operator, True, "Замовлення передано в Нову пошту, ТТН надійде на пошту протягом години. Перепрошуємо за затримку.", minutes_ago=270)
        _stamp(SupportTicket, t2.pk,
               last_user_message_at=timezone.now() - timedelta(minutes=300),
               last_staff_message_at=timezone.now() - timedelta(minutes=270),
               updated_at=timezone.now() - timedelta(minutes=270))

        t3 = _ticket(extras[0], "Товар прийшов пошкоджений", priority="urgent", hours_ago=2)
        _msg(t3, extras[0], False, "Отримав монітор, на корпусі тріщина. Що робити далі?", minutes_ago=110)
        _stamp(SupportTicket, t3.pk,
               last_user_message_at=timezone.now() - timedelta(minutes=110),
               updated_at=timezone.now() - timedelta(minutes=110))

        t4 = _ticket(extras[1], "Не можу оформити повернення", priority="high", hours_ago=30)
        _msg(t4, extras[1], False, "Кнопка повернення не працює в кабінеті.", minutes_ago=1800)
        _stamp(SupportTicket, t4.pk,
               last_user_message_at=timezone.now() - timedelta(hours=30),
               updated_at=timezone.now() - timedelta(hours=30))

        t5 = _ticket(extras[2], "Компенсація за затримку доставки", assigned=operator, hours_ago=6)
        _msg(t5, extras[2], False, "Замовлення йшло два тижні замість трьох днів.", minutes_ago=360)
        _msg(t5, operator, True, "Перепрошуємо за затримку. Нарахую вам бонуси як компенсацію.", minutes_ago=340)
        _stamp(SupportTicket, t5.pk,
               last_user_message_at=timezone.now() - timedelta(minutes=360),
               last_staff_message_at=timezone.now() - timedelta(minutes=340),
               updated_at=timezone.now() - timedelta(minutes=340))
        ActionApproval.objects.create(
            requested_by=operator, ticket=t5, action_type=ActionApproval.GRANT_BONUSES,
            amount=2000, status=ActionApproval.PENDING,
        )

        t6 = _ticket(extras[3], "Уточнення щодо гарантії", priority="low", assigned=owner, hours_ago=8)
        _msg(t6, extras[3], False, "Чи покриває гарантія заміну батареї?", minutes_ago=480)
        _msg(t6, owner, True, "Так, протягом перших 12 місяців заміна батареї безкоштовна.", minutes_ago=460)
        _stamp(SupportTicket, t6.pk,
               last_user_message_at=timezone.now() - timedelta(minutes=480),
               last_staff_message_at=timezone.now() - timedelta(minutes=460),
               updated_at=timezone.now() - timedelta(minutes=460))

        t7 = _ticket(extras[4], "Рахунок для оплати від компанії", hours_ago=3)
        _msg(t7, extras[4], False, "Потрібен рахунок на ТОВ, куди надіслати реквізити?", minutes_ago=170)
        _stamp(SupportTicket, t7.pk,
               last_user_message_at=timezone.now() - timedelta(minutes=170),
               updated_at=timezone.now() - timedelta(minutes=170))

        # --- closed history: the source of the dashboard counters -----------
        def close_batch(staff, count, positives, start_day):
            """Create `count` closed tickets credited to `staff`; rate the first
            `positives` 👍 and the rest 👎."""
            rated = 0
            for i in range(count):
                subj, ask, reply = RESOLVED[i % len(RESOLVED)]
                cust = customers[i % len(customers)]
                day = start_day + i
                t = _ticket(cust, subj, status="closed", assigned=staff, hours_ago=day * 24 + 4)
                _msg(t, cust, False, ask, minutes_ago=day * 1440 + 200)
                _msg(t, staff, True, reply, minutes_ago=day * 1440 + 150)
                closed = timezone.now() - timedelta(days=day, hours=2)
                _stamp(SupportTicket, t.pk, closed_by=staff, closed_at=closed,
                       last_user_message_at=timezone.now() - timedelta(minutes=day * 1440 + 200),
                       last_staff_message_at=timezone.now() - timedelta(minutes=day * 1440 + 150),
                       updated_at=closed)
                if rated < positives + 2:
                    SupportRating.objects.create(
                        ticket=t, staff=staff, is_positive=rated < positives
                    )
                    rated += 1

        close_batch(owner, 24, 20, start_day=2)
        close_batch(operator, 16, 13, start_day=3)

        # --- flagged product comments ---------------------------------------
        if products:
            for idx, (stars, text) in enumerate(FLAGGED):
                Review.objects.create(
                    user=customers[idx % len(customers)], product=products[idx],
                    rating=stars, text=text, needs_support=True,
                    support_status=Review.SUPPORT_PENDING,
                )
            for idx, (stars, text) in enumerate(RESOLVED_REVIEWS):
                r = Review.objects.create(
                    user=customers[idx % len(customers)], product=products[idx + 3],
                    rating=stars, text=text, needs_support=True,
                    support_status=Review.SUPPORT_RESOLVED, support_resolved_by=owner,
                    support_resolved_at=timezone.now() - timedelta(days=idx + 1),
                )
                ReviewReply.objects.create(
                    review=r, user=owner,
                    text="Дякуємо за відгук! Радий, що питання вирішилося.",
                )

        # --- audit trail: recent enough to fill the visible page ------------
        A = AdminAuditLog
        entries = [
            (operator, A.ACTION_IMPERSONATE_END, primary, t3, {}, 92),
            (operator, A.ACTION_IMPERSONATE_START, primary, t3, {}, 100),
            (owner, A.ACTION_CLOSE_TICKET, extras[3], t6, {}, 150),
            (operator, A.ACTION_GRANT_BONUSES, extras[2], t5, {"amount": 200}, 260),
            (operator, A.ACTION_TAG_ADD, primary, None, {"tag": "VIP"}, 300),
            (owner, A.ACTION_TAG_ADD, extras[2], None, {"tag": "Проблемний"}, 340),
            (operator, A.ACTION_GRANT_BONUSES, extras[0], t3, {"amount": 500}, 420),
            (owner, A.ACTION_CLOSE_TICKET, extras[1], None, {}, 500),
            (operator, A.ACTION_TAG_ADD, extras[0], None, {"tag": "Постійний клієнт"}, 620),
            (operator, A.ACTION_IMPERSONATE_END, extras[1], None, {}, 700),
            (operator, A.ACTION_IMPERSONATE_START, extras[1], None, {}, 706),
            (owner, A.ACTION_GRANT_BONUSES, extras[4], None, {"amount": 1000}, 820),
            (owner, A.ACTION_CLOSE_TICKET, primary, None, {}, 900),
            (operator, A.ACTION_TAG_REMOVE, extras[3], None, {"tag": "Проблемний"}, 1010),
        ]
        for admin_user, action, target, ticket, meta, minutes_ago in entries:
            row = A.objects.create(
                admin_user=admin_user, action_type=action, target_user=target,
                ticket=ticket, meta=meta,
            )
            _stamp(A, row.pk, created_at=timezone.now() - timedelta(minutes=minutes_ago))

        s = ImpersonationSession.objects.create(staff=operator, target_user=primary)
        _stamp(ImpersonationSession, s.pk,
               started_at=timezone.now() - timedelta(minutes=100),
               ended_at=timezone.now() - timedelta(minutes=92))

        self.stdout.write(self.style.SUCCESS(
            "Demo dataset rebuilt.\n"
            f"  customer  {PRIMARY[1]} / {PASSWORD}\n"
            f"  operator  {OPERATOR[1]} / {PASSWORD}  (staff)\n"
            f"  owner     {OWNER[1]} / {PASSWORD}  (superuser, no Django admin)\n"
            f"  {SupportTicket.objects.filter(status='open').count()} open tickets, "
            f"{SupportTicket.objects.filter(status='closed').count()} closed, "
            f"{SupportRating.objects.count()} ratings, "
            f"{A.objects.count()} audit entries, "
            f"{Review.objects.filter(needs_support=True).count()} flagged reviews."
        ))
