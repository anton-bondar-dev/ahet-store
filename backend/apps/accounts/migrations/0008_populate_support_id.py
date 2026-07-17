import secrets

from django.db import migrations

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def populate_support_ids(apps, schema_editor):
    Profile = apps.get_model("accounts", "Profile")
    existing = set(
        Profile.objects.exclude(support_id__isnull=True).values_list("support_id", flat=True)
    )
    for profile in Profile.objects.filter(support_id__isnull=True):
        while True:
            candidate = "USR-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))
            if candidate not in existing:
                existing.add(candidate)
                break
        profile.support_id = candidate
        profile.save(update_fields=["support_id"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_profile_operator_status_profile_support_id")]
    operations = [migrations.RunPython(populate_support_ids, migrations.RunPython.noop)]
