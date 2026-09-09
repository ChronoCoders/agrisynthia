import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_VARS = (
    "DATABASE_NAME",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_HOST",
    "DATABASE_PORT",
)

CHILD_SOURCE = """
import json
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agrisynthia.settings")

try:
    import django

    django.setup()
except BaseException as exc:
    result = {
        "error": type(exc).__module__ + "." + type(exc).__name__,
        "message": str(exc),
    }
else:
    from django.conf import settings

    default = settings.DATABASES["default"]
    result = {"engine": default["ENGINE"], "port": str(default.get("PORT", ""))}

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(result, handle)
"""


def load_settings(environment, **database_vars):
    env = dict(os.environ)
    for name in DATABASE_VARS:
        env.pop(name, None)
    env["DJANGO_ENVIRONMENT"] = environment
    env["DJANGO_SETTINGS_MODULE"] = "agrisynthia.settings"
    env["PYTHONPATH"] = str(BASE_DIR)
    # Pinned so the engine assertions do not depend on the host having GDAL.
    env["GEODJANGO_ENABLED"] = "False"
    # Both are demanded by validate_environment before DATABASES is reached.
    env["DJANGO_SECRET_KEY"] = "not-a-real-key-only-for-this-subprocess"
    env["DJANGO_ALLOWED_HOSTS"] = "localhost,127.0.0.1"
    env.update(database_vars)

    work_dir = Path(tempfile.mkdtemp())
    try:
        script = work_dir / "probe.py"
        script.write_text(CHILD_SOURCE, encoding="utf-8")
        result_path = work_dir / "result.json"
        completed = subprocess.run(
            [sys.executable, str(script), str(result_path)],
            cwd=str(BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
        )
        if not result_path.exists():
            raise AssertionError(
                "settings probe did not report a result, exit=%s stderr=%s"
                % (completed.returncode, completed.stderr[-2000:])
            )
        return json.loads(result_path.read_text(encoding="utf-8"))
    finally:
        for leftover in sorted(work_dir.glob("*")):
            leftover.unlink()
        work_dir.rmdir()


class DatabaseConfigurationContractTests(SimpleTestCase):
    def setUp(self):
        # The absent cases only mean what they say while .env leaves these unset,
        # because settings.py calls load_dotenv before reading them.
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            body = env_file.read_text(encoding="utf-8", errors="replace")
            for line in body.splitlines():
                name = line.split("=", 1)[0].strip()
                self.assertNotIn(
                    name,
                    DATABASE_VARS,
                    ".env defines %s, so the absent cases are not absent" % name,
                )

    def assertRefused(self, result):
        self.assertEqual(result.get("error"), "django.core.exceptions.ImproperlyConfigured")

    def test_development_without_database_config_uses_sqlite(self):
        result = load_settings("development")
        self.assertIsNone(result.get("error"))
        self.assertTrue(result["engine"].endswith("sqlite3"), result["engine"])

    def test_test_environment_without_database_config_uses_sqlite(self):
        result = load_settings("test")
        self.assertIsNone(result.get("error"))
        self.assertTrue(result["engine"].endswith("sqlite3"), result["engine"])

    def test_production_missing_name_is_refused(self):
        result = load_settings(
            "production",
            DATABASE_USER="agri",
            DATABASE_PASSWORD="secret",
            DATABASE_HOST="db.internal",
        )
        self.assertRefused(result)
        self.assertIn("DATABASE_NAME", result["message"])

    def test_production_missing_password_is_refused(self):
        result = load_settings(
            "production",
            DATABASE_NAME="agrisynthia",
            DATABASE_USER="agri",
            DATABASE_HOST="db.internal",
        )
        self.assertRefused(result)
        self.assertIn("DATABASE_PASSWORD", result["message"])

    def test_staging_missing_host_is_refused(self):
        result = load_settings(
            "staging",
            DATABASE_NAME="agrisynthia",
            DATABASE_USER="agri",
            DATABASE_PASSWORD="secret",
        )
        self.assertRefused(result)
        self.assertIn("DATABASE_HOST", result["message"])

    def test_unrecognised_environment_missing_user_is_refused(self):
        result = load_settings(
            "prod",
            DATABASE_NAME="agrisynthia",
            DATABASE_PASSWORD="secret",
            DATABASE_HOST="db.internal",
        )
        self.assertRefused(result)
        self.assertIn("DATABASE_USER", result["message"])

    def test_empty_password_is_reported_as_empty_not_missing(self):
        result = load_settings(
            "production",
            DATABASE_NAME="agrisynthia",
            DATABASE_USER="agri",
            DATABASE_PASSWORD="",
            DATABASE_HOST="db.internal",
        )
        self.assertRefused(result)
        self.assertIn("DATABASE_PASSWORD", result["message"])
        self.assertIn("empty", result["message"].lower())

    def test_absent_variable_is_not_reported_as_empty(self):
        result = load_settings(
            "production",
            DATABASE_USER="agri",
            DATABASE_PASSWORD="secret",
            DATABASE_HOST="db.internal",
        )
        self.assertRefused(result)
        self.assertNotIn("empty", result["message"].lower())

    def test_complete_production_config_selects_postgresql(self):
        result = load_settings(
            "production",
            DATABASE_NAME="agrisynthia",
            DATABASE_USER="agri",
            DATABASE_PASSWORD="secret",
            DATABASE_HOST="db.internal",
        )
        self.assertIsNone(result.get("error"))
        self.assertTrue(result["engine"].endswith("postgresql"), result["engine"])
        self.assertEqual(result["port"], "5432")
