import logging
import os
from datetime import timedelta
from typing import List, Optional

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.utils import timezone

from detection.models import DetectionResult
from dron_map.models import Projects
from reports.models import GeneratedReport, ScheduledReport
from reports.generators.pdf_detection import generate_detection_pdf
from reports.generators.pdf_drone import generate_drone_pdf
from reports.generators.excel_report import generate_detection_excel, generate_drone_excel

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def generate_detection_report(
    detection_result_id: int,
    formats: List[str],
    user_id: Optional[int] = None,
) -> dict:
    results = {}
    try:
        detection_result = DetectionResult.objects.get(pk=detection_result_id)
    except DetectionResult.DoesNotExist:
        logger.error("DetectionResult %s bulunamadı.", detection_result_id)
        return results

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning("Kullanıcı %s bulunamadı, rapor sahipsiz oluşturulacak.", user_id)

    for fmt in formats:
        report_record = GeneratedReport.objects.create(
            report_type="detection",
            format=fmt,
            status="processing",
            detection_result=detection_result,
            created_by=user,
        )

        try:
            file_path = None
            if fmt == "pdf":
                file_path = generate_detection_pdf(detection_result)
            elif fmt == "xlsx":
                file_path = generate_detection_excel([detection_result])

            if file_path:
                report_record.file_path = file_path
                report_record.status = "ready"
                report_record.completed_at = timezone.now()
                report_record.save()
                results[fmt] = file_path
            else:
                report_record.status = "failed"
                report_record.error_message = "Desteklenmeyen format veya üretim başarısız."
                report_record.save()

        except Exception as e:
            logger.exception(
                "DetectionResult %s için %s raporu üretilemedi", detection_result_id, fmt
            )
            report_record.status = "failed"
            report_record.error_message = str(e)
            report_record.save()

    return results


@shared_task
def generate_drone_report(
    project_id: int,
    analysis_data: dict,
    formats: List[str],
    user_id: Optional[int] = None,
) -> dict:
    results = {}
    try:
        project = Projects.objects.get(pk=project_id)
    except Projects.DoesNotExist:
        logger.error("Proje %s bulunamadı.", project_id)
        return results

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning("Kullanıcı %s bulunamadı, rapor sahipsiz oluşturulacak.", user_id)

    for fmt in formats:
        report_record = GeneratedReport.objects.create(
            report_type="drone",
            format=fmt,
            status="processing",
            project=project,
            created_by=user,
        )

        try:
            file_path = None
            if fmt == "pdf":
                file_path = generate_drone_pdf(project, analysis_data)
            elif fmt == "xlsx":
                file_path = generate_drone_excel(project, analysis_data)

            if file_path:
                report_record.file_path = file_path
                report_record.status = "ready"
                report_record.completed_at = timezone.now()
                report_record.save()
                results[fmt] = file_path
            else:
                report_record.status = "failed"
                report_record.error_message = "Desteklenmeyen format veya üretim başarısız."
                report_record.save()

        except Exception as e:
            logger.exception("Proje %s için %s raporu üretilemedi", project_id, fmt)
            report_record.status = "failed"
            report_record.error_message = str(e)
            report_record.save()

    return results


@shared_task
def send_scheduled_reports() -> dict:
    from django.conf import settings

    now = timezone.now()
    due = ScheduledReport.objects.filter(is_active=True, next_run__lte=now).select_related("user", "project")
    sent = 0
    failed = 0

    for schedule in due:
        try:
            file_path = None

            if schedule.report_type == "detection":
                results = DetectionResult.objects.filter(
                    created_by=schedule.user
                ).order_by("-created_at")[:10]
                if not results.exists():
                    _advance_schedule(schedule, now)
                    continue
                if schedule.format == "pdf":
                    file_path = generate_detection_pdf(results.first())
                else:
                    file_path = generate_detection_excel(list(results))

            elif schedule.report_type == "drone" and schedule.project:
                from analysis_logger.service import get_latest_analysis_data
                analysis_data = get_latest_analysis_data(schedule.project.pk)
                if not analysis_data:
                    _advance_schedule(schedule, now)
                    continue
                if schedule.format == "pdf":
                    file_path = generate_drone_pdf(schedule.project, analysis_data)
                else:
                    file_path = generate_drone_excel(schedule.project, analysis_data)

            if file_path:
                _email_report(schedule, file_path, settings)
                GeneratedReport.objects.create(
                    report_type=schedule.report_type,
                    format=schedule.format,
                    status="ready",
                    project=schedule.project,
                    created_by=schedule.user,
                    file_path=file_path,
                    completed_at=now,
                )
                sent += 1

            _advance_schedule(schedule, now)

        except Exception:
            logger.exception("Planlanmış rapor gönderilemedi: schedule_id=%s", schedule.pk)
            failed += 1
            _advance_schedule(schedule, now)

    return {"sent": sent, "failed": failed}


def _advance_schedule(schedule: ScheduledReport, now) -> None:
    schedule.last_sent = now
    if schedule.frequency == "daily":
        schedule.next_run = now + timedelta(days=1)
    elif schedule.frequency == "weekly":
        schedule.next_run = now + timedelta(weeks=1)
    else:
        schedule.next_run = now + timedelta(days=30)
    schedule.save(update_fields=["last_sent", "next_run"])


def _email_report(schedule: ScheduledReport, file_path: str, settings) -> None:
    from django.conf import settings as dj_settings
    full_path = os.path.join(dj_settings.MEDIA_ROOT, file_path)
    if not os.path.exists(full_path):
        return

    freq_label = schedule.get_frequency_display()
    type_label = schedule.get_report_type_display()
    subject = f"Agrisynthia — {freq_label} {type_label}"
    body = (
        f"Merhaba {schedule.user.get_full_name() or schedule.user.username},\n\n"
        f"{freq_label} {type_label} raporunuz ekte sunulmaktadır.\n\n"
        "Agrisynthia Sistemi"
    )
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=dj_settings.DEFAULT_FROM_EMAIL,
        to=[schedule.user.email],
    )
    ext = "pdf" if schedule.format == "pdf" else "xlsx"
    mime = "application/pdf" if ext == "pdf" else (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    with open(full_path, "rb") as f:
        email.attach(os.path.basename(full_path), f.read(), mime)
    email.send(fail_silently=True)
