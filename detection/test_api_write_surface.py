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

ALICE_SLUG = "aliceslug"
BOB_SLUG = "bobslug"


@override_settings(USE_R2=False)
class DetectionWriteSurfaceTests(TestCase):
    def setUp(self):
        post_save.disconnect(auto_generate_detection_report, sender=DetectionResult)

        self.tmp = Path(tempfile.mkdtemp())
        patcher = patch("detection.views.BASE_DIR", self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self.alice = User.objects.create_user(username="alice", password="password")
        self.bob = User.objects.create_user(username="bob", password="password")

        self.alice_path = self._make(self.alice, ALICE_SLUG, "alice.jpg")
        self.bob_path = self._make(self.bob, BOB_SLUG, "bob.jpg")
        self.alice_row = DetectionResult.objects.get(created_by=self.alice)

    def tearDown(self):
        post_save.connect(auto_generate_detection_report, sender=DetectionResult)

    def _make(self, owner, slug, filename):
        relative = "detected/%s/%s" % (slug, filename)
        target = self.tmp / "media" / "detected" / slug
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

    def _media_url(self, relative):
        return reverse("detection:serve-media", args=[relative])

    def test_patch_cannot_redirect_ownership_to_another_slug(self):
        self.client.force_login(self.alice)
        victim_url = self._media_url(self.bob_path)

        denied_before = self.client.get(victim_url)
        self.assertEqual(denied_before.status_code, 404)

        self.client.patch(
            "/api/detections/%d/" % self.alice_row.id,
            {"image_path": "detected/%s/" % BOB_SLUG},
            content_type="application/json",
        )

        denied_after = self.client.get(victim_url)
        self.assertEqual(denied_after.status_code, 404)

        self.alice_row.refresh_from_db()
        self.assertEqual(self.alice_row.image_path, self.alice_path)

    def test_write_methods_are_not_accepted(self):
        self.client.force_login(self.alice)
        detail = "/api/detections/%d/" % self.alice_row.id
        payload = {"image_path": "detected/%s/" % BOB_SLUG}

        self.assertEqual(
            self.client.post(
                "/api/detections/", payload, content_type="application/json"
            ).status_code,
            405,
        )
        self.assertEqual(
            self.client.put(detail, payload, content_type="application/json").status_code,
            405,
        )
        self.assertEqual(
            self.client.patch(detail, payload, content_type="application/json").status_code,
            405,
        )
        self.assertEqual(self.client.delete(detail).status_code, 405)

    def test_read_methods_still_work(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get("/api/detections/").status_code, 200)
        self.assertEqual(
            self.client.get("/api/detections/%d/" % self.alice_row.id).status_code, 200
        )
