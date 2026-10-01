import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import TestCase

BASE_DIR = Path(__file__).resolve().parent.parent

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

    result = {"model": getattr(settings, "ANTHROPIC_MODEL", None)}

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(result, handle)
"""


def load_settings(environment, model):
    """Import the real settings module in a subprocess and report what happened.

    The guard runs at import time, so only a separate interpreter can observe
    both the raising and the non raising case in one suite.
    """
    env = dict(os.environ)
    for name in ("DJANGO_ENVIRONMENT", "ANTHROPIC_MODEL"):
        env.pop(name, None)
    if environment is not None:
        env["DJANGO_ENVIRONMENT"] = environment
    if model is not None:
        env["ANTHROPIC_MODEL"] = model
    env["DJANGO_SETTINGS_MODULE"] = "agrisynthia.settings"
    env["PYTHONPATH"] = str(BASE_DIR)
    env["GEODJANGO_ENABLED"] = "False"
    env["DJANGO_SECRET_KEY"] = "not-a-real-key-only-for-this-subprocess"
    env["DJANGO_ALLOWED_HOSTS"] = "localhost,127.0.0.1"
    env["DATABASE_NAME"] = "agrisynthia"
    env["DATABASE_USER"] = "agri"
    env["DATABASE_PASSWORD"] = "secret"
    env["DATABASE_HOST"] = "db.internal"
    env["REDIS_PASSWORD"] = "secret"

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
                "settings probe reported nothing, exit=%s stderr=%s"
                % (done.returncode, done.stderr[-2000:])
            )
        return json.loads(out.read_text(encoding="utf-8"))
    finally:
        for leftover in sorted(work_dir.glob("*")):
            leftover.unlink()
        work_dir.rmdir()


IMPROPERLY_CONFIGURED = "django.core.exceptions.ImproperlyConfigured"


class ChatbotModelConfigTests(TestCase):
    def test_production_without_the_model_refuses_to_start(self):
        result = load_settings("production", None)
        self.assertEqual(result.get("error"), IMPROPERLY_CONFIGURED)
        self.assertIn("ANTHROPIC_MODEL", result["message"])

    def test_absent_environment_name_without_the_model_refuses_to_start(self):
        # ENVIRONMENT defaults an absent name to development, which would exempt
        # it. The guard reads the variable raw so that cannot happen.
        result = load_settings(None, None)
        self.assertEqual(result.get("error"), IMPROPERLY_CONFIGURED)
        self.assertIn("ANTHROPIC_MODEL", result["message"])

    def test_unrecognised_environment_name_without_the_model_refuses_to_start(self):
        result = load_settings("staging", None)
        self.assertEqual(result.get("error"), IMPROPERLY_CONFIGURED)

    def test_test_environment_without_the_model_starts(self):
        result = load_settings("test", None)
        self.assertIsNone(result.get("error"), result.get("message"))
        self.assertIsNone(result["model"])

    def test_development_environment_without_the_model_starts(self):
        result = load_settings("development", None)
        self.assertIsNone(result.get("error"), result.get("message"))

    def test_production_with_the_model_starts_and_carries_the_value(self):
        # Without this the suite would also pass if the guard always raised.
        result = load_settings("production", "a-model-identifier")
        self.assertIsNone(result.get("error"), result.get("message"))
        self.assertEqual(result["model"], "a-model-identifier")

    def test_production_with_a_blank_model_refuses_to_start(self):
        result = load_settings("production", "")
        self.assertEqual(result.get("error"), IMPROPERLY_CONFIGURED)
