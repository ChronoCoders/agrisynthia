# -*- coding: utf-8 -*-
from rest_framework import serializers

from .models import DetectionResult, MultiDetectionBatch


class DetectionResultSerializer(serializers.ModelSerializer):
    """Serializer for fruit detection results"""

    class Meta:
        model = DetectionResult
        fields = [
            "id",
            "fruit_type",
            "tree_count",
            "tree_age",
            "detected_count",
            "weight",
            "total_weight",
            "processing_time",
            "confidence_score",
            "model_version",
            "threshold_used",
            "image_path",
            "bbox_coordinates",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_tree_count(self, value):
        if value <= 0:
            raise serializers.ValidationError("Tree count must be positive")
        return value

    def validate_detected_count(self, value):
        """Ensure detected count is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Detected count cannot be negative")
        return value


class MultiDetectionBatchSerializer(serializers.ModelSerializer):
    """Serializer for multi-image detection batches"""

    class Meta:
        model = MultiDetectionBatch
        fields = [
            "id",
            "fruit_type",
            "batch_hash",
            "image_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "batch_hash"]

    def validate_image_count(self, value):
        """Ensure image count is positive"""
        if value < 1:
            raise serializers.ValidationError("Image count must be at least 1")
        return value
