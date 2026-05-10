# -*- coding: utf-8 -*-
"""
Agronomic yield prediction using detection counts + Sentinel-2 NDVI.

Model logic
-----------
1. Detection-based fruit density  →  extrapolate to full tree set
2. NDVI stress factor             →  scale predicted yield up/down
3. Tree-age correction            →  young trees bear fewer fruits
4. Fruit-type specific parameters →  weight per fruit, seasonal peak NDVI
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Agronomic constants (literature / field averages for Mediterranean region)
# ---------------------------------------------------------------------------

_SPECIES_PARAMS: dict[str, dict] = {
    "mandalina": {
        "label": "Mandalina",
        "avg_weight_kg": 0.11,       # kg per fruit
        "peak_ndvi": 0.65,           # expected NDVI at optimal health
        "full_bearing_age": 5,       # years until full production
        "max_fruits_per_tree": 350,
    },
    "elma": {
        "label": "Elma",
        "avg_weight_kg": 0.18,
        "peak_ndvi": 0.60,
        "full_bearing_age": 5,
        "max_fruits_per_tree": 250,
    },
    "armut": {
        "label": "Armut",
        "avg_weight_kg": 0.15,
        "peak_ndvi": 0.58,
        "full_bearing_age": 6,
        "max_fruits_per_tree": 200,
    },
    "seftali": {
        "label": "Şeftali",
        "avg_weight_kg": 0.14,
        "peak_ndvi": 0.55,
        "full_bearing_age": 4,
        "max_fruits_per_tree": 180,
    },
    "nar": {
        "label": "Nar",
        "avg_weight_kg": 0.38,
        "peak_ndvi": 0.52,
        "full_bearing_age": 4,
        "max_fruits_per_tree": 150,
    },
}

_DEFAULT_PARAMS = {
    "label": "Genel",
    "avg_weight_kg": 0.15,
    "peak_ndvi": 0.60,
    "full_bearing_age": 5,
    "max_fruits_per_tree": 200,
}

# Confidence interval half-width as fraction of predicted value
_CI_HALF_WIDTH = 0.25


@dataclass
class YieldEstimate:
    fruit_type: str
    tree_count: int
    tree_age: int
    detected_count: int
    avg_ndvi: Optional[float]

    # Derived
    species_label: str = field(init=False)
    fruits_per_tree_detected: float = field(init=False)
    ndvi_factor: float = field(init=False)
    age_factor: float = field(init=False)
    predicted_fruits_total: float = field(init=False)
    predicted_yield_kg: float = field(init=False)
    yield_low_kg: float = field(init=False)
    yield_high_kg: float = field(init=False)
    avg_weight_kg: float = field(init=False)
    explanation: list[str] = field(init=False)

    def __post_init__(self):
        params = _SPECIES_PARAMS.get(self.fruit_type.lower().replace("ş", "s").replace("ı", "i"), _DEFAULT_PARAMS)
        self.species_label = params["label"]
        self.avg_weight_kg = params["avg_weight_kg"]
        self.explanation = []

        # --- 1. Fruits per tree from detection sample ---
        # Assumes the detection image covers roughly 1/10 of the orchard (conservative)
        sample_fraction = max(1.0 / max(self.tree_count, 1), 0.01)
        if self.detected_count > 0 and self.tree_count > 0:
            raw_fpt = self.detected_count / (self.tree_count * sample_fraction)
            # Cap at species maximum
            self.fruits_per_tree_detected = min(raw_fpt, params["max_fruits_per_tree"])
        else:
            self.fruits_per_tree_detected = params["max_fruits_per_tree"] * 0.5
        self.explanation.append(
            f"Görüntüden ağaç başına tespit: {self.fruits_per_tree_detected:.0f} meyve"
        )

        # --- 2. NDVI stress factor ---
        if self.avg_ndvi is not None:
            peak = params["peak_ndvi"]
            ratio = self.avg_ndvi / peak
            # sigmoid-like clamp: very low NDVI → heavy yield penalty
            self.ndvi_factor = max(0.3, min(1.0, ratio ** 1.5))
            self.explanation.append(
                f"NDVI faktörü: {self.ndvi_factor:.2f} (ort. NDVI={self.avg_ndvi:.3f}, ideal={peak})"
            )
        else:
            self.ndvi_factor = 0.85  # unknown → assume slight stress
            self.explanation.append("NDVI verisi yok — varsayılan faktör 0.85 uygulandı")

        # --- 3. Tree age correction ---
        full_age = params["full_bearing_age"]
        if self.tree_age <= 0:
            self.age_factor = 0.3
        elif self.tree_age < full_age:
            self.age_factor = 0.3 + 0.7 * (self.tree_age / full_age)
        else:
            self.age_factor = 1.0
        self.explanation.append(
            f"Ağaç yaşı faktörü: {self.age_factor:.2f} ({self.tree_age} yıl, tam verim yaşı={full_age})"
        )

        # --- 4. Final prediction ---
        self.predicted_fruits_total = (
            self.fruits_per_tree_detected
            * self.tree_count
            * self.ndvi_factor
            * self.age_factor
        )
        self.predicted_yield_kg = self.predicted_fruits_total * self.avg_weight_kg
        self.yield_low_kg = self.predicted_yield_kg * (1 - _CI_HALF_WIDTH)
        self.yield_high_kg = self.predicted_yield_kg * (1 + _CI_HALF_WIDTH)

    def as_dict(self) -> dict:
        return {
            "fruit_type": self.fruit_type,
            "species_label": self.species_label,
            "tree_count": self.tree_count,
            "tree_age": self.tree_age,
            "detected_count": self.detected_count,
            "avg_ndvi": round(self.avg_ndvi, 3) if self.avg_ndvi is not None else None,
            "ndvi_factor": round(self.ndvi_factor, 3),
            "age_factor": round(self.age_factor, 3),
            "fruits_per_tree": round(self.fruits_per_tree_detected, 1),
            "predicted_fruits_total": round(self.predicted_fruits_total),
            "avg_weight_kg": self.avg_weight_kg,
            "predicted_yield_kg": round(self.predicted_yield_kg, 1),
            "yield_low_kg": round(self.yield_low_kg, 1),
            "yield_high_kg": round(self.yield_high_kg, 1),
            "predicted_yield_ton": round(self.predicted_yield_kg / 1000, 2),
            "explanation": self.explanation,
        }


def predict_yield_for_project(project) -> Optional[dict]:
    """
    Build a YieldEstimate from the latest DetectionResult and SatelliteNDVI for *project*.
    Returns None if there is not enough data.
    """
    from detection.models import DetectionResult

    latest_detection = (
        DetectionResult.objects
        .filter(created_by=project.created_by)
        .order_by("-created_at")
        .values("fruit_type", "tree_count", "tree_age", "detected_count", "weight")
        .first()
    )
    if not latest_detection:
        return None

    ndvi_qs = project.ndvi_readings.order_by("-date").values_list("mean_ndvi", flat=True)[:6]
    avg_ndvi = (sum(ndvi_qs) / len(ndvi_qs)) if ndvi_qs else None

    estimate = YieldEstimate(
        fruit_type=latest_detection["fruit_type"],
        tree_count=latest_detection["tree_count"] or 1,
        tree_age=latest_detection["tree_age"] or 0,
        detected_count=latest_detection["detected_count"] or 0,
        avg_ndvi=avg_ndvi,
    )
    return estimate.as_dict()
