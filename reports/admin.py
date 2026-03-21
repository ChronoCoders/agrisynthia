from django.contrib import admin
from .models import GeneratedReport

@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ("report_type", "format", "status", "created_by", "created_at")
    list_filter = ("report_type", "status", "format")
    search_fields = ("detection_result__id", "project__name")
    readonly_fields = ("created_at", "completed_at", "error_message")
