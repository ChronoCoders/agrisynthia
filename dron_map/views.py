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
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from detection.constants import DRONE_ALLOWED_EXTENSIONS, MAX_DRONE_FILE_SIZE
from yolowebapp2 import hashing, options, predict_tree, tasknode
from yolowebapp2 import histogram as hs

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

                # Save project to database with transaction
                try:
                    with transaction.atomic():
                        form.instance.hashing_path = hashing_result[1]
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

                # Process task (non-critical, log but don't fail)
                try:
                    p = tasknode.Node_processing(str(hashing_result[0]))
                    p.download_task(f"{BASE_DIR}/static/results/{hashing_result[1]}")
                except Exception as e:
                    logger.error("Task processing error: %s", e)
                    # Don't raise, just log - this is not critical

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
