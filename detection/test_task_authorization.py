from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse

from detection.models import DetectionResult, ModelVersion
from reports.signals import auto_generate_detection_report

# Smallest byte string python-magic reports as image/jpeg, so the upload
# survives both magic checks in async_detection without shipping a fixture file.
JPEG = (
    bytes.fromhex("ffd8ffe000104a46494600010101006000600000")
    + b"\xff\xdb\x00C\x00"
    + bytes(64)
    + b"\xff\xd9"
)

ALICE_TASK = "11111111-1111-4111-8111-111111111111"
UNKNOWN_TASK = "99999999-9999-4999-8999-999999999999"


class TaskObservationAuthorizationTests(TestCase):
    def setUp(self):
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.alice = User.objects.create_user(username="alice", password="password")
        self.bob = User.objects.create_user(username="bob", password="password")
        ModelVersion.objects.create(
            fruit_type="elma",
            version="v1",
            weights_path="models/elma/v1/weights.pt",
            is_active=True,
        )
        self._dispatch_as(self.alice, ALICE_TASK)

    def tearDown(self):
        post_save.connect(auto_generate_detection_report, sender=DetectionResult)

    def _dispatch_as(self, user, task_id):
        self.client.force_login(user)
        with patch("detection.views.process_image_detection.delay") as mock_delay:
            mock_delay.return_value.id = task_id
            response = self.client.post(
                reverse("detection:async_detection"),
                {
                    "meyve_grubu": "elma",
                    "agac_sayisi": "10",
                    "agac_yasi": "3",
                    "file": SimpleUploadedFile("x.jpg", JPEG, content_type="image/jpeg"),
                },
            )
        self.assertEqual(response.status_code, 202, response.content[:300])
        return response

    def _status_url(self, task_id):
        return reverse("detection:task_status", args=[task_id])

    def _stream_url(self, task_id):
        return reverse("detection:task_stream", args=[task_id])

    def test_owner_can_poll_own_task(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self._status_url(ALICE_TASK)).status_code, 200)

    def test_foreign_user_cannot_poll_task_status(self):
        self.client.force_login(self.bob)
        response = self.client.get(self._status_url(ALICE_TASK))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"detected_count", response.content)

    def test_foreign_user_cannot_open_task_stream(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self._stream_url(ALICE_TASK)).status_code, 404)

    def test_unknown_task_is_refused(self):
        self.client.force_login(self.alice)
        self.assertEqual(
            self.client.get(self._status_url(UNKNOWN_TASK)).status_code, 404
        )
