from django.urls import path, re_path

from . import views

app_name = "detection"

urlpatterns = [
    path("", views.index, name="index"),
    path("mcti/", views.multi_detection_image, name="multi_detection_image"),
    re_path(
        r"^download_image/(?P<slug>[\w-]+)/$",
        views.download_image,
        name="download_image",
    ),
    path("system-monitoring/", views.system_monitoring, name="system_monitoring"),
    path("async-detection/", views.async_detection, name="async_detection"),
    path("task-status/<str:task_id>/", views.task_status, name="task_status"),
    path("task-stream/<str:task_id>/", views.detection_task_stream, name="task_stream"),
    path("cache/invalidate/", views.cache_invalidate, name="cache_invalidate"),
    path("cache/statistics/", views.cache_statistics, name="cache_statistics"),
    path("media/<path:file_path>", views.serve_media_file, name="serve-media"),
]
