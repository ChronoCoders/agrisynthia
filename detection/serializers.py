from rest_framework import serializers

from .models import DetectionResult


class DetectionResultSerializer(serializers.ModelSerializer):
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
        if value < 0:
            raise serializers.ValidationError("Detected count cannot be negative")
        return value
