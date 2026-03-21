# -*- coding: utf-8 -*-
"""
Tests for decision_engine.service — pure function, no DB required.
"""
from decision_engine.service import generate_recommendations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stress_data(*zones):
    """Build a minimal stress_zones dict from a list of (zone_id, stress_class, area_ha)."""
    features = [
        {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "zone_id": zid,
                "stress_class": sc,
                "area_ha": area,
            },
        }
        for zid, sc, area in zones
    ]
    return {"type": "FeatureCollection", "features": features}


EMPTY_DENSITY = {"type": "FeatureCollection", "features": []}


# ---------------------------------------------------------------------------
# Empty / edge inputs
# ---------------------------------------------------------------------------

def test_empty_stress_zones_returns_no_recommendations():
    result = generate_recommendations(EMPTY_DENSITY, _make_stress_data())
    assert result["recommendations"] == []
    assert result["total_recommendations"] == 0


def test_healthy_zones_skipped():
    stress = _make_stress_data(("z1", "healthy", 5.0))
    result = generate_recommendations(EMPTY_DENSITY, stress)
    assert result["recommendations"] == []


def test_zero_area_zone_skipped():
    stress = _make_stress_data(("z1", "high_stress", 0.0))
    result = generate_recommendations(EMPTY_DENSITY, stress)
    assert result["recommendations"] == []


def test_none_zone_id_skipped():
    features = [{"type": "Feature", "geometry": None,
                 "properties": {"zone_id": None, "stress_class": "high_stress", "area_ha": 3.0}}]
    stress = {"type": "FeatureCollection", "features": features}
    result = generate_recommendations(EMPTY_DENSITY, stress)
    assert result["recommendations"] == []


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

def test_high_stress_large_area_is_critical():
    stress = _make_stress_data(("z1", "high_stress", 3.0))
    recs = generate_recommendations(EMPTY_DENSITY, stress)["recommendations"]
    assert len(recs) == 1
    assert recs[0]["severity"] == "critical"


def test_high_stress_medium_area_is_high():
    stress = _make_stress_data(("z1", "high_stress", 1.5))
    recs = generate_recommendations(EMPTY_DENSITY, stress)["recommendations"]
    assert recs[0]["severity"] == "high"


def test_high_stress_small_area_is_medium():
    stress = _make_stress_data(("z1", "high_stress", 0.5))
    recs = generate_recommendations(EMPTY_DENSITY, stress)["recommendations"]
    assert recs[0]["severity"] == "medium"


def test_medium_stress_produces_medium_severity():
    stress = _make_stress_data(("z1", "medium", 2.0))
    recs = generate_recommendations(EMPTY_DENSITY, stress)["recommendations"]
    assert recs[0]["severity"] == "medium"


# ---------------------------------------------------------------------------
# Multiple zones
# ---------------------------------------------------------------------------

def test_multiple_zones_all_returned():
    stress = _make_stress_data(
        ("z1", "high_stress", 3.0),
        ("z2", "medium", 1.0),
        ("z3", "healthy", 5.0),  # should be skipped
    )
    result = generate_recommendations(EMPTY_DENSITY, stress)
    assert result["total_recommendations"] == 2
    ids = {r["zone_id"] for r in result["recommendations"]}
    assert "z3" not in ids


def test_recommendation_contains_required_keys():
    stress = _make_stress_data(("z1", "high_stress", 3.0))
    rec = generate_recommendations(EMPTY_DENSITY, stress)["recommendations"][0]
    for key in ("zone_id", "area_ha", "severity", "action"):
        assert key in rec


def test_total_recommendations_matches_list_length():
    stress = _make_stress_data(
        ("a", "high_stress", 1.0),
        ("b", "medium", 0.5),
    )
    result = generate_recommendations(EMPTY_DENSITY, stress)
    assert result["total_recommendations"] == len(result["recommendations"])
