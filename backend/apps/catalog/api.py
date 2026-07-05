from typing import List

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
