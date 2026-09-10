import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent

FILESYSTEM = "django.core.files.storage.filesystem.FileSystemStorage"
DJANGO_STATIC = "django.contrib.staticfiles.storage.StaticFilesStorage"
PROJECT_STATIC = "agrisynthia.storage.IgnoreDuplicatesStaticFilesStorage"
# R2MediaStorage.__new__ returns an S3Boto3Storage, which django-storages 1.14
# resolves to this class, so the configured path is not the resolved one.
S3 = "storages.backends.s3.S3Storage"

# hasattr(settings, "STORAGES") is true even on the legacy settings, because
# Django populates it from them, and DEFAULT_FILE_STORAGE always reads back a
# global default. Neither can tell the two configurations apart. The count of
# RemovedInDjango warnings raised during setup can.
CHILD_SOURCE = """
import json
import os
import sys
import warnings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agrisynthia.settings")
caught = []
try:
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        import django

        django.setup()
        caught = [
            str(w.message) for w in seen if "RemovedInDjango" in type(w.message).__name__
        ]

    from django.contrib.staticfiles.storage import staticfiles_storage
    from django.core.files.storage import default_storage

    def path_of(obj):
        cls = obj.__class__
        return cls.__module__ + "." + cls.__name__

    result = {
        "default_class": path_of(default_storage),
        "static_class": path_of(staticfiles_storage),
        "deprecations": caught,
    }
except BaseException as exc:
    result = {
        "error": type(exc).__name__,
        "message": str(exc)[:400],
        "deprecations": caught,
    }

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(result, handle)
"""


def resolve_storage(environment, use_r2):
    env = dict(os.environ)
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "agrisynthia.settings",
            "PYTHONPATH": str(BASE_DIR),
            "DJANGO_ENVIRONMENT": environment,
            "GEODJANGO_ENABLED": "False",
            "DJANGO_SECRET_KEY": "not-a-real-key-only-for-this-subprocess",
            "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
            "DATABASE_NAME": "agrisynthia",
            "DATABASE_USER": "agri",
            "DATABASE_PASSWORD": "secret",
            "DATABASE_HOST": "db.internal",
            "REDIS_PASSWORD": "not-a-real-password-only-for-this-subprocess",
            "USE_R2": "True" if use_r2 else "False",
            "R2_ACCOUNT_ID": "account",
            "R2_BUCKET_NAME": "bucket",
            "R2_ACCESS_KEY_ID": "not-a-real-key",
            "R2_SECRET_ACCESS_KEY": "not-a-real-secret",
        }
    )

    work_dir = Path(tempfile.mkdtemp())
    try:
        script = work_dir / "probe.py"
        script.write_text(CHILD_SOURCE, encoding="utf-8")
        out = work_dir / "result.json"
        done = subprocess.run(
            [sys.executable, str(script), str(out)],
            cwd=str(BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
        )
        if not out.exists():
            raise AssertionError(
                "storage probe reported nothing, exit=%s stderr=%s"
                % (done.returncode, done.stderr[-2000:])
            )
        return json.loads(out.read_text(encoding="utf-8"))
    finally:
        for leftover in sorted(work_dir.glob("*")):
            leftover.unlink()
        work_dir.rmdir()


class StorageBackendContractTests(SimpleTestCase):
    def assertResolves(self, environment, use_r2, default_class, static_class):
        result = resolve_storage(environment, use_r2)
        self.assertIsNone(result.get("error"), result.get("message"))
        self.assertEqual(result["default_class"], default_class)
        self.assertEqual(result["static_class"], static_class)
        return result

    def test_development_without_r2_uses_local_backends(self):
        self.assertResolves("development", False, FILESYSTEM, DJANGO_STATIC)

    def test_development_with_r2_uses_s3_for_media_only(self):
        self.assertResolves("development", True, S3, DJANGO_STATIC)

    def test_production_without_r2_keeps_the_duplicate_tolerant_static_backend(self):
        self.assertResolves("production", False, FILESYSTEM, PROJECT_STATIC)

    def test_production_with_r2_uses_s3_and_the_project_static_backend(self):
        self.assertResolves("production", True, S3, PROJECT_STATIC)

    def test_no_removed_setting_is_used_in_any_combination(self):
        offenders = {}
        for environment in ("development", "production"):
            for use_r2 in (False, True):
                result = resolve_storage(environment, use_r2)
                self.assertIsNone(result.get("error"), result.get("message"))
                if result["deprecations"]:
                    offenders["%s/USE_R2=%s" % (environment, use_r2)] = result[
                        "deprecations"
                    ]
        self.assertEqual(offenders, {})
