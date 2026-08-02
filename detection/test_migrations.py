"""Tests for the data migration that seeds ModelVersion rows.

pytest.ini runs with --nomigrations, so RunPython(seed_model_versions)
never executes during the suite and this code had no automated cover at
all. That matters more than it sounds: the migration decides where every
weights file is expected to live, and its least obvious branch is the
reason `manage.py migrate_model_files` is mandatory rather than a
convenience.

The function is called directly with a stub `apps` rather than run
through the migration framework, which keeps it working under
--nomigrations without a second pytest invocation.

Why substituting the live model for a historical one is safe here:
apps.get_model() in a real migration returns the model as it existed at
0012, not the current class. seed_model_versions touches exactly
fruit_type, version, weights_path, framework, is_active,
checksum_sha256, and notes. All seven exist both at 0012 and now, with
the same types, so the live model is a faithful stand-in. This was
checked, not assumed. If a later migration changes any of those seven
fields, this substitution stops being valid and these tests need to move
to a real historical model via django_test_migrations or --migrations.
"""
import hashlib
import importlib

import pytest

from detection.models import ModelVersion

pytestmark = pytest.mark.django_db

MIGRATION = "detection.migrations.0012_seed_model_versions"
FRUIT_TYPES = ["mandalina", "elma", "armut", "seftale", "nar", "agac"]


class _StubApps:
    """Minimal stand-in for the migration's `apps` registry."""

    def get_model(self, app_label, model_name):
        assert (app_label, model_name) == ("detection", "ModelVersion")
        return ModelVersion


class _Ancestor:
    """Returns `root` after exactly three `.parent` lookups.

    The migration computes its project root as
    Path(__file__).resolve().parent.parent.parent, walking up from
    migrations/ to detection/ to the root. Patching the module's Path
    with this lets a test point that root at a temporary directory.
    """

    def __init__(self, root, remaining):
        self._root = root
        self._remaining = remaining

    def resolve(self):
        return self

    @property
    def parent(self):
        if self._remaining <= 1:
            return self._root
        return _Ancestor(self._root, self._remaining - 1)


@pytest.fixture
def seed(monkeypatch):
    """Run seed_model_versions with the project root pointed at tmp_path."""
    mod = importlib.import_module(MIGRATION)

    def _run(root):
        monkeypatch.setattr(mod, "Path", lambda *a, **k: _Ancestor(root, 3))
        mod.seed_model_versions(_StubApps(), None)

    return _run


def _write(path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def test_seeds_every_fruit_type_when_no_weights_present(seed, tmp_path):
    """The fresh install case: nothing on disk yet."""
    seed(tmp_path)

    rows = {mv.fruit_type: mv for mv in ModelVersion.objects.all()}
    assert set(rows) == set(FRUIT_TYPES), "one row per fruit type, including agac"
    assert len(rows) == 6

    for fruit_type, mv in rows.items():
        assert mv.version == "v1"
        assert mv.weights_path == f"models/{fruit_type}/v1/weights.pt"
        assert mv.framework == "YOLOv7"
        assert mv.checksum_sha256 == "", "nothing on disk to hash"
        # ModelVersion.clean() enforces a single active row per fruit type.
        # A seed that produced an inactive row, or two active ones, would
        # surface much later as a confusing LookupError at inference.
        assert mv.is_active is True

    for fruit_type in FRUIT_TYPES:
        assert (
            ModelVersion.objects.filter(fruit_type=fruit_type, is_active=True).count() == 1
        )


def test_flat_weights_hash_a_file_the_row_does_not_point_at(seed, tmp_path):
    """The behaviour that makes migrate_model_files mandatory.

    With weights in the flat layout the README used to document, the
    migration hashes models/<fruit>.pt but still records the versioned
    models/<fruit>/v1/weights.pt as weights_path. The result is a row
    whose checksum belongs to a file at a different path from the one it
    points at, and whose recorded path does not exist at all. Inference
    then fails with FileNotFoundError until migrate_model_files runs.

    Asserting only that the checksum is non-empty would pass on a version
    that hashed the wrong file, so this pins the exact digest.
    """
    flat = tmp_path / "models" / "mandalina.pt"
    flat_digest = _write(flat, b"flat-layout-weights-payload")

    seed(tmp_path)

    mv = ModelVersion.objects.get(fruit_type="mandalina")

    # The row points at the versioned location...
    assert mv.weights_path == "models/mandalina/v1/weights.pt"
    versioned = tmp_path / "models" / "mandalina" / "v1" / "weights.pt"
    assert not versioned.exists(), "the recorded path does not exist yet"

    # ...while the checksum is of the flat file somewhere else entirely.
    assert mv.checksum_sha256 != ""
    assert mv.checksum_sha256 == flat_digest
    assert flat.exists()


def test_versioned_weights_hash_the_path_the_row_points_at(seed, tmp_path):
    """The post-migrate_model_files state: path and checksum agree."""
    versioned = tmp_path / "models" / "elma" / "v1" / "weights.pt"
    digest = _write(versioned, b"versioned-layout-weights-payload")

    seed(tmp_path)

    mv = ModelVersion.objects.get(fruit_type="elma")
    assert mv.weights_path == "models/elma/v1/weights.pt"
    assert (tmp_path / mv.weights_path).exists()
    assert mv.checksum_sha256 == digest


def test_versioned_layout_wins_when_both_exist(seed, tmp_path):
    """Branch order: versioned is checked before flat, so it takes priority.

    This is the state right after migrate_model_files if a stale flat copy
    was left behind. Hashing the stale file would store a checksum that
    fails verification against the file actually loaded.
    """
    flat_digest = _write(tmp_path / "models" / "nar.pt", b"stale-flat-copy")
    versioned_digest = _write(
        tmp_path / "models" / "nar" / "v1" / "weights.pt", b"current-versioned-copy"
    )
    assert flat_digest != versioned_digest

    seed(tmp_path)

    mv = ModelVersion.objects.get(fruit_type="nar")
    assert mv.checksum_sha256 == versioned_digest
    assert mv.checksum_sha256 != flat_digest


def test_rerun_does_not_duplicate_or_overwrite(seed, tmp_path):
    """get_or_create means a second run is a no-op, not a re-seed."""
    seed(tmp_path)
    ModelVersion.objects.filter(fruit_type="armut").update(
        checksum_sha256="deadbeef", notes="edited by hand"
    )

    seed(tmp_path)

    assert ModelVersion.objects.count() == 6
    mv = ModelVersion.objects.get(fruit_type="armut")
    assert mv.checksum_sha256 == "deadbeef", "existing rows are left alone"
    assert mv.notes == "edited by hand"


def test_unseed_removes_the_v1_rows(seed, tmp_path):
    """The reverse operation, so a rollback is not left half applied."""
    mod = importlib.import_module(MIGRATION)
    seed(tmp_path)
    assert ModelVersion.objects.count() == 6

    mod.unseed_model_versions(_StubApps(), None)
    assert ModelVersion.objects.filter(version="v1").count() == 0
