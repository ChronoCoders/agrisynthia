from django.urls import include, path
from rest_framework.routers import DefaultRouter

from detection.api_views import DetectionResultViewSet
from dron_map.api_views import ProjectViewSet

router = DefaultRouter()

router.register(r"detections", DetectionResultViewSet, basename="detection")
router.register(r"projects", ProjectViewSet, basename="project")

urlpatterns = [
    path("", include(router.urls)),
]
