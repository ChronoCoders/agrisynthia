# -*- coding: utf-8 -*-
"""
Tests for dron_map app.

This module provides test cases for the drone mapping functionality including:
- Project CRUD operations
- API endpoints
- File upload validation
- Vegetation index calculations

To run tests:
    python manage.py test dron_map
"""

import io
from unittest.mock import patch, MagicMock

from PIL import Image
from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Projects


class ProjectModelTests(TestCase):
    """Test cases for the Projects model."""

    def setUp(self):
        """Set up test data."""
        self.project = Projects.objects.create(
            Farm="Test Farm",
            Field="Field A",
            Title="Test Project",
            State="Active",
        )

    def test_project_creation(self):
        """Test that a project can be created."""
        self.assertEqual(self.project.Farm, "Test Farm")
        self.assertEqual(self.project.Field, "Field A")
        self.assertEqual(self.project.State, "Active")

    def test_project_string_representation(self):
        """Test the string representation of a project."""
        self.assertIsNotNone(str(self.project))


class ProjectAPITests(APITestCase):
    """Test cases for the Projects API endpoints."""

    def setUp(self):
        """Set up test user and authenticate."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        self.project = Projects.objects.create(
            Farm="API Test Farm",
            Field="Field B",
            Title="API Test Project",
            State="Active",
        )

    def test_list_projects_requires_auth(self):
        """Test that listing projects requires authentication."""
        self.client.logout()
        response = self.client.get("/api/projects/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_projects(self):
        """Test listing all projects."""
        response = self.client.get("/api/projects/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_project_statistics(self):
        """Test getting project statistics."""
        response = self.client.get("/api/projects/statistics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_projects", response.data)

    def test_filter_projects_by_farm(self):
        """Test filtering projects by farm name."""
        response = self.client.get("/api/projects/?Farm=API Test Farm")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ProjectViewTests(TestCase):
    """Test cases for project web views."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="viewuser", password="testpass123"
        )

    def test_projects_page_requires_login(self):
        """Test that projects page requires authentication."""
        response = self.client.get("/dron-map/projects/")
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_projects_page_authenticated(self):
        """Test accessing projects page when authenticated."""
        self.client.login(username="viewuser", password="testpass123")
        response = self.client.get("/dron-map/projects/")
        self.assertIn(response.status_code, [200, 302])


class ProjectViewCreateTests(TestCase):
    """Test project creation via web views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="mapuser", password="pass123")
        self.client.login(username="mapuser", password="pass123")

    def test_add_project_page_loads(self):
        """Add project page should return 200."""
        response = self.client.get("/dron-map/projects/add/")
        self.assertIn(response.status_code, [200, 302])

    def test_map_page_requires_login(self):
        """Map page should redirect unauthenticated users."""
        self.client.logout()
        response = self.client.get("/dron-map/map/1/")
        self.assertEqual(response.status_code, 302)


class ProjectAPIWriteTests(APITestCase):
    """Test project create/update/delete via API."""

    def setUp(self):
        self.user = User.objects.create_user(username="apiwriter", password="pass123")
        self.client.force_authenticate(user=self.user)

    def test_create_project(self):
        """Authenticated user should be able to create a project."""
        response = self.client.post(
            "/api/projects/",
            {
                "Farm": "New Farm",
                "Field": "Field C",
                "Title": "New Project",
                "State": "Active",
            },
            format="json",
        )
        self.assertIn(response.status_code, [200, 201])

    def test_unauthenticated_cannot_create_project(self):
        """Unauthenticated requests should be rejected."""
        self.client.logout()
        response = self.client.post(
            "/api/projects/",
            {"Farm": "Hack Farm"},
            format="json",
        )
        self.assertIn(response.status_code, [401, 403])


class HealthAlgorithmTests(TestCase):
    """Test vegetation index algorithm names are valid."""

    def test_health_algorithms_not_empty(self):
        """HEALTH_ALGORITHMS dict should have entries."""
        from dron_map.views import HEALTH_ALGORITHMS
        self.assertGreater(len(HEALTH_ALGORITHMS), 0)

    def test_ndvi_present(self):
        """NDVI must be present as it is the most common index."""
        from dron_map.views import HEALTH_ALGORITHMS
        self.assertIn("ndvi", HEALTH_ALGORITHMS)


# ---------------------------------------------------------------------------
# Shared helpers for analysis action tests
# ---------------------------------------------------------------------------

def _make_density_data():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[]]},
                "properties": {
                    "tree_count": 20,
                    "density_per_ha": 200.0,
                    "density_label": "normal",
                },
            }
        ],
    }


def _make_stress_data():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[]]},
                "properties": {
                    "zone_id": "z1",
                    "stress_class": "high_stress",
                    "stress_label": "Yüksek Stres",
                    "area_ha": 1.5,
                },
            }
        ],
        "ozet": {
            "toplam_stres_alani_ha": 1.5,
            "yuksek_stres_alani_ha": 1.5,
            "yuksek_stres_yuzde": 30.0,
            "en_buyuk_zon_ha": 1.5,
        },
    }


def _make_analysis_data(raster_path=None):
    from pathlib import Path
    from dron_map.api_views import _AnalysisData
    return _AnalysisData(
        density_data=_make_density_data(),
        stress_data=_make_stress_data(),
        raster_path=raster_path or Path("/fake/ortho.tif"),
    )


# ---------------------------------------------------------------------------
# Mocked analysis action tests
# ---------------------------------------------------------------------------

class ProjectDensityActionTests(APITestCase):
    """Tests for the /density/ action with mocked YOLO inference."""

    def setUp(self):
        self.user = User.objects.create_user(username="dmap_user", password="pass")
        self.client.force_authenticate(user=self.user)
        self.project = Projects.objects.create(
            Farm="Mock Farm", Field="F1", Title="Mock Project", State="Active",
            created_by=self.user,
        )

    def _url(self):
        return f"/api/projects/{self.project.pk}/density/"

    def test_density_returns_400_when_no_orthophoto(self):
        with patch("dron_map.api_views.ProjectViewSet._get_orthophoto_path", return_value=None):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)

    def test_density_returns_feature_collection_on_success(self):
        with patch("dron_map.api_views.ProjectViewSet._get_orthophoto_path",
                   return_value=MagicMock()), \
             patch("dron_map.api_views.predict_tree.predict",
                   return_value=(5, "uid", 0.9, [{"x": 100, "y": 200}])), \
             patch("dron_map.api_views.pixel_to_geo",
                   return_value=[{"lon": 28.97, "lat": 41.00}]), \
             patch("dron_map.api_views.generate_density_grid",
                   return_value=_make_density_data()):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["type"], "FeatureCollection")

    def test_density_returns_500_when_yolo_fails(self):
        with patch("dron_map.api_views.ProjectViewSet._get_orthophoto_path",
                   return_value=MagicMock()), \
             patch("dron_map.api_views.predict_tree.predict",
                   side_effect=RuntimeError("GPU OOM")):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 500)
        self.assertIn("detail", response.data)


class ProjectDecisionsActionTests(APITestCase):
    """Tests for the /decisions/ action — uses _run_analysis mock."""

    def setUp(self):
        self.user = User.objects.create_user(username="dec_user", password="pass")
        self.client.force_authenticate(user=self.user)
        self.project = Projects.objects.create(
            Farm="Dec Farm", Field="F2", Title="Dec Project", State="Active",
            created_by=self.user,
        )

    def _url(self):
        return f"/api/projects/{self.project.pk}/decisions/"

    def test_decisions_propagates_run_analysis_error(self):
        from rest_framework.response import Response as DRFResponse
        mock_error = DRFResponse({"detail": "ortofoto yok"}, status=400)
        with patch("dron_map.api_views.ProjectViewSet._run_analysis",
                   return_value=mock_error):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)

    def test_decisions_returns_recommendations(self):
        with patch("dron_map.api_views.ProjectViewSet._run_analysis",
                   return_value=_make_analysis_data()), \
             patch("dron_map.api_views.generate_recommendations",
                   return_value={
                       "recommendations": [
                           {"zone_id": "z1", "area_ha": 1.5, "severity": "high",
                            "action": "irrigate"}
                       ],
                       "total_recommendations": 1,
                   }):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("oneriler", response.data)
        self.assertEqual(response.data["toplam_oneri"], 1)

    def test_decisions_empty_when_no_stress_zones(self):
        empty_analysis = _make_analysis_data()
        empty_analysis.stress_data["features"] = []
        with patch("dron_map.api_views.ProjectViewSet._run_analysis",
                   return_value=empty_analysis), \
             patch("dron_map.api_views.generate_recommendations",
                   return_value={"recommendations": [], "total_recommendations": 0}):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["toplam_oneri"], 0)


class ProjectYieldActionTests(APITestCase):
    """Tests for the /yield/ action — uses _run_analysis mock."""

    def setUp(self):
        self.user = User.objects.create_user(username="yield_user", password="pass")
        self.client.force_authenticate(user=self.user)
        self.project = Projects.objects.create(
            Farm="Yield Farm", Field="F3", Title="Yield Project", State="Active",
            created_by=self.user,
        )

    def _url(self, **params):
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        base = f"/api/projects/{self.project.pk}/yield/"
        return f"{base}?{qs}" if qs else base

    def test_yield_propagates_run_analysis_error(self):
        from rest_framework.response import Response as DRFResponse
        mock_error = DRFResponse({"detail": "ortofoto yok"}, status=400)
        with patch("dron_map.api_views.ProjectViewSet._run_analysis",
                   return_value=mock_error):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)

    def test_yield_returns_prediction_fields(self):
        with patch("dron_map.api_views.ProjectViewSet._run_analysis",
                   return_value=_make_analysis_data()), \
             patch("dron_map.api_views._compute_average_ndvi", return_value=0.65):
            response = self.client.get(self._url(tree_age=10))
        self.assertEqual(response.status_code, 200)
        self.assertIn("tahmini_verim_kg", response.data)
        self.assertIn("kalite_skoru", response.data)

    def test_yield_accepts_fruit_type_param(self):
        with patch("dron_map.api_views.ProjectViewSet._run_analysis",
                   return_value=_make_analysis_data()), \
             patch("dron_map.api_views._compute_average_ndvi", return_value=0.65):
            response = self.client.get(self._url(meyve_grubu="elma", tree_age=8))
        self.assertEqual(response.status_code, 200)

    def test_yield_kalite_skoru_in_range(self):
        with patch("dron_map.api_views.ProjectViewSet._run_analysis",
                   return_value=_make_analysis_data()), \
             patch("dron_map.api_views._compute_average_ndvi", return_value=0.5):
            response = self.client.get(self._url())
        score = float(response.data["kalite_skoru"])
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
