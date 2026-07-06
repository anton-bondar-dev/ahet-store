from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "price", "sku", "stock", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("title", "sku")
    prepopulated_fields = {"slug": ("title",)}
