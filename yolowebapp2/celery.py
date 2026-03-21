# -*- coding: utf-8 -*-
"""
Celery configuration for FarmVision project.

This module initializes the Celery application and configures it
to work with Django settings.
"""
import os

from celery import Celery

# Set default Django settings module for Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yolowebapp2.settings")

# Create Celery application
app = Celery("farmvision")

# Load Celery configuration from Django settings
# Using 'CELERY_' as prefix for all Celery-related settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all registered Django apps
# This will automatically find tasks.py files in each app
app.autodiscover_tasks()
