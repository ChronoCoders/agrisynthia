# -*- coding: utf-8 -*-
"""
Tests for yield_prediction.service — pure function, no DB required.
"""
import pytest

from yield_prediction.service import predict_yield, DEFAULT_WEIGHT_PER_FRUIT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_features(**overrides):
    features = {
        "detected_tree_count": 100.0,
        "density_per_ha": 300.0,
        "total_stressed_area_percent": 0.0,
        "largest_stress_zone_ha": 0.0,
        "average_ndvi": 0.7,
        "tree_age": 10.0,
    }
    features.update(overrides)
    return features


# ---------------------------------------------------------------------------
# Zero / missing inputs
# ---------------------------------------------------------------------------

def test_zero_trees_returns_zero_yield():
    result = predict_yield(_base_features(detected_tree_count=0))
    assert result["tahmini_verim_kg"] == 0.0
    assert result["kalite_skoru"] == 0.0


def test_empty_features_returns_zero():
    result = predict_yield({})
    assert result["tahmini_verim_kg"] == 0.0


def test_none_values_treated_as_zero():
    result = predict_yield({"detected_tree_count": None})
    assert result["tahmini_verim_kg"] == 0.0


# ---------------------------------------------------------------------------
# Metadata keys always present
# ---------------------------------------------------------------------------

def test_metadata_always_present():
    result = predict_yield(_base_features())
    assert "model_version" in result
    assert "yontem" in result
    assert "uyari" in result


def test_metadata_present_even_for_zero_trees():
    result = predict_yield(_base_features(detected_tree_count=0))
    assert "yontem" in result
    assert "uyari" in result


def test_yontem_is_rule_based():
    result = predict_yield(_base_features())
    assert result["yontem"] == "rule_based"


# ---------------------------------------------------------------------------
# Fruit weight lookup
# ---------------------------------------------------------------------------

def test_known_fruit_type_uses_correct_weight():
    result_elma = predict_yield(_base_features(detected_tree_count=100), fruit_type="elma")
    result_nar = predict_yield(_base_features(detected_tree_count=100), fruit_type="nar")
    # Pomegranate (0.30 kg) should yield more than apple (0.105 kg) all else equal
    assert result_nar["tahmini_verim_kg"] > result_elma["tahmini_verim_kg"]


def test_unknown_fruit_type_uses_default_weight():
    result = predict_yield(_base_features(detected_tree_count=10), fruit_type="bilinmeyen")
    # base_yield = 10 * DEFAULT_WEIGHT_PER_FRUIT = 2.0 kg before adjustment factors
    assert result["tahmini_verim_kg"] > 0.0


# ---------------------------------------------------------------------------
# Stress factor
# ---------------------------------------------------------------------------

def test_high_stress_reduces_yield():
    low = predict_yield(_base_features(total_stressed_area_percent=0.0))
    high = predict_yield(_base_features(total_stressed_area_percent=80.0))
    assert high["tahmini_verim_kg"] < low["tahmini_verim_kg"]


def test_stress_reduces_quality_score():
    low = predict_yield(_base_features(total_stressed_area_percent=0.0))
    high = predict_yield(_base_features(total_stressed_area_percent=90.0))
    assert high["kalite_skoru"] < low["kalite_skoru"]


def test_stress_clamped_at_100():
    result = predict_yield(_base_features(total_stressed_area_percent=200.0))
    # Should not crash and should equal the 100% stress result
    expected = predict_yield(_base_features(total_stressed_area_percent=100.0))
    assert result["tahmini_verim_kg"] == expected["tahmini_verim_kg"]


# ---------------------------------------------------------------------------
# NDVI factor
# ---------------------------------------------------------------------------

def test_negative_ndvi_reduces_yield():
    healthy = predict_yield(_base_features(average_ndvi=0.7))
    dead = predict_yield(_base_features(average_ndvi=-0.5))
    assert dead["tahmini_verim_kg"] < healthy["tahmini_verim_kg"]


# ---------------------------------------------------------------------------
# Tree age factor
# ---------------------------------------------------------------------------

def test_young_trees_lower_yield():
    young = predict_yield(_base_features(tree_age=1.0))
    mature = predict_yield(_base_features(tree_age=10.0))
    assert young["tahmini_verim_kg"] < mature["tahmini_verim_kg"]


def test_old_trees_lower_yield():
    prime = predict_yield(_base_features(tree_age=15.0))
    old = predict_yield(_base_features(tree_age=50.0))
    assert old["tahmini_verim_kg"] < prime["tahmini_verim_kg"]


# ---------------------------------------------------------------------------
# Quality score range
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stress,ndvi,age", [
    (0.0, 0.8, 10.0),
    (50.0, 0.3, 5.0),
    (90.0, -0.2, 1.0),
    (100.0, 0.0, 25.0),
])
def test_quality_score_within_bounds(stress, ndvi, age):
    result = predict_yield(_base_features(
        total_stressed_area_percent=stress,
        average_ndvi=ndvi,
        tree_age=age,
    ))
    assert 0.0 <= result["kalite_skoru"] <= 100.0


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

def test_yield_is_float():
    result = predict_yield(_base_features())
    assert isinstance(result["tahmini_verim_kg"], float)


def test_quality_score_is_float():
    result = predict_yield(_base_features())
    assert isinstance(result["kalite_skoru"], float)
