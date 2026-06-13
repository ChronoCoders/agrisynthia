from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_list, name="list"),
    path("request/detection/", views.request_detection_report, name="request-detection"),
    path("request/drone/", views.request_drone_report, name="request-drone"),
    path("download/<int:report_id>/", views.download_report, name="download"),
    path("delete/<int:report_id>/", views.delete_report, name="delete"),
    path("schedule/create/", views.create_schedule, name="schedule-create"),
    path("schedule/<int:schedule_id>/delete/", views.delete_schedule, name="schedule-delete"),
    path("schedule/<int:schedule_id>/toggle/", views.toggle_schedule, name="schedule-toggle"),
]
