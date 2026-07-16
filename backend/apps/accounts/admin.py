from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from .models import LoginChallenge, Profile, TelegramLinkToken

# Replace the default User admin with one built for quick role management:
# is_staff / is_superuser are shown, editable inline from the list, and filterable.
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username", "email", "first_name", "is_active", "is_staff", "is_superuser",
    )
    list_editable = ("is_active", "is_staff", "is_superuser")
    list_filter = ("is_staff", "is_superuser", "is_active")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "telegram_username", "is_2fa_enabled")
    search_fields = ("user__username", "telegram_username", "telegram_chat_id")


@admin.register(LoginChallenge)
class LoginChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "match_code", "created_at", "expires_at")
    list_filter = ("status",)


admin.site.register(TelegramLinkToken)
