import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.test import TestCase, override_settings
from django.urls import reverse

from detection.models import DetectionResult, ModelVersion
from detection.tasks import process_image_detection
from reports.signals import auto_generate_detection_report

ASYNC_UID = "asyncuid"
SOURCE_NAME = "upload.jpg"


@override_settings(USE_R2=False)
class AsyncDetectionOwnershipTests(TestCase):
    def setUp(self):
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.tmp = Path(tempfile.mkdtemp())
        patcher = patch("detection.views.BASE_DIR", self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self.user = User.objects.create_user(username="owner", password="password")
        # Migration 0012 seeds one active v1 per fruit type, so this row
        # already exists when the suite runs with migrations enabled.
        # update_or_create states the precondition the test needs without
        # assuming which mode built the database.
        ModelVersion.objects.update_or_create(
            fruit_type="elma",
            version="v1",
            defaults={
                "weights_path": "models/elma/v1/weights.pt",
                "is_active": True,
            },
        )

    def tearDown(self):
        post_save.connect(auto_generate_detection_report, sender=DetectionResult)

    def _run_task(self):
        # apply() runs inline with a real task id, which update_state requires.
        return process_image_detection.apply(
            kwargs={
                "image_path": "/tmp/%s" % SOURCE_NAME,
                "fruit_type": "elma",
                "tree_count": 3,
                "tree_age": 2,
                "user_id": self.user.pk,
            }
        )

    @patch("detection.tasks.predict_tree.predict", autospec=True)
    def test_async_detection_records_the_requester(self, mock_predict):
        mock_predict.return_value = (b"7", ASYNC_UID, 0.91, [])
        self._run_task()
        row = DetectionResult.objects.get(fruit_type="elma")
        self.assertEqual(row.created_by_id, self.user.pk)

    @patch("detection.tasks.predict_tree.predict", autospec=True)
    def test_owner_can_fetch_media_from_an_async_detection(self, mock_predict):
        mock_predict.return_value = (b"7", ASYNC_UID, 0.91, [])
        self._run_task()
        row = DetectionResult.objects.get(fruit_type="elma")

        target = self.tmp / "media" / "detected" / ASYNC_UID
        target.mkdir(parents=True, exist_ok=True)
        (target / SOURCE_NAME).write_bytes(b"image-bytes")

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("detection:serve-media", args=[row.image_path])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Accel-Redirect"], "/media/" + row.image_path)
