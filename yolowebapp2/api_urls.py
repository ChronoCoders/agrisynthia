# -*- coding: utf-8 -*-
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from detection.api_views import DetectionResultViewSet, MultiDetectionBatchViewSet
from dron_map.api_views import ProjectViewSet

# Create API router
router = DefaultRouter()

# Register ViewSets
router.register(r"detections", DetectionResultViewSet, basename="detection")
router.register(r"batches", MultiDetectionBatchViewSet, basename="batch")
router.register(r"projects", ProjectViewSet, basename="project")

# API URL patterns
urlpatterns = [
    path("", include(router.urls)),
]
