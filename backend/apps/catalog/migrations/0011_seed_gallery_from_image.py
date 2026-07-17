from django.db import migrations


def image_to_gallery(apps, schema_editor):
    """Backfill the new gallery: every product that already has a single `image`
    gets a matching ProductImage at position 0, so existing products keep their
    picture (now as the first slide of the slider). Idempotent."""
    Product = apps.get_model("catalog", "Product")
    ProductImage = apps.get_model("catalog", "ProductImage")
    for product in Product.objects.all():
        name = product.image.name if product.image else ""
        if not name:
            continue
        if not ProductImage.objects.filter(product=product).exists():
            ProductImage.objects.create(product=product, image=name, position=0)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0010_productimage"),
    ]

    operations = [
        migrations.RunPython(image_to_gallery, noop),
    ]
