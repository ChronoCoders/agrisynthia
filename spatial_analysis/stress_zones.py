from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import rasterio
from pyproj import Geod, Transformer
from rasterio import features, windows

from .config import NDVI_HIGH, NDVI_LOW, MIN_ZONE_AREA_HA


def _read_ndvi_raster(ndvi_path: str) -> rasterio.io.DatasetReader:
    path = Path(ndvi_path)
    if not path.exists():
        raise FileNotFoundError(f"NDVI raster not found: {ndvi_path}")
    return rasterio.open(path)


def _classify_ndvi(
    array: np.ndarray, low_threshold: float, high_threshold: float
) -> np.ndarray:
    classified = np.zeros_like(array, dtype=np.uint8)
    classified[array < low_threshold] = 1
    classified[(array >= low_threshold) & (array <= high_threshold)] = 2
    classified[array > high_threshold] = 3
    return classified


def _polygon_area_ha(geom: Dict[str, object], geod: Geod) -> float:
    geom_type = geom.get("type")
    coords = geom.get("coordinates", [])

    if geom_type == "Polygon":
        rings = coords
    elif geom_type == "MultiPolygon":
        rings = [ring for poly in coords for ring in poly]
    else:
        return 0.0

    area_m2_total = 0.0
    for ring in rings:
        if not ring:
            continue
        lons, lats = zip(*ring)
        area_m2, _ = geod.polygon_area_perimeter(lons, lats)
        area_m2_total += abs(area_m2)

    return area_m2_total / 10000.0


def _reproject_geom_to_wgs84(
    geom: Dict[str, object], transformer: Transformer | None
) -> Dict[str, object]:
    if transformer is None:
        return geom

    geom_type = geom.get("type")
    coords = geom.get("coordinates", [])

    if geom_type == "Polygon":
        new_coords = [
            [transformer.transform(x, y) for x, y in ring] for ring in coords
        ]
        return {"type": "Polygon", "coordinates": new_coords}
    if geom_type == "MultiPolygon":
        new_coords = []
        for poly in coords:
            new_poly = [[transformer.transform(x, y) for x, y in ring] for ring in poly]
            new_coords.append(new_poly)
        return {"type": "MultiPolygon", "coordinates": new_coords}
    return geom


def _iter_windows(width: int, height: int, tile_size: int = 1024):
    for row_off in range(0, height, tile_size):
        win_h = min(tile_size, height - row_off)
        for col_off in range(0, width, tile_size):
            win_w = min(tile_size, width - col_off)
            yield windows.Window(col_off, row_off, win_w, win_h)


def generate_stress_zones(
    ndvi_path: str,
    low_threshold: float | None = None,
    high_threshold: float | None = None,
    min_area_ha: float | None = None,
) -> Dict[str, object]:
    low = NDVI_LOW if low_threshold is None else low_threshold
    high = NDVI_HIGH if high_threshold is None else high_threshold
    min_area = MIN_ZONE_AREA_HA if min_area_ha is None else min_area_ha
    geod = Geod(ellps="WGS84")

    features_geo: List[Dict[str, object]] = []

    total_area_ha = 0.0
    high_area_ha = 0.0
    largest_zone_ha = 0.0
    zone_id = 0

    with _read_ndvi_raster(ndvi_path) as src:
        if src.crs and str(src.crs).upper() != "EPSG:4326":
            transformer = Transformer.from_crs(
                src.crs, "EPSG:4326", always_xy=True
            )
        else:
            transformer = None

        for window in _iter_windows(src.width, src.height):
            ndvi_block = src.read(1, window=window).astype("float32")
            classified_block = _classify_ndvi(ndvi_block, low, high)
            block_transform = windows.transform(window, src.transform)

            for geom, value in features.shapes(
                classified_block, transform=block_transform
            ):
                cls = int(value)
                if cls == 0:
                    continue

                geom_wgs84 = _reproject_geom_to_wgs84(geom, transformer)
                area_ha = _polygon_area_ha(geom_wgs84, geod)
                if area_ha < min_area:
                    continue

                if cls == 1:
                    stress_class = "high_stress"
                elif cls == 2:
                    stress_class = "medium"
                else:
                    stress_class = "healthy"

                zone_id += 1

                if stress_class != "healthy":
                    total_area_ha += area_ha
                    if stress_class == "high_stress":
                        high_area_ha += area_ha
                    if area_ha > largest_zone_ha:
                        largest_zone_ha = area_ha

                features_geo.append(
                    {
                        "type": "Feature",
                        "geometry": geom_wgs84,
                        "properties": {
                            "zone_id": zone_id,
                            "stress_class": stress_class,
                            "area_ha": round(area_ha, 3),
                        },
                    }
                )

    total_area_ha = round(total_area_ha, 3)
    high_area_ha = round(high_area_ha, 3)
    largest_zone_ha = round(largest_zone_ha, 3)

    summary = {
        "total_area_ha": total_area_ha,
        "high_stress_area_ha": high_area_ha,
        "high_stress_area_percent": (high_area_ha / total_area_ha * 100.0)
        if total_area_ha > 0
        else 0.0,
        "largest_zone_ha": largest_zone_ha,
    }

    return {
        "type": "FeatureCollection",
        "features": features_geo,
        "summary": summary,
    }
