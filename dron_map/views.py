# -*- coding: utf-8 -*-
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from detection.constants import DRONE_ALLOWED_EXTENSIONS, MAX_DRONE_FILE_SIZE
from agrisynthia import hashing, options, predict_tree, tasknode
from agrisynthia import histogram as hs

from .forms import Projects_Form
from .models import Projects

BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

HEALTH_ALGORITHMS = {
    "ndvi": "Ndvi",
    "gli": "Gli",
    "vari": "Vari",
    "vndvi": "VNDVI",
    "ndyi": "NDYI",
    "ndre": "NDRE",
    "ndwi": "NDWI",
    "ndvi_blue": "NDVI_Blue",
    "endvi": "ENDVI",
    "mpri": "MPRI",
    "exg": "EXG",
    "tgi": "TGI",
    "bai": "BAI",
    "gndvi": "GNDVI",
    "grvi": "GRVI",
    "savi": "SAVI",
    "mnli": "MNLI",
    "msr": "MSR",
    "rdvi": "RDVI",
    "tdvi": "TDVI",
    "osavi": "OSAVI",
    "lai": "LAI",
    "evi": "EVI",
    "arvi": "ARVI",
}


def validate_uploaded_files(files: List[Any]) -> None:
    if not files:
        raise ValidationError("Dosya bulunamadı")

    for uploaded_file in files:
        if not uploaded_file:
            raise ValidationError("Geçersiz dosya")

        if uploaded_file.size > MAX_DRONE_FILE_SIZE:
            raise ValidationError(f"Dosya çok büyük: {uploaded_file.name}")

        if uploaded_file.size == 0:
            raise ValidationError(f"Boş dosya: {uploaded_file.name}")

        # Extract basename to prevent path traversal
        filename = os.path.basename(uploaded_file.name)

        # Check for path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            logger.warning("Path traversal attempt detected: %s", uploaded_file.name)
            raise ValidationError(f"Geçersiz dosya adı: {uploaded_file.name}")

        ext = filename.split(".")[-1].lower()
        if ext not in DRONE_ALLOWED_EXTENSIONS:
            raise ValidationError(f"Geçersiz dosya tipi: {ext}")


def task_path(task_id: str, dir_path: str, filename: str) -> str:
    return f"results/{task_id}/{dir_path}/{filename}"


def get_full_task_path(task_id: str, dir_path: str, filename: str) -> str:
    return os.path.join(BASE_DIR, f"static/results/{task_id}/{dir_path}", filename)


def get_statistics(task_id: str, stat_type: str) -> Dict[str, Any]:
    if stat_type == "static":
        task = get_full_task_path(task_id, "odm_report", "stats.json")

        if os.path.isfile(task):
            try:
                import json

                with open(task) as f:
                    j = json.load(f)
            except Exception as e:
                return {"error": str(e)}
            return {
                "gsd": j.get("odm_processing_statistics", {}).get("average_gsd"),
                "area": j.get("processing_statistics", {}).get("area"),
                "date": j.get("processing_statistics", {}).get("date"),
                "end_date": j.get("processing_statistics", {}).get("end_date"),
            }
        else:
            return {}

    elif stat_type in ("orthophoto", "plant"):
        task = task_path(task_id, "odm_orthophoto", "odm_orthophoto.tif")
        return {"odm_orthophoto": task}

    elif stat_type == "dsm":
        task = task_path(task_id, "odm_dem", "dsm.tif")
        return {"dsm": task}

    elif stat_type == "dtm":
        task = task_path(task_id, "odm_dem", "dtm.tif")
        return {"dtm": task}

    elif stat_type == "camera_shots":
        task = task_path(task_id, "odm_report", "shots.geojson")
        if os.path.isfile(task):
            try:
                import json

                with open(task) as f:
                    j = json.load(f)
            except Exception as e:
                return {"error": str(e)}
            return {"camera_shots": j}
        else:
            return {}

    elif stat_type == "images_info":
        task = get_full_task_path(task_id, "/", "images.json")

        if os.path.exists(task):
            try:
                import json

                with open(task) as f:
                    j = json.load(f)
            except Exception as e:
                return {"error": str(e)}
            return {
                "camera_model": j[0].get("camera_model"),
                "altitude": j[0].get("altitude"),
            }
        else:
            return {}

    return {}


@login_required
def projects(request: HttpRequest) -> HttpResponse:
    projes = Projects.objects.all()
    return render(request, "projects.html", {"projes": projes, "userss": request.user})


@login_required
def add_projects(
    request: HttpRequest, slug: Optional[str] = None, project_id: Optional[int] = None
) -> HttpResponse:
    if slug == "update" and project_id:
        if not hasattr(request.user, "is_staff") or not request.user.is_staff:
            raise PermissionDenied("Güncelleme yetkisi yok")

        projes = get_object_or_404(Projects, id=project_id)

        if request.method == "POST":
            try:
                form = Projects_Form(request.POST, request.FILES, instance=projes)
                if form.is_valid():
                    try:
                        with transaction.atomic():
                            form.save()
                        logger.info("Proje güncellendi: %s", projes.id)
                        return redirect("dron_map:projects")
                    except Exception as e:
                        logger.error("Veritabanı güncelleme hatası: %s", e)
                        return render(
                            request,
                            "add-projects.html",
                            {
                                "projes": projes,
                                "error": "Proje güncellenemedi",
                                "userss": request.user,
                            },
                        )
                return render(
                    request,
                    "add-projects.html",
                    {"projes": projes, "errors": form.errors, "userss": request.user},
                )
            except Exception as e:
                logger.error("Update error: %s", e)
                return render(
                    request,
                    "add-projects.html",
                    {
                        "projes": projes,
                        "error": "Güncelleme hatası",
                        "userss": request.user,
                    },
                )

        return render(
            request, "add-projects.html", {"projes": projes, "userss": request.user}
        )

    elif slug == "delete" and project_id:
        if not hasattr(request.user, "is_staff") or not request.user.is_staff:
            raise PermissionDenied("Silme yetkisi yok")

        projes = get_object_or_404(Projects, id=project_id)

        try:
            deleted_project_id = projes.id
            with transaction.atomic():
                projes.delete()
            logger.info("Proje silindi: %s", deleted_project_id)
            return redirect("dron_map:projects")
        except Exception as e:
            logger.error("Proje silme hatası: %s: %s", project_id, e)
            return render(
                request,
                "add-projects.html",
                {"projes": projes, "error": "Proje silinemedi", "userss": request.user},
            )

    elif slug == "add":
        if request.method == "POST":
            try:
                form = Projects_Form(request.POST, request.FILES)

                if not form.is_valid():
                    return render(
                        request,
                        "add-projects.html",
                        {"errors": form.errors, "userss": request.user},
                    )

                images_list = request.FILES.getlist("picture")
                validate_uploaded_files(images_list)

                title = form.cleaned_data["Title"]
                field = form.cleaned_data["Field"]

                # Create hashing path
                try:
                    hashing_result = hashing.add_prefix(filename=f"{title}{field}")
                    upload_dir = Path(hashing_result[0])
                except Exception as e:
                    logger.error("Hashing path oluşturma hatası: %s", e)
                    raise ValidationError("Proje dizini oluşturulamadı")

                # Save uploaded images
                saved_files_dir = None
                try:
                    for image in images_list:
                        # Sanitize filename to prevent path traversal
                        if image.name is None:
                            raise ValidationError("Dosya adı bulunamadı")

                        safe_filename = os.path.basename(image.name)
                        if (
                            ".." in safe_filename
                            or "/" in safe_filename
                            or "\\" in safe_filename
                        ):
                            logger.warning(
                                "Path traversal attempt in filename: %s", image.name
                            )
                            raise ValidationError(f"Geçersiz dosya adı: {image.name}")

                        fs = FileSystemStorage(location=str(hashing_result[0]))
                        saved_path = fs.save(safe_filename, image)
                        if not saved_path:
                            logger.error("Dosya kaydetme başarısız: %s", safe_filename)
                            raise IOError(f"Dosya kaydedilemedi: {safe_filename}")
                    saved_files_dir = upload_dir
                except Exception as e:
                    logger.error("Görüntü kaydetme hatası: %s", e)
                    # Clean up any files that were saved
                    if upload_dir.exists():
                        try:
                            shutil.rmtree(str(upload_dir))
                            logger.info("Hatalı dosyalar temizlendi: %s", upload_dir)
                        except Exception as cleanup_error:
                            logger.error("Dosya temizleme hatası: %s", cleanup_error)
                    raise ValidationError(f"Dosyalar kaydedilemedi: {str(e)}")

                # Parse optional field polygon from form
                import json as _json
                from django.contrib.gis.geos import GEOSGeometry as _GEOSGeometry
                raw_polygon = request.POST.get("field_polygon_json", "").strip()
                parsed_polygon = None
                if raw_polygon:
                    try:
                        ring = _json.loads(raw_polygon)
                        geojson = _json.dumps({"type": "Polygon", "coordinates": [ring]})
                        parsed_polygon = _GEOSGeometry(geojson, srid=4326)
                    except Exception:
                        logger.warning("Geçersiz field_polygon JSON, atlandı.")

                # Save project to database with transaction
                try:
                    with transaction.atomic():
                        form.instance.hashing_path = hashing_result[1]
                        form.instance.created_by = request.user
                        if parsed_polygon is not None:
                            form.instance.field_polygon = parsed_polygon
                        project = form.save()
                        logger.info("Proje veritabanına kaydedildi: %s", project.id)
                except Exception as e:
                    logger.error("Veritabanı kaydetme hatası: %s", e)
                    # Database save failed, clean up saved files
                    if saved_files_dir and saved_files_dir.exists():
                        try:
                            shutil.rmtree(str(saved_files_dir))
                            logger.info(
                                "Veritabanı hatası nedeniyle dosyalar silindi: %s",
                                saved_files_dir,
                            )
                        except Exception as cleanup_error:
                            logger.error("Dosya temizleme hatası: %s", cleanup_error)
                    raise ValidationError("Proje kaydedilemedi")

                # Dispatch ODM processing as async Celery task
                from django.conf import settings
                if settings.ODM_ENABLED:
                    try:
                        from dron_map.tasks import process_odm_task
                        process_odm_task.delay(project.id)
                        logger.info(
                            "ODM Celery task gönderildi: proje %s", project.id
                        )
                    except Exception as e:
                        logger.error(
                            "ODM task gönderilemedi proje %s: %s", project.id, e
                        )
                        # Non-critical: project saved, ODM will be skipped

                # Dispatch Sentinel-2 NDVI fetch if polygon was provided
                if parsed_polygon:
                    try:
                        from dron_map.tasks import fetch_sentinel2_ndvi
                        fetch_sentinel2_ndvi.delay(project.id, days_back=90)
                        logger.info("Sentinel-2 NDVI task gönderildi: proje %s", project.id)
                    except Exception as e:
                        logger.error("Sentinel-2 task gönderilemedi proje %s: %s", project.id, e)

                return redirect("dron_map:projects")

            except ValidationError as e:
                return render(
                    request,
                    "add-projects.html",
                    {"error": str(e), "userss": request.user},
                )
            except Exception as e:
                logger.error("Add project error: %s", e)
                return render(
                    request,
                    "add-projects.html",
                    {"error": "Proje oluşturulamadı", "userss": request.user},
                )

        return render(request, "add-projects.html", {"userss": request.user})

    # Default case: if no slug matches, redirect to projects list
    return redirect("dron_map:projects")


def convert(input_path: str, output_path: str) -> None:
    try:
        from osgeo import gdal

        dataset1 = gdal.Open(input_path)
        if dataset1 is None:
            error_msg = f"GDAL: Kaynak dosya açılamadı: {input_path}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        projection = dataset1.GetProjection()
        geotransform = dataset1.GetGeoTransform()

        dataset2 = gdal.Open(output_path, gdal.GA_Update)
        if dataset2 is None:
            error_msg = f"GDAL: Hedef dosya açılamadı: {output_path}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        dataset2.SetGeoTransform(geotransform)
        dataset2.SetProjection(projection)
        dataset2.GetRasterBand(1).SetNoDataValue(0)

        # Close datasets
        dataset1 = None
        dataset2 = None

    except ImportError as e:
        error_msg = f"GDAL kütüphanesi yüklenemedi: {e}"
        logger.error(error_msg)
        raise ImportError(error_msg)
    except AttributeError as e:
        error_msg = f"GDAL dataset hatalı: {e}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"GDAL dönüştürme hatası: {e}"
        logger.error(error_msg)
        raise


@login_required
def maping(request: HttpRequest, id: int) -> HttpResponse:
    projes = get_object_or_404(Projects, id=id)
    algo = options.algorithm
    colors = options.colormaps

    if request.method == "POST":
        orthophoto = get_statistics(task_id=projes.hashing_path, stat_type="orthophoto")
        static = get_statistics(task_id=projes.hashing_path, stat_type="static")
        images_info = get_statistics(
            task_id=projes.hashing_path, stat_type="images_info"
        )

        try:
            range_values = request.POST.getlist("range")
            post_range = tuple(float(v) for v in range_values[:2])
            post_range = (-abs(post_range[0]), abs(post_range[1]))
        except (ValueError, IndexError, TypeError):
            return render(
                request,
                "map.html",
                {
                    "projes": projes,
                    "orthophoto": orthophoto,
                    "algo": options.algorithm,
                    "colors": options.colormaps,
                    "static": static,
                    "images_info": images_info,
                    "error": "Geçersiz aralık değeri",
                },
            )

        health_color = request.POST.get("health_color", "")
        cmap = request.POST.get("cmap", "")

        if health_color == "detect":
            try:
                detec, unique_id, _ = predict_tree.predict(
                    path_to_weights="agac.pt",
                    path_to_source=f'{BASE_DIR}/static/{orthophoto["odm_orthophoto"]}',
                )
                convert(
                    f'{BASE_DIR}/static/{orthophoto["odm_orthophoto"]}',
                    f"{BASE_DIR}/static/detected/{unique_id}/odm_orthophoto.tif",
                )
                return render(
                    request,
                    "map.html",
                    {
                        "orthophoto": {
                            "path": f"detected/{unique_id}/odm_orthophoto.tif",
                            "colormap": cmap,
                            "ranges": post_range,
                        },
                        "algo": algo,
                        "colors": colors,
                        "static": static,
                        "images_info": images_info,
                        "detection": detec.decode("utf-8"),
                    },
                )
            except (ValueError, ImportError) as e:
                logger.error("Detection conversion error: %s", e)
                return render(
                    request,
                    "map.html",
                    {
                        "projes": projes,
                        "orthophoto": orthophoto,
                        "algo": algo,
                        "colors": colors,
                        "static": static,
                        "images_info": images_info,
                        "error": "Algılama veya dönüştürme hatası",
                    },
                )
            except Exception as e:
                logger.error("Unexpected detection error: %s", e)
                return render(
                    request,
                    "map.html",
                    {
                        "projes": projes,
                        "orthophoto": orthophoto,
                        "algo": algo,
                        "colors": colors,
                        "static": static,
                        "images_info": images_info,
                        "error": "Beklenmeyen bir hata oluştu",
                    },
                )

        elif health_color in HEALTH_ALGORITHMS:
            try:
                orthophoto_path = f'{BASE_DIR}/static/{orthophoto["odm_orthophoto"]}'

                # Check if file exists
                if not os.path.exists(orthophoto_path):
                    logger.error("Orthophoto bulunamadı: %s", orthophoto_path)
                    return render(
                        request,
                        "map.html",
                        {
                            "projes": projes,
                            "orthophoto": orthophoto,
                            "algo": algo,
                            "colors": colors,
                            "static": static,
                            "images_info": images_info,
                            "error": "Orthophoto dosyası bulunamadı",
                        },
                    )

                health_algorithm = hs.algos(orthophoto_path, projes.hashing_path)
                method = getattr(health_algorithm, HEALTH_ALGORITHMS[health_color])
                result = method(post_range, cmap)
                return render(
                    request,
                    "map.html",
                    {
                        "orthophoto": result,
                        "algo": algo,
                        "colors": colors,
                        "static": static,
                        "images_info": images_info,
                    },
                )

            except AttributeError as e:
                logger.error("Algoritma metodu bulunamadı: %s: %s", health_color, e)
                return render(
                    request,
                    "map.html",
                    {
                        "projes": projes,
                        "orthophoto": orthophoto,
                        "algo": algo,
                        "colors": colors,
                        "static": static,
                        "images_info": images_info,
                        "error": "Algoritma bulunamadı",
                    },
                )
            except Exception as e:
                logger.error("Sağlık algoritması hatası: %s: %s", health_color, e)
                return render(
                    request,
                    "map.html",
                    {
                        "projes": projes,
                        "orthophoto": orthophoto,
                        "algo": algo,
                        "colors": colors,
                        "static": static,
                        "images_info": images_info,
                        "error": "Algoritma işleme hatası",
                    },
                )

        # Default return for POST if no health_color action matched
        return render(
            request,
            "map.html",
            {
                "projes": projes,
                "orthophoto": orthophoto,
                "algo": algo,
                "colors": colors,
                "static": static,
                "images_info": images_info,
            },
        )
    else:
        orthophoto = get_statistics(task_id=projes.hashing_path, stat_type="orthophoto")
        static = get_statistics(task_id=projes.hashing_path, stat_type="static")
        images_info = get_statistics(
            task_id=projes.hashing_path, stat_type="images_info"
        )

        return render(
            request,
            "map.html",
            {
                "projes": projes,
                "orthophoto": orthophoto,
                "algo": algo,
                "colors": colors,
                "static": static,
                "images_info": images_info,
            },
        )

@login_required
def field_overview(request: HttpRequest) -> HttpResponse:
    """
    Full-screen map showing all of the user's fields as colored polygons.
    Color indicates NDVI health: green ≥ 0.5, yellow 0.3–0.5, red < 0.3, grey = no data.
    """
    import json as _json

    projects = Projects.objects.filter(created_by=request.user)

    features = []
    for p in projects:
        latest = p.ndvi_readings.order_by("-date").values("date", "mean_ndvi").first()

        if latest:
            ndvi = latest["mean_ndvi"]
            if ndvi >= 0.5:
                color = "#2E7D32"
                health = "Sağlıklı"
            elif ndvi >= 0.3:
                color = "#F9A825"
                health = "Uyarı"
            else:
                color = "#C62828"
                health = "Stresli"
            ndvi_display = round(ndvi, 3)
            ndvi_date = latest["date"].isoformat()
        else:
            color = "#9E9E9E"
            health = "Veri yok"
            ndvi_display = None
            ndvi_date = None

        if p.field_polygon:
            import json as _json
            geometry = _json.loads(p.field_polygon.geojson)
        else:
            geometry = None

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": p.id,
                "farm": p.Farm,
                "field": p.Field,
                "title": p.Title,
                "odm_status": p.odm_status,
                "ndvi": ndvi_display,
                "ndvi_date": ndvi_date,
                "health": health,
                "color": color,
                "has_polygon": bool(p.field_polygon),
                "map_url": f"/dron-map/map/{p.id}/",
            },
        })

    geojson = _json.dumps({"type": "FeatureCollection", "features": features})
    return render(request, "field-overview.html", {
        "userss": request.user,
        "geojson": geojson,
        "total": len(features),
        "with_polygon": sum(1 for f in features if f["properties"]["has_polygon"]),
    })


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """
    Field monitoring dashboard — aggregates NDVI trends and detection history
    for the current user's projects.
    """
    import json as _json
    from datetime import date, timedelta

    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate

    from detection.models import DetectionResult
    from dron_map.models import SatelliteNDVI

    projects = list(Projects.objects.filter(created_by=request.user).order_by("Farm", "Field"))
    detections_qs = DetectionResult.objects.filter(created_by=request.user)

    # ── Summary cards ────────────────────────────────────────────────────────
    total_projects = len(projects)
    total_detections = detections_qs.count()

    latest_ndvis = []
    for p in projects:
        last = p.ndvi_readings.order_by("-date").values("mean_ndvi").first()
        if last:
            latest_ndvis.append(last["mean_ndvi"])

    avg_ndvi = round(sum(latest_ndvis) / len(latest_ndvis), 3) if latest_ndvis else None
    healthy_count = sum(1 for v in latest_ndvis if v >= 0.5)
    stressed_count = sum(1 for v in latest_ndvis if v < 0.3)

    # ── Field health table ───────────────────────────────────────────────────
    field_rows = []
    for p in projects:
        readings = list(p.ndvi_readings.order_by("date").values("date", "mean_ndvi"))
        latest_ndvi = readings[-1]["mean_ndvi"] if readings else None
        prev_ndvi = readings[-2]["mean_ndvi"] if len(readings) >= 2 else None

        if latest_ndvi is not None and prev_ndvi is not None:
            diff = latest_ndvi - prev_ndvi
            trend = "up" if diff > 0.02 else ("down" if diff < -0.02 else "stable")
        else:
            trend = None

        last_det = (
            detections_qs.order_by("-created_at").values("fruit_type", "created_at").first()
        )

        field_rows.append({
            "project": p,
            "latest_ndvi": round(latest_ndvi, 3) if latest_ndvi is not None else None,
            "trend": trend,
            "last_detection": last_det,
            "ndvi_count": len(readings),
        })

    # ── NDVI multi-line chart data ───────────────────────────────────────────
    ndvi_datasets = []
    colors = [
        "#2E7D32", "#1565C0", "#E65100", "#6A1B9A",
        "#00838F", "#AD1457", "#F9A825", "#4E342E",
    ]
    for i, p in enumerate(projects):
        readings = list(
            p.ndvi_readings.order_by("date").values("date", "mean_ndvi")
        )
        if not readings:
            continue
        color = colors[i % len(colors)]
        ndvi_datasets.append({
            "label": f"{p.Farm} / {p.Field}",
            "data": [{"x": r["date"].isoformat(), "y": round(r["mean_ndvi"], 3)} for r in readings],
            "borderColor": color,
            "backgroundColor": color + "22",
            "borderWidth": 2,
            "pointRadius": 3,
            "tension": 0.3,
            "fill": False,
        })

    # ── Detection history bar chart (last 60 days, by fruit type) ───────────
    cutoff = date.today() - timedelta(days=60)
    fruit_colors = {
        "mandalina": "#FF8C00", "elma": "#C62828", "armut": "#F9A825",
        "seftale": "#E91E63", "nar": "#880E4F",
    }

    det_by_date_fruit = (
        detections_qs
        .filter(created_at__date__gte=cutoff)
        .annotate(day=TruncDate("created_at"))
        .values("day", "fruit_type")
        .annotate(total=Sum("detected_count"))
        .order_by("day")
    )

    # Build label list (all days in range) and datasets per fruit type
    all_days = [(date.today() - timedelta(days=d)).isoformat() for d in range(59, -1, -1)]
    fruit_totals: dict[str, dict[str, int]] = {}
    for row in det_by_date_fruit:
        ft = row["fruit_type"]
        day = row["day"].isoformat()
        fruit_totals.setdefault(ft, {})
        fruit_totals[ft][day] = row["total"]

    det_datasets = []
    for ft, day_map in fruit_totals.items():
        color = fruit_colors.get(ft, "#607D8B")
        det_datasets.append({
            "label": ft.capitalize(),
            "data": [day_map.get(d, 0) for d in all_days],
            "backgroundColor": color + "CC",
            "borderColor": color,
            "borderWidth": 1,
        })

    # ── Recent detections (last 10) ──────────────────────────────────────────
    recent_detections = list(
        detections_qs.order_by("-created_at")
        .values("fruit_type", "detected_count", "confidence_score", "created_at")[:10]
    )
    for r in recent_detections:
        r["created_at"] = r["created_at"].strftime("%d.%m.%Y %H:%M")

    return render(request, "dashboard.html", {
        "userss": request.user,
        "total_projects": total_projects,
        "total_detections": total_detections,
        "avg_ndvi": avg_ndvi,
        "healthy_count": healthy_count,
        "stressed_count": stressed_count,
        "field_rows": field_rows,
        "ndvi_chart_json": _json.dumps({"datasets": ndvi_datasets}),
        "det_labels_json": _json.dumps(all_days),
        "det_datasets_json": _json.dumps(det_datasets),
        "recent_detections": recent_detections,
    })


@login_required
def ndvi_data(request, project_id: int) -> JsonResponse:
    """
    Return Sentinel-2 NDVI time series for a project as JSON.
    GET /dron-map/projects/<id>/ndvi/
    """
    from dron_map.models import SatelliteNDVI

    project = get_object_or_404(Projects, id=project_id, created_by=request.user)
    readings = list(
        SatelliteNDVI.objects.filter(project=project)
        .order_by("date")
        .values("date", "mean_ndvi", "min_ndvi", "max_ndvi", "cloud_cover")
    )
    # Convert date objects to ISO strings for JSON
    for r in readings:
        r["date"] = r["date"].isoformat()

    has_polygon = bool(project.field_polygon)
    return JsonResponse({
        "project_id": project_id,
        "has_polygon": has_polygon,
        "readings": readings,
    })


@login_required
def yield_prediction(request: HttpRequest) -> HttpResponse:
    """
    Yield prediction page: lets the user pick a project and see an estimate
    built from detection data + Sentinel-2 NDVI via the yield_predictor module.
    Also accepts a manual form so users can override tree_count / tree_age.
    """
    from detection.models import DetectionResult
    from .yield_predictor import YieldEstimate, _SPECIES_PARAMS

    projects = list(Projects.objects.filter(created_by=request.user).order_by("Farm", "Field"))

    estimate_dict = None
    selected_project = None
    error = None

    if request.method == "POST":
        try:
            project_id = request.POST.get("project_id")
            fruit_type = request.POST.get("fruit_type", "").strip()
            tree_count = int(request.POST.get("tree_count") or 0)
            tree_age = int(request.POST.get("tree_age") or 0)
            detected_count = int(request.POST.get("detected_count") or 0)
            avg_ndvi_raw = request.POST.get("avg_ndvi") or None
            avg_ndvi = float(avg_ndvi_raw) if avg_ndvi_raw else None

            if project_id:
                selected_project = get_object_or_404(Projects, pk=project_id, created_by=request.user)
                # Pull NDVI from DB if not manually provided
                if avg_ndvi is None:
                    qs = selected_project.ndvi_readings.order_by("-date").values_list("mean_ndvi", flat=True)[:6]
                    avg_ndvi = (sum(qs) / len(qs)) if qs else None
                # Pull detection if not manually provided
                if not detected_count or not fruit_type:
                    det = DetectionResult.objects.filter(created_by=request.user).order_by("-created_at").first()
                    if det:
                        fruit_type = fruit_type or det.fruit_type
                        tree_count = tree_count or det.tree_count or 1
                        tree_age = tree_age or det.tree_age or 0
                        detected_count = detected_count or det.detected_count or 0

            if not fruit_type:
                error = "Meyve türü seçilmedi."
            elif not tree_count:
                error = "Ağaç sayısı girilmedi."
            else:
                est = YieldEstimate(
                    fruit_type=fruit_type,
                    tree_count=tree_count,
                    tree_age=tree_age,
                    detected_count=detected_count,
                    avg_ndvi=avg_ndvi,
                )
                estimate_dict = est.as_dict()
        except Exception as exc:
            logger.error("Verim tahmini hatası: %s", exc)
            error = "Hesaplama sırasında hata oluştu."

    fruit_types = list(_SPECIES_PARAMS.keys())
    return render(request, "yield-prediction.html", {
        "userss": request.user,
        "projects": projects,
        "selected_project": selected_project,
        "estimate": estimate_dict,
        "error": error,
        "fruit_types": fruit_types,
    })


@login_required
def odm_status(request, project_id: int) -> JsonResponse:
    """
    Return current ODM processing status for a project.
    GET /dron-map/projects/{id}/odm-status/
    """
    project = get_object_or_404(Projects, id=project_id, created_by=request.user)
    return JsonResponse({
        "project_id": project.id,
        "odm_status": project.odm_status,
        "odm_task_id": project.odm_task_id,
        "odm_error": project.odm_error,
        "ready": project.odm_status == Projects.ODM_COMPLETED,
    })
