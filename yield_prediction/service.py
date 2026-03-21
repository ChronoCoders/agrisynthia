from __future__ import annotations

from typing import Dict, Mapping

from spatial_analysis.config import YIELD_MODEL_METADATA
from detection.constants import FRUIT_WEIGHTS


DEFAULT_WEIGHT_PER_FRUIT = 0.2

_UYARI = (
    "Bu tahmin kural tabanlı bir formülle üretilmiştir; "
    "gerçek hasat verisiyle kalibre edilmemiştir."
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def predict_yield(
    features: Mapping[str, float],
    fruit_type: str | None = None,
) -> Dict[str, object]:
    detected_tree_count = float(features.get("detected_tree_count", 0.0) or 0.0)
    avg_density_per_ha = float(features.get("density_per_ha", 0.0) or 0.0)
    stress_percent = float(features.get("total_stressed_area_percent", 0.0) or 0.0)
    largest_stress_zone_ha = float(features.get("largest_stress_zone_ha", 0.0) or 0.0)
    average_ndvi = float(features.get("average_ndvi", 0.0) or 0.0)
    tree_age = float(features.get("tree_age", 0.0) or 0.0)

    stress_percent = _clamp(stress_percent, 0.0, 100.0)
    detected_tree_count = max(detected_tree_count, 0.0)
    avg_density_per_ha = max(avg_density_per_ha, 0.0)
    largest_stress_zone_ha = max(largest_stress_zone_ha, 0.0)
    tree_age = max(tree_age, 0.0)

    if fruit_type:
        weight_per_fruit = FRUIT_WEIGHTS.get(fruit_type, DEFAULT_WEIGHT_PER_FRUIT)
    else:
        weight_per_fruit = DEFAULT_WEIGHT_PER_FRUIT

    base_yield_kg = detected_tree_count * weight_per_fruit

    _meta = {
        "model_version": YIELD_MODEL_METADATA["version"],
        "yontem": YIELD_MODEL_METADATA["type"],
        "uyari": _UYARI,
    }

    if base_yield_kg <= 0.0:
        return {"tahmini_verim_kg": 0.0, "kalite_skoru": 0.0, **_meta}

    ndvi_normalized = _clamp((average_ndvi + 1.0) / 2.0, 0.0, 1.0)
    ndvi_factor = 0.3 + ndvi_normalized * 0.9

    stress_factor = 1.1 - 0.6 * (stress_percent / 100.0)
    stress_factor = _clamp(stress_factor, 0.5, 1.1)

    optimal_density = 300.0
    if avg_density_per_ha <= 0.0:
        density_factor = 0.8
    else:
        density_ratio = _clamp(avg_density_per_ha / optimal_density, 0.0, 2.0)
        density_deviation = abs(density_ratio - 1.0)
        density_factor = 1.0 - _clamp(density_deviation * 0.4, 0.0, 0.4)

    if tree_age <= 3.0:
        age_factor = 0.7 + 0.1 * (tree_age / 3.0)
    elif tree_age <= 20.0:
        age_factor = 1.0
    else:
        extra_age = tree_age - 20.0
        age_factor = 1.0 - _clamp(extra_age * 0.02, 0.0, 0.4)

    raw_yield_kg = (
        base_yield_kg * ndvi_factor * stress_factor * density_factor * age_factor
    )

    confidence = 0.9
    confidence -= 0.3 * (stress_percent / 100.0)
    largest_zone_factor = _clamp(largest_stress_zone_ha / 5.0, 0.0, 1.0)
    confidence -= 0.2 * largest_zone_factor
    confidence -= 0.2 * abs(ndvi_normalized - 0.7)

    missing_feature_penalty = 0.0
    if avg_density_per_ha == 0.0:
        missing_feature_penalty += 0.05
    if largest_stress_zone_ha == 0.0 and stress_percent == 0.0:
        missing_feature_penalty += 0.05
    confidence -= missing_feature_penalty
    confidence = _clamp(confidence, 0.1, 0.99)

    return {
        "tahmini_verim_kg": round(max(raw_yield_kg, 0.0), 2),
        # Renamed from guven_skoru to kalite_skoru — this is not a calibrated
        # probability; it is a rule-derived quality indicator (0–100).
        "kalite_skoru": round(confidence * 100.0, 1),
        **_meta,
    }
