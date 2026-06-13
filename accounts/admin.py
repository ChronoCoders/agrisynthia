from django.contrib import admin

from .models import BackupCode, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "language", "email_verified", "totp_enabled", "phone", "created_at"]
    list_filter = ["language", "email_verified", "totp_enabled"]
    search_fields = ["user__username", "user__email", "phone"]
    readonly_fields = ["created_at", "email_verification_token", "totp_secret"]
    fieldsets = [
        (None, {"fields": ["user", "avatar", "phone", "language"]}),
        ("E-posta Doğrulama", {"fields": ["email_verified", "email_verification_token"]}),
        ("2FA", {"fields": ["totp_enabled", "totp_secret"]}),
        ("NDVI Bildirimleri", {"fields": ["ndvi_alert_enabled", "ndvi_alert_threshold_low", "ndvi_alert_threshold_high"]}),
        ("Meta", {"fields": ["created_at"]}),
    ]


@admin.register(BackupCode)
class BackupCodeAdmin(admin.ModelAdmin):
    list_display = ["user", "used", "created_at"]
    list_filter = ["used"]
    search_fields = ["user__username"]
    readonly_fields = ["code_hash", "created_at"]
