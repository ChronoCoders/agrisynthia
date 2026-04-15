# -*- coding: utf-8 -*-
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class DetectionResult(models.Model):
    fruit_type: models.CharField = models.CharField(max_length=50, db_index=True)
    tree_count: models.IntegerField = models.IntegerField()
    tree_age: models.IntegerField = models.IntegerField(db_index=True)
    detected_count: models.IntegerField = models.IntegerField()
    weight: models.FloatField = models.FloatField()
    total_weight: models.FloatField = models.FloatField()
    processing_time: models.FloatField = models.FloatField()
    confidence_score: models.FloatField = models.FloatField(
        null=True, blank=True, help_text="Average confidence score from YOLO detection"
    )
    model_version: models.CharField = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Model file name and version used for this detection, e.g. mandalina.pt v1.0.0",
    )
    threshold_used: models.FloatField = models.FloatField(
        null=True,
        blank=True,
        help_text="Confidence threshold used during inference",
    )
    task_id: models.CharField = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Celery task ID for async processing",
    )
    image_path: models.CharField = models.CharField(max_length=255)
    bbox_coordinates: models.JSONField = models.JSONField(
        null=True,
        blank=True,
        help_text="List of detection bounding box center coordinates in pixels: [{'x': int, 'y': int}, ...]",
    )
    created_at: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, db_index=True
    )
    created_by: models.ForeignKey = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="detection_results",
        db_index=True,
    )

    class Meta:
        db_table = "detection_results"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.fruit_type} - {self.detected_count} adet"

    @classmethod
    def check_model_degradation(cls, fruit_type=None, days=7, threshold=0.7):
        """
        Detect model degradation by checking average confidence score.

        Args:
            fruit_type: Optional fruit type to check (if None, checks all)
            days: Number of days to look back (default: 7)
            threshold: Minimum acceptable average confidence (default: 0.7)

        Returns:
            dict: {
                'is_degraded': bool,
                'avg_confidence': float,
                'sample_count': int,
                'fruit_type': str or None,
                'period_days': int
            }
        """
        from django.db.models import Avg, Count

        cutoff_date = timezone.now() - timedelta(days=days)

        queryset = cls.objects.filter(
            created_at__gte=cutoff_date, confidence_score__isnull=False
        )

        if fruit_type:
            queryset = queryset.filter(fruit_type=fruit_type)

        stats = queryset.aggregate(
            avg_confidence=Avg("confidence_score"), sample_count=Count("id")
        )

        avg_confidence = stats["avg_confidence"] or 0.0
        sample_count = stats["sample_count"] or 0

        # Require at least 10 samples for reliable assessment
        is_degraded = sample_count >= 10 and avg_confidence < threshold

        return {
            "is_degraded": is_degraded,
            "avg_confidence": round(avg_confidence, 3) if avg_confidence else None,
            "sample_count": sample_count,
            "fruit_type": fruit_type,
            "period_days": days,
            "threshold": threshold,
        }


class MultiDetectionBatch(models.Model):
    fruit_type: models.CharField = models.CharField(max_length=50, db_index=True)
    batch_hash: models.CharField = models.CharField(
        max_length=100, unique=True, db_index=True
    )
    image_count: models.IntegerField = models.IntegerField()
    created_at: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, db_index=True
    )

    class Meta:
        db_table = "multi_detection_batches"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.fruit_type} - {self.batch_hash}"
