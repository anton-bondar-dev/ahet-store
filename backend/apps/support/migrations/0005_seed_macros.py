from django.db import migrations

DEFAULT_MACROS = [
    ("Запит номера замовлення", "Вітаю, {first_name}! Уточніть, будь ласка, номер вашого замовлення, щоб я міг допомогти."),
    ("Вибачення за очікування", "{first_name}, перепрошуємо за очікування! Вже розбираємось із вашим питанням."),
    ("Питання вирішено", "{first_name}, ваше питання вирішено. Якщо буде щось іще — звертайтесь! Гарного дня 🙂"),
    ("Уточнення деталей", "Дякуємо за звернення! Щоб швидше допомогти, опишіть, будь ласка, проблему детальніше."),
]


def seed_macros(apps, schema_editor):
    SupportMacro = apps.get_model("support", "SupportMacro")
    for title, content in DEFAULT_MACROS:
        SupportMacro.objects.get_or_create(title=title, defaults={"content": content})


def unseed_macros(apps, schema_editor):
    SupportMacro = apps.get_model("support", "SupportMacro")
    SupportMacro.objects.filter(title__in=[t for t, _ in DEFAULT_MACROS]).delete()


class Migration(migrations.Migration):
    dependencies = [("support", "0004_seed_customer_tags")]
    operations = [migrations.RunPython(seed_macros, unseed_macros)]
