"""Model-level tests for the catalog app.

Covers the two model behaviours that carry real logic:
  * Category — the materialized-path tree (path/depth on save, ancestor_ids,
    re-parent cascade, rebuild_paths).
  * Product — the computed properties (is_new, effective_price, bonus_amount,
    image_urls) and recompute_rating().
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.catalog.models import Category, Product, ProductImage


# --------------------------------------------------------------------------- #
# Category: materialized-path tree maintenance
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestCategoryTree:
    def test_root_gets_self_path_and_zero_depth(self):
        root = Category.objects.create(name="Root", slug="root")
        assert root.path == f"{root.pk}/"
        assert root.depth == 0

    def test_child_path_extends_parent_and_bumps_depth(self):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        grand = Category.objects.create(name="Grand", slug="grand", parent=child)

        assert child.path == f"{root.pk}/{child.pk}/"
        assert child.depth == 1
        assert grand.path == f"{root.pk}/{child.pk}/{grand.pk}/"
        assert grand.depth == 2

    def test_ancestor_ids_excludes_self_and_is_root_first(self):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        grand = Category.objects.create(name="Grand", slug="grand", parent=child)

        assert grand.ancestor_ids == [root.pk, child.pk]
        assert root.ancestor_ids == []

    def test_reparent_rewrites_path_and_cascades_to_descendants(self):
        root = Category.objects.create(name="Root", slug="root")
        mid = Category.objects.create(name="Mid", slug="mid", parent=root)
        leaf = Category.objects.create(name="Leaf", slug="leaf", parent=mid)
        new_root = Category.objects.create(name="NewRoot", slug="new-root")

        mid.parent = new_root
        mid.save()

        mid.refresh_from_db()
        leaf.refresh_from_db()
        assert mid.path == f"{new_root.pk}/{mid.pk}/"
        assert mid.depth == 1
        # The descendant's path/depth were rewritten by the cascade, not left stale.
        assert leaf.path == f"{new_root.pk}/{mid.pk}/{leaf.pk}/"
        assert leaf.depth == 2

    def test_rebuild_paths_repairs_corrupted_paths(self):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        # Simulate a corrupted denormalization (e.g. after a raw bulk edit).
        Category.objects.filter(pk=child.pk).update(path="999/", depth=42)

        Category.rebuild_paths()

        child.refresh_from_db()
        assert child.path == f"{root.pk}/{child.pk}/"
        assert child.depth == 1

    def test_default_ordering_places_parent_before_descendants(self):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        grand = Category.objects.create(name="Grand", slug="grand", parent=child)
        Category.objects.create(name="AAA", slug="aaa")  # separate root

        ordered = list(Category.objects.all())
        # The DFS contract: a node always precedes its descendants...
        assert ordered.index(root) < ordered.index(child) < ordered.index(grand)
        # ...and the whole list is exactly the materialized-path ordering.
        assert ordered == sorted(ordered, key=lambda c: (c.path, c.name))

    def test_str_is_name(self):
        assert str(Category.objects.create(name="Gadgets", slug="g")) == "Gadgets"


# --------------------------------------------------------------------------- #
# Product: computed properties
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestProductProperties:
    def test_is_new_true_for_freshly_created(self, product_factory):
        assert product_factory().is_new is True

    def test_is_new_false_when_older_than_30_days(self, product_factory):
        p = product_factory()
        p.created_at = timezone.now() - timedelta(days=31)
        assert p.is_new is False

    def test_is_new_false_when_badge_disabled(self, product_factory):
        # Recent, but admin suppressed the badge.
        p = product_factory(disable_new_badge=True)
        assert p.is_new is False

    def test_effective_price_regular_without_discount(self, product_factory):
        p = product_factory(price="120.00")
        p.refresh_from_db()  # load price as a Decimal, as the API does
        assert p.effective_price == Decimal("120.00")

    def test_effective_price_uses_discount_when_active(self, product_factory):
        p = product_factory(price="120.00", discount_price="90.00", is_active=True)
        p.refresh_from_db()
        assert p.effective_price == Decimal("90.00")

    def test_effective_price_ignores_discount_when_inactive(self, product_factory):
        # A discount only applies while the product is on sale (is_active).
        p = product_factory(price="120.00", discount_price="90.00", is_active=False)
        p.refresh_from_db()
        assert p.effective_price == Decimal("120.00")

    def test_bonus_amount_is_one_percent_of_effective_price(self, product_factory):
        p = product_factory(price="250.00")
        p.refresh_from_db()
        assert p.bonus_amount == 2  # int(250 / 100)

    def test_bonus_amount_follows_active_discount(self, product_factory):
        p = product_factory(price="500.00", discount_price="250.00", is_active=True)
        p.refresh_from_db()
        assert p.bonus_amount == 2  # int(250 / 100), the discounted price

    def test_bonus_amount_custom_override_wins(self, product_factory):
        p = product_factory(price="250.00", custom_bonus=99)
        assert p.bonus_amount == 99

    def test_bonus_amount_custom_override_zero_is_respected(self, product_factory):
        # custom_bonus=0 must win over the 1% fallback (None-check, not truthiness).
        p = product_factory(price="250.00", custom_bonus=0)
        assert p.bonus_amount == 0

    def test_str_is_title(self, category_factory):
        p = Product.objects.create(
            category=category_factory(), title="Cool Widget", slug="cw", price="1.00"
        )
        assert str(p) == "Cool Widget"

    def test_default_ordering_is_title(self, category_factory):
        cat = category_factory()
        Product.objects.create(category=cat, title="Zeta", slug="z", price="1.00")
        Product.objects.create(category=cat, title="Alpha", slug="a", price="1.00")
        Product.objects.create(category=cat, title="Mike", slug="m", price="1.00")
        assert [p.title for p in Product.objects.all()] == ["Alpha", "Mike", "Zeta"]


# --------------------------------------------------------------------------- #
# Product: image gallery
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestProductImages:
    def test_image_urls_empty_without_image_or_gallery(self, product_factory):
        assert product_factory().image_urls == []

    def test_image_urls_from_gallery_ordered_by_position(self, product_factory):
        p = product_factory()
        # Inserted out of order; image_urls must respect `position`.
        ProductImage.objects.create(product=p, image="products/images/b.jpg", position=2)
        ProductImage.objects.create(product=p, image="products/images/a.jpg", position=1)
        assert p.image_urls == [
            "/media/products/images/a.jpg",
            "/media/products/images/b.jpg",
        ]

    def test_image_urls_falls_back_to_legacy_image(self, product_factory):
        # No gallery rows → fall back to the single legacy `image` field.
        p = product_factory(image="products/images/legacy.jpg")
        assert p.image_urls == ["/media/products/images/legacy.jpg"]


# --------------------------------------------------------------------------- #
# Product: rating aggregation
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestRecomputeRating:
    def test_recompute_rating_averages_and_counts(self, product_factory, make_user):
        from apps.reviews.models import Review

        p = product_factory()
        Review.objects.create(user=make_user("ra"), product=p, rating=4)
        Review.objects.create(user=make_user("rb"), product=p, rating=3)

        p.recompute_rating()

        p.refresh_from_db()
        assert p.average_rating == 3.5
        assert p.reviews_count == 2

    def test_recompute_rating_zero_when_no_reviews(self, product_factory):
        p = product_factory()
        p.recompute_rating()
        p.refresh_from_db()
        assert p.average_rating == 0
        assert p.reviews_count == 0


# --------------------------------------------------------------------------- #
# Product: DB constraints
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestProductConstraints:
    def test_slug_is_unique(self, category_factory):
        cat = category_factory()
        Product.objects.create(category=cat, title="A", slug="dup", price="1.00")
        with pytest.raises(IntegrityError):
            Product.objects.create(category=cat, title="B", slug="dup", price="1.00")

    def test_sku_is_unique(self, category_factory):
        cat = category_factory()
        Product.objects.create(category=cat, title="A", slug="a", price="1.00", sku="SKU1")
        with pytest.raises(IntegrityError):
            Product.objects.create(category=cat, title="B", slug="b", price="1.00", sku="SKU1")
