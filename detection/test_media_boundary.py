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

ALICE_SLUG = "alicesync"
BOB_SLUG = "bobsync"
ASYNC_SLUG = "aliceasync"
ASYNC_SOURCE = "upload.jpg"


@override_settings(USE_R2=False)
class MediaBoundarySystemTests(TestCase):
    def setUp(self):
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.tmp = Path(tempfile.mkdtemp())
        patcher = patch("detection.views.BASE_DIR", self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "media").mkdir(parents=True, exist_ok=True)

        self.alice = User.objects.create_user(username="alice", password="password")
        self.bob = User.objects.create_user(username="bob", password="password")
        ModelVersion.objects.create(
            fruit_type="elma",
            version="v1",
            weights_path="models/elma/v1/weights.pt",
            is_active=True,
        )

        self.alice_sync = self._sync_detection(self.alice, ALICE_SLUG, "alice.jpg")
        self.bob_sync = self._sync_detection(self.bob, BOB_SLUG, "bob.jpg")
        self._archive(ALICE_SLUG)
        self._archive(BOB_SLUG)
        self.alice_async = self._async_detection()

    def tearDown(self):
        post_save.connect(auto_generate_detection_report, sender=DetectionResult)

    def _media_file(self, slug, filename):
        target = self.tmp / "media" / "detected" / slug
        target.mkdir(parents=True, exist_ok=True)
        (target / filename).write_bytes(b"image-bytes")

    def _archive(self, slug):
        (self.tmp / "media" / ("%s_result.zip" % slug)).write_bytes(b"archive-bytes")

    def _sync_detection(self, owner, slug, filename):
        self._media_file(slug, filename)
        return DetectionResult.objects.create(
            fruit_type="elma",
            tree_count=1,
            tree_age=1,
            detected_count=1,
            weight=1.0,
            total_weight=1.0,
            processing_time=1.0,
            image_path="detected/%s/%s" % (slug, filename),
            created_by=owner,
        )

    def _async_detection(self):
        with patch("detection.tasks.predict_tree.predict", autospec=True) as mock_predict:
            mock_predict.return_value = (b"5", ASYNC_SLUG, 0.9, [])
            process_image_detection.apply(
                kwargs={
                    "image_path": "/tmp/%s" % ASYNC_SOURCE,
                    "fruit_type": "elma",
                    "tree_count": 2,
                    "tree_age": 1,
                    "user_id": self.alice.pk,
                }
            )
        row = DetectionResult.objects.get(image_path__startswith="detected/%s/" % ASYNC_SLUG)
        self._media_file(ASYNC_SLUG, ASYNC_SOURCE)
        return row

    def _media_url(self, relative):
        return reverse("detection:serve-media", args=[relative])

    def _archive_url(self, slug):
        return reverse("detection:download_image", args=[slug])

    def test_foreign_media_and_archive_are_unreachable(self):
        self.client.force_login(self.alice)
        self.assertEqual(
            self.client.get(self._media_url(self.bob_sync.image_path)).status_code, 404
        )
        self.assertEqual(self.client.get(self._archive_url(BOB_SLUG)).status_code, 404)

    def test_write_surface_cannot_restore_reach(self):
        self.client.force_login(self.alice)
        response = self.client.patch(
            "/api/detections/%d/" % self.alice_sync.id,
            {"image_path": "detected/%s/" % BOB_SLUG},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 405)

        self.assertEqual(
            self.client.get(self._media_url(self.bob_sync.image_path)).status_code, 404
        )
        self.assertEqual(self.client.get(self._archive_url(BOB_SLUG)).status_code, 404)

        self.alice_sync.refresh_from_db()
        self.assertEqual(
            self.alice_sync.image_path, "detected/%s/alice.jpg" % ALICE_SLUG
        )

    def test_own_media_and_archive_remain_reachable(self):
        self.client.force_login(self.alice)
        self.assertEqual(
            self.client.get(self._media_url(self.alice_sync.image_path)).status_code, 200
        )
        self.assertEqual(
            self.client.get(self._media_url(self.alice_async.image_path)).status_code, 200
        )
        self.assertEqual(self.client.get(self._archive_url(ALICE_SLUG)).status_code, 200)
