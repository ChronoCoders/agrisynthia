import logging
import os

from celery import shared_task

logger = logging.getLogger(__name__)

BBOX = [30.05, 36.18, 30.28, 36.38]  # Finike, Antalya
STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
MAX_CLOUD = 15
FALLBACK_MAX_CLOUD = 30


@shared_task(name="website.tasks.refresh_ndvi_hero", bind=True, max_retries=3)
def refresh_ndvi_hero(self):
    """
    Fetch the latest low-cloud Sentinel-2 scene over Finike (Antalya),
    compute NDVI, apply colormap, and overwrite static/website/img/ndvi_hero.png.
    Runs monthly via Celery Beat.
    """
    try:
        import numpy as np
        from datetime import datetime, timedelta
        from PIL import Image
        from pystac_client import Client
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.windows import from_bounds
        from pyproj import Transformer

        out_path = _resolve_output_path()
        logger.info("refresh_ndvi_hero: starting — output=%s", out_path)

        client = Client.open(STAC_URL)
        item = _find_best_scene(client)
        if item is None:
            logger.error("refresh_ndvi_hero: no usable scene found")
            return {"status": "no_scene"}

        date_str = item.datetime.strftime("%Y-%m-%d") if item.datetime else "unknown"
        cloud = item.properties.get("eo:cloud_cover", "?")
        logger.info("refresh_ndvi_hero: scene=%s date=%s cloud=%s%%", item.id, date_str, cloud)

        assets = item.assets
        red_href = _get_asset_href(assets, ["red", "B04", "b04"])
        nir_href = _get_asset_href(assets, ["nir", "B08", "b08"])

        red = _read_band(red_href, BBOX)
        nir = _read_band(nir_href, BBOX)

        red_f = red.astype("float32")
        nir_f = nir.astype("float32")
        denom = nir_f + red_f
        ndvi = np.where(denom > 0, (nir_f - red_f) / denom, 0.0)

        lut = _build_colormap()
        uint8 = ((np.clip(ndvi, -1, 1) + 1) / 2 * 255).astype("uint8")
        rgba = lut[uint8]

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img = Image.fromarray(rgba, mode="RGBA").resize((800, 500), Image.LANCZOS)
        img.save(out_path, "PNG", optimize=True)

        median_ndvi = float(np.nanmedian(ndvi))
        healthy_pct = int(np.sum(ndvi >= 0.5) / ndvi.size * 100)
        logger.info(
            "refresh_ndvi_hero: saved — median_ndvi=%.3f healthy=%d%% date=%s",
            median_ndvi, healthy_pct, date_str,
        )
        return {"status": "ok", "scene": item.id, "date": date_str, "median_ndvi": median_ndvi}

    except Exception as exc:
        logger.exception("refresh_ndvi_hero: failed — %s", exc)
        raise self.retry(exc=exc, countdown=3600)


def _find_best_scene(client):
    from datetime import datetime, timedelta
    date_end = datetime.utcnow()
    date_start = date_end - timedelta(days=90)
    dt_range = f"{date_start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{date_end.strftime('%Y-%m-%dT%H:%M:%SZ')}"

    for max_cloud in (MAX_CLOUD, FALLBACK_MAX_CLOUD):
        search = client.search(
            collections=[COLLECTION],
            bbox=BBOX,
            datetime=dt_range,
            query={"eo:cloud_cover": {"lt": max_cloud}},
            max_items=20,
        )
        items = sorted(
            search.items(),
            key=lambda i: i.datetime or __import__("datetime").datetime.min,
            reverse=True,
        )
        if items:
            return items[0]
    return None


def _get_asset_href(assets, keys):
    for k in keys:
        if k in assets:
            return assets[k].href
    raise KeyError(f"None of {keys} found in scene assets")


def _read_band(href, bbox, target_size=512):
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds
    from pyproj import Transformer

    with rasterio.open(href) as src:
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        xmin, ymin = transformer.transform(bbox[0], bbox[1])
        xmax, ymax = transformer.transform(bbox[2], bbox[3])
        window = from_bounds(xmin, ymin, xmax, ymax, transform=src.transform)
        return src.read(
            1, window=window,
            out_shape=(target_size, target_size),
            resampling=Resampling.bilinear,
        )


def _resolve_output_path():
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    return os.path.join(project_root, "static", "website", "img", "ndvi_hero.png")


_COLORMAP_STOPS = [
    (0,   (178, 34,  34,  255)),
    (64,  (210, 90,  30,  255)),
    (100, (240, 180, 20,  255)),
    (128, (255, 230, 80,  255)),
    (160, (180, 220, 60,  255)),
    (200, (60,  160, 50,  255)),
    (230, (30,  100, 30,  255)),
    (255, (10,  60,  10,  255)),
]


def _build_colormap():
    import numpy as np
    lut = np.zeros((256, 4), dtype="uint8")
    for i in range(len(_COLORMAP_STOPS) - 1):
        v0, c0 = _COLORMAP_STOPS[i]
        v1, c1 = _COLORMAP_STOPS[i + 1]
        for v in range(v0, v1 + 1):
            t = (v - v0) / (v1 - v0) if v1 != v0 else 0
            lut[v] = [int(c0[k] + t * (c1[k] - c0[k])) for k in range(4)]
    return lut
