# -*- coding: utf-8 -*-
"""
FarmVision Django Application

This module ensures that the Celery app is loaded when Django starts,
so that shared_task decorator will use this app.
"""

# Import Celery app to ensure it's always imported when Django starts
from .celery import app as celery_app

__all__ = ("celery_app",)
