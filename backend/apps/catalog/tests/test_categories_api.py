"""GET /api/catalog/categories — the category tree endpoint.

Public (no auth), ordered by materialized path so the frontend can build the
sidebar directly, with breadcrumb `ancestors` attached in bulk.
"""
import pytest

from apps.catalog.models import Category

URL = "/api/catalog/categories"


@pytest.mark.django_db
class TestListCategories:
    def test_empty_returns_empty_list(self, api):
        resp = api.get(URL)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_is_public_no_auth_required(self, api, category_factory):
        category_factory()
        assert api.get(URL).status_code == 200

    def test_returns_tree_fields(self, api):
        root = Category.objects.create(name="Root", slug="root", description="d")
        child = Category.objects.create(name="Child", slug="child", parent=root)

        by_slug = {c["slug"]: c for c in api.get(URL).json()}
        assert by_slug["root"]["parent_id"] is None
        assert by_slug["root"]["depth"] == 0
        assert by_slug["root"]["description"] == "d"
        assert by_slug["child"]["parent_id"] == root.id
        assert by_slug["child"]["depth"] == 1

    def test_ordering_is_depth_first(self, api):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        grand = Category.objects.create(name="Grand", slug="grand", parent=child)
        other_root = Category.objects.create(name="ZOther", slug="zother")

        names = [c["name"] for c in api.get(URL).json()]
        # A node is immediately followed by its descendants (path ordering);
        # the second root sorts after the whole first subtree.
        assert names.index(root.name) < names.index(child.name) < names.index(grand.name)
        assert names.index(grand.name) < names.index(other_root.name)

    def test_ancestors_breadcrumbs_populated(self, api):
        root = Category.objects.create(name="Root", slug="root")
        child = Category.objects.create(name="Child", slug="child", parent=root)
        grand = Category.objects.create(name="Grand", slug="grand", parent=child)

        by_slug = {c["slug"]: c for c in api.get(URL).json()}
        assert [a["name"] for a in by_slug["grand"]["ancestors"]] == ["Root", "Child"]
        assert by_slug["root"]["ancestors"] == []
        # Breadcrumb nodes are brief (id/name/slug only).
        assert set(by_slug["grand"]["ancestors"][0].keys()) == {"id", "name", "slug"}
