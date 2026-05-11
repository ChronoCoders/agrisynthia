from django.contrib import admin
from .models import ChatLead, NewsletterSubscriber


@admin.register(ChatLead)
class ChatLeadAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "created_at")
    search_fields = ("full_name", "email", "phone")
    readonly_fields = ("created_at",)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "subscribed_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("email",)
    readonly_fields = ("subscribed_at",)
