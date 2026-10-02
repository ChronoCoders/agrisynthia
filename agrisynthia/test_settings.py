"""
Test-specific Django settings.
Overrides production settings for testing.
"""
import os

# ANTHROPIC_MODEL is required unless DJANGO_ENVIRONMENT names development or
# test, and an absent name counts as production. Naming the environment here
# instead would push validate_environment into its production branch and demand
# DJANGO_SECRET_KEY, so the suite supplies a placeholder identifier and leaves
# the environment alone. The suite never calls the chatbot, and
# test_chatbot_model_config.py exercises the guard itself in subprocesses.
os.environ.setdefault("ANTHROPIC_MODEL", "placeholder-for-tests")

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
