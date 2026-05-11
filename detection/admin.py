# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.html import format_html

from detection.models import DetectionResult, ModelVersion, MultiDetectionBatch


@admin.register(DetectionResult)
class DetectionResultAdmin(admin.ModelAdmin):
    list_display = ["fruit_type", "detected_count", "confidence_score", "model_version", "created_at"]
    list_filter = ["fruit_type", "created_at"]
    search_fields = ["fruit_type", "model_version", "task_id"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


@admin.register(MultiDetectionBatch)
class MultiDetectionBatchAdmin(admin.ModelAdmin):
    list_display = ["fruit_type", "batch_hash", "image_count", "created_at"]
    list_filter = ["fruit_type", "created_at"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


def _activate_versions(modeladmin, request, queryset):
    for mv in queryset:
        ModelVersion.objects.filter(fruit_type=mv.fruit_type, is_active=True).exclude(
            pk=mv.pk
        ).update(is_active=False)
        mv.is_active = True
        mv.save()
    modeladmin.message_user(request, f"Activated {queryset.count()} version(s).")

_activate_versions.short_description = "Activate selected versions (deactivates others for same fruit)"


def _deactivate_versions(modeladmin, request, queryset):
    queryset.update(is_active=False)
    modeladmin.message_user(request, f"Deactivated {queryset.count()} version(s).")

_deactivate_versions.short_description = "Deactivate selected versions"


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = [
        "fruit_type",
        "version",
        "framework",
        "active_badge",
        "weights_path",
        "checksum_sha256",
        "created_at",
    ]
    list_filter = ["fruit_type", "framework", "is_active"]
    search_fields = ["fruit_type", "version", "notes"]
    readonly_fields = ["created_at"]
    ordering = ["fruit_type", "-created_at"]
    actions = [_activate_versions, _deactivate_versions]

    @admin.display(boolean=True, description="Active")
    def active_badge(self, obj):
        return obj.is_active
