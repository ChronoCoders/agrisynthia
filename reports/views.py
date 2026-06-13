import json
import logging
import os
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings

from dron_map.models import Projects
from .models import GeneratedReport, ScheduledReport
from .tasks import generate_detection_report, generate_drone_report
from analysis_logger.service import get_latest_analysis_data
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


@login_required
@require_GET
def report_list(request):
    reports = GeneratedReport.objects.filter(created_by=request.user).order_by("-created_at")
    schedules = ScheduledReport.objects.filter(user=request.user).order_by("next_run")
    projects = Projects.objects.filter(created_by=request.user).order_by("Farm", "Field")
    return render(request, "reports/report_list.html", {
        "reports": reports,
        "schedules": schedules,
        "projects": projects,
    })


@login_required
@require_POST
def request_detection_report(request):
    try:
        data = json.loads(request.body)
        detection_result_id = data.get("detection_result_id")
        formats = data.get("formats", ["pdf"])

        if not detection_result_id:
            return JsonResponse({"error": "detection_result_id zorunludur"}, status=400)

        task = generate_detection_report.delay(
            detection_result_id, formats=formats, user_id=request.user.pk
        )
        return JsonResponse(
            {"task_id": task.id, "message": "Rapor oluşturma başlatıldı"}, status=202
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": _("Geçersiz JSON")}, status=400)
    except Exception as e:
        logger.error("Tespit raporu isteği hatası: %s", e)
        return JsonResponse({"error": _("Rapor isteği işlenemedi")}, status=500)


@login_required
@require_POST
def request_drone_report(request):
    try:
        data = json.loads(request.body)
        project_id = data.get("project_id")
        formats = data.get("formats", ["pdf"])

        if not project_id:
            return JsonResponse({"error": "project_id zorunludur"}, status=400)

        analysis_data = get_latest_analysis_data(project_id)
        if not analysis_data:
            return JsonResponse(
                {"error": _("Bu proje için analiz verisi bulunamadı")}, status=404
            )

        task = generate_drone_report.delay(
            project_id, analysis_data, formats=formats, user_id=request.user.pk
        )
        return JsonResponse(
            {"task_id": task.id, "message": "Drone raporu oluşturma başlatıldı"},
            status=202,
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": _("Geçersiz JSON")}, status=400)
    except Exception as e:
        logger.error("Drone raporu isteği hatası: %s", e)
        return JsonResponse({"error": _("Rapor isteği işlenemedi")}, status=500)


@login_required
@require_GET
def download_report(request, report_id):
    report = get_object_or_404(GeneratedReport, pk=report_id, created_by=request.user)

    if report.status != "ready" or not report.file_path:
        raise Http404("Rapor hazır değil veya dosya eksik.")

    full_path = os.path.abspath(
        os.path.join(settings.MEDIA_ROOT, report.file_path)
    )
    media_root = os.path.abspath(settings.MEDIA_ROOT)

    if not full_path.startswith(media_root + os.sep):
        logger.warning("Path traversal girişimi engellendi: %s", full_path)
        raise Http404("Geçersiz dosya yolu.")

    if not os.path.exists(full_path):
        raise Http404("Dosya diskte bulunamadı.")

    content_type = "application/octet-stream"
    if report.format == "pdf":
        content_type = "application/pdf"
    elif report.format == "xlsx":
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    response = FileResponse(open(full_path, "rb"), content_type=content_type)
    response["Content-Disposition"] = (
        f'attachment; filename="{os.path.basename(full_path)}"'
    )
    return response


@login_required
@require_POST
def delete_report(request, report_id):
    report = get_object_or_404(GeneratedReport, id=report_id, created_by=request.user)

    if report.file_path:
        full_path = os.path.abspath(
            os.path.join(settings.MEDIA_ROOT, report.file_path)
        )
        media_root = os.path.abspath(settings.MEDIA_ROOT)

        if full_path.startswith(media_root + os.sep) and os.path.exists(full_path):
            try:
                os.remove(full_path)
            except OSError as e:
                logger.error("Rapor dosyası silinirken hata: %s — %s", full_path, e)

    report.delete()
    return JsonResponse({"message": "Rapor başarıyla silindi."}, status=200)


@login_required
@require_POST
def create_schedule(request):
    report_type = request.POST.get("report_type")
    fmt = request.POST.get("format")
    frequency = request.POST.get("frequency")
    project_id = request.POST.get("project_id") or None

    valid_types = {"detection", "drone"}
    valid_formats = {"pdf", "xlsx"}
    valid_freqs = {"daily", "weekly", "monthly"}

    if report_type not in valid_types or fmt not in valid_formats or frequency not in valid_freqs:
        messages.error(request, _("Geçersiz zamanlama parametresi."))
        return redirect("reports:list")

    project = None
    if project_id:
        project = get_object_or_404(Projects, pk=project_id, created_by=request.user)

    now = timezone.now()
    if frequency == "daily":
        next_run = now + timedelta(days=1)
    elif frequency == "weekly":
        next_run = now + timedelta(weeks=1)
    else:
        next_run = now + timedelta(days=30)

    ScheduledReport.objects.create(
        user=request.user,
        report_type=report_type,
        format=fmt,
        frequency=frequency,
        project=project,
        next_run=next_run,
    )
    messages.success(request, _("Zamanlama oluşturuldu."))
    return redirect("reports:list")


@login_required
@require_POST
def delete_schedule(request, schedule_id):
    schedule = get_object_or_404(ScheduledReport, pk=schedule_id, user=request.user)
    schedule.delete()
    return JsonResponse({"message": "Zamanlama silindi."}, status=200)


@login_required
@require_POST
def toggle_schedule(request, schedule_id):
    schedule = get_object_or_404(ScheduledReport, pk=schedule_id, user=request.user)
    schedule.is_active = not schedule.is_active
    schedule.save(update_fields=["is_active"])
    return JsonResponse({"is_active": schedule.is_active}, status=200)
