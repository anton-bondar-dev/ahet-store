from django.contrib import admin

from .models import LoginChallenge, Profile, TelegramLinkToken


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "telegram_username", "is_2fa_enabled")
    search_fields = ("user__username", "telegram_username", "telegram_chat_id")


@admin.register(LoginChallenge)
class LoginChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "match_code", "created_at", "expires_at")
    list_filter = ("status",)


admin.site.register(TelegramLinkToken)
