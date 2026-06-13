"""
Management command: render_ndvi_hero

Fetches the most recent low-cloud Sentinel-2 scene over Finike, Antalya
(Turkey's mandarin belt), computes NDVI, applies a green→yellow→red colormap,
and saves the result to static/website/img/ndvi_hero.png.

Usage:
    python manage.py render_ndvi_hero
    python manage.py render_ndvi_hero --bbox 30.05 36.18 30.28 36.38
    python manage.py render_ndvi_hero --max-cloud 20
"""

import io
import os

import numpy as np
from django.core.management.base import BaseCommand
from PIL import Image


# Finike, Antalya — prime mandarin orchard area
DEFAULT_BBOX = [30.05, 36.18, 30.28, 36.38]

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# NDVI colormap: value → RGBA  (-1 → +1 mapped to 0 → 255)
# Deep red (stressed) → yellow (moderate) → green (healthy) → dark green (dense)
COLORMAP_STOPS = [
    (0,   (178, 34,  34,  255)),   # -1.0  bare/water
    (64,  (210, 90,  30,  255)),   # -0.5  sparse
    (100, (240, 180, 20,  255)),   # ~-0.2 low vegetation
    (128, (255, 230, 80,  255)),   #  0.0  very low
    (160, (180, 220, 60,  255)),   # +0.25 moderate
    (200, (60,  160, 50,  255)),   # +0.57 healthy
    (230, (30,  100, 30,  255)),   # +0.80 dense
    (255, (10,  60,  10,  255)),   # +1.0  very dense
]


def _build_colormap() -> np.ndarray:
    lut = np.zeros((256, 4), dtype=np.uint8)
    stops = COLORMAP_STOPS
    for i in range(len(stops) - 1):
        v0, c0 = stops[i]
        v1, c1 = stops[i + 1]
        for v in range(v0, v1 + 1):
            t = (v - v0) / (v1 - v0) if v1 != v0 else 0
            lut[v] = [int(c0[k] + t * (c1[k] - c0[k])) for k in range(4)]
    return lut


def _ndvi_to_uint8(ndvi: np.ndarray) -> np.ndarray:
    """Map NDVI [-1, 1] → [0, 255]."""
    clipped = np.clip(ndvi, -1, 1)
    return ((clipped + 1) / 2 * 255).astype(np.uint8)


def _apply_colormap(uint8: np.ndarray, lut: np.ndarray) -> np.ndarray:
    return lut[uint8]


class Command(BaseCommand):
    help = "Render a real Sentinel-2 NDVI tile for the homepage hero card."

    def add_arguments(self, parser):
        parser.add_argument(
            "--bbox", nargs=4, type=float, default=DEFAULT_BBOX,
            metavar=("W", "S", "E", "N"),
            help="Bounding box in WGS-84 (default: Finike, Antalya)",
        )
        parser.add_argument(
            "--max-cloud", type=int, default=15,
            help="Maximum cloud cover percentage (default: 15)",
        )
        parser.add_argument(
            "--output", type=str, default=None,
            help="Output PNG path (default: static/website/img/ndvi_hero.png)",
        )

    def handle(self, *args, **options):
        from pystac_client import Client
        import rasterio
        from rasterio.enums import Resampling

        bbox = options["bbox"]
        max_cloud = options["max_cloud"]

        if options["output"]:
            out_path = options["output"]
        else:
            base = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )))
            out_path = os.path.join(base, "static", "website", "img", "ndvi_hero.png")

        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        self.stdout.write("Searching for Sentinel-2 scenes...")
        client = Client.open(STAC_URL)

        from datetime import datetime, timedelta
        date_end = datetime.utcnow()
        date_start = date_end - timedelta(days=90)
        datetime_range = f"{date_start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{date_end.strftime('%Y-%m-%dT%H:%M:%SZ')}"

        search = client.search(
            collections=[COLLECTION],
            bbox=bbox,
            datetime=datetime_range,
            query={"eo:cloud_cover": {"lt": max_cloud}},
            max_items=20,
        )

        items = sorted(
            search.items(),
            key=lambda i: i.datetime or datetime.min.replace(tzinfo=None),
            reverse=True,
        )
        if not items:
            self.stderr.write(self.style.ERROR(
                f"No scenes found with cloud cover < {max_cloud}%. "
                "Try --max-cloud 30"
            ))
            return

        item = items[0]
        date_str = item.datetime.strftime("%Y-%m-%d") if item.datetime else "unknown"
        cloud = item.properties.get("eo:cloud_cover", "?")
        self.stdout.write(f"Using scene: {item.id}  date={date_str}  cloud={cloud}%")

        assets = item.assets
        red_href = assets.get("red", assets.get("B04", assets.get("b04"))).href
        nir_href = assets.get("nir", assets.get("B08", assets.get("b08"))).href

        self.stdout.write("Reading Red band...")
        red = self._read_band(red_href, bbox)
        self.stdout.write("Reading NIR band...")
        nir = self._read_band(nir_href, bbox)

        self.stdout.write("Computing NDVI...")
        red_f = red.astype(np.float32)
        nir_f = nir.astype(np.float32)
        denom = nir_f + red_f
        ndvi = np.where(denom > 0, (nir_f - red_f) / denom, 0.0)

        median_ndvi = float(np.nanmedian(ndvi))
        healthy_pct = int(np.sum(ndvi >= 0.5) / ndvi.size * 100)
        self.stdout.write(
            f"NDVI stats — median={median_ndvi:.3f}  healthy={healthy_pct}%"
        )

        self.stdout.write("Applying colormap and saving PNG...")
        lut = _build_colormap()
        uint8 = _ndvi_to_uint8(ndvi)
        rgba = _apply_colormap(uint8, lut)

        img = Image.fromarray(rgba, mode="RGBA")
        img = img.resize((800, 500), Image.LANCZOS)
        img.save(out_path, "PNG", optimize=True)

        self.stdout.write(self.style.SUCCESS(
            f"\nSaved: {out_path}\n"
            f"Median NDVI : {median_ndvi:.3f}\n"
            f"Healthy area: {healthy_pct}%\n"
            f"Scene date  : {date_str}\n"
        ))

        self.stdout.write(self.style.WARNING(
            f"Update home.html hero stats:\n"
            f"  Ort. NDVI  → {median_ndvi:.2f}\n"
            f"  Sağlıklı   → %{healthy_pct}\n"
            f"  Scene date → {date_str}\n"
        ))

    @staticmethod
    def _read_band(href: str, bbox: list, target_size: int = 512) -> np.ndarray:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.windows import from_bounds
        from pyproj import Transformer

        with rasterio.open(href) as src:
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            xmin, ymin = transformer.transform(bbox[0], bbox[1])
            xmax, ymax = transformer.transform(bbox[2], bbox[3])

            window = from_bounds(xmin, ymin, xmax, ymax, transform=src.transform)
            data = src.read(
                1,
                window=window,
                out_shape=(target_size, target_size),
                resampling=Resampling.bilinear,
            )
        return data
