import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from celery import shared_task

from detection.models import DetectionResult, ModelVersion
from agrisynthia import predict_tree

from detection.constants import (
    DETECTION_CONFIDENCE_THRESHOLD,
    FRUIT_WEIGHTS,
)

logger = logging.getLogger(__name__)


def _send_degradation_alert(alerts: list) -> None:
    import json
    import urllib.request
    from django.conf import settings
    from django.core.cache import cache

    if not alerts:
        return

    cache_key = "agrisynthia:alert:model_degradation"
    if cache.get(cache_key):
        logger.info("Alert cooldown active, skipping alert dispatch")
        return

    alert_text = "\n".join(alerts)
    cooldown = getattr(settings, "ALERT_COOLDOWN_SECONDS", 3600)

    cache.set(cache_key, True, timeout=cooldown)

    webhook_url = getattr(settings, "ALERT_WEBHOOK_URL", "")
    if webhook_url:
        try:
            payload = {
                "text": f"*Agrisynthia Model Degradation Alert*\n{alert_text}",
                "username": "Agrisynthia Monitor",
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

    recipients = getattr(settings, "ALERT_EMAIL_RECIPIENTS", [])
    recipients = [r.strip() for r in recipients if r.strip()]
    if recipients:
        try:
            from django.core.mail import send_mail
            from django.conf import settings as django_settings

            send_mail(
                subject="[Agrisynthia] Model Degradation Detected",
                message=f"Model degradation alerts:\n\n{alert_text}",
                from_email=getattr(
                    django_settings, "DEFAULT_FROM_EMAIL", "noreply@agrisynthia.local"
                ),
                recipient_list=recipients,
                fail_silently=False,
            )
            logger.info(
                "Degradation alert email sent to %s recipients", len(recipients)
            )
        except Exception as email_error:
            logger.error("Failed to send email alert: %s", email_error)


@shared_task(
    bind=True,
    name="detection.tasks.process_image_detection",
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
)
def process_image_detection(
    self,
    image_path: str,
    fruit_type: str,
    tree_count: int,
    tree_age: int,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        self.update_state(
            state="PROCESSING", meta={"status": "Görüntü işleniyor...", "progress": 10}
        )

        try:
            ModelVersion.get_active(fruit_type)
        except LookupError as exc:
            raise ValueError(f"Geçersiz veya aktif versiyonu olmayan meyve grubu: {fruit_type}") from exc

        conf_thres = DETECTION_CONFIDENCE_THRESHOLD

        logger.info(
            "Task %s: Starting detection for %s on image %s",
            self.request.id,
            fruit_type,
            image_path,
        )

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
                fruit_type=fruit_type,
                path_to_source=image_path,
                return_boxes=True,
            )

            count_str = detec.decode("utf-8")
            detected_count = int(count_str)

        except Exception as e:
            logger.error("Task %s: Detection failed: %s", self.request.id, e)
            raise

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

        try:
            _mv = ModelVersion.get_active(fruit_type)
            _model_version_label = f"{fruit_type}:{_mv.version}"
        except LookupError:
            _model_version_label = fruit_type

        detection_result = DetectionResult.objects.create(
            fruit_type=fruit_type,
            tree_count=tree_count,
            tree_age=tree_age,
            detected_count=detected_count,
            weight=weight,
            total_weight=total_weight,
            processing_time=processing_time,
            confidence_score=confidence_score,
            model_version=_model_version_label,
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

        try:
            if os.path.exists(image_path):
                os.unlink(image_path)
                logger.debug(
                    "Task %s: Cleaned up temp file %s", self.request.id, image_path
                )
        except Exception as cleanup_error:
            logger.warning(f"Task {self.request.id}: Cleanup failed: {cleanup_error}")

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

        try:
            if os.path.exists(image_path):
                os.unlink(image_path)
        except BaseException:
            pass

        self.update_state(
            state="FAILURE",
            meta={
                "status": "Hata oluştu",
                "error": str(e),
                "exc_type": type(e).__name__,
            },
        )

        raise


@shared_task(name="detection.tasks.check_model_health")
def check_model_health() -> Dict[str, Any]:
    logger.info("Starting model health check...")

    active_versions = ModelVersion.objects.filter(is_active=True).order_by("fruit_type")
    results = {}
    alerts = []

    for mv in active_versions:
        fruit = mv.fruit_type
        try:
            status = DetectionResult.check_model_degradation(
                fruit_type=fruit, days=7, threshold=0.7
            )

            results[fruit] = status

            if status["is_degraded"]:
                alert_msg = (
                    f"⚠️ Model Degradation Alert: {fruit} ({mv.version}) "
                    f"confidence={status['avg_confidence']:.3f} "
                    f"(threshold=0.7, samples={status['sample_count']})"
                )
                logger.warning(alert_msg)
                alerts.append(alert_msg)
            else:
                logger.info(
                    f"✅ {fruit} ({mv.version}): OK "
                    f"(confidence={status['avg_confidence']:.3f}, "
                    f"samples={status['sample_count']})"
                )

        except Exception as e:
            logger.error("Health check failed for %s (%s): %s", fruit, mv.version, e)
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

        image_paths = list(old_results.values_list("image_path", flat=True))

        deleted_db_count, _ = old_results.delete()

        deleted_dirs = set()
        for image_path in image_paths:
            if not image_path:
                continue
            try:
                full_path = (media_root / image_path).resolve()
                if not str(full_path).startswith(str(media_root.resolve())):
                    logger.warning("Path traversal attempt in cleanup: %s", image_path)
                    continue

                if full_path.exists():
                    full_path.unlink()
                    deleted_file_count += 1

                parent_dir = full_path.parent
                if str(parent_dir).startswith(str(media_root.resolve())):
                    deleted_dirs.add(parent_dir)

            except Exception as file_error:
                logger.warning("Failed to delete file %s: %s", image_path, file_error)
                failed_file_count += 1

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
