from django.contrib import admin

from .models import ChatMessage, SupportRating, SupportTicket


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("sender", "from_staff", "text", "created_at")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "subject", "closed_by", "updated_at")
    list_filter = ("status",)
    search_fields = ("user__username", "subject")
    inlines = [ChatMessageInline]


@admin.register(SupportRating)
class SupportRatingAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "staff", "is_positive", "created_at")
    list_filter = ("is_positive", "staff")
    search_fields = ("staff__username", "ticket__user__username")
