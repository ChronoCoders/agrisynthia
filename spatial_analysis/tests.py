# -*- coding: utf-8 -*-
"""
Tests for spatial_analysis.density — pure math, no real raster required.
"""
import pytest

from spatial_analysis.density import generate_density_grid, DetectionPoint


# ---------------------------------------------------------------------------
# generate_density_grid
# ---------------------------------------------------------------------------

def test_empty_points_returns_empty_feature_collection():
    result = generate_density_grid([])
    assert result["type"] == "FeatureCollection"
    assert result["features"] == []


def test_single_point_produces_one_feature():
    # (lon, lat) near Istanbul
    points = [(28.9784, 41.0082)]
    result = generate_density_grid(points, grid_size_meters=100.0)
    assert len(result["features"]) == 1


def test_feature_has_required_keys():
    points = [(28.9784, 41.0082), (28.9785, 41.0082)]
    result = generate_density_grid(points, grid_size_meters=100.0)
    feature = result["features"][0]
    assert feature["type"] == "Feature"
    props = feature["properties"]
    for key in ("tree_count", "density_per_ha", "density_label"):
        assert key in props


def test_geometry_is_polygon():
    points = [(28.9784, 41.0082)]
    result = generate_density_grid(points, grid_size_meters=100.0)
    geom = result["features"][0]["geometry"]
    assert geom["type"] == "Polygon"
    # Closed ring: first == last
    ring = geom["coordinates"][0]
    assert ring[0] == ring[-1]


def test_tree_count_sums_to_total_input():
    # Two identical points fall in the same cell
    points = [(28.9784, 41.0082), (28.9784, 41.0082)]
    result = generate_density_grid(points, grid_size_meters=100.0)
    total = sum(f["properties"]["tree_count"] for f in result["features"])
    assert total == 2


def test_points_far_apart_land_in_different_cells():
    # 2 km apart — should produce two cells at 100 m grid
    points = [(28.9784, 41.0082), (29.0000, 41.0082)]
    result = generate_density_grid(points, grid_size_meters=100.0)
    assert len(result["features"]) >= 2


@pytest.mark.parametrize("grid_size", [10.0, 50.0, 200.0])
def test_custom_grid_size_accepted(grid_size):
    points = [(28.9784, 41.0082), (28.9790, 41.0090)]
    result = generate_density_grid(points, grid_size_meters=grid_size)
    assert result["type"] == "FeatureCollection"


def test_density_label_low_for_sparse_grid():
    # Single tree in a large cell → density is very low
    points = [(28.9784, 41.0082)]
    result = generate_density_grid(points, grid_size_meters=1000.0)  # 100 ha cell
    label = result["features"][0]["properties"]["density_label"]
    assert label == "düşük"


def test_density_per_ha_positive():
    points = [(28.9784, 41.0082)]
    result = generate_density_grid(points, grid_size_meters=100.0)
    assert result["features"][0]["properties"]["density_per_ha"] > 0.0


# ---------------------------------------------------------------------------
# DetectionPoint dataclass
# ---------------------------------------------------------------------------

def test_detection_point_stores_xy():
    pt = DetectionPoint(x=10, y=20)
    assert pt.x == 10
    assert pt.y == 20
