from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "title", "category", "price", "sku", "stock", "is_active",
        "disable_new_badge", "custom_bonus",
    )
    list_filter = ("category", "is_active", "disable_new_badge")
    list_editable = ("disable_new_badge", "custom_bonus")
    search_fields = ("title", "sku")
    prepopulated_fields = {"slug": ("title",)}
