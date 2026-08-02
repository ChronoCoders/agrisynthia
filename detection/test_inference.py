"""End to end regression tests for the YOLO inference path.

These exist because `predict()` raised RuntimeError on every call for
months without a single test noticing. The cause was `if det:` on the
(n, 6) tensor non_max_suppression returns, which raises for every n:
"no values is ambiguous" at n=0 and "more than one value is ambiguous"
at n>=1. Both branches are covered below, since a test that only fed an
image with detections would have missed the empty case and vice versa.

The tests need real weights, which are gitignored and roughly 300 MB, so
they skip when the file is absent rather than fail. That keeps a bare
checkout green while still catching the regression on any machine that
can actually run inference.
"""
import os
import shutil
import uuid

import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db

BASE_DIR = settings.BASE_DIR
WEIGHTS = os.path.join(BASE_DIR, "models", "mandalina", "v1", "weights.pt")

requires_weights = pytest.mark.skipif(
    not os.path.exists(WEIGHTS),
    reason=f"model weights not present at {WEIGHTS}",
)

try:
    import cv2
    import numpy as np
    import torch  # noqa: F401

    _DEPS = True
except Exception:  # pragma: no cover
    _DEPS = False

requires_deps = pytest.mark.skipif(
    not _DEPS, reason="torch, cv2 or numpy not installed"
)


def _write_image(path, blobs):
    """Green canopy with `blobs` orange circles on it."""
    img = np.zeros((640, 640, 3), np.uint8)
    img[:, :] = (40, 90, 40)
    rng = np.random.default_rng(0)
    for _ in range(blobs):
        x, y = rng.integers(40, 600, 2)
        r = int(rng.integers(12, 22))
        cv2.circle(img, (int(x), int(y)), r, (30, 140, 235), -1)
    cv2.imwrite(str(path), img)
    return str(path)


@pytest.fixture(scope="module")
def active_model(django_db_setup, django_db_blocker):
    """Point an active ModelVersion at the real weights on disk.

    Module scoped so the 300 MB load happens once. pytest.ini runs with
    --nomigrations, so the seed migration never runs and the row has to be
    created here. The version string is unique per run to avoid colliding
    with the process local cache in predict_tree.
    """
    if not os.path.exists(WEIGHTS) or not _DEPS:
        yield None
        return

    from detection.models import ModelVersion
    from agrisynthia import predict_tree

    version = f"test-{uuid.uuid4().hex[:8]}"
    with django_db_blocker.unblock():
        mv = ModelVersion.objects.create(
            fruit_type="mandalina",
            version=version,
            weights_path="models/mandalina/v1/weights.pt",
            is_active=True,
            checksum_sha256="",
        )
        yield mv
        mv.delete()

    predict_tree.evict_model_cache("mandalina")


@pytest.fixture
def output_cleanup():
    """Remove whatever predict() wrote under static/detected/."""
    created = []
    yield created
    for uid in created:
        shutil.rmtree(os.path.join(BASE_DIR, "static", "detected", uid), ignore_errors=True)


@requires_deps
@requires_weights
def test_predict_returns_detections(active_model, tmp_path, output_cleanup, settings):
    """The non-empty branch. This is the case `if det:` broke."""
    settings.MODEL_CHECKSUM_VERIFY = False
    from agrisynthia import predict_tree

    image = _write_image(tmp_path / "orchard.jpg", blobs=25)
    count, uid, confidence, boxes = predict_tree.predict(
        "mandalina", image, return_boxes=True
    )
    output_cleanup.append(uid)

    detected = int(count.decode())
    assert detected > 0, "expected detections on a synthetic orchard frame"
    assert len(boxes) == detected, "box count must match reported count"
    assert 0.0 < confidence <= 1.0
    assert all({"x", "y"} == set(b) for b in boxes)
    assert all(0 <= b["x"] <= 640 and 0 <= b["y"] <= 640 for b in boxes)

    written = os.path.join(BASE_DIR, "static", "detected", uid)
    assert os.path.isdir(written), "annotated output directory not written"
    assert os.listdir(written), "annotated output directory is empty"


@requires_deps
@requires_weights
def test_predict_handles_zero_detections(active_model, tmp_path, output_cleanup, settings):
    """The empty branch. `if det:` also raised when nothing was found."""
    settings.MODEL_CHECKSUM_VERIFY = False
    from agrisynthia import predict_tree

    image = _write_image(tmp_path / "bare.jpg", blobs=0)
    count, uid, confidence, boxes = predict_tree.predict(
        "mandalina", image, return_boxes=True
    )
    output_cleanup.append(uid)

    assert int(count.decode()) == 0
    assert boxes == []
    assert confidence == 0.0


@requires_deps
@requires_weights
def test_predict_without_boxes_returns_three_tuple(active_model, tmp_path, output_cleanup, settings):
    """return_boxes=False is the shape the sync view consumes."""
    settings.MODEL_CHECKSUM_VERIFY = False
    from agrisynthia import predict_tree

    image = _write_image(tmp_path / "orchard.jpg", blobs=25)
    result = predict_tree.predict("mandalina", image)
    assert len(result) == 3
    count, uid, confidence = result
    output_cleanup.append(uid)
    assert int(count.decode()) > 0


@requires_deps
@requires_weights
def test_get_model_is_cached(active_model, settings):
    """Second load must come from the process cache, not disk."""
    settings.MODEL_CHECKSUM_VERIFY = False
    from agrisynthia import predict_tree

    first = predict_tree.get_model("mandalina")
    second = predict_tree.get_model("mandalina")
    assert first is second


@pytest.mark.django_db
def test_get_model_refuses_when_checksum_missing(settings):
    """Verification on with nothing to verify must fail closed.

    0012_seed_model_versions leaves checksum_sha256 empty when the weights
    were absent at migrate time, which is the normal fresh install. This
    used to warn and load anyway, meaning MODEL_CHECKSUM_VERIFY could be
    on and checking nothing. No weights needed: the guard runs before the
    file is opened.
    """
    from detection.models import ModelVersion
    from agrisynthia import predict_tree

    settings.MODEL_CHECKSUM_VERIFY = True
    version = f"test-{uuid.uuid4().hex[:8]}"
    ModelVersion.objects.create(
        fruit_type="armut",
        version=version,
        weights_path="models/armut/v1/weights.pt",
        is_active=True,
        checksum_sha256="",
    )
    predict_tree.evict_model_cache("armut")

    if not os.path.exists(os.path.join(BASE_DIR, "models", "armut", "v1", "weights.pt")):
        pytest.skip("armut weights absent; FileNotFoundError would mask the checksum guard")

    with pytest.raises(RuntimeError, match="no stored checksum"):
        predict_tree.get_model("armut")

    predict_tree.evict_model_cache("armut")


@pytest.mark.django_db
def test_get_model_reports_missing_weights_clearly():
    """A fresh install with weights in the flat layout lands here."""
    from detection.models import ModelVersion
    from agrisynthia import predict_tree

    version = f"test-{uuid.uuid4().hex[:8]}"
    ModelVersion.objects.create(
        fruit_type="nar",
        version=version,
        weights_path="models/nar/v1/does-not-exist.pt",
        is_active=True,
        checksum_sha256="",
    )
    predict_tree.evict_model_cache("nar")

    with pytest.raises(FileNotFoundError, match="migrate_model_files"):
        predict_tree.get_model("nar")

    predict_tree.evict_model_cache("nar")


@pytest.mark.django_db
def test_get_model_without_active_version_raises_lookup():
    from agrisynthia import predict_tree

    predict_tree.evict_model_cache("seftale")
    with pytest.raises(LookupError, match="No active ModelVersion"):
        predict_tree.get_model("seftale")
