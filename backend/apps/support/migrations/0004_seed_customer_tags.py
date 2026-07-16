from django.db import migrations

DEFAULT_TAGS = [
    ("VIP", "#f59e0b"),
    ("Проблемний", "#dc2626"),
    ("Часті повернення", "#6366f1"),
]


def seed_tags(apps, schema_editor):
    CustomerTag = apps.get_model("support", "CustomerTag")
    for label, color in DEFAULT_TAGS:
        CustomerTag.objects.get_or_create(label=label, defaults={"color": color})


def unseed_tags(apps, schema_editor):
    CustomerTag = apps.get_model("support", "CustomerTag")
    CustomerTag.objects.filter(label__in=[label for label, _ in DEFAULT_TAGS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("support", "0003_customertag_chatmessage_is_system_chatmessage_meta_and_more"),
    ]
    operations = [migrations.RunPython(seed_tags, unseed_tags)]
