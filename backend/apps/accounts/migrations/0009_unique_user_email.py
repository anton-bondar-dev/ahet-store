from django.db import migrations


def dedup_emails(apps, schema_editor):
    """Make emails case-insensitively unique on the existing rows so the unique
    index below can be created. Empty or duplicate emails are rewritten to a
    unique placeholder (transient — the user base is wiped/reseeded afterwards)."""
    User = apps.get_model("auth", "User")
    seen = set()
    for user in User.objects.all().order_by("pk"):
        email = (user.email or "").strip().lower()
        if not email or email in seen:
            user.email = f"legacy.{user.pk}@placeholder.invalid"
            user.save(update_fields=["email"])
            seen.add(user.email.lower())
        else:
            seen.add(email)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_populate_support_id"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [
        migrations.RunPython(dedup_emails, migrations.RunPython.noop),
        # auth.User is Django's built-in model, so enforce uniqueness with a
        # case-insensitive DB unique index (app layer also checks on register).
        migrations.RunSQL(
            "CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_ci_unique "
            "ON auth_user (LOWER(email));",
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_ci_unique;",
        ),
    ]
