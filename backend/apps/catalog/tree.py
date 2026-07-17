"""Category-tree helpers shared by the catalog API.

Both operations are designed to stay O(1) in round-trips regardless of how deep
or wide the tree is:

* `descendant_id_subquery` returns a *lazy* queryset of PKs matched by a single
  indexed prefix scan (`path LIKE '1/5/%'`). Passed into
  `Product.objects.filter(category_id__in=...)`, Django inlines it as one SQL
  statement — no recursion, no per-level queries.

* `attach_ancestors` resolves the breadcrumb chain for many categories with a
  single extra query (fetch every referenced ancestor once, wire them up in
  memory), so serializing a whole product list never becomes N+1.
"""

from .models import Category


def descendant_id_subquery(category: Category):
    """Lazy queryset of the category's PK and all descendant PKs (inclusive).

    `path` ends in a slash, so the prefix match can't collide across siblings
    (e.g. "1/" never matches "10/")."""
    return Category.objects.filter(path__startswith=category.path).values_list(
        "id", flat=True
    )


def attach_ancestors(categories) -> None:
    """Populate `_ancestors` (root → parent, excluding self) on each category
    in-place using one bulk query. `categories` may contain duplicates (e.g. the
    same category instance repeated across a product list)."""
    categories = list(categories)
    needed: set[int] = set()
    for cat in categories:
        needed.update(cat.ancestor_ids)

    nodes = (
        {c.id: c for c in Category.objects.filter(id__in=needed)} if needed else {}
    )
    for cat in categories:
        cat._ancestors = [nodes[i] for i in cat.ancestor_ids if i in nodes]
