from django.contrib import admin

from .models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code", "discount_type", "discount_value", "is_active",
        "valid_until", "used_count", "max_uses",
    )
    list_filter = ("discount_type", "is_active")
    search_fields = ("code",)
