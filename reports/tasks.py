# -*- coding: utf-8 -*-
import logging
from typing import List, Optional

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from detection.models import DetectionResult
from dron_map.models import Projects
from reports.models import GeneratedReport
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
    """
    Generates reports for a given DetectionResult in specified formats.
    """
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
    """
    Generates reports for a given Project (Drone Analysis) in specified formats.
    """
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
