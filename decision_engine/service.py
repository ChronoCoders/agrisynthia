from __future__ import annotations

from typing import Dict, List


def generate_recommendations(
    density_data: Dict[str, object], stress_zones: Dict[str, object]
) -> Dict[str, object]:
    recommendations: List[Dict[str, object]] = []

    for feature in stress_zones.get("features", []):
        props = feature.get("properties", {}) or {}
        zone_id = props.get("zone_id")
        stress = props.get("stress_class")
        area = float(props.get("area_ha") or 0.0)

        if area <= 0.0 or zone_id is None:
            continue

        if stress == "high_stress":
            if area > 2.0:
                severity = "critical"
                action = "intensive localized irrigation and immediate agronomist inspection"
            elif area > 1.0:
                severity = "high"
                action = "localized irrigation and remedial treatment"
            else:
                severity = "medium"
                action = "localized irrigation and close monitoring"
        elif stress == "medium":
            severity = "medium"
            action = "advisory monitoring and field scouting"
        else:
            continue

        recommendations.append(
            {
                "zone_id": zone_id,
                "area_ha": area,
                "severity": severity,
                "action": action,
            }
        )

    return {
        "recommendations": recommendations,
        "total_recommendations": len(recommendations),
    }
