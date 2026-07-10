from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router

from .models import Category, Product
from .schemas import CategoryOut, ProductOut

router = Router(tags=["catalog"])


@router.get("/categories", response=List[CategoryOut], operation_id="list_categories")
def list_categories(request):
    return Category.objects.all()


@router.get("/products", response=List[ProductOut], operation_id="list_products")
def list_products(request):
    return Product.objects.select_related("category").all()


# Defined after the literal routes above so `/categories` and `/products`
# resolve first and are not captured by the `{slug}` path parameter.
@router.get("/{slug}", response=ProductOut, operation_id="get_product")
def get_product(request, slug: str):
    return get_object_or_404(Product.objects.select_related("category"), slug=slug)
