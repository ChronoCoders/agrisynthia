"""
Test-specific Django settings.
Overrides production settings for testing.
"""
import os

# settings.py treats an absent DJANGO_ENVIRONMENT as production, so the test
# settings name the environment before importing them.
os.environ.setdefault("DJANGO_ENVIRONMENT", "test")

from .settings import *  # noqa: E402

# OVERRIDE CACHE TO USE DUMMY BACKEND
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    },
    # The alias must exist or every rate limited view raises here. Dummy keeps
    # the suite's existing behaviour; tests that need a live limiter override it.
    "ratelimit": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    },
}

# DISABLE CELERY FOR TESTS
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# FASTER PASSWORD HASHING FOR TESTS
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# DISABLE DEBUG TOOLBAR IN TESTS
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: False,
}

# SUPPRESS LOGGING DURING TESTS
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        "": {
            "handlers": ["null"],
            "level": "CRITICAL",
        },
    },
}
