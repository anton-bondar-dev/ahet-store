from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class _PostgresOnly:
    """Run the wrapped schema operation only on PostgreSQL. On other backends
    (e.g. the sqlite test database) it is a no-op, so the migration graph stays
    identical everywhere while pg_trgm — a Postgres-only feature — is skipped."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != "postgresql":
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != "postgresql":
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)


class TrigramExtensionPG(_PostgresOnly, TrigramExtension):
    pass


class RunSQLPG(_PostgresOnly, migrations.RunSQL):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_product_discount_end_date_product_discount_price_and_more"),
    ]

    operations = [
        # Enable pg_trgm for typo-tolerant (trigram) search — Postgres only.
        TrigramExtensionPG(),
        # GIN trigram index to keep word-similarity searches fast on titles.
        RunSQLPG(
            sql=(
                "CREATE INDEX IF NOT EXISTS product_title_trgm "
                "ON catalog_product USING gin (title gin_trgm_ops);"
            ),
            reverse_sql="DROP INDEX IF EXISTS product_title_trgm;",
        ),
    ]
