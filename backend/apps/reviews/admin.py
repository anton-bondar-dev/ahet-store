from django.contrib import admin

from .models import Review, ReviewReply


class ReviewReplyInline(admin.TabularInline):
    model = ReviewReply
    extra = 1


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "user", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("product__title", "user__username", "text")
    inlines = [ReviewReplyInline]
