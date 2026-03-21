# -*- coding: utf-8 -*-
"""
Celery tasks for asynchronous image detection processing.

This module contains background tasks for:
- Async image detection
- Model health monitoring
- Batch processing
"""
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from celery import shared_task

from detection.models import DetectionResult
from yolowebapp2 import predict_tree

from detection.constants import (
    DETECTION_CONFIDENCE_THRESHOLD,
    FRUIT_MODEL_PATHS,
    FRUIT_WEIGHTS,
)

logger = logging.getLogger(__name__)

# Use constants from central configuration
FRUIT_MODELS = {k: str(v) for k, v in FRUIT_MODEL_PATHS.items()}


def _send_degradation_alert(alerts: list) -> None:
    """
    Send model degradation alerts via webhook and/or email.
    Uses cache to prevent duplicate alerts within cooldown window.
    """
    import json
    import urllib.request
    from django.conf import settings
    from django.core.cache import cache

    if not alerts:
        return

    # Check cooldown — don't spam alerts
    cache_key = "farmvision:alert:model_degradation"
    if cache.get(cache_key):
        logger.info("Alert cooldown active, skipping alert dispatch")
        return

    alert_text = "\n".join(alerts)
    cooldown = getattr(settings, "ALERT_COOLDOWN_SECONDS", 3600)

    # Set cooldown flag
    cache.set(cache_key, True, timeout=cooldown)

    # Webhook alert (Slack/Teams/Discord compatible)
    webhook_url = getattr(settings, "ALERT_WEBHOOK_URL", "")
    if webhook_url:
        try:
            payload = {
                "text": f"*FarmVision Model Degradation Alert*\n{alert_text}",
                "username": "FarmVision Monitor",
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info("Degradation alert sent to webhook")
                else:
                    logger.warning("Webhook returned status %s", response.status)
        except Exception as webhook_error:
            logger.error("Failed to send webhook alert: %s", webhook_error)

    # Email alert
    recipients = getattr(settings, "ALERT_EMAIL_RECIPIENTS", [])
    recipients = [r.strip() for r in recipients if r.strip()]
    if recipients:
        try:
            from django.core.mail import send_mail
            from django.conf import settings as django_settings

            send_mail(
                subject="[FarmVision] Model Degradation Detected",
                message=f"Model degradation alerts:\n\n{alert_text}",
                from_email=getattr(
                    django_settings, "DEFAULT_FROM_EMAIL", "noreply@farmvision.local"
                ),
                recipient_list=recipients,
                fail_silently=False,
            )
            logger.info(
                "Degradation alert email sent to %s recipients", len(recipients)
            )
        except Exception as email_error:
            logger.error("Failed to send email alert: %s", email_error)


@shared_task(bind=True, name="detection.tasks.process_image_detection")
def process_image_detection(
    self,
    image_path: str,
    fruit_type: str,
    tree_count: int,
    tree_age: int,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Asynchronous image detection task.

    Args:
        self: Celery task instance (for updating state)
        image_path: Path to the uploaded image file
        fruit_type: Type of fruit to detect
        tree_count: Number of trees
        tree_age: Age of trees
        user_id: Optional user ID who initiated the task

    Returns:
        dict: Detection results including count, weight, confidence, etc.

    Raises:
        Exception: If detection fails
    """
    try:
        # Update task state to PROCESSING
        self.update_state(
            state="PROCESSING", meta={"status": "Görüntü işleniyor...", "progress": 10}
        )

        if fruit_type not in FRUIT_MODELS:
            raise ValueError(f"Geçersiz meyve grubu: {fruit_type}")

        model_path = FRUIT_MODELS[fruit_type]
        conf_thres = DETECTION_CONFIDENCE_THRESHOLD

        logger.info(
            "Task %s: Starting detection for %s on image %s",
            self.request.id,
            fruit_type,
            image_path,
        )

        # Update state
        self.update_state(
            state="PROCESSING", meta={"status": "Model yükleniyor...", "progress": 30}
        )

        start_time = time.time()

        try:
            (
                detec,
                unique_id,
                confidence_score,
                bbox_centers,
            ) = predict_tree.predict(
                path_to_weights=model_path,
                path_to_source=image_path,
                return_boxes=True,
            )

            # Extract detection count
            count_str = detec.decode("utf-8")
            detected_count = int(count_str)

        except Exception as e:
            logger.error("Task %s: Detection failed: %s", self.request.id, e)
            raise

        # Update state
        self.update_state(
            state="PROCESSING",
            meta={"status": "Sonuçlar hesaplanıyor...", "progress": 70},
        )

        weight_per_fruit = FRUIT_WEIGHTS[fruit_type]
        weight = detected_count * weight_per_fruit
        total_weight = tree_count * weight
        processing_time = time.time() - start_time

        self.update_state(
            state="PROCESSING",
            meta={"status": "Veritabanına kaydediliyor...", "progress": 90},
        )

        detection_result = DetectionResult.objects.create(
            fruit_type=fruit_type,
            tree_count=tree_count,
            tree_age=tree_age,
            detected_count=detected_count,
            weight=weight,
            total_weight=total_weight,
            processing_time=processing_time,
            confidence_score=confidence_score,
            model_version=Path(model_path).name,
            threshold_used=conf_thres,
            image_path=f"detected/{unique_id}/{Path(image_path).name}",
            task_id=self.request.id,
            bbox_coordinates=bbox_centers,
        )

        logger.info(
            "Task %s: Detection completed. Count=%s, Confidence=%.3f",
            self.request.id,
            detected_count,
            confidence_score,
        )

        # Clean up temp file
        try:
            if os.path.exists(image_path):
                os.unlink(image_path)
                logger.debug(
                    "Task %s: Cleaned up temp file %s", self.request.id, image_path
                )
        except Exception as cleanup_error:
            logger.warning(f"Task {self.request.id}: Cleanup failed: {cleanup_error}")

        # Return results
        result = {
            "task_id": str(self.request.id),
            "status": "SUCCESS",
            "fruit_type": str(fruit_type),
            "detected_count": int(detected_count),
            "weight": float(weight),
            "total_weight": float(total_weight),
            "confidence_score": float(confidence_score),
            "processing_time": float(processing_time),
            "image_path": f"detected/{unique_id}/{Path(image_path).name}",
            "unique_id": str(unique_id),
            "detection_result_id": int(detection_result.pk),
        }

        return result

    except Exception as e:
        logger.error(f"Task {self.request.id}: Fatal error: {e}", exc_info=True)

        # Clean up on failure
        try:
            if os.path.exists(image_path):
                os.unlink(image_path)
        except BaseException:
            pass

        # Update task state to FAILURE with error info
        self.update_state(
            state="FAILURE",
            meta={
                "status": "Hata oluştu",
                "error": str(e),
                "exc_type": type(e).__name__,
            },
        )

        # Re-raise so Celery marks task as failed
        raise


@shared_task(name="detection.tasks.check_model_health")
def check_model_health() -> Dict[str, Any]:
    """
    Periodic task to check model health and degradation.

    This task runs daily via Celery Beat and checks if any
    models are showing signs of degradation.

    Returns:
        dict: Health check results for all models
    """
    logger.info("Starting model health check...")

    fruits = ["mandalina", "elma", "armut", "seftale", "nar"]
    results = {}
    alerts = []

    for fruit in fruits:
        try:
            status = DetectionResult.check_model_degradation(
                fruit_type=fruit, days=7, threshold=0.7
            )

            results[fruit] = status

            if status["is_degraded"]:
                alert_msg = (
                    f"⚠️ Model Degradation Alert: {fruit} "
                    f"confidence={status['avg_confidence']:.3f} "
                    f"(threshold=0.7, samples={status['sample_count']})"
                )
                logger.warning(alert_msg)
                alerts.append(alert_msg)
            else:
                logger.info(
                    f"✅ {fruit}: OK "
                    f"(confidence={status['avg_confidence']:.3f}, "
                    f"samples={status['sample_count']})"
                )

        except Exception as e:
            logger.error("Health check failed for %s: %s", fruit, e)
            results[fruit] = {"error": str(e)}

    if alerts:
        _send_degradation_alert(alerts)

    return {
        "timestamp": time.time(),
        "results": results,
        "alerts": alerts,
        "overall_healthy": len(alerts) == 0,
    }


@shared_task(bind=True, name="detection.tasks.cleanup_old_results")
def cleanup_old_results(self, days_old: int = 30) -> Dict[str, Any]:
    """
    Cleanup old detection results and associated files.

    Args:
        self: Celery task instance
        days_old: Remove results older than this many days

    Returns:
        dict: Cleanup statistics
    """
    import shutil
    from datetime import timedelta
    from pathlib import Path

    from django.conf import settings
    from django.utils import timezone

    logger.info("Starting cleanup of results older than %s days...", days_old)

    cutoff_date = timezone.now() - timedelta(days=days_old)
    media_root = Path(settings.MEDIA_ROOT)

    deleted_db_count = 0
    deleted_file_count = 0
    failed_file_count = 0

    try:
        old_results = DetectionResult.objects.filter(created_at__lt=cutoff_date)

        # Collect file paths before deleting DB records
        image_paths = list(old_results.values_list("image_path", flat=True))

        # Delete DB records
        deleted_db_count, _ = old_results.delete()

        # Delete associated media files
        deleted_dirs = set()
        for image_path in image_paths:
            if not image_path:
                continue
            try:
                full_path = (media_root / image_path).resolve()
                # Security: ensure path is within media root
                if not str(full_path).startswith(str(media_root.resolve())):
                    logger.warning("Path traversal attempt in cleanup: %s", image_path)
                    continue

                if full_path.exists():
                    full_path.unlink()
                    deleted_file_count += 1

                # Track parent directory for potential cleanup
                parent_dir = full_path.parent
                if str(parent_dir).startswith(str(media_root.resolve())):
                    deleted_dirs.add(parent_dir)

            except Exception as file_error:
                logger.warning("Failed to delete file %s: %s", image_path, file_error)
                failed_file_count += 1

        # Remove empty directories
        for dir_path in deleted_dirs:
            try:
                if dir_path.exists() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    logger.debug("Removed empty directory: %s", dir_path)
            except Exception as dir_error:
                logger.debug("Could not remove directory %s: %s", dir_path, dir_error)

        logger.info(
            "Cleanup completed: %s DB records, %s files deleted, %s file failures",
            deleted_db_count,
            deleted_file_count,
            failed_file_count,
        )

        return {
            "status": "SUCCESS",
            "deleted_db_count": int(deleted_db_count),
            "deleted_file_count": int(deleted_file_count),
            "failed_file_count": int(failed_file_count),
            "cutoff_date": cutoff_date.isoformat(),
        }

    except Exception as e:
        logger.error("Cleanup failed: %s", e, exc_info=True)
        return {"status": "FAILURE", "error": str(e)}
