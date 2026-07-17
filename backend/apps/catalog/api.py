from typing import List, Optional

from django.contrib.postgres.search import TrigramWordSimilarity
from django.db.models import F, Value
from django.db.models.functions import Greatest, Lower
from django.shortcuts import get_object_or_404
from ninja import Router

from .models import Category, Product
from .schemas import CategoryOut, ProductOut, SuggestionOut

router = Router(tags=["catalog"])

# Minimum trigram word-similarity score for a row to count as a match.
SIMILARITY_THRESHOLD = 0.30
# Category matches are weighted below product-title matches in search results.
CATEGORY_WEIGHT = 0.6
# Product-title suggestions rank below category suggestions.
PRODUCT_SUGGESTION_WEIGHT = 0.85
MAX_SUGGESTIONS = 10


@router.get("/categories", response=List[CategoryOut], operation_id="list_categories")
def list_categories(request):
    return Category.objects.all()


@router.get("/products", response=List[ProductOut], operation_id="list_products")
def list_products(request, q: Optional[str] = None, sort: Optional[str] = None):
    products = Product.objects.select_related("category")
    if not q or not q.strip():
        products = products.with_trending_score()
        if sort == "popular":
            # Trending engine: time-decayed popularity score.
            return products.order_by("-trending_score", "title")
        return products.all()

    ql = q.strip().lower()
    return (
        products.annotate(
            title_sim=TrigramWordSimilarity(ql, Lower("title")),
            category_sim=TrigramWordSimilarity(ql, Lower("category__name")),
        )
        # Title outranks category via CATEGORY_WEIGHT; Greatest keeps the best of the two.
        .annotate(rank=Greatest("title_sim", F("category_sim") * Value(CATEGORY_WEIGHT)))
        .filter(rank__gte=SIMILARITY_THRESHOLD)
        .order_by("-rank", "title")
    )


@router.get("/suggestions", response=List[SuggestionOut], operation_id="get_suggestions")
def get_suggestions(request, q: str = ""):
    if not q or not q.strip():
        return []

    ql = q.strip().lower()

    # Categories rank above products (category > title priority for autocomplete).
    scored: list[tuple[float, SuggestionOut]] = []

    categories = (
        Category.objects.annotate(sim=TrigramWordSimilarity(ql, Lower("name")))
        .filter(sim__gte=SIMILARITY_THRESHOLD)
        .order_by("-sim")
    )
    for cat in categories:
        scored.append((cat.sim, SuggestionOut(text=cat.name, type="category")))

    products = (
        Product.objects.annotate(sim=TrigramWordSimilarity(ql, Lower("title")))
        .filter(sim__gte=SIMILARITY_THRESHOLD)
        .order_by("-sim")[:MAX_SUGGESTIONS * 2]
    )
    for prod in products:
        scored.append(
            (prod.sim * PRODUCT_SUGGESTION_WEIGHT, SuggestionOut(text=prod.title, type="product"))
        )

    scored.sort(key=lambda pair: pair[0], reverse=True)

    # Dedupe by text (case-insensitive), keep the highest-scored occurrence, cap the list.
    seen: set[str] = set()
    result: list[SuggestionOut] = []
    for _, suggestion in scored:
        key = suggestion.text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(suggestion)
        if len(result) >= MAX_SUGGESTIONS:
            break
    return result


# Defined after the literal routes above so `/categories`, `/products`, and
# `/suggestions` resolve first and are not captured by the `{slug}` path parameter.
@router.get("/{slug}", response=ProductOut, operation_id="get_product")
def get_product(request, slug: str):
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug)
    # Count the view for the trending engine (atomic, doesn't touch `product`).
    Product.objects.filter(id=product.id).update(views_count=F("views_count") + 1)
    return product
