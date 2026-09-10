import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml
from django.test import Client, TestCase, override_settings

BASE_DIR = Path(__file__).resolve().parent.parent

REDIS_VARS = (
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_DB",
    "REDIS_PASSWORD",
    "REDIS_CACHE_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
)

# Every character that makes a URI ambiguous if it reaches the string unencoded.
NASTY_PASSWORD = "p@ss:w/rd#1%x"

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

    caches = settings.CACHES
    result = {
        "broker": settings.CELERY_BROKER_URL,
        "backend": settings.CELERY_RESULT_BACKEND,
        "cache_location": caches["default"]["LOCATION"],
        "cache_ignores": caches["default"].get("OPTIONS", {}).get("IGNORE_EXCEPTIONS"),
        "ratelimit_alias": getattr(settings, "RATELIMIT_USE_CACHE", None),
        "aliases": sorted(caches.keys()),
    }
    if "ratelimit" in caches:
        result["ratelimit_location"] = caches["ratelimit"]["LOCATION"]
        result["ratelimit_options"] = caches["ratelimit"].get("OPTIONS", {})
        result["ratelimit_ignores"] = result["ratelimit_options"].get(
            "IGNORE_EXCEPTIONS"
        )

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(result, handle)
"""


def _substitute(value, supplied):
    def repl(match):
        name, op, arg = match.group(1), match.group(2), match.group(3)
        if name in supplied:
            return supplied[name]
        if op == ":-":
            return arg
        if op == ":?":
            raise AssertionError("compose requires %s but the test supplied none" % name)
        return ""

    return re.sub(r"\$\{(\w+)(:-|:\?)?([^}]*)\}", repl, str(value))


def compose_environment(service, supplied):
    doc = yaml.safe_load((BASE_DIR / "docker-compose.yml").read_text(encoding="utf-8"))
    raw = doc["services"][service].get("environment") or {}
    if isinstance(raw, list):
        raw = dict(item.split("=", 1) for item in raw)
    return {key: _substitute(value, supplied) for key, value in raw.items()}


def load_settings(environment="production", **overrides):
    env = dict(os.environ)
    for name in REDIS_VARS:
        env.pop(name, None)
    env["DJANGO_ENVIRONMENT"] = environment
    env["DJANGO_SETTINGS_MODULE"] = "agrisynthia.settings"
    env["PYTHONPATH"] = str(BASE_DIR)
    env["GEODJANGO_ENABLED"] = "False"
    env["DJANGO_SECRET_KEY"] = "not-a-real-key-only-for-this-subprocess"
    env["DJANGO_ALLOWED_HOSTS"] = "localhost,127.0.0.1"
    env["DATABASE_NAME"] = "agrisynthia"
    env["DATABASE_USER"] = "agri"
    env["DATABASE_PASSWORD"] = "secret"
    env["DATABASE_HOST"] = "db.internal"
    env.update({k: v for k, v in overrides.items() if v is not None})

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


class RedisUrlConstructionTests(TestCase):
    def test_password_with_uri_significant_characters_resolves(self):
        result = load_settings(
            REDIS_HOST="redis", REDIS_PORT="6379", REDIS_PASSWORD=NASTY_PASSWORD
        )
        self.assertIsNone(result.get("error"), result.get("message"))
        for key in ("broker", "backend", "cache_location"):
            parts = urlsplit(result[key])
            self.assertEqual(parts.hostname, "redis", key)
            # urlsplit leaves userinfo percent encoded, so the round trip is
            # the real oracle: the URL must decode back to the exact secret.
            self.assertEqual(unquote(parts.password), NASTY_PASSWORD, key)

    def test_broker_and_backend_carry_credentials(self):
        result = load_settings(REDIS_HOST="redis", REDIS_PASSWORD="plain-secret")
        self.assertIsNone(result.get("error"), result.get("message"))
        self.assertEqual(unquote(urlsplit(result["broker"]).password), "plain-secret")
        self.assertEqual(unquote(urlsplit(result["backend"]).password), "plain-secret")

    def test_logical_databases_are_separated(self):
        result = load_settings(REDIS_HOST="redis", REDIS_PASSWORD="plain-secret")
        self.assertIsNone(result.get("error"), result.get("message"))
        broker_db = urlsplit(result["broker"]).path
        cache_db = urlsplit(result["cache_location"]).path
        limit_db = urlsplit(result["ratelimit_location"]).path
        self.assertEqual(len({broker_db, cache_db, limit_db}), 3)

    def test_production_without_redis_password_fails(self):
        result = load_settings(REDIS_HOST="redis", REDIS_PASSWORD="")
        self.assertEqual(
            result.get("error"), "django.core.exceptions.ImproperlyConfigured"
        )
        self.assertIn("REDIS_PASSWORD", result["message"])

    def test_development_without_redis_password_still_loads(self):
        result = load_settings(environment="development", REDIS_PASSWORD="")
        self.assertIsNone(result.get("error"), result.get("message"))


class ComposeEnvironmentTests(TestCase):
    def _resolved(self, service):
        supplied = {
            "REDIS_PASSWORD": NASTY_PASSWORD,
            "DATABASE_PASSWORD": "secret",
            "DJANGO_SECRET_KEY": "not-a-real-key-only-for-this-subprocess",
        }
        env = compose_environment(service, supplied)
        return load_settings(**env)

    def test_web_cache_resolves_to_the_redis_service_with_credentials(self):
        result = self._resolved("web")
        self.assertIsNone(result.get("error"), result.get("message"))
        parts = urlsplit(result["cache_location"])
        # The credential assertion is the discriminating one. A host check alone
        # passes locally because .env supplies REDIS_CACHE_URL while compose
        # does not, which is the false green shape this suite keeps hitting.
        self.assertNotIn(parts.hostname, ("localhost", "127.0.0.1"))
        self.assertEqual(unquote(parts.password), NASTY_PASSWORD)

    def test_worker_broker_resolves_with_credentials(self):
        result = self._resolved("celery_worker")
        self.assertIsNone(result.get("error"), result.get("message"))
        self.assertEqual(unquote(urlsplit(result["broker"]).password), NASTY_PASSWORD)
        self.assertEqual(unquote(urlsplit(result["backend"]).password), NASTY_PASSWORD)


class RateLimitCachePolicyTests(TestCase):
    def test_rate_limit_alias_is_separate_and_does_not_ignore_failures(self):
        result = load_settings(REDIS_HOST="redis", REDIS_PASSWORD="plain-secret")
        self.assertIsNone(result.get("error"), result.get("message"))
        self.assertIn("ratelimit", result["aliases"])
        self.assertEqual(result["ratelimit_alias"], "ratelimit")
        self.assertTrue(result["cache_ignores"])
        self.assertNotEqual(result.get("ratelimit_ignores"), True)

    def test_rate_limit_cache_failure_does_not_permit_the_request(self):
        # The alias options come from the real settings module, so restoring
        # fail-open there makes this test permit the request and fail.
        probe = load_settings(REDIS_HOST="redis", REDIS_PASSWORD="plain-secret")
        self.assertIsNone(probe.get("error"), probe.get("message"))
        options = dict(probe["ratelimit_options"])
        options["SOCKET_CONNECT_TIMEOUT"] = 1
        options["SOCKET_TIMEOUT"] = 1
        dead = {
            "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
            "ratelimit": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": "redis://127.0.0.1:6399/9",
                "OPTIONS": options,
            },
        }
        with override_settings(CACHES=dead, RATELIMIT_USE_CACHE="ratelimit"):
            client = Client(raise_request_exception=False)
            response = client.post("/accounts/register/", {})
            # Measured: a fully dead cache is refused either way, 403 when the
            # backend swallows the error and 500 when it does not, so 'not 200'
            # cannot tell the two policies apart. Pinning the propagated error
            # is what binds this test to the alias policy in settings.
            self.assertGreaterEqual(response.status_code, 500)
