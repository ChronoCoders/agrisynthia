from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import rasterio
from pyproj import Transformer

from .config import GRID_SIZE_METERS


@dataclass
class DetectionPoint:
    x: int
    y: int


def _get_transformer(dataset: rasterio.io.DatasetReader) -> Transformer:
    src_crs = dataset.crs
    if src_crs is None:
        raise ValueError("Source raster has no CRS; cannot compute geo coordinates")
    return Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)


def pixel_to_geo(
    raster_path: str, detections: Iterable[DetectionPoint]
) -> List[Dict[str, float]]:
    path = Path(raster_path)
    if not path.exists():
        raise FileNotFoundError(f"Raster not found: {raster_path}")

    with rasterio.open(path) as src:
        transform = src.transform
        transformer = _get_transformer(src)

        coords: List[Dict[str, float]] = []
        for d in detections:
            px = int(d.x)
            py = int(d.y)
            x, y = rasterio.transform.xy(transform, py, px)
            lon, lat = transformer.transform(x, y)
            coords.append({"lat": float(lat), "lon": float(lon)})

    return coords


def generate_density_grid(
    points: List[Tuple[float, float]], grid_size_meters: float | None = None
) -> Dict[str, object]:
    if not points:
        return {"type": "FeatureCollection", "features": []}

    lons = np.array([p[0] for p in points], dtype=np.float64)
    lats = np.array([p[1] for p in points], dtype=np.float64)

    lon0 = float(lons.min())
    lat0 = float(lats.min())

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x0, y0 = transformer.transform(lon0, lat0)

    xs, ys = transformer.transform(lons, lats)

    cell_size = GRID_SIZE_METERS if grid_size_meters is None else grid_size_meters

    gx = ((xs - x0) / cell_size).astype(int)
    gy = ((ys - y0) / cell_size).astype(int)

    unique, counts = np.unique(np.stack([gx, gy], axis=1), axis=0, return_counts=True)

    cell_area_m2 = cell_size * cell_size
    cell_area_ha = cell_area_m2 / 10000.0

    features: List[Dict[str, object]] = []

    for (cell_x, cell_y), count in zip(unique, counts):
        min_x = x0 + cell_x * cell_size
        min_y = y0 + cell_y * cell_size
        max_x = min_x + cell_size
        max_y = min_y + cell_size

        west, south = transformer.transform(min_x, min_y, direction="INVERSE")
        east, north = transformer.transform(max_x, max_y, direction="INVERSE")

        density_per_ha = float(count / cell_area_ha) if cell_area_ha > 0 else 0.0

        if density_per_ha < 50.0:
            label = "düşük"
        elif density_per_ha < 150.0:
            label = "normal"
        else:
            label = "yüksek"

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [west, south],
                            [east, south],
                            [east, north],
                            [west, north],
                            [west, south],
                        ]
                    ],
                },
                "properties": {
                    "tree_count": int(count),
                    "density_per_ha": density_per_ha,
                    "density_label": label,
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}
