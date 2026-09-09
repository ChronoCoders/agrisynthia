from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.urls import Resolver404, resolve
from rest_framework.test import APITestCase

from detection.models import DetectionResult
from reports.signals import auto_generate_detection_report


class DetectionActionTenantIsolationTests(APITestCase):
    def setUp(self):
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.alice = User.objects.create_user(username="alice", password="password")
        self.bob = User.objects.create_user(username="bob", password="password")
        self.carol = User.objects.create_user(username="carol", password="password")

        self.alice_row = DetectionResult.objects.create(
            fruit_type="elma",
            tree_count=50,
            tree_age=7,
            detected_count=500,
            weight=2.0,
            total_weight=1000.0,
            processing_time=4.0,
            model_version="elma.pt v9.9.9",
            image_path="alice_orchard.jpg",
            created_by=self.alice,
        )

        self.bob_row = DetectionResult.objects.create(
            fruit_type="nar",
            tree_count=3,
            tree_age=2,
            detected_count=7,
            weight=2.0,
            total_weight=14.0,
            processing_time=1.0,
            model_version="nar.pt v1.1.1",
            image_path="bob_orchard.jpg",
            created_by=self.bob,
        )

    def tearDown(self):
        post_save.connect(auto_generate_detection_report, sender=DetectionResult)

    def test_list_does_not_leak_across_users(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get("/api/detections/")
        rows = response.data["results"]
        ids = [row["id"] for row in rows]
        self.assertIn(self.bob_row.id, ids)
        self.assertNotIn(self.alice_row.id, ids)
        self.assertNotIn("alice_orchard.jpg", [row["image_path"] for row in rows])

    def test_recent_does_not_leak_across_users(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get("/api/detections/recent/")
        rows = response.data
        self.assertNotIn(self.alice_row.id, [row["id"] for row in rows])
        self.assertNotIn("alice_orchard.jpg", [row["image_path"] for row in rows])
        self.assertNotIn("elma.pt v9.9.9", [row["model_version"] for row in rows])

    def test_statistics_counts_only_own_rows(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get("/api/detections/statistics/")
        overall = response.data["overall"]
        self.assertEqual(overall["total_detections"], 1)
        self.assertEqual(overall["total_fruits_detected"], 7)
        self.assertEqual(overall["total_weight"], 14.0)
        self.assertEqual(overall["avg_processing_time"], 1.0)

        by_fruit = list(response.data["by_fruit_type"])
        self.assertEqual([entry["fruit_type"] for entry in by_fruit], ["nar"])
        self.assertEqual(by_fruit[0]["total_detected"], 7)

    def test_statistics_empty_for_user_without_detections(self):
        self.client.force_authenticate(user=self.carol)
        response = self.client.get("/api/detections/statistics/")
        overall = response.data["overall"]
        self.assertEqual(overall["total_detections"], 0)
        self.assertIsNone(overall["total_fruits_detected"])
        self.assertIsNone(overall["total_weight"])
        self.assertIsNone(overall["avg_processing_time"])
        self.assertEqual(list(response.data["by_fruit_type"]), [])


class WithdrawnBatchApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="batchuser", password="password")
        self.client.force_authenticate(user=self.user)

    def test_batch_list_route_is_withdrawn(self):
        self.assertEqual(self.client.get("/api/batches/").status_code, 404)
        with self.assertRaises(Resolver404):
            resolve("/api/batches/")

    def test_batch_summary_route_is_withdrawn(self):
        self.assertEqual(self.client.get("/api/batches/1/summary/").status_code, 404)
        with self.assertRaises(Resolver404):
            resolve("/api/batches/1/summary/")
