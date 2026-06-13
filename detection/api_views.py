from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DetectionResult, MultiDetectionBatch
from .serializers import DetectionResultSerializer, MultiDetectionBatchSerializer


class DetectionResultViewSet(viewsets.ModelViewSet):
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
        if self.request.user.is_authenticated:
            qs = qs.filter(created_by=self.request.user)
        else:
            qs = qs.none()
        if self.action == "list":
            qs = qs.defer("bbox_coordinates")
        return qs

    @action(detail=False, methods=["get"])
    def statistics(self, request):
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
        recent_results = self.queryset.order_by("-created_at")[:10]
        serializer = self.get_serializer(recent_results, many=True)
        return Response(serializer.data)


class MultiDetectionBatchViewSet(viewsets.ModelViewSet):
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
        batch = self.get_object()
        return Response(
            {
                "batch_hash": batch.batch_hash,
                "fruit_type": batch.fruit_type,
                "image_count": batch.image_count,
                "created_at": batch.created_at,
            }
        )
