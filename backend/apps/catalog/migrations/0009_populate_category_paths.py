from django.db import migrations


def populate_paths(apps, schema_editor):
    """Backfill the materialized path/depth for pre-existing categories. Before
    any nesting is introduced they are all roots, so path = "<pk>/" and
    depth = 0. The seed command reorganizes them and calls rebuild afterwards."""
    Category = apps.get_model("catalog", "Category")
    for category in Category.objects.all():
        Category.objects.filter(pk=category.pk).update(
            path=f"{category.pk}/", depth=0
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_alter_category_options_category_depth_and_more"),
    ]

    operations = [
        migrations.RunPython(populate_paths, noop),
    ]
