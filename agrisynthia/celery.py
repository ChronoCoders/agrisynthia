import os
import warnings

from celery import Celery

# Billiard soft timeouts require SIGUSR1 which is unavailable on Windows
warnings.filterwarnings("ignore", message="Soft timeouts are not supported", category=UserWarning, module="billiard")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agrisynthia.settings")

app = Celery("agrisynthia")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
