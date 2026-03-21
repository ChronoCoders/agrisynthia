# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import Projects


@admin.register(Projects)
class ProjectsAdmin(admin.ModelAdmin):
    list_display = ["id", "Farm", "Field", "Title", "State", "Data_time"]
    search_fields = ["Farm", "Field", "Title"]
    list_filter = ["State", "Data_time"]
    readonly_fields = ["Data_time", "hashing_path"]
