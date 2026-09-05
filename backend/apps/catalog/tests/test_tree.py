"""Tests for the tree helpers in apps/catalog/tree.py.

These back the cascading category filter and the breadcrumb attachment used
across the catalog API, so they get direct unit coverage.
"""
import pytest

from apps.catalog.models import Category
from apps.catalog.tree import attach_ancestors, descendant_id_subquery


@pytest.mark.django_db
class TestDescendantSubquery:
    def test_includes_self_and_all_descendants(self):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        grand = Category.objects.create(name="Grand", slug="grand", parent=child)

        ids = set(descendant_id_subquery(root))
        assert ids == {root.pk, child.pk, grand.pk}

    def test_excludes_sibling_subtree(self):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        other = Category.objects.create(name="Other", slug="other")
        other_child = Category.objects.create(name="OChild", slug="ochild", parent=other)

        ids = set(descendant_id_subquery(root))
        assert other.pk not in ids
        assert other_child.pk not in ids

    def test_leaf_returns_only_itself(self):
        root = Category.objects.create(name="Root", slug="root")
        leaf = Category.objects.create(name="Leaf", slug="leaf", parent=root)
        assert set(descendant_id_subquery(leaf)) == {leaf.pk}


@pytest.mark.django_db
class TestAttachAncestors:
    def test_attaches_root_to_parent_chain_in_order(self):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        grand = Category.objects.create(name="Grand", slug="grand", parent=child)

        attach_ancestors([grand])
        assert [c.id for c in grand._ancestors] == [root.id, child.id]

    def test_root_gets_empty_ancestors(self):
        root = Category.objects.create(name="Root", slug="root")
        attach_ancestors([root])
        assert root._ancestors == []

    def test_handles_duplicate_instances(self):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        # A product list repeats the same category object many times.
        dup_a = Category.objects.get(pk=child.pk)
        dup_b = Category.objects.get(pk=child.pk)
        attach_ancestors([dup_a, dup_b])
        assert [c.id for c in dup_a._ancestors] == [root.id]
        assert [c.id for c in dup_b._ancestors] == [root.id]
