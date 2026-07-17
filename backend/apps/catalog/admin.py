from django.contrib import admin

from .models import Category, Product, ProductImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "depth", "path")
    list_filter = ("depth", "parent")
    search_fields = ("name", "slug", "path")
    autocomplete_fields = ("parent",)
    readonly_fields = ("path", "depth")
    prepopulated_fields = {"slug": ("name",)}
    actions = ("rebuild_paths_action",)

    @admin.action(description="Rebuild category paths/depths from parent links")
    def rebuild_paths_action(self, request, queryset):
        Category.rebuild_paths()
        self.message_user(request, "Category paths rebuilt.")


class ProductImageInline(admin.TabularInline):
    # Gallery editor: add multiple images and set their slider order via
    # `position` (lower = earlier). Ordered by position in the form too.
    model = ProductImage
    extra = 1
    fields = ("image", "position")
    ordering = ("position", "id")


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
    # Images are managed solely through the gallery inline below. The legacy
    # single `image` field is hidden so it doesn't duplicate that control.
    exclude = ("image",)
    inlines = [ProductImageInline]
