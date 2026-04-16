# -*- coding: utf-8 -*-
from django.urls import path

from . import views

app_name = "dron_map"

urlpatterns = [
    path("projects/", views.projects, name="projects"),
    path("projects/<slug:slug>/", views.add_projects, name="add_projects"),
    path("projects/<slug:slug>/<int:project_id>/", views.add_projects, name="edit_project"),
    path("map/<int:id>/", views.maping, name="map"),
    path("projects/<int:project_id>/odm-status/", views.odm_status, name="odm_status"),
]
