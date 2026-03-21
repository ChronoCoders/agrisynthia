# -*- coding: utf-8 -*-
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="detection.DetectionResult")
def auto_generate_detection_report(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from reports.tasks import generate_detection_report
        generate_detection_report.delay(instance.pk, formats=["pdf", "xlsx"])
        logger.info("Auto-report task queued for DetectionResult %s", instance.pk)
    except Exception as e:
        logger.error("Failed to queue auto-report for DetectionResult %s: %s", instance.pk, e)
