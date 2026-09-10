import json

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse

from detection.models import DetectionResult
from reports.signals import auto_generate_detection_report

ALICE_COUNT = 500
BOB_COUNT = 7


class DashboardAggregateScopeTests(TestCase):
    def setUp(self):
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.alice = User.objects.create_user(username="alice", password="password")
        self.bob = User.objects.create_user(username="bob", password="password")
        self._detection(self.alice, ALICE_COUNT, "alice.jpg")
        self._detection(self.bob, BOB_COUNT, "bob.jpg")

    def tearDown(self):
        post_save.connect(auto_generate_detection_report, sender=DetectionResult)

    def _detection(self, owner, detected_count, filename):
        return DetectionResult.objects.create(
            fruit_type="elma",
            tree_count=1,
            tree_age=1,
            detected_count=detected_count,
            weight=1.0,
            total_weight=1.0,
            processing_time=1.0,
            image_path="detected/%s/%s" % (owner.username, filename),
            created_by=owner,
        )

    def _chart_values(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse("detection:index"))
        self.assertEqual(response.status_code, 200)
        return json.loads(response.context["chart_data"])["values"]

    def test_chart_averages_only_the_callers_detections(self):
        # Both rows land in the same month, so a global average would be the mean
        # of the two counts rather than either tenant's own figure.
        self.assertEqual(self._chart_values(self.bob), [float(BOB_COUNT)])
        self.assertEqual(self._chart_values(self.alice), [float(ALICE_COUNT)])

    def test_chart_is_empty_for_a_user_without_detections(self):
        carol = User.objects.create_user(username="carol", password="password")
        self.assertIsNone(self._chart_values(carol))
