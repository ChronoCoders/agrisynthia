# -*- coding: utf-8 -*-
"""
Celery tasks for ODM (NodeODM) processing and Sentinel-2 NDVI fetching.

ODM flow:
  1. User uploads drone images via the add-project form.
  2. Images are saved to disk synchronously.
  3. process_odm_task is dispatched as a Celery task (async).
  4. The task creates a NodeODM task, polls for completion, then downloads
     the output assets into static/results/{hashing_path}/.
  5. Project.odm_status is updated at each step so the frontend can poll.

Sentinel-2 flow:
  1. User draws a field polygon when creating/editing a project.
  2. fetch_sentinel2_ndvi(project_id) queries Element84 Earth Search STAC,
     reads B04/B08 COG bands via rio-tiler, computes NDVI statistics, and
     stores one SatelliteNDVI row per scene date.
  3. refresh_all_sentinel2_ndvi() dispatches fetch_sentinel2_ndvi for every
     project that has a polygon. Run weekly via Celery Beat.
"""
import logging
import os
from pathlib import Path

import numpy as np
import requests as http_requests
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(settings.BASE_DIR)

# ---------------------------------------------------------------------------
# Sentinel-2 helpers
# ---------------------------------------------------------------------------

_STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1"
_STAC_COLLECTION = "sentinel-2-l2a"
# Asset key candidates for red (B04) and NIR (B08) across catalog versions
_RED_KEYS = ("red",)
_NIR_KEYS = ("nir", "nir08", "B08")


def _polygon_bbox(coords: list) -> list:
    """Return [min_lng, min_lat, max_lng, max_lat] from a GeoJSON ring."""
    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return [min(lngs), min(lats), max(lngs), max(lats)]


def _search_scenes(bbox: list, start: str, end: str, cloud_max: int = 30) -> list:
    resp = http_requests.post(
        f"{_STAC_ENDPOINT}/search",
        json={
            "collections": [_STAC_COLLECTION],
            "bbox": bbox,
            "datetime": f"{start}/{end}",
            "query": {"eo:cloud_cover": {"lt": cloud_max}},
            "sortby": [{"field": "datetime", "direction": "asc"}],
            "limit": 100,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("features", [])


def _get_asset_href(assets: dict, keys: tuple) -> str | None:
    for k in keys:
        href = assets.get(k, {}).get("href")
        if href:
            return href
    return None


def _compute_ndvi(red_href: str, nir_href: str, bbox: list) -> dict | None:
    """Read COG bands for bbox and return NDVI statistics, or None if too few pixels."""
    from rio_tiler.io import Reader

    with Reader(red_href) as r:
        red_img = r.part(bbox)
    with Reader(nir_href) as r:
        nir_img = r.part(bbox)

    red = red_img.data[0].astype(float)
    nir = nir_img.data[0].astype(float)

    denom = nir + red
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = np.where(denom > 0, (nir - red) / denom, np.nan)

    valid = ndvi[~np.isnan(ndvi)]
    if valid.size < 10:
        return None

    return {
        "mean": float(np.nanmean(valid)),
        "min": float(np.nanmin(valid)),
        "max": float(np.nanmax(valid)),
        "std": float(np.nanstd(valid)),
    }


@shared_task(bind=True, max_retries=0, name="dron_map.process_odm_task")
def process_odm_task(self, project_id: int) -> dict:
    """
    Run NodeODM processing for a project.

    Args:
        project_id: Primary key of the dron_map.Projects instance.

    Returns:
        dict with keys: project_id, status, odm_task_id, output_path
    """
    from dron_map.models import Projects

    try:
        project = Projects.objects.get(pk=project_id)
    except Projects.DoesNotExist:
        logger.error("process_odm_task: proje bulunamadı pk=%s", project_id)
        return {"error": f"Proje bulunamadı: {project_id}"}

    if not settings.ODM_ENABLED:
        logger.info("ODM devre dışı; proje %s atlandı.", project_id)
        project.odm_status = Projects.ODM_DISABLED
        project.save(update_fields=["odm_status"])
        return {"project_id": project_id, "status": Projects.ODM_DISABLED}

    # Locate uploaded images — saved by the view into static/images_ortho/{hashing_path}
    image_dir = BASE_DIR / "static" / "images_ortho" / project.hashing_path
    output_dir = BASE_DIR / "static" / "results" / project.hashing_path

    if not image_dir.exists():
        err = f"Görüntü dizini bulunamadı: {image_dir}"
        logger.error("process_odm_task proje %s: %s", project_id, err)
        project.odm_status = Projects.ODM_FAILED
        project.odm_error = err
        project.save(update_fields=["odm_status", "odm_error"])
        return {"project_id": project_id, "error": err}

    # Mark as processing
    project.odm_status = Projects.ODM_PROCESSING
    project.save(update_fields=["odm_status"])

    try:
        from pyodm import Node
        from pyodm.exceptions import TaskFailedError

        node = Node(
            host=settings.ODM_HOST,
            port=settings.ODM_PORT,
            token=settings.ODM_TOKEN or None,
        )

        # Collect image files
        import glob as glob_mod
        images = (
            glob_mod.glob(str(image_dir / "*.JPG"))
            + glob_mod.glob(str(image_dir / "*.jpg"))
            + glob_mod.glob(str(image_dir / "*.PNG"))
            + glob_mod.glob(str(image_dir / "*.png"))
        )

        if not images:
            raise ValueError(f"Klasörde desteklenen görüntü bulunamadı: {image_dir}")

        logger.info(
            "ODM task başlatılıyor — proje %s, %d görüntü, host=%s:%s",
            project_id, len(images), settings.ODM_HOST, settings.ODM_PORT,
        )

        task = node.create_task(
            images,
            options={"dsm": True, "dtm": True, "orthophoto-resolution": 5},
        )

        project.odm_task_id = task.uuid
        project.save(update_fields=["odm_task_id"])
        logger.info("ODM task oluşturuldu: %s (proje %s)", task.uuid, project_id)

        # Block until ODM finishes (runs in Celery worker, not in web process)
        task.wait_for_completion()

        # Download results
        output_dir.mkdir(parents=True, exist_ok=True)
        task.download_assets(str(output_dir))
        logger.info("ODM sonuçları indirildi: %s (proje %s)", output_dir, project_id)

        project.odm_status = Projects.ODM_COMPLETED
        project.odm_error = None
        project.save(update_fields=["odm_status", "odm_error"])

        return {
            "project_id": project_id,
            "status": Projects.ODM_COMPLETED,
            "odm_task_id": task.uuid,
            "output_path": str(output_dir),
        }

    except Exception as e:
        logger.error(
            "ODM işleme hatası proje %s: %s", project_id, e, exc_info=True
        )
        project.odm_status = Projects.ODM_FAILED
        project.odm_error = str(e)
        project.save(update_fields=["odm_status", "odm_error"])
        return {"project_id": project_id, "error": str(e)}


@shared_task(name="dron_map.watchdog_stuck_odm_tasks")
def watchdog_stuck_odm_tasks() -> dict:
    """
    Periodic watchdog that marks ODM projects stuck in 'processing' as failed.

    A project is considered stuck if it has been in ODM_PROCESSING status for
    longer than ODM_STUCK_TIMEOUT_MINUTES (default 120 minutes). This covers the
    case where the Celery worker crashed mid-task and never updated the status.
    """
    from datetime import timedelta

    from django.utils import timezone

    from dron_map.models import Projects

    timeout_minutes = getattr(settings, "ODM_STUCK_TIMEOUT_MINUTES", 120)
    cutoff = timezone.now() - timedelta(minutes=timeout_minutes)

    stuck = Projects.objects.filter(
        odm_status=Projects.ODM_PROCESSING,
        updated_at__lt=cutoff,
    )

    count = stuck.count()
    if count == 0:
        logger.info("ODM watchdog: stuck proje yok.")
        return {"recovered": 0}

    ids = list(stuck.values_list("pk", flat=True))
    stuck.update(
        odm_status=Projects.ODM_FAILED,
        odm_error=f"Watchdog: {timeout_minutes} dakika sonra zaman aşımı.",
    )
    logger.warning(
        "ODM watchdog: %d takılı proje başarısız olarak işaretlendi (pk=%s)",
        count, ids,
    )
    return {"recovered": count, "project_ids": ids}


# ---------------------------------------------------------------------------
# Sentinel-2 NDVI tasks
# ---------------------------------------------------------------------------

@shared_task(name="dron_map.fetch_sentinel2_ndvi")
def fetch_sentinel2_ndvi(project_id: int, days_back: int = 90) -> dict:
    """
    Fetch Sentinel-2 NDVI time series for a single project.

    Queries Element84 Earth Search (free, no auth) for sentinel-2-l2a scenes
    that intersect the project's field_polygon, reads B04/B08 COG bands via
    rio-tiler, computes NDVI statistics, and upserts SatelliteNDVI rows.
    Already-stored dates are skipped to avoid redundant downloads.

    Args:
        project_id: PK of the dron_map.Projects instance.
        days_back: How many days back from today to search.
    """
    from datetime import date, timedelta

    from dron_map.models import Projects, SatelliteNDVI

    try:
        project = Projects.objects.get(pk=project_id)
    except Projects.DoesNotExist:
        logger.error("fetch_sentinel2_ndvi: proje bulunamadı pk=%s", project_id)
        return {"error": f"Proje bulunamadı: {project_id}"}

    if not project.field_polygon:
        logger.info("fetch_sentinel2_ndvi: proje %s için polygon tanımlanmamış, atlandı.", project_id)
        return {"project_id": project_id, "skipped": "polygon yok"}

    bbox = _polygon_bbox(project.field_polygon)
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)
    cloud_max = getattr(settings, "SENTINEL2_CLOUD_MAX", 30)

    logger.info(
        "Sentinel-2 NDVI fetch — proje %s, bbox=%s, %s→%s, cloud<%s%%",
        project_id, bbox, start_date, end_date, cloud_max,
    )

    try:
        scenes = _search_scenes(bbox, start_date.isoformat(), end_date.isoformat(), cloud_max)
    except Exception as e:
        logger.error("STAC arama hatası proje %s: %s", project_id, e)
        return {"project_id": project_id, "error": str(e)}

    saved = 0
    skipped = 0
    for scene in scenes:
        scene_date_str = scene["properties"]["datetime"][:10]
        assets = scene.get("assets", {})

        red_href = _get_asset_href(assets, _RED_KEYS)
        nir_href = _get_asset_href(assets, _NIR_KEYS)

        if not red_href or not nir_href:
            logger.debug("STAC sahne %s: kırmızı/NIR asset bulunamadı, atlandı.", scene.get("id"))
            skipped += 1
            continue

        if SatelliteNDVI.objects.filter(project=project, date=scene_date_str).exists():
            skipped += 1
            continue

        try:
            stats = _compute_ndvi(red_href, nir_href, bbox)
            if stats is None:
                logger.debug("STAC sahne %s: geçerli piksel yetersiz, atlandı.", scene.get("id"))
                skipped += 1
                continue

            SatelliteNDVI.objects.create(
                project=project,
                date=scene_date_str,
                mean_ndvi=stats["mean"],
                min_ndvi=stats["min"],
                max_ndvi=stats["max"],
                std_ndvi=stats["std"],
                cloud_cover=scene["properties"].get("eo:cloud_cover"),
                scene_id=scene.get("id", ""),
            )
            saved += 1
            logger.info("NDVI kaydedildi: proje %s, tarih=%s, mean=%.3f", project_id, scene_date_str, stats["mean"])

        except Exception as e:
            logger.warning("NDVI hesaplama hatası sahne %s: %s", scene.get("id"), e)
            skipped += 1

    logger.info(
        "fetch_sentinel2_ndvi tamamlandı — proje %s: %d sahne, %d kaydedildi, %d atlandı",
        project_id, len(scenes), saved, skipped,
    )
    return {"project_id": project_id, "scenes": len(scenes), "saved": saved, "skipped": skipped}


@shared_task(name="dron_map.refresh_all_sentinel2_ndvi")
def refresh_all_sentinel2_ndvi() -> dict:
    """
    Dispatch fetch_sentinel2_ndvi for all projects that have a field polygon.
    Run weekly via Celery Beat to keep NDVI time series current.
    """
    from dron_map.models import Projects

    ids = list(
        Projects.objects.exclude(field_polygon__isnull=True).values_list("pk", flat=True)
    )
    for pk in ids:
        fetch_sentinel2_ndvi.delay(pk, days_back=14)

    logger.info("refresh_all_sentinel2_ndvi: %d proje için task gönderildi.", len(ids))
    return {"dispatched": len(ids)}


# ---------------------------------------------------------------------------
# NDVI stress alert task
# ---------------------------------------------------------------------------

@shared_task(name="dron_map.send_ndvi_stress_alerts")
def send_ndvi_stress_alerts() -> dict:
    """
    Weekly task: email each user a summary of their stressed/warning fields.

    Thresholds (configurable via settings):
      NDVI_STRESS_THRESHOLD  < value → stressed  (default 0.3)
      NDVI_WARN_THRESHOLD    < value → warning   (default 0.5)

    A per-user cache key prevents duplicate emails within
    NDVI_ALERT_COOLDOWN_DAYS (default 7 days).
    """
    from collections import defaultdict

    from django.contrib.auth import get_user_model
    from django.core.cache import cache
    from django.core.mail import send_mail

    from dron_map.models import Projects

    User = get_user_model()

    stress_threshold = getattr(settings, "NDVI_STRESS_THRESHOLD", 0.3)
    warn_threshold   = getattr(settings, "NDVI_WARN_THRESHOLD", 0.5)
    cooldown_days    = getattr(settings, "NDVI_ALERT_COOLDOWN_DAYS", 7)
    cooldown_secs    = cooldown_days * 86400
    from_email       = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@agrisynthia.io")

    # Collect latest NDVI per project, grouped by owner
    alerts_by_user: dict[int, list[dict]] = defaultdict(list)

    projects = Projects.objects.exclude(created_by__isnull=True).select_related("created_by")
    for project in projects:
        latest = project.ndvi_readings.order_by("-date").values("date", "mean_ndvi").first()
        if latest is None:
            continue

        ndvi = latest["mean_ndvi"]
        if ndvi >= warn_threshold:
            continue  # healthy — no alert needed

        level = "stressed" if ndvi < stress_threshold else "warning"
        alerts_by_user[project.created_by_id].append({
            "farm":  project.Farm,
            "field": project.Field,
            "title": project.Title,
            "ndvi":  round(ndvi, 3),
            "date":  latest["date"].isoformat(),
            "level": level,
        })

    if not alerts_by_user:
        logger.info("send_ndvi_stress_alerts: uyarı gerektiren tarla yok.")
        return {"users_alerted": 0, "fields_flagged": 0}

    users_alerted = 0
    fields_flagged = 0

    for user_id, field_alerts in alerts_by_user.items():
        cache_key = f"agrisynthia:alert:ndvi:{user_id}"
        if cache.get(cache_key):
            logger.info("NDVI uyarı cooldown aktif, kullanıcı %s atlandı.", user_id)
            continue

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            continue

        recipient = user.email
        if not recipient:
            logger.info("Kullanıcı %s e-posta adresi yok, atlandı.", user_id)
            continue

        stressed = [f for f in field_alerts if f["level"] == "stressed"]
        warning  = [f for f in field_alerts if f["level"] == "warning"]

        lines = ["Merhaba,\n",
                 "Aşağıdaki tarlalarınızda Sentinel-2 NDVI değerleri düşük seviyede.\n"]

        if stressed:
            lines.append("🔴 STRESLİ TARLALAR (NDVI < {:.1f}):".format(stress_threshold))
            for f in stressed:
                lines.append(f"  • {f['farm']} / {f['field']} ({f['title']})"
                              f" — NDVI: {f['ndvi']}  [{f['date']}]")

        if warning:
            lines.append("\n🟡 UYARI (NDVI {:.1f}–{:.1f}):".format(stress_threshold, warn_threshold))
            for f in warning:
                lines.append(f"  • {f['farm']} / {f['field']} ({f['title']})"
                              f" — NDVI: {f['ndvi']}  [{f['date']}]")

        lines += [
            "\nDaha fazla bilgi için Agrisynthia kontrol panelini ziyaret edin.",
            "\n— Agrisynthia Otomatik İzleme Sistemi",
        ]

        subject = (
            "[Agrisynthia] Tarla Stres Uyarısı"
            if stressed
            else "[Agrisynthia] Tarla NDVI Uyarısı"
        )

        try:
            send_mail(
                subject=subject,
                message="\n".join(lines),
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False,
            )
            cache.set(cache_key, True, timeout=cooldown_secs)
            users_alerted += 1
            fields_flagged += len(field_alerts)
            logger.info(
                "NDVI uyarı e-postası gönderildi: %s (%d tarla)",
                recipient, len(field_alerts),
            )
        except Exception as e:
            logger.error("NDVI uyarı e-postası gönderilemedi %s: %s", recipient, e)

    logger.info(
        "send_ndvi_stress_alerts tamamlandı: %d kullanıcı uyarıldı, %d tarla işaretlendi.",
        users_alerted, fields_flagged,
    )
    return {"users_alerted": users_alerted, "fields_flagged": fields_flagged}
