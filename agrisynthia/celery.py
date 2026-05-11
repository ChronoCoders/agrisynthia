# -*- coding: utf-8 -*-
"""
Celery configuration for Agrisynthia project.

This module initializes the Celery application and configures it
to work with Django settings.
"""
import os
import warnings

from celery import Celery

# Billiard soft timeouts require SIGUSR1 which is unavailable on Windows
warnings.filterwarnings("ignore", message="Soft timeouts are not supported", category=UserWarning, module="billiard")

# Set default Django settings module for Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agrisynthia.settings")

# Create Celery application
app = Celery("agrisynthia")

# Load Celery configuration from Django settings
# Using 'CELERY_' as prefix for all Celery-related settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all registered Django apps
# This will automatically find tasks.py files in each app
app.autodiscover_tasks()
