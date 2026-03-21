# -*- coding: utf-8 -*-
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DetectionResult, MultiDetectionBatch
from .serializers import DetectionResultSerializer, MultiDetectionBatchSerializer


class DetectionResultViewSet(viewsets.ModelViewSet):
    """
    API endpoint for fruit detection results

    Provides CRUD operations for detection results including:
    - List all results (GET /api/detections/)
    - Retrieve single result (GET /api/detections/{id}/)
    - Create new result (POST /api/detections/)
    - Update result (PUT/PATCH /api/detections/{id}/)
    - Delete result (DELETE /api/detections/{id}/)
    - Filter by fruit type (GET /api/detections/?fruit_type=apple)
    - Search by fruit type (GET /api/detections/?search=apple)
    - Get statistics (GET /api/detections/statistics/)

    Note: Authentication required for all endpoints to protect detection data.
    """

    queryset = DetectionResult.objects.all()
    serializer_class = DetectionResultSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["fruit_type", "tree_age"]
    search_fields = ["fruit_type", "image_path"]
    ordering_fields = ["created_at", "detected_count", "total_weight"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        # bbox_coordinates can be several MB per row; exclude it from list pages
        # where callers only need summary fields.  Detail / retrieve still loads it.
        if self.action == "list":
            qs = qs.defer("bbox_coordinates")
        return qs

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """
        Get detection statistics across all results
        GET /api/detections/statistics/
        """
        from django.db.models import Avg, Count, Sum

        stats = DetectionResult.objects.aggregate(
            total_detections=Count("id"),
            total_fruits_detected=Sum("detected_count"),
            total_weight=Sum("total_weight"),
            avg_processing_time=Avg("processing_time"),
        )

        fruit_stats = DetectionResult.objects.values("fruit_type").annotate(
            count=Count("id"),
            total_detected=Sum("detected_count"),
            total_weight=Sum("total_weight"),
        )

        return Response(
            {
                "overall": stats,
                "by_fruit_type": fruit_stats,
            }
        )

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """
        Get recent detection results (last 10)
        GET /api/detections/recent/
        """
        recent_results = self.queryset.order_by("-created_at")[:10]
        serializer = self.get_serializer(recent_results, many=True)
        return Response(serializer.data)


class MultiDetectionBatchViewSet(viewsets.ModelViewSet):
    """
    API endpoint for multi-image detection batches

    Provides CRUD operations for batch processing:
    - List all batches (GET /api/batches/)
    - Retrieve single batch (GET /api/batches/{id}/)
    - Create new batch (POST /api/batches/)
    - Update batch (PUT/PATCH /api/batches/{id}/)
    - Delete batch (DELETE /api/batches/{id}/)
    - Filter by fruit type (GET /api/batches/?fruit_type=apple)
    """

    queryset = MultiDetectionBatch.objects.all()
    serializer_class = MultiDetectionBatchSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["fruit_type"]
    search_fields = ["fruit_type", "batch_hash"]
    ordering_fields = ["created_at", "image_count"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """
        Get batch summary with image count and metadata
        GET /api/batches/{id}/summary/
        """
        batch = self.get_object()
        return Response(
            {
                "batch_hash": batch.batch_hash,
                "fruit_type": batch.fruit_type,
                "image_count": batch.image_count,
                "created_at": batch.created_at,
            }
        )
