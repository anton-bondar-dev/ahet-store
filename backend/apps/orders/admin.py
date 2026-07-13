from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_title", "quantity", "price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "status", "total_price", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "first_name", "last_name", "email", "phone", "session_id")
    inlines = [OrderItemInline]
