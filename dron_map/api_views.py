# -*- coding: utf-8 -*-
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Union

import numpy as np
import rasterio
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from spatial_analysis.config import (
    GRID_SIZE_METERS,
    MIN_ZONE_AREA_HA,
    NDVI_HIGH,
    NDVI_LOW,
    YIELD_MODEL_VERSION,
)
from analysis_logger.service import log_full_analysis
from .models import Projects
from .serializers import ProjectSerializer, ProjectSummarySerializer
from .views import get_statistics

from spatial_analysis.density import DetectionPoint, generate_density_grid, pixel_to_geo
from spatial_analysis.stress_zones import generate_stress_zones
from decision_engine.service import generate_recommendations
from yield_prediction.service import predict_yield
from yolowebapp2.histogram import algos
from yolowebapp2 import predict_tree


BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)


def _iter_windows(width: int, height: int, tile_size: int = 1024):
    for row_off in range(0, height, tile_size):
        win_h = min(tile_size, height - row_off)
        for col_off in range(0, width, tile_size):
            win_w = min(tile_size, width - col_off)
            yield rasterio.windows.Window(col_off, row_off, win_w, win_h)


def _compute_average_ndvi(raster_path: str) -> float:
    path = Path(raster_path)
    if not path.exists():
        return 0.0

    total = 0.0
    count = 0

    with rasterio.open(path) as src:
        height = src.height
        width = src.width

        for window in _iter_windows(width, height):
            red = src.read(1, window=window).astype("float32")
            nir = src.read(4, window=window).astype("float32")
            ndvi = (nir - red) / (nir + red)
            valid = np.isfinite(ndvi)
            if not valid.any():
                continue
            values = ndvi[valid]
            total += float(values.sum())
            count += int(values.size)

    if count == 0:
        return 0.0

    return float(total / count)


def _aggregate_density_metrics(density_data: Dict[str, object]) -> Tuple[float, float]:
    features = density_data.get("features", []) or []

    total_tree_count = 0.0
    density_values = []

    for feature in features:
        props = feature.get("properties", {}) or {}
        tree_count = props.get("tree_count")
        density_per_ha = props.get("density_per_ha")
        if tree_count is not None:
            try:
                total_tree_count += float(tree_count)
            except (TypeError, ValueError):
                continue
        if density_per_ha is not None:
            try:
                density_values.append(float(density_per_ha))
            except (TypeError, ValueError):
                continue

    if density_values:
        avg_density_per_ha = float(sum(density_values) / len(density_values))
    else:
        avg_density_per_ha = 0.0

    return total_tree_count, avg_density_per_ha


def _extract_stress_summary(stress_data: Dict[str, object]) -> Tuple[float, float]:
    summary = stress_data.get("ozet", {}) or {}

    total_stressed_area_percent = float(summary.get("yuksek_stres_yuzde") or 0.0)
    largest_stress_zone_ha = float(summary.get("en_buyuk_zon_ha") or 0.0)

    return total_stressed_area_percent, largest_stress_zone_ha


@dataclass
class _AnalysisData:
    """Holds pre-computed density and stress data so each inference runs only once."""
    density_data: Dict[str, object]
    stress_data: Dict[str, object]
    raster_path: Path


class ProjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint for drone mapping projects

    Provides CRUD operations for farm projects:
    - List all projects (GET /api/projects/)
    - Retrieve single project (GET /api/projects/{id}/)
    - Create new project (POST /api/projects/)
    - Update project (PUT/PATCH /api/projects/{id}/)
    - Delete project (DELETE /api/projects/{id}/)
    - Filter by farm/field/state (GET /api/projects/?Farm=MyFarm)
    - Search by farm/field/title (GET /api/projects/?search=apple)
    - Get project summary (GET /api/projects/{id}/summary/)
    - List by farm (GET /api/projects/by_farm/)

    Note: Authentication required for all endpoints to protect farm data.
    """

    queryset = Projects.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["Farm", "Field", "State"]
    search_fields = ["Farm", "Field", "Title"]
    ordering_fields = ["Data_time", "Farm", "Field"]
    ordering = ["-Data_time"]

    def get_serializer_class(self):
        """Use summary serializer for list action"""
        if self.action == "list":
            return ProjectSummarySerializer
        return ProjectSerializer

    def perform_create(self, serializer):
        """Generate hashing_path on creation"""
        from yolowebapp2 import hashing
        from rest_framework.exceptions import ValidationError

        title = serializer.validated_data.get("Title", "")
        field = serializer.validated_data.get("Field", "")

        try:
            # Generate unique hash based on title and field
            hashing_result = hashing.add_prefix(filename=f"{title}{field}")
            # hashing_result is (full_path, hash_string)
            serializer.save(hashing_path=hashing_result[1])
        except Exception as e:
            raise ValidationError(f"Karma yol oluşturulamadı: {str(e)}")

    def _get_orthophoto_path(self, project: Projects) -> Path | None:
        stats = get_statistics(task_id=project.hashing_path, stat_type="orthophoto")
        rel_path = stats.get("odm_orthophoto")
        if not rel_path:
            return None
        return BASE_DIR / "static" / rel_path

    def _run_analysis(
        self,
        project: Projects,
        grid_size: float = GRID_SIZE_METERS,
        ndvi_low: float = NDVI_LOW,
        ndvi_high: float = NDVI_HIGH,
        min_area_ha: float = MIN_ZONE_AREA_HA,
    ) -> "Union[_AnalysisData, Response]":
        """Run YOLO inference and NDVI computation exactly once.

        Returns an ``_AnalysisData`` on success, or a ``Response`` error on
        failure so callers can return it immediately.
        """
        raster_path = self._get_orthophoto_path(project)
        if raster_path is None:
            return Response(
                {"detail": "Bu proje için ortofoto mevcut değil."}, status=400
            )

        # --- NDVI raster (once) ---
        ndvi_algo = algos(str(raster_path), project.hashing_path)
        ndvi_result = ndvi_algo.Ndvi()
        ndvi_rel_path = ndvi_result.get("path")
        if not ndvi_rel_path:
            return Response(
                {"detail": "NDVI sonucu yolu belirlenemedi."}, status=500
            )
        ndvi_path = BASE_DIR / "static" / ndvi_rel_path

        # --- Stress zones from NDVI (once) ---
        try:
            zones = generate_stress_zones(
                str(ndvi_path),
                low_threshold=ndvi_low,
                high_threshold=ndvi_high,
                min_area_ha=min_area_ha,
            )
        except Exception as e:
            logger.error(
                "Proje %s stres zonu üretim hatası: %s", project.id, e, exc_info=True
            )
            return Response({"detail": "Stres zonları üretilemedi."}, status=500)

        label_map = {
            "high_stress": "Yüksek Stres",
            "medium": "Orta Stres",
            "healthy": "Sağlıklı",
        }
        stress_features = []
        for feature in zones.get("features", []):
            props = dict(feature.get("properties", {}) or {})
            props["stress_label"] = label_map.get(props.get("stress_class"), "")
            stress_features.append(
                {
                    "type": feature.get("type", "Feature"),
                    "geometry": feature.get("geometry"),
                    "properties": props,
                }
            )
        summary = zones.get("summary", {}) or {}
        ozet = {
            "toplam_stres_alani_ha": round(
                float(summary.get("total_area_ha") or 0.0), 3
            ),
            "yuksek_stres_alani_ha": round(
                float(summary.get("high_stress_area_ha") or 0.0), 3
            ),
            "yuksek_stres_yuzde": round(
                float(summary.get("high_stress_area_percent") or 0.0), 1
            ),
            "en_buyuk_zon_ha": round(
                float(summary.get("largest_zone_ha") or 0.0), 3
            ),
        }
        stress_data: Dict[str, object] = {
            "type": zones.get("type", "FeatureCollection"),
            "features": stress_features,
            "ozet": ozet,
        }

        # --- YOLO tree detection (once) ---
        try:
            (
                _detec,
                _unique_id,
                _confidence,
                bbox_centers,
            ) = predict_tree.predict(
                path_to_weights="agac.pt",
                path_to_source=str(raster_path),
                return_boxes=True,
            )
        except Exception as e:
            logger.error(
                "Proje %s yoğunluk tespiti hatası: %s", project.id, e, exc_info=True
            )
            return Response({"detail": "Ağaç tespiti başarısız oldu."}, status=500)

        detections = [DetectionPoint(x=p["x"], y=p["y"]) for p in bbox_centers]
        try:
            geo_points = pixel_to_geo(str(raster_path), detections)
        except Exception as e:
            logger.error(
                "Proje %s koordinat dönüşüm hatası: %s", project.id, e, exc_info=True
            )
            return Response(
                {"detail": "Piksel-coğrafi koordinat dönüşümü başarısız oldu."},
                status=500,
            )

        lonlat_points = [(p["lon"], p["lat"]) for p in geo_points]
        density_data: Dict[str, object] = generate_density_grid(
            lonlat_points, grid_size
        )

        return _AnalysisData(
            density_data=density_data,
            stress_data=stress_data,
            raster_path=raster_path,
        )

    @action(detail=False, methods=["get"])
    def by_farm(self, request):
        """
        Get projects grouped by farm
        GET /api/projects/by_farm/
        """
        from itertools import groupby
        from operator import attrgetter

        # Fetch all projects in one query, ordered by farm
        all_projects = Projects.objects.all().order_by("Farm")

        result = []
        # Group by farm name using itertools.groupby (efficient, no N+1)
        for farm_name, projects in groupby(all_projects, key=attrgetter("Farm")):
            projects_list = list(projects)
            serializer = ProjectSummarySerializer(projects_list, many=True)
            result.append(
                {
                    "farm": farm_name,
                    "project_count": len(projects_list),
                    "projects": serializer.data,
                }
            )

        return Response(result)

    @action(detail=False, methods=["get"])
    def by_state(self, request):
        """
        Get projects grouped by state
        GET /api/projects/by_state/
        """
        from django.db.models import Count

        states = (
            Projects.objects.values("State")
            .annotate(project_count=Count("id"))
            .order_by("State")
        )

        return Response(states)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """
        Get detailed project summary
        GET /api/projects/{id}/summary/
        """
        project = self.get_object()
        return Response(
            {
                "id": project.id,
                "farm": project.Farm,
                "field": project.Field,
                "title": project.Title,
                "state": project.State,
                "created": project.Data_time,
                "has_picture": bool(project.picture),
                "hashing_path": project.hashing_path,
            }
        )

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """
        Get project statistics
        GET /api/projects/statistics/
        """
        from django.db.models import Count

        stats = {
            "total_projects": Projects.objects.count(),
            "total_farms": Projects.objects.values("Farm").distinct().count(),
            "total_fields": Projects.objects.values("Field").distinct().count(),
            "projects_by_state": list(
                Projects.objects.values("State").annotate(count=Count("id"))
            ),
        }

        return Response(stats)

    @action(detail=True, methods=["get"], url_path="density")
    def density(self, request, pk=None):
        project = self.get_object()
        raster_path = self._get_orthophoto_path(project)
        if raster_path is None:
            return Response(
                {"detail": "Bu proje için ortofoto mevcut değil."}, status=400
            )

        try:
            (
                _detec,
                _unique_id,
                _confidence,
                bbox_centers,
            ) = predict_tree.predict(
                path_to_weights="agac.pt",
                path_to_source=str(raster_path),
                return_boxes=True,
            )
        except Exception as e:
            logger.error("Proje %s yoğunluk tespiti hatası: %s", project.id, e, exc_info=True)
            return Response(
                {"detail": "Ağaç tespiti başarısız oldu."}, status=500
            )

        detections = [DetectionPoint(x=p["x"], y=p["y"]) for p in bbox_centers]

        try:
            geo_points = pixel_to_geo(str(raster_path), detections)
        except Exception as e:
            logger.error("Proje %s koordinat dönüşüm hatası: %s", project.id, e, exc_info=True)
            return Response(
                {"detail": "Piksel-coğrafi koordinat dönüşümü başarısız oldu."},
                status=500,
            )

        lonlat_points = [(p["lon"], p["lat"]) for p in geo_points]

        grid_size_param = request.query_params.get("grid_size_meters")
        try:
            grid_size = (
                float(grid_size_param) if grid_size_param is not None else GRID_SIZE_METERS
            )
        except ValueError:
            grid_size = GRID_SIZE_METERS

        feature_collection = generate_density_grid(lonlat_points, grid_size)
        return Response(feature_collection)

    @action(detail=True, methods=["get"], url_path="stress-zones")
    def stress_zones(self, request, pk=None):
        project = self.get_object()
        raster_path = self._get_orthophoto_path(project)
        if raster_path is None:
            return Response(
                {"detail": "Bu proje için ortofoto mevcut değil."}, status=400
            )

        ndvi_algo = algos(str(raster_path), project.hashing_path)
        ndvi_result = ndvi_algo.Ndvi()
        ndvi_rel_path = ndvi_result.get("path")
        if not ndvi_rel_path:
            return Response(
                {"detail": "NDVI sonucu yolu belirlenemedi."}, status=500
            )

        ndvi_path = BASE_DIR / "static" / ndvi_rel_path

        low_param = request.query_params.get("low")
        high_param = request.query_params.get("high")
        min_area_param = request.query_params.get("min_area")

        try:
            low_threshold = (
                float(low_param) if low_param is not None else NDVI_LOW
            )
        except ValueError:
            low_threshold = NDVI_LOW

        try:
            high_threshold = (
                float(high_param) if high_param is not None else NDVI_HIGH
            )
        except ValueError:
            high_threshold = NDVI_HIGH

        try:
            min_area_ha = (
                float(min_area_param)
                if min_area_param is not None
                else MIN_ZONE_AREA_HA
            )
        except ValueError:
            min_area_ha = MIN_ZONE_AREA_HA

        try:
            zones = generate_stress_zones(
                str(ndvi_path),
                low_threshold=low_threshold,
                high_threshold=high_threshold,
                min_area_ha=min_area_ha,
            )
        except Exception as e:
            logger.error("Proje %s stres zonu üretim hatası: %s", project.id, e, exc_info=True)
            return Response(
                {"detail": "Stres zonları üretilemedi."}, status=500
            )

        features_source = zones.get("features", [])
        features_target = []

        label_map = {
            "high_stress": "Yüksek Stres",
            "medium": "Orta Stres",
            "healthy": "Sağlıklı",
        }

        for feature in features_source:
            props = feature.get("properties", {}) or {}
            stress_class = props.get("stress_class")
            stress_label = label_map.get(stress_class, "")

            new_props = dict(props)
            new_props["stress_label"] = stress_label

            features_target.append(
                {
                    "type": feature.get("type", "Feature"),
                    "geometry": feature.get("geometry"),
                    "properties": new_props,
                }
            )

        summary = zones.get("summary", {}) or {}
        total_area_ha = float(summary.get("total_area_ha") or 0.0)
        high_area_ha = float(summary.get("high_stress_area_ha") or 0.0)
        high_percent = float(summary.get("high_stress_area_percent") or 0.0)
        largest_zone_ha = float(summary.get("largest_zone_ha") or 0.0)

        ozet = {
            "toplam_stres_alani_ha": round(total_area_ha, 3),
            "yuksek_stres_alani_ha": round(high_area_ha, 3),
            "yuksek_stres_yuzde": round(high_percent, 1),
            "en_buyuk_zon_ha": round(largest_zone_ha, 3),
        }

        response_data = {
            "type": zones.get("type", "FeatureCollection"),
            "features": features_target,
            "ozet": ozet,
        }

        return Response(response_data)

    @action(detail=True, methods=["get"], url_path="decisions")
    def decisions(self, request, pk=None):
        project = self.get_object()

        analysis = self._run_analysis(project)
        if isinstance(analysis, Response):
            return analysis

        recommendations = generate_recommendations(
            analysis.density_data, analysis.stress_data
        )
        recs_source = recommendations.get("recommendations", []) or []

        severity_map = {
            "critical": "Kritik",
            "high": "Yüksek",
            "medium": "Orta",
        }

        action_map = {
            "critical": "Acil sulama ve saha kontrolü önerilir.",
            "high": "Lokal sulama önerilir.",
            "medium": "Yakın takip önerilir.",
        }

        recs_target = []
        for rec in recs_source:
            severity_code = rec.get("severity")
            priority = severity_map.get(severity_code, "")
            action_text = action_map.get(severity_code, "Gözlem tavsiye edilir.")

            recs_target.append(
                {
                    "zone_id": rec.get("zone_id"),
                    "alan_ha": rec.get("area_ha"),
                    "oncelik": priority,
                    "aksiyon": action_text,
                }
            )

        response_data = {
            "oneriler": recs_target,
            "toplam_oneri": len(recs_target),
        }

        return Response(response_data)

    @action(detail=True, methods=["get"], url_path="yield")
    def yield_prediction(self, request, pk=None):
        project = self.get_object()

        analysis = self._run_analysis(project)
        if isinstance(analysis, Response):
            return analysis

        density_data = analysis.density_data
        total_tree_count, avg_density_per_ha = _aggregate_density_metrics(density_data)

        stress_data = analysis.stress_data
        (
            total_stressed_area_percent,
            largest_stress_zone_ha,
        ) = _extract_stress_summary(stress_data)

        average_ndvi = _compute_average_ndvi(str(analysis.raster_path))

        age_param = request.query_params.get("tree_age")
        try:
            tree_age = float(age_param) if age_param is not None else 7.0
        except ValueError:
            tree_age = 7.0
        fruit_type_param = request.query_params.get("meyve_grubu")

        feature_vector = {
            "detected_tree_count": total_tree_count,
            "density_per_ha": avg_density_per_ha,
            "total_stressed_area_percent": total_stressed_area_percent,
            "largest_stress_zone_ha": largest_stress_zone_ha,
            "average_ndvi": average_ndvi,
            "tree_age": tree_age,
        }

        result = predict_yield(feature_vector, fruit_type_param)

        return Response(result)

    @action(detail=True, methods=["get"], url_path="full-analysis")
    def full_analysis(self, request, pk=None):
        """
        Full pipeline: NDVI → stress zones → density → yield → recommendations.
        Each heavy computation (YOLO inference, NDVI raster) runs exactly once.
        """
        import traceback

        project = self.get_object()

        raster_path = self._get_orthophoto_path(project)
        if raster_path is None:
            return Response(
                {"hata": "Orthophoto bu proje için mevcut değil."},
                status=400,
            )

        ndvi_low = NDVI_LOW
        ndvi_high = NDVI_HIGH
        min_area_ha = MIN_ZONE_AREA_HA
        grid_size = GRID_SIZE_METERS

        start_time = timezone.now()

        try:
            # --- Step 1: NDVI raster (once) ---
            ndvi_algo = algos(str(raster_path), project.hashing_path)
            ndvi_result = ndvi_algo.Ndvi()
            ndvi_rel_path = ndvi_result.get("path")
            if not ndvi_rel_path:
                raise ValueError("NDVI sonucu yolu belirlenemedi.")
            ndvi_path = BASE_DIR / "static" / ndvi_rel_path

            # --- Step 2: Stress zones from NDVI raster (once) ---
            try:
                zones = generate_stress_zones(
                    str(ndvi_path),
                    low_threshold=ndvi_low,
                    high_threshold=ndvi_high,
                    min_area_ha=min_area_ha,
                )
            except Exception as e:
                raise ValueError(f"Stres zonları üretilemedi: {e}")

            label_map = {
                "high_stress": "Yüksek Stres",
                "medium": "Orta Stres",
                "healthy": "Sağlıklı",
            }
            stress_features = []
            for feature in zones.get("features", []):
                props = dict(feature.get("properties", {}) or {})
                props["stress_label"] = label_map.get(props.get("stress_class"), "")
                stress_features.append(
                    {
                        "type": feature.get("type", "Feature"),
                        "geometry": feature.get("geometry"),
                        "properties": props,
                    }
                )
            summary = zones.get("summary", {}) or {}
            ozet = {
                "toplam_stres_alani_ha": round(float(summary.get("total_area_ha") or 0.0), 3),
                "yuksek_stres_alani_ha": round(float(summary.get("high_stress_area_ha") or 0.0), 3),
                "yuksek_stres_yuzde": round(float(summary.get("high_stress_area_percent") or 0.0), 1),
                "en_buyuk_zon_ha": round(float(summary.get("largest_zone_ha") or 0.0), 3),
            }
            stress_data = {
                "type": zones.get("type", "FeatureCollection"),
                "features": stress_features,
                "ozet": ozet,
            }

            # --- Step 3: Tree detection + density grid (once) ---
            try:
                (
                    _detec,
                    _unique_id,
                    _confidence,
                    bbox_centers,
                ) = predict_tree.predict(
                    path_to_weights="agac.pt",
                    path_to_source=str(raster_path),
                    return_boxes=True,
                )
            except Exception as e:
                raise ValueError(f"Ağaç tespiti başarısız: {e}")

            detections = [DetectionPoint(x=p["x"], y=p["y"]) for p in bbox_centers]
            try:
                geo_points = pixel_to_geo(str(raster_path), detections)
            except Exception as e:
                raise ValueError(f"Piksel-coğrafi dönüşüm başarısız: {e}")

            lonlat_points = [(p["lon"], p["lat"]) for p in geo_points]
            density_data = generate_density_grid(lonlat_points, grid_size)

            # --- Step 4: Aggregate metrics ---
            total_tree_count, avg_density_per_ha = _aggregate_density_metrics(density_data)
            total_stressed_area_percent, largest_stress_zone_ha = _extract_stress_summary(stress_data)
            average_ndvi = _compute_average_ndvi(str(ndvi_path))

            age_param = request.query_params.get("tree_age")
            try:
                tree_age = float(age_param) if age_param is not None else 7.0
            except ValueError:
                tree_age = 7.0
            fruit_type_param = request.query_params.get("meyve_grubu")

            feature_vector = {
                "detected_tree_count": total_tree_count,
                "density_per_ha": avg_density_per_ha,
                "total_stressed_area_percent": total_stressed_area_percent,
                "largest_stress_zone_ha": largest_stress_zone_ha,
                "average_ndvi": average_ndvi,
                "tree_age": tree_age,
            }

            # --- Step 5: Yield prediction ---
            yield_result = predict_yield(feature_vector, fruit_type_param)

            # --- Step 6: Recommendations (uses pre-computed data, no re-inference) ---
            recommendations = generate_recommendations(density_data, stress_data)
            severity_map = {"critical": "Kritik", "high": "Yüksek", "medium": "Orta"}
            action_map = {
                "critical": "Acil sulama ve saha kontrolü önerilir.",
                "high": "Lokal sulama önerilir.",
                "medium": "Yakın takip önerilir.",
            }
            recs_target = []
            for rec in recommendations.get("recommendations", []) or []:
                severity_code = rec.get("severity")
                recs_target.append(
                    {
                        "zone_id": rec.get("zone_id"),
                        "alan_ha": rec.get("area_ha"),
                        "oncelik": severity_map.get(severity_code, ""),
                        "aksiyon": action_map.get(severity_code, "Gözlem tavsiye edilir."),
                    }
                )

            end_time = timezone.now()

            log_full_analysis(
                project_id=project.id,
                raster_path=str(raster_path),
                start_time=start_time,
                end_time=end_time,
                ndvi_low=ndvi_low,
                ndvi_high=ndvi_high,
                min_area_ha=min_area_ha,
                grid_size=grid_size,
                yield_model_version=YIELD_MODEL_VERSION,
                success=True,
                error_message=None,
                stack_trace=None,
            )

            toplam_verim = float(yield_result.get("tahmini_verim_kg") or 0.0)
            try:
                project_area_ha = float(request.query_params.get("project_area_ha"))
            except (TypeError, ValueError):
                project_area_ha = 0.0
            hektar_basi_verim = (toplam_verim / project_area_ha) if project_area_ha > 0 else 0.0

            return Response(
                {
                    "stres_analizi": stress_data,
                    "yogunluk_analizi": density_data,
                    "verim_tahmini": {
                        "tahmini_verim_kg": round(toplam_verim, 2),
                        "hektar_basi_verim": round(hektar_basi_verim, 2),
                        "kalite_skoru": float(yield_result.get("kalite_skoru") or 0.0),
                    },
                    "oneriler": {"oneriler": recs_target, "toplam_oneri": len(recs_target)},
                    "islem_bilgisi": {
                        "islem_suresi_saniye": (end_time - start_time).total_seconds(),
                        "model_versiyonu": YIELD_MODEL_VERSION,
                    },
                }
            )

        except Exception as e:
            end_time = timezone.now()
            stack_trace = traceback.format_exc()

            log_full_analysis(
                project_id=project.id,
                raster_path=str(raster_path),
                start_time=start_time,
                end_time=end_time,
                ndvi_low=ndvi_low,
                ndvi_high=ndvi_high,
                min_area_ha=min_area_ha,
                grid_size=grid_size,
                yield_model_version=YIELD_MODEL_VERSION,
                success=False,
                error_message=str(e),
                stack_trace=stack_trace,
            )

            # Do not expose internal error details to the client
            logger.error("Proje %s tam analiz hatası: %s", project.id, e, exc_info=True)
            return Response(
                {"hata": "Analiz sırasında hata oluştu. Lütfen sistem günlüklerini inceleyin."},
                status=500,
            )
