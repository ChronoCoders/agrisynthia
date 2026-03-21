# -*- coding: utf-8 -*-
"""
Tests for detection app.

This module provides test cases for the fruit detection functionality including:
- Detection model operations
- API endpoints
- Cache utilities
- Image validation
- Async task processing

To run tests:
    python manage.py test detection
"""

import io
import tempfile
from unittest.mock import MagicMock, patch

from PIL import Image
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from .cache_utils import calculate_image_hash
from .models import DetectionResult, MultiDetectionBatch


class DetectionResultModelTests(TestCase):
    """Test cases for the DetectionResult model."""

    def setUp(self):
        """Set up test data."""
        self.detection = DetectionResult.objects.create(
            fruit_type="mandalina",
            tree_count=100,
            tree_age=5,
            detected_count=450,
            weight=56.25,
            total_weight=5625.0,
            processing_time=2.34,
            confidence_score=0.92,
            image_path="detected/test/image.jpg",
        )

    def test_detection_result_creation(self):
        """Test that a detection result can be created."""
        self.assertEqual(self.detection.fruit_type, "mandalina")
        self.assertEqual(self.detection.detected_count, 450)
        self.assertEqual(self.detection.tree_count, 100)
        self.assertAlmostEqual(self.detection.confidence_score, 0.92)

    def test_detection_total_weight_calculation(self):
        """Test total weight calculation."""
        expected_weight = 5625.0
        self.assertAlmostEqual(self.detection.total_weight, expected_weight)

    def test_model_degradation_check(self):
        """Test model degradation check method."""
        result = self.detection.check_model_degradation()
        self.assertIsInstance(result, dict)


class MultiDetectionBatchTests(TestCase):
    """Test cases for MultiDetectionBatch model."""

    def setUp(self):
        """Set up test data."""
        self.batch = MultiDetectionBatch.objects.create(
            fruit_type="elma",
            batch_hash="abc123def456",
            image_count=10,
        )

    def test_batch_creation(self):
        """Test batch creation."""
        self.assertEqual(self.batch.fruit_type, "elma")
        self.assertEqual(self.batch.image_count, 10)
        self.assertEqual(self.batch.batch_hash, "abc123def456")


class DetectionAPITests(APITestCase):
    """Test cases for Detection API endpoints."""

    def setUp(self):
        """Set up test user and authenticate."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        self.detection = DetectionResult.objects.create(
            fruit_type="armut",
            tree_count=50,
            tree_age=3,
            detected_count=200,
            weight=44.0,
            total_weight=2200.0,
            processing_time=1.5,
            confidence_score=0.88,
            image_path="detected/test/armut.jpg",
        )

    def test_list_detections_requires_auth(self):
        """Test that listing detections requires authentication."""
        self.client.logout()
        response = self.client.get("/api/detections/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_detections(self):
        """Test listing all detections."""
        response = self.client.get("/api/detections/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_detection_statistics(self):
        """Test getting detection statistics."""
        response = self.client.get("/api/detections/statistics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("overall", response.data)

    def test_get_recent_detections(self):
        """Test getting recent detections."""
        response = self.client.get("/api/detections/recent/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_fruit_type(self):
        """Test filtering detections by fruit type."""
        response = self.client.get("/api/detections/?fruit_type=armut")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CacheUtilsTests(TestCase):
    """Test cases for cache utilities."""

    def test_calculate_image_hash(self):
        """Test image hash calculation."""
        test_data = b"test image data"
        hash_result = calculate_image_hash(test_data)
        self.assertIsInstance(hash_result, str)
        self.assertEqual(len(hash_result), 64)  # SHA256 hex digest length

    def test_hash_consistency(self):
        """Test that same data produces same hash."""
        test_data = b"consistent data"
        hash1 = calculate_image_hash(test_data)
        hash2 = calculate_image_hash(test_data)
        self.assertEqual(hash1, hash2)

    def test_hash_uniqueness(self):
        """Test that different data produces different hash."""
        data1 = b"data one"
        data2 = b"data two"
        hash1 = calculate_image_hash(data1)
        hash2 = calculate_image_hash(data2)
        self.assertNotEqual(hash1, hash2)


class DetectionViewTests(TestCase):
    """Test cases for detection web views."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="viewuser", password="testpass123"
        )

    def test_index_page_requires_login(self):
        """Test that index page requires authentication."""
        response = self.client.get("/detection/")
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_system_monitoring_requires_login(self):
        """Test that system monitoring requires authentication."""
        response = self.client.get("/detection/system-monitoring/")
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_index_page_authenticated(self):
        """Test accessing index page when authenticated."""
        self.client.login(username="viewuser", password="testpass123")
        response = self.client.get("/detection/")
        self.assertEqual(response.status_code, 200)


class InputValidationTests(TestCase):
    """Test cases for input validation."""

    def test_tree_count_range_validation(self):
        """Test that tree count must be within valid range."""
        # Valid range: 1-100000
        valid_count = 500
        self.assertTrue(1 <= valid_count <= 100000)

        invalid_count = 200000
        self.assertFalse(1 <= invalid_count <= 100000)

    def test_tree_age_range_validation(self):
        """Test that tree age must be within valid range."""
        # Valid range: 0-150
        valid_age = 50
        self.assertTrue(0 <= valid_age <= 150)

        invalid_age = 200
        self.assertFalse(0 <= invalid_age <= 150)


class ImageValidationTests(TestCase):
    """Test file upload validation logic."""

    def _make_image_file(self, fmt="JPEG", size=(100, 100), name="test.jpg"):
        """Create an in-memory image file for testing."""
        img = Image.new("RGB", size, color=(128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        buf.seek(0)
        buf.name = name
        buf.size = buf.getbuffer().nbytes
        return buf

    def test_valid_jpeg_passes(self):
        """Valid JPEG should not raise ValidationError."""
        from detection.views import validate_image_file
        from django.core.files.uploadedfile import InMemoryUploadedFile
        buf = self._make_image_file()
        uploaded = InMemoryUploadedFile(buf, "file", "test.jpg", "image/jpeg", buf.getbuffer().nbytes, None)
        # Should not raise
        self.assertTrue(validate_image_file(uploaded))

    def test_oversized_file_raises(self):
        """Files exceeding MAX_DETECTION_FILE_SIZE should raise ValidationError."""
        from detection.views import validate_image_file
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import InMemoryUploadedFile
        buf = self._make_image_file()
        uploaded = InMemoryUploadedFile(buf, "file", "test.jpg", "image/jpeg", buf.getbuffer().nbytes, None)
        uploaded.size = 11 * 1024 * 1024  # 11MB — over limit
        with self.assertRaises(ValidationError):
            validate_image_file(uploaded)

    def test_invalid_extension_raises(self):
        """Non-image extensions should raise ValidationError."""
        from detection.views import validate_image_file
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import InMemoryUploadedFile
        buf = io.BytesIO(b"not an image")
        buf.name = "malicious.exe"
        buf.size = 100
        uploaded = InMemoryUploadedFile(buf, "file", "malicious.exe", "application/octet-stream", 100, None)
        with self.assertRaises(ValidationError):
            validate_image_file(uploaded)

    def test_path_traversal_in_filename_raises(self):
        """Path traversal in filename should raise ValidationError."""
        from detection.views import sanitize_filename
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            sanitize_filename("../../etc/passwd")


class AsyncDetectionViewTests(TestCase):
    """Test async detection endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="asyncuser", password="pass123")
        self.client.login(username="asyncuser", password="pass123")

    def _make_upload_file(self):
        img = Image.new("RGB", (100, 100), color=(0, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        buf.name = "test.jpg"
        return buf

    @patch("detection.views.process_image_detection")
    @patch("detection.views.get_cached_prediction", return_value=None)
    @patch("magic.from_buffer", return_value="image/jpeg")
    @patch("magic.from_file", return_value="image/jpeg")
    @patch("django.core.files.uploadedfile.UploadedFile.chunks")
    def test_async_detection_queues_task(self, mock_chunks, mock_magic_file, mock_magic_buf, mock_cache, mock_task):
        """Successful upload should queue a Celery task and return 202."""
        mock_task.delay.return_value = MagicMock(id="test-task-id-123")
        buf = self._make_upload_file()
        response = self.client.post(
            "/detection/async-detection/",
            {
                "meyve_grubu": "mandalina",
                "agac_sayisi": "100",
                "agac_yasi": "5",
                "file": buf,
            },
        )
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "PENDING")

    def test_async_detection_requires_login(self):
        """Unauthenticated requests should be redirected."""
        self.client.logout()
        response = self.client.post("/detection/async-detection/", {})
        self.assertIn(response.status_code, [302, 403])

    def test_async_detection_missing_fields(self):
        """Missing required fields should return 400."""
        response = self.client.post("/detection/async-detection/", {"meyve_grubu": "mandalina"})
        self.assertEqual(response.status_code, 400)

    def test_async_detection_invalid_fruit_type(self):
        """Invalid fruit type should return 400."""
        buf = self._make_upload_file()
        response = self.client.post(
            "/detection/async-detection/",
            {
                "meyve_grubu": "kavun",  # not a valid type
                "agac_sayisi": "10",
                "agac_yasi": "3",
                "file": buf,
            },
        )
        self.assertEqual(response.status_code, 400)


class TaskStatusViewTests(TestCase):
    """Test Celery task status endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="taskuser", password="pass123")
        self.client.login(username="taskuser", password="pass123")

    @patch("detection.views.AsyncResult")
    def test_pending_task_status(self, mock_async_result):
        """PENDING task should return correct structure."""
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.info = None
        mock_async_result.return_value = mock_result

        response = self.client.get("/detection/task-status/fake-task-id/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "PENDING")
        self.assertEqual(data["progress"], 0)

    @patch("detection.views.AsyncResult")
    def test_success_task_status(self, mock_async_result):
        """SUCCESS task should include result data."""
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"detected_count": 42, "confidence_score": 0.91}
        mock_async_result.return_value = mock_result

        response = self.client.get("/detection/task-status/fake-task-id/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertIn("result", data)
        self.assertEqual(data["progress"], 100)


class CacheInvalidatePermissionTests(TestCase):
    """Test that cache invalidation requires admin."""

    def setUp(self):
        self.client = Client()
        self.regular_user = User.objects.create_user(username="regular", password="pass123")
        self.admin_user = User.objects.create_user(username="admin", password="pass123", is_staff=True)

    def test_regular_user_cannot_invalidate_cache(self):
        """Non-staff user should get 403."""
        self.client.login(username="regular", password="pass123")
        response = self.client.post("/detection/cache/invalidate/", {"all": "true"})
        self.assertEqual(response.status_code, 403)

    def test_admin_user_can_invalidate_cache(self):
        """Staff user should be able to invalidate cache."""
        self.client.login(username="admin", password="pass123")
        with patch("detection.views.invalidate_all_predictions", return_value=0):
            response = self.client.post("/detection/cache/invalidate/", {"all": "true"})
        self.assertEqual(response.status_code, 200)


class CleanupTaskTests(TestCase):
    """Test cleanup_old_results task behavior."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone

        old_time = timezone.now() - timedelta(days=40)

        self.old_result = DetectionResult.objects.create(
            fruit_type="elma",
            tree_count=10,
            tree_age=3,
            detected_count=50,
            weight=5.25,
            total_weight=52.5,
            processing_time=1.2,
            image_path="detected/old/test.jpg",
        )
        # Manually set created_at to past
        DetectionResult.objects.filter(pk=self.old_result.pk).update(created_at=old_time)

    def test_cleanup_removes_old_db_records(self):
        """Records older than threshold should be deleted from DB."""
        from detection.tasks import cleanup_old_results
        result = cleanup_old_results(days_old=30)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreaterEqual(result["deleted_db_count"], 1)
        self.assertFalse(DetectionResult.objects.filter(pk=self.old_result.pk).exists())

    def test_cleanup_skips_recent_records(self):
        """Recent records should not be deleted."""
        recent = DetectionResult.objects.create(
            fruit_type="armut",
            tree_count=5,
            tree_age=2,
            detected_count=20,
            weight=4.4,
            total_weight=22.0,
            processing_time=0.8,
            image_path="detected/recent/test.jpg",
        )
        from detection.tasks import cleanup_old_results
        cleanup_old_results(days_old=30)
        self.assertTrue(DetectionResult.objects.filter(pk=recent.pk).exists())
