from django.contrib import admin

from .models import ChatMessage, SupportTicket


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("sender", "from_staff", "text", "created_at")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "subject", "updated_at")
    list_filter = ("status",)
    search_fields = ("user__username", "subject")
    inlines = [ChatMessageInline]
