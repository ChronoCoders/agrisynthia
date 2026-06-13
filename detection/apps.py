import os

from django.apps import AppConfig


class DetectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "detection"

    def ready(self):
        if os.environ.get("RUN_MAIN") != "true":
            return

        print("Detection app ready. Models will load on first use.")
