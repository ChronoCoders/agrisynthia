NDVI_LOW = 0.3
NDVI_HIGH = 0.5
MIN_ZONE_AREA_HA = 0.02
GRID_SIZE_METERS = 10.0

YIELD_MODEL_METADATA = {
    "version": "v1.0",
    "type": "rule_based",
    "description": (
        "Kural tabanlı verim tahmini. Gerçek hasat verisiyle kalibre edilmemiştir. "
        "Sonuçlar yönlendirici nitelikte olup kesin tahmin değildir."
    ),
}

# Kept for backwards-compatible imports
YIELD_MODEL_VERSION = YIELD_MODEL_METADATA["version"]
