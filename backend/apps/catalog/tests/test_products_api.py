"""GET /api/catalog/products (list) and GET /api/catalog/{slug} (detail).

Both are public. The list supports a cascading `category` filter (a parent
returns its whole subtree). Detail resolves by slug and counts a view.

NOTE: the `q=` trigram search and `sort=popular` trending order rely on
Postgres-only SQL (WORD_SIMILARITY / Extract-epoch DurationField) and raise on
the sqlite test DB, so their happy paths are skipped with a reason below; the
non-search behaviour is asserted fully.
"""
from decimal import Decimal

import pytest

from apps.catalog.models import Category, Product

LIST = "/api/catalog/products"


@pytest.fixture
def tree(db):
    """A small category tree with products at different depths.

    Root
      └─ Child
           └─ Grand   (Alpha)
      (Zeta on Root, Mid[inactive] on Root)
    """
    root = Category.objects.create(name="Root", slug="root")
    child = Category.objects.create(name="Child", slug="child", parent=root)
    grand = Category.objects.create(name="Grand", slug="grand", parent=child)
    zeta = Product.objects.create(category=root, title="Zeta", slug="zeta", price="10.00", stock=1)
    alpha = Product.objects.create(category=grand, title="Alpha", slug="alpha", price="10.00", stock=1)
    mid = Product.objects.create(
        category=root, title="Mid", slug="mid", price="10.00", stock=1, is_active=False
    )
    return dict(root=root, child=child, grand=grand, zeta=zeta, alpha=alpha, mid=mid)


@pytest.mark.django_db
class TestListProducts:
    def test_is_public_no_auth(self, api, product_factory):
        product_factory()
        assert api.get(LIST).status_code == 200

    def test_empty_returns_empty_list(self, api):
        assert api.get(LIST).json() == []

    def test_lists_all_products_ordered_by_title(self, api, tree):
        titles = [p["title"] for p in api.get(LIST).json()]
        # Default Product ordering is by title (alphabetical).
        assert titles == sorted(titles)
        assert {"Alpha", "Zeta"} <= set(titles)

    def test_product_payload_has_computed_fields(self, api, product_factory):
        product_factory(price="250.00")
        row = api.get(LIST).json()[0]
        assert row["is_new"] is True
        assert row["bonus_amount"] == 2  # 1% of 250
        assert Decimal(str(row["price"])) == Decimal("250.00")
        assert row["images"] == []
        assert row["image"] is None
        # The nested category carries breadcrumb ancestors (no N+1).
        assert "ancestors" in row["category"]

    def test_category_filter_returns_only_that_category(self, api, tree):
        resp = api.get(LIST, {"category": tree["grand"].id}).json()
        assert sorted(p["title"] for p in resp) == ["Alpha"]

    def test_category_filter_cascades_to_subtree(self, api, tree):
        # Selecting the root returns products from the whole subtree.
        resp = api.get(LIST, {"category": tree["root"].id}).json()
        assert sorted(p["title"] for p in resp) == ["Alpha", "Mid", "Zeta"]

    def test_category_filter_unknown_id_returns_empty(self, api, tree):
        assert api.get(LIST, {"category": 999999}).json() == []

    def test_whitespace_query_is_treated_as_no_search(self, api, tree):
        # A blank/whitespace q must fall through to the plain list (no trigram),
        # not error and not filter anything out.
        resp = api.get(LIST, {"q": "   "})
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_nested_product_breadcrumbs_are_correct(self, api, tree):
        rows = {p["title"]: p for p in api.get(LIST).json()}
        assert [a["name"] for a in rows["Alpha"]["category"]["ancestors"]] == ["Root", "Child"]

    @pytest.mark.xfail(
        reason="BUG: the public product list does not filter is_active; "
        "inactive products are currently returned to shoppers.",
        strict=True,
    )
    def test_inactive_products_are_hidden_from_public_list(self, api, tree):
        titles = [p["title"] for p in api.get(LIST).json()]
        assert "Mid" not in titles  # 'Mid' is is_active=False

    @pytest.mark.skip(
        reason="sort=popular uses with_trending_score() (Extract-epoch / DurationField), "
        "which is Postgres-only and raises on the sqlite test DB."
    )
    def test_sort_popular(self, api, tree):
        api.get(LIST, {"sort": "popular"})

    @pytest.mark.skip(
        reason="q= search uses TrigramWordSimilarity (WORD_SIMILARITY), Postgres-only; "
        "raises 'no such function' on the sqlite test DB."
    )
    def test_trigram_search(self, api, tree):
        api.get(LIST, {"q": "alph"})


@pytest.mark.django_db
class TestProductDetail:
    def test_detail_by_slug_happy_path(self, api, product_factory):
        p = product_factory()
        resp = api.get(f"/api/catalog/{p.slug}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == p.id
        assert body["slug"] == p.slug

    def test_detail_is_public_no_auth(self, api, product_factory):
        p = product_factory()
        assert api.get(f"/api/catalog/{p.slug}").status_code == 200

    def test_detail_unknown_slug_404(self, api):
        assert api.get("/api/catalog/no-such-slug").status_code == 404

    def test_detail_increments_view_count(self, api, product_factory):
        p = product_factory()
        assert p.views_count == 0
        api.get(f"/api/catalog/{p.slug}")
        api.get(f"/api/catalog/{p.slug}")
        p.refresh_from_db()
        assert p.views_count == 2

    def test_detail_includes_breadcrumbs(self, api, tree):
        body = api.get(f"/api/catalog/{tree['alpha'].slug}").json()
        assert [a["name"] for a in body["category"]["ancestors"]] == ["Root", "Child"]

    def test_literal_routes_win_over_slug_param(self, api, category_factory):
        # '/categories' must resolve to the list endpoint, not be captured as a
        # product slug, even though no product with that slug exists.
        category_factory()
        assert api.get("/api/catalog/categories").status_code == 200
