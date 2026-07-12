from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_product_discount_end_date_product_discount_price_and_more"),
    ]

    operations = [
        # Enable pg_trgm for typo-tolerant (trigram) search.
        TrigramExtension(),
        # GIN trigram index to keep word-similarity searches fast on titles.
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS product_title_trgm "
                "ON catalog_product USING gin (title gin_trgm_ops);"
            ),
            reverse_sql="DROP INDEX IF EXISTS product_title_trgm;",
        ),
    ]
