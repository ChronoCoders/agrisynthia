import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.test import TestCase, override_settings
from django.urls import reverse

from detection.models import DetectionResult
from reports.signals import auto_generate_detection_report


@override_settings(USE_R2=False)
class MediaAuthorizationTests(TestCase):
    def setUp(self):
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.tmp = Path(tempfile.mkdtemp())
        patcher = patch("detection.views.BASE_DIR", self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self.alice = User.objects.create_user(username="alice", password="password")
        self.bob = User.objects.create_user(username="bob", password="password")

        self.alice_path = self._make_detection(self.alice, "alice-dir", "alice.jpg")
        self.bob_path = self._make_detection(self.bob, "bob-dir", "bob.jpg")

    def tearDown(self):
        post_save.connect(auto_generate_detection_report, sender=DetectionResult)

    def _make_detection(self, owner, folder, filename):
        relative = "detected/%s/%s" % (folder, filename)
        target = self.tmp / "media" / "detected" / folder
        target.mkdir(parents=True, exist_ok=True)
        (target / filename).write_bytes(b"image-bytes")
        DetectionResult.objects.create(
            fruit_type="elma",
            tree_count=1,
            tree_age=1,
            detected_count=1,
            weight=1.0,
            total_weight=1.0,
            processing_time=1.0,
            image_path=relative,
            created_by=owner,
        )
        return relative

    def _url(self, relative):
        return reverse("detection:serve-media", args=[relative])

    def test_owner_can_fetch_own_file(self):
        self.client.force_login(self.alice)
        response = self.client.get(self._url(self.alice_path))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Accel-Redirect"], "/media/" + self.alice_path)

    def test_foreign_owner_is_refused(self):
        self.client.force_login(self.bob)
        response = self.client.get(self._url(self.alice_path))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("X-Accel-Redirect", response)

    @override_settings(USE_R2=True)
    @patch(
        "django.core.files.storage.default_storage.url",
        return_value="https://r2.example/signed",
    )
    def test_foreign_owner_is_refused_under_r2(self, mock_url):
        self.client.force_login(self.bob)
        response = self.client.get(self._url(self.alice_path))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_url.called)

    def test_path_without_owning_object_is_refused(self):
        target = self.tmp / "media" / "unknown"
        target.mkdir(parents=True, exist_ok=True)
        (target / "orphan.bin").write_bytes(b"orphan")
        self.client.force_login(self.bob)
        response = self.client.get(self._url("unknown/orphan.bin"))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("X-Accel-Redirect", response)

    def test_authorization_is_decided_before_existence(self):
        self.client.force_login(self.bob)
        existing = self.client.get(self._url(self.alice_path))
        missing = self.client.get(self._url("detected/alice-dir/ghost.jpg"))
        self.assertEqual(missing.status_code, existing.status_code)
        self.assertEqual(existing.status_code, 404)
