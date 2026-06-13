import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import magic
from celery.result import AsyncResult
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from detection.cache_utils import (
    calculate_image_hash,
    get_cache_statistics,
    get_cached_prediction,
    invalidate_all_predictions,
    invalidate_prediction_cache,
    set_cached_prediction,
)
from detection.constants import (
    DETECTION_ALLOWED_EXTENSIONS,
    DETECTION_ALLOWED_MIME_TYPES,
    DETECTION_CONFIDENCE_THRESHOLD,
    FRUIT_MODEL_PATHS,
    FRUIT_WEIGHTS,
    MAX_DETECTION_FILE_SIZE,
)
from detection.models import ModelVersion
from detection.tasks import process_image_detection
from agrisynthia import hashing, predict_tree

BASE_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)

FRUIT_MODELS = {k: str(v) for k, v in FRUIT_MODEL_PATHS.items()}


def validate_image_file(file: UploadedFile) -> bool:
    if not file:
        raise ValidationError("Dosya bulunamadı")

    if file.size is not None and file.size > MAX_DETECTION_FILE_SIZE:
        raise ValidationError("Dosya boyutu çok büyük (maksimum 10MB)")

    if file.name is None:
        raise ValidationError("Dosya adı bulunamadı")

    filename = os.path.basename(file.name)

    if ".." in filename or "/" in filename or "\\" in filename:
        logger.warning("Path traversal attempt detected: %s", file.name)
        raise ValidationError("Geçersiz dosya adı")

    ext = filename.split(".")[-1].lower()
    if ext not in DETECTION_ALLOWED_EXTENSIONS:
        raise ValidationError("Geçersiz dosya formatı")

    try:
        file.seek(0)
        file_header = file.read(2048)
        file.seek(0)
        mime = magic.from_buffer(file_header, mime=True)
    except Exception as e:
        logger.error("Magic bytes okunamadı — %s: %s", file.name, e)
        raise ValidationError("Dosya tipi belirlenemedi")

    if mime not in DETECTION_ALLOWED_MIME_TYPES:
        logger.warning(
            "MIME tipi uyuşmazlığı: beklenen resim, alınan %s — dosya: %s",
            mime,
            file.name,
        )
        raise ValidationError(f"Geçersiz dosya tipi: {mime}")

    return True


def extract_detection_count(detec_result: bytes) -> int:
    try:
        count_str = detec_result.decode("utf-8")
        return int(count_str)
    except (ValueError, UnicodeDecodeError, AttributeError) as e:
        logger.error("Algılama sonucu parse hatası: %s", e)
        raise ValidationError("Algılama sonucu işlenemedi")


def sanitize_filename(filename: str) -> str:
    if ".." in filename or "/" in filename or "\\" in filename:
        logger.warning(
            "Path traversal attempt detected in sanitize_filename: %s", filename
        )
        raise ValidationError("Geçersiz dosya adı - güvenlik ihlali tespit edildi")

    filename = os.path.basename(filename)

    name, ext = os.path.splitext(filename)
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-"))

    if not ext or len(ext) > 10:
        ext = ".jpg"

    return f"{uuid.uuid4().hex}_{safe_name[:50]}{ext.lower()}"


@login_required
@require_http_methods(["GET"])
def serve_media_file(request: HttpRequest, file_path: str) -> HttpResponse:
    from django.conf import settings as django_settings

    clean_path = os.path.normpath(file_path).lstrip("/").replace("\\", "/")
    if ".." in clean_path:
        return HttpResponse("Geçersiz dosya yolu", status=400)

    if getattr(django_settings, "USE_R2", False):
        from django.core.files.storage import default_storage
        signed_url = default_storage.url(clean_path)
        return redirect(signed_url)

    full_path = (BASE_DIR / "media" / clean_path).resolve()
    media_root = (BASE_DIR / "media").resolve()

    if not str(full_path).startswith(str(media_root)):
        return HttpResponse("Geçersiz dosya yolu", status=400)

    if not full_path.exists():
        return HttpResponse("Dosya bulunamadı", status=404)

    response = HttpResponse()
    response["X-Accel-Redirect"] = f"/media/{clean_path}"
    response["Content-Type"] = ""
    return response


@login_required
@ratelimit(key="user", rate="30/m", method="POST", block=True)
def index(request: HttpRequest) -> HttpResponse:
    response: Dict[str, Any] = {}

    import json
    from datetime import timedelta

    from django.db.models import Avg
    from django.db.models.functions import TruncMonth
    from django.utils import timezone

    from detection.models import DetectionResult

    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_stats = (
        DetectionResult.objects.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(avg_count=Avg("detected_count"))
        .order_by("month")
    )

    chart_labels = []
    chart_values = []
    for stat in monthly_stats:
        chart_labels.append(stat["month"].strftime("%Y-%m"))
        chart_values.append(float(stat["avg_count"]) if stat["avg_count"] else 0)

    chart_data = json.dumps(
        {
            "labels": chart_labels if chart_labels else None,
            "values": chart_values if chart_values else None,
            "label": "Aylık Ortalama Tespit Sayısı",
        }
    )

    if request.method == "POST":
        try:
            meyve_grubu = request.POST.get("meyve_grubu")
            agac_sayisi = request.POST.get("agac_sayisi")
            agac_yasi = request.POST.get("agac_yasi")
            ekim_sirasi = request.POST.get("ekim_sirasi")
            filename = request.FILES.get("file")

            if not all((meyve_grubu, agac_sayisi, agac_yasi, ekim_sirasi, filename)):
                return render(request, "main.html", {"error": "Tüm alanları doldurun"})

            if filename is None:
                return render(request, "main.html", {"error": "Dosya bulunamadı"})

            validate_image_file(filename)

            try:
                if agac_sayisi is None:
                    return render(
                        request, "main.html", {"error": "Ağaç sayısı gerekli"}
                    )
                agac_sayisi_int = int(agac_sayisi)
                if not (1 <= agac_sayisi_int <= 100000):
                    return render(
                        request,
                        "main.html",
                        {"error": "Ağaç sayısı 1-100000 arasında olmalı"},
                    )
            except ValueError:
                return render(request, "main.html", {"error": "Geçersiz sayı formatı"})

            try:
                if agac_yasi is None:
                    return render(request, "main.html", {"error": "Ağaç yaşı gerekli"})
                agac_yasi_int = int(agac_yasi)
                if not (0 <= agac_yasi_int <= 150):
                    return render(
                        request,
                        "main.html",
                        {"error": "Ağaç yaşı 0-150 arasında olmalı"},
                    )
            except ValueError:
                return render(request, "main.html", {"error": "Geçersiz yaş formatı"})

            if meyve_grubu not in FRUIT_MODELS:
                return render(request, "main.html", {"error": "Geçersiz meyve grubu"})

            safe_filename = sanitize_filename(filename.name or "")

            filename.seek(0)
            image_data = filename.read()
            filename.seek(0)

            image_hash = calculate_image_hash(image_data)

            cached_result = get_cached_prediction(image_hash, meyve_grubu)

            if cached_result:
                logger.info(
                    "Using cached result for %s, hash=%s...",
                    meyve_grubu,
                    image_hash[:16],
                )

                cached_weight = (
                    cached_result["weight_per_fruit"] * cached_result["detected_count"]
                )

                response["count"] = cached_result["detected_count"]
                response["kilo"] = cached_weight
                response["toplam_agirlik"] = agac_sayisi_int * cached_weight
                response["time"] = "0.00"
                response["image"] = cached_result["image_path"]
                response["confidence"] = f"{cached_result['confidence_score']:.2%}"
                response["from_cache"] = True

                try:
                    try:
                        _mv = ModelVersion.get_active(meyve_grubu)
                        _model_version_label = f"{meyve_grubu}:{_mv.version}"
                    except LookupError:
                        _model_version_label = meyve_grubu
                    detection_instance = DetectionResult.objects.create(
                        fruit_type=meyve_grubu,
                        tree_count=agac_sayisi_int,
                        tree_age=agac_yasi_int,
                        detected_count=cached_result["detected_count"],
                        weight=response["kilo"],
                        total_weight=response["toplam_agirlik"],
                        processing_time=0.0,
                        confidence_score=cached_result["confidence_score"],
                        model_version=_model_version_label,
                        threshold_used=DETECTION_CONFIDENCE_THRESHOLD,
                        image_path=cached_result["image_path"],
                        bbox_coordinates=cached_result.get("bbox_coordinates"),
                        created_by=request.user,
                    )
                    response["detection_id"] = detection_instance.pk
                except Exception as e:
                    logger.error("Cache detection save error: %s", e)
            else:
                temp_dir = Path(tempfile.gettempdir())
                tmp_path = (temp_dir / safe_filename).resolve()

                if not str(tmp_path).startswith(str(temp_dir.resolve())):
                    logger.warning("Path traversal attempt detected: %s", tmp_path)
                    raise ValidationError("Geçersiz dosya yolu")

                try:
                    with open(tmp_path, "wb") as tmp:
                        tmp.write(image_data)
                except Exception as e:
                    logger.error("Geçici dosya yazma hatası: %s: %s", tmp_path, e)
                    raise ValidationError("Dosya yüklenirken hata oluştu")

                start_time = time.time()

                try:
                    conf_thres = DETECTION_CONFIDENCE_THRESHOLD
                    detec, unique_id, confidence_score, bbox_centers = (
                        predict_tree.predict(
                            fruit_type=meyve_grubu,
                            path_to_source=str(tmp_path),
                            return_boxes=True,
                        )
                    )
                    count = extract_detection_count(detec)
                    weight_per_fruit = FRUIT_WEIGHTS[meyve_grubu]
                    processing_time = time.time() - start_time

                    response["count"] = count
                    response["kilo"] = count * weight_per_fruit
                    response["toplam_agirlik"] = agac_sayisi_int * response["kilo"]
                    response["time"] = f"{processing_time:.2f}"
                    response["image"] = f"detected/{unique_id}/{safe_filename}"
                    response["confidence"] = f"{confidence_score:.2%}"
                    response["from_cache"] = False

                    cache_data = {
                        "detected_count": count,
                        "weight_per_fruit": weight_per_fruit,
                        "confidence_score": confidence_score,
                        "image_path": f"detected/{unique_id}/{safe_filename}",
                        "fruit_type": meyve_grubu,
                        "image_hash": image_hash,
                        "bbox_coordinates": bbox_centers,
                    }
                    set_cached_prediction(image_hash, meyve_grubu, cache_data)

                    try:
                        _mv = ModelVersion.get_active(meyve_grubu)
                        _model_version_label = f"{meyve_grubu}:{_mv.version}"
                    except LookupError:
                        _model_version_label = meyve_grubu

                    try:
                        detection_instance = DetectionResult.objects.create(
                            fruit_type=meyve_grubu,
                            tree_count=agac_sayisi_int,
                            tree_age=agac_yasi_int,
                            detected_count=count,
                            weight=response["kilo"],
                            total_weight=response["toplam_agirlik"],
                            processing_time=processing_time,
                            confidence_score=confidence_score,
                            model_version=_model_version_label,
                            threshold_used=conf_thres,
                            image_path=f"detected/{unique_id}/{safe_filename}",
                            bbox_coordinates=bbox_centers,
                            created_by=request.user,
                        )
                        logger.info(
                            f"Detection result saved: {meyve_grubu}, count={count}, confidence={confidence_score:.3f}"
                        )
                        response["detection_id"] = detection_instance.pk
                    except Exception as db_error:
                        logger.error("Veritabanı kaydetme hatası: %s", db_error)

                except (FileNotFoundError, RuntimeError, ValueError, IOError) as e:
                    logger.error("Model algılama hatası: %s", e)
                    raise ValidationError(
                        "Algılama işlemi başarısız oldu. Lütfen tekrar deneyin."
                    )
                finally:
                    try:
                        if tmp_path.exists():
                            tmp_path.unlink()
                    except Exception as e:
                        logger.error("Geçici dosya silme hatası: %s: %s", tmp_path, e)

        except ValidationError as e:
            return render(request, "main.html", {"error": str(e)})
        except Exception as e:
            logger.error("İşlem hatası: %s", e)
            return render(
                request,
                "main.html",
                {"error": "Bir hata oluştu", "chart_data": chart_data},
            )

    context: Dict[str, Any] = {"chart_data": chart_data}
    if response:
        context["response"] = response
    return render(request, "main.html", context)


@login_required
@ratelimit(key="user", rate="10/m", method="POST", block=True)
def multi_detection_image(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        try:
            meyve_grubu = request.POST.get("meyve_grubu")
            ekim_sirasi = request.POST.get("ekim_sirasi")
            agac_sayisi = request.POST.get("agac_sayisi")
            agac_yasi = request.POST.get("agac_yasi")
            filelist = request.FILES.getlist("file")

            if not meyve_grubu or not ekim_sirasi or not filelist:
                return render(
                    request,
                    "multi_detection_fruit.html",
                    {"error": "Tüm alanları doldurun"},
                )

            for image_file in filelist:
                validate_image_file(image_file)

            try:
                agac_sayisi_int = int(agac_sayisi) if agac_sayisi else 0
                if agac_sayisi_int and not (1 <= agac_sayisi_int <= 100000):
                    return render(
                        request,
                        "multi_detection_fruit.html",
                        {"error": "Ağaç sayısı 1-100000 arasında olmalı"},
                    )
            except ValueError:
                return render(
                    request, "multi_detection_fruit.html", {"error": "Geçersiz ağaç sayısı"}
                )

            try:
                agac_yasi_int = int(agac_yasi) if agac_yasi else 0
                if agac_yasi_int and not (0 <= agac_yasi_int <= 150):
                    return render(
                        request,
                        "multi_detection_fruit.html",
                        {"error": "Ağaç yaşı 0-150 arasında olmalı"},
                    )
            except ValueError:
                return render(
                    request, "multi_detection_fruit.html", {"error": "Geçersiz ağaç yaşı"}
                )

            if meyve_grubu not in FRUIT_MODELS:
                return render(
                    request,
                    "multi_detection_fruit.html",
                    {"error": "Geçersiz meyve grubu"},
                )

            try:
                hass = hashing.add_prefix2(filename=f"{time.time()}")
            except Exception as e:
                logger.error("Hash oluşturma hatası: %s", e)
                raise ValidationError("Dizin oluşturulamadı")

            upload_dir = None
            try:
                upload_dir = Path(hass[0])
                upload_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error("Çıktı dizini oluşturma hatası: %s: %s", hass[0], e)
                raise ValidationError("Çıktı dizini oluşturulamadı")

            try:
                for image in filelist:
                    if not image.name:
                        raise ValidationError("Dosya adı bulunamadı")

                    safe_image_name = os.path.basename(image.name)
                    if (
                        ".." in safe_image_name
                        or "/" in safe_image_name
                        or "\\" in safe_image_name
                    ):
                        logger.warning(
                            "Path traversal attempt in filename: %s", image.name
                        )
                        raise ValidationError(f"Geçersiz dosya adı: {image.name}")

                    img_path = Path(hass[0]) / safe_image_name
                    with open(img_path, "wb") as f:
                        for chunk in image.chunks():
                            f.write(chunk)
            except Exception as e:
                logger.error("Dosya kaydetme hatası: %s", e)
                if upload_dir and upload_dir.exists():
                    try:
                        shutil.rmtree(str(upload_dir))
                        logger.info("Hatalı dosyalar temizlendi: %s", upload_dir)
                    except Exception as cleanup_error:
                        logger.error("Dosya temizleme hatası: %s", cleanup_error)
                raise ValidationError("Dosyalar kaydedilemedi")

            try:
                _, total_count = predict_tree.multi_predictor(
                    fruit_type=meyve_grubu,
                    path_to_source=hass[0],
                    ekim_sirasi=ekim_sirasi,
                    hashing=hass[1],
                )

                try:
                    try:
                        _mv = ModelVersion.get_active(meyve_grubu)
                        _model_version_label = f"{meyve_grubu}:{_mv.version}"
                    except LookupError:
                        _model_version_label = meyve_grubu

                    weight_per_fruit = FRUIT_WEIGHTS.get(meyve_grubu, 0.125)
                    weight = total_count * weight_per_fruit
                    total_weight = agac_sayisi_int * weight

                    DetectionResult.objects.create(
                        fruit_type=meyve_grubu,
                        tree_count=agac_sayisi_int,
                        tree_age=agac_yasi_int,
                        detected_count=total_count,
                        weight=weight,
                        total_weight=total_weight,
                        processing_time=0.0,
                        confidence_score=0.0,
                        model_version=_model_version_label,
                        threshold_used=DETECTION_CONFIDENCE_THRESHOLD,
                        image_path=f"detected/{hass[1]}/",
                        bbox_coordinates=None,
                        created_by=request.user,
                    )
                    logger.info(
                        "Multi-detection batch saved: %s, trees=%s, age=%s, hash=%s",
                        meyve_grubu, agac_sayisi_int, agac_yasi_int, hass[1],
                    )
                except Exception as db_error:
                    logger.error("Multi-detection DB kayıt hatası: %s", db_error)

                return render(
                    request, "multi_detection_fruit.html", {"response": hass[1]}
                )

            except (FileNotFoundError, RuntimeError, ValueError, IOError) as e:
                logger.error("Çoklu algılama işlemi hatası: %s", e)
                if upload_dir and upload_dir.exists():
                    try:
                        shutil.rmtree(str(upload_dir))
                        logger.info(
                            "Algılama hatası nedeniyle dosyalar silindi: %s", upload_dir
                        )
                    except Exception as cleanup_error:
                        logger.error("Dosya temizleme hatası: %s", cleanup_error)
                raise ValidationError(f"Algılama başarısız: {str(e)}")

        except ValidationError as e:
            return render(request, "multi_detection_fruit.html", {"error": str(e)})
        except Exception as e:
            logger.error("Çoklu algılama hatası: %s", e)
            return render(
                request, "multi_detection_fruit.html", {"error": "Bir hata oluştu"}
            )

    return render(request, "multi_detection_fruit.html")


@login_required
def download_image(request: HttpRequest, slug: str) -> FileResponse | HttpResponse:
    try:
        safe_slug = "".join(c for c in slug if c.isalnum() or c in ("-", "_"))
        if safe_slug != slug:
            return HttpResponse("Geçersiz dosya adı", status=400)

        file_path = (BASE_DIR / "media" / f"{safe_slug}_result.zip").resolve()
        media_dir = (BASE_DIR / "media").resolve()

        if not str(file_path).startswith(str(media_dir)):
            return HttpResponse("Geçersiz dosya yolu", status=400)

        if not file_path.exists():
            return HttpResponse("Dosya bulunamadı", status=404)

        file_handle = open(file_path, "rb")
        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename=f"{safe_slug}_result.zip",
        )
        return response
    except Exception as e:
        logger.error("Dosya indirme hatası: %s", e)
        return HttpResponse("Dosya indirilemedi", status=500)


@login_required
def system_monitoring(request: HttpRequest) -> HttpResponse:
    import platform
    from datetime import datetime

    import psutil

    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024**3)
        memory_used_gb = memory.used / (1024**3)
        memory_available_gb = memory.available / (1024**3)
        memory_percent = memory.percent

        disk = psutil.disk_usage("/")
        disk_total_gb = disk.total / (1024**3)
        disk_used_gb = disk.used / (1024**3)
        disk_free_gb = disk.free / (1024**3)
        disk_percent = disk.percent

        system_info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }

        from django.utils import timezone

        boot_time = timezone.make_aware(datetime.fromtimestamp(psutil.boot_time()))
        uptime = timezone.now() - boot_time
        uptime_str = f"{uptime.days} gün, {uptime.seconds // 3600} saat, {(uptime.seconds % 3600) // 60} dakika"

        uptime_days = uptime.days + (uptime.seconds / 86400)
        uptime_percent = min(100, (uptime_days / 30) * 100)

        from detection.model_registry import get_loaded_models_info

        loaded_models = get_loaded_models_info()

        context = {
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "cpu_freq": cpu_freq.current if cpu_freq else 0,
            "memory_total_gb": f"{memory_total_gb:.2f}",
            "memory_used_gb": f"{memory_used_gb:.2f}",
            "memory_available_gb": f"{memory_available_gb:.2f}",
            "memory_percent": memory_percent,
            "disk_total_gb": f"{disk_total_gb:.2f}",
            "disk_used_gb": f"{disk_used_gb:.2f}",
            "disk_free_gb": f"{disk_free_gb:.2f}",
            "disk_percent": disk_percent,
            "system_info": system_info,
            "boot_time": boot_time,
            "uptime_str": uptime_str,
            "uptime_days": uptime_days,
            "uptime_percent": uptime_percent,
            "loaded_models": loaded_models,
        }

        return render(request, "system_monitoring.html", context)

    except Exception as e:
        logger.error("Sistem izleme hatası: %s", e)
        return render(
            request,
            "system_monitoring.html",
            {"error": f"Sistem bilgileri alınamadı: {str(e)}"},
        )


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="30/m", method="POST", block=True)
def async_detection(request: HttpRequest) -> JsonResponse:
    try:
        meyve_grubu = request.POST.get("meyve_grubu")
        agac_sayisi = request.POST.get("agac_sayisi")
        agac_yasi = request.POST.get("agac_yasi")
        filename = request.FILES.get("file")

        if not all((meyve_grubu, agac_sayisi, agac_yasi, filename)):
            return JsonResponse({"error": "Tüm alanları doldurun"}, status=400)

        if filename is None:
            return JsonResponse({"error": "Dosya bulunamadı"}, status=400)

        validate_image_file(filename)

        try:
            if agac_sayisi is None or agac_yasi is None:
                return JsonResponse(
                    {"error": "Ağaç sayısı ve yaşı gerekli"}, status=400
                )
            agac_sayisi_int = int(agac_sayisi)
            agac_yasi_int = int(agac_yasi)
        except ValueError:
            return JsonResponse({"error": "Geçersiz sayı formatı"}, status=400)

        if meyve_grubu not in FRUIT_MODELS:
            return JsonResponse({"error": "Geçersiz meyve grubu"}, status=400)

        safe_filename = sanitize_filename(filename.name or "")

        filename.seek(0)
        image_data = filename.read()
        filename.seek(0)

        image_hash = calculate_image_hash(image_data)

        cached_result = get_cached_prediction(image_hash, meyve_grubu)

        if cached_result:
            logger.info(
                "Async endpoint: Using cached result for %s, hash=%s...",
                meyve_grubu,
                image_hash[:16],
            )

            cached_weight = (
                cached_result["weight_per_fruit"] * cached_result["detected_count"]
            )

            return JsonResponse(
                {
                    "task_id": None,
                    "status": "SUCCESS",
                    "message": "Önbellekten döndürüldü",
                    "from_cache": True,
                    "result": {
                        "detected_count": cached_result["detected_count"],
                        "weight": cached_weight,
                        "total_weight": agac_sayisi_int * cached_weight,
                        "confidence_score": cached_result["confidence_score"],
                        "image_path": cached_result["image_path"],
                        "processing_time": 0.0,
                    },
                },
                status=200,
            )

        temp_dir = Path(tempfile.gettempdir())
        tmp_path = (temp_dir / safe_filename).resolve()

        if not str(tmp_path).startswith(str(temp_dir.resolve())):
            logger.warning("Path traversal attempt detected: %s", tmp_path)
            return JsonResponse({"error": "Geçersiz dosya yolu"}, status=400)

        try:
            with open(tmp_path, "wb") as tmp:
                tmp.write(image_data)

            actual_mime = magic.from_file(str(tmp_path), mime=True)
            if actual_mime not in DETECTION_ALLOWED_MIME_TYPES:
                tmp_path.unlink()
                logger.warning("MIME type mismatch after upload: %s", actual_mime)
                return JsonResponse({"error": "Geçersiz dosya formatı"}, status=400)

        except Exception as e:
            logger.error("Geçici dosya yazma hatası: %s: %s", tmp_path, e)
            if tmp_path.exists():
                tmp_path.unlink()
            return JsonResponse({"error": "Dosya yüklenirken hata oluştu"}, status=500)

        task = process_image_detection.delay(
            image_path=str(tmp_path),
            fruit_type=meyve_grubu,
            tree_count=agac_sayisi_int,
            tree_age=agac_yasi_int,
            user_id=request.user.pk if request.user.is_authenticated else None,
        )

        logger.info("Async detection task queued: %s for %s", task.id, meyve_grubu)

        return JsonResponse(
            {
                "task_id": task.id,
                "status": "PENDING",
                "message": "Görüntü işleme kuyruğa eklendi",
                "from_cache": False,
                "stream_url": f"/detection/task-stream/{task.id}/",
            },
            status=202,
        )

    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        logger.error("Async detection hatası: %s", e)
        return JsonResponse({"error": "Bir hata oluştu"}, status=500)


@login_required
@require_http_methods(["GET"])
def task_status(request: HttpRequest, task_id: str) -> JsonResponse:
    try:
        result = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "status": result.state,
        }

        if result.state == "PENDING":
            response_data["message"] = "Görev bekleniyor..."
            response_data["progress"] = 0

        elif result.state == "PROCESSING":
            info = result.info or {}
            response_data["message"] = info.get("status", "İşleniyor...")
            response_data["progress"] = info.get("progress", 50)

        elif result.state == "SUCCESS":
            response_data["result"] = result.result
            response_data["message"] = "İşlem tamamlandı"
            response_data["progress"] = 100

        elif result.state == "FAILURE":
            info = result.info or {}
            error_msg = str(result.info) if result.info else "Bilinmeyen hata"
            response_data["error"] = error_msg
            response_data["message"] = "İşlem başarısız"
            response_data["progress"] = 0

        else:
            response_data["message"] = f"Durum: {result.state}"
            response_data["progress"] = 0

        return JsonResponse(response_data)

    except Exception as e:
        logger.error("Task status check hatası: %s", e)
        return JsonResponse(
            {
                "task_id": task_id,
                "error": "Görev durumu alınamadı",
                "status": "UNKNOWN",
            },
            status=500,
        )


@login_required
@require_http_methods(["GET"])
def detection_task_stream(request: HttpRequest, task_id: str) -> StreamingHttpResponse:
    import json

    def _event_stream():
        for _ in range(600):
            try:
                result = AsyncResult(task_id)
                state = result.state

                if state == "PENDING":
                    payload = {"status": "PENDING", "progress": 0, "message": "Görev bekleniyor..."}

                elif state == "PROCESSING":
                    info = result.info or {}
                    payload = {
                        "status": "PROCESSING",
                        "progress": info.get("progress", 10),
                        "message": info.get("status", "İşleniyor..."),
                    }

                elif state == "SUCCESS":
                    payload = {
                        "status": "SUCCESS",
                        "progress": 100,
                        "message": "İşlem tamamlandı",
                        "result": result.result,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    yield f"data: {json.dumps({'status': 'done'})}\n\n"
                    return

                elif state == "FAILURE":
                    error_msg = str(result.info) if result.info else "Bilinmeyen hata"
                    payload = {
                        "status": "FAILURE",
                        "progress": 0,
                        "message": "İşlem başarısız",
                        "error": error_msg,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    yield f"data: {json.dumps({'status': 'done'})}\n\n"
                    return

                else:
                    payload = {"status": state, "progress": 0, "message": f"Durum: {state}"}

                yield f"data: {json.dumps(payload)}\n\n"

            except Exception as e:
                logger.error("SSE stream hatası task=%s: %s", task_id, e)
                yield f"data: {json.dumps({'status': 'FAILURE', 'error': str(e)})}\n\n"
                yield f"data: {json.dumps({'status': 'done'})}\n\n"
                return

            time.sleep(1)

        yield f"data: {json.dumps({'status': 'TIMEOUT', 'message': 'İstek zaman aşımına uğradı'})}\n\n"
        yield f"data: {json.dumps({'status': 'done'})}\n\n"

    response = StreamingHttpResponse(_event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@login_required
@require_http_methods(["POST", "DELETE"])
def cache_invalidate(request: HttpRequest) -> JsonResponse:
    if not request.user.is_staff:
        return JsonResponse(
            {"success": False, "error": "Bu işlem için yönetici yetkisi gerekli"},
            status=403,
        )

    try:
        from detection.cache_utils import (
            invalidate_all_predictions,
            invalidate_prediction_cache,
        )

        if request.method == "POST":
            image_hash = request.POST.get("image_hash")
            fruit_type = request.POST.get("fruit_type")
            invalidate_all = request.POST.get("all", "").lower() == "true"
        else:
            image_hash = request.GET.get("image_hash")
            fruit_type = request.GET.get("fruit_type")
            invalidate_all = request.GET.get("all", "").lower() == "true"

        if invalidate_all:
            deleted_count = invalidate_all_predictions(fruit_type=fruit_type)
            message = f"{deleted_count} önbellek anahtarı silindi"
            if fruit_type:
                message += f" ({fruit_type} için)"

            return JsonResponse(
                {"success": True, "deleted_count": deleted_count, "message": message}
            )

        elif image_hash and fruit_type:
            success = invalidate_prediction_cache(image_hash, fruit_type)
            if success:
                return JsonResponse(
                    {
                        "success": True,
                        "deleted_count": 1,
                        "message": f"Önbellek anahtarı silindi: {fruit_type}, hash={image_hash[:16]}...",
                    }
                )
            else:
                return JsonResponse(
                    {
                        "success": False,
                        "deleted_count": 0,
                        "message": "Önbellek anahtarı bulunamadı",
                    },
                    status=404,
                )

        else:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Geçersiz parametreler. image_hash+fruit_type veya all=true gerekli",
                },
                status=400,
            )

    except Exception as e:
        logger.error("Cache invalidation hatası: %s", e)
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def cache_statistics(request: HttpRequest) -> JsonResponse:
    if not request.user.is_staff:
        return JsonResponse(
            {"success": False, "error": "Bu işlem için yönetici yetkisi gerekli"},
            status=403,
        )

    try:
        from detection.cache_utils import get_cache_statistics

        stats = get_cache_statistics()

        return JsonResponse(stats)

    except Exception as e:
        logger.error("Cache statistics hatası: %s", e)
        return JsonResponse({"redis_available": False, "error": str(e)}, status=500)
