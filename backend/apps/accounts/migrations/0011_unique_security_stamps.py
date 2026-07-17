import uuid

from django.db import migrations


def randomize_stamps(apps, schema_editor):
    # AddField with a callable default assigns the SAME value to all existing
    # rows — give each profile its own stamp so tokens are independent.
    Profile = apps.get_model("accounts", "Profile")
    for profile in Profile.objects.all():
        profile.security_stamp = uuid.uuid4()
        profile.save(update_fields=["security_stamp"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_profile_last_seen_at_profile_last_user_agent_and_more"),
    ]
    operations = [migrations.RunPython(randomize_stamps, migrations.RunPython.noop)]
