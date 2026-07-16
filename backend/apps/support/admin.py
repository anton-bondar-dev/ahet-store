from django.contrib import admin

from .models import (
    ActionApproval,
    AdminAuditLog,
    ChatMessage,
    CustomerTag,
    CustomerTagAssignment,
    ImpersonationSession,
    SupportMacro,
    SupportRating,
    SupportTicket,
)


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


@admin.register(CustomerTag)
class CustomerTagAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "color", "created_at")


@admin.register(CustomerTagAssignment)
class CustomerTagAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "tag", "assigned_by", "created_at")
    search_fields = ("user__username", "tag__label")


@admin.register(SupportMacro)
class SupportMacroAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_by", "updated_at")
    search_fields = ("title", "content")


@admin.register(ImpersonationSession)
class ImpersonationSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "staff", "target_user", "started_at", "ended_at")
    search_fields = ("staff__username", "target_user__username")


@admin.register(ActionApproval)
class ActionApprovalAdmin(admin.ModelAdmin):
    list_display = ("id", "action_type", "requested_by", "amount", "percent", "status", "created_at")
    list_filter = ("status", "action_type")


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action_type", "admin_user", "target_user", "ticket", "created_at")
    list_filter = ("action_type",)
    search_fields = ("admin_user__username", "target_user__username")
    readonly_fields = ("admin_user", "action_type", "target_user", "ticket", "meta", "created_at")

    def has_add_permission(self, request):
        return False  # audit log is append-only via the API
