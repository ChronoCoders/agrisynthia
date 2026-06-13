"""
Locust load profile for Agrisynthia staging.

Run against a staging host that mirrors prod (real Postgres, Redis, Celery worker,
nginx). Running against `python manage.py runserver` measures Django's single-threaded
limits, not the real system.

Usage:
    locust -f scripts/locustfile.py --host https://staging.example.com
        # → web UI at http://localhost:8089

Headless example:
    locust -f scripts/locustfile.py --host https://staging.example.com \
        --users 50 --spawn-rate 5 --run-time 5m --headless --csv reports/load

Three user classes are defined; pick one per run with --tags, or mix with
weight=N annotations.

Required env vars:
    LOCUST_TEST_USERNAME    valid login on the target environment
    LOCUST_TEST_PASSWORD    matching password
    LOCUST_FRUIT            optional, default "mandalina"

Don't ever point this at production. The detection endpoint enqueues Celery work
and the SSE endpoint holds connections open for ~10 minutes.
"""
import os
import random
import time
from pathlib import Path

from locust import HttpUser, task, between, events

USERNAME = os.environ.get("LOCUST_TEST_USERNAME", "loadtest")
PASSWORD = os.environ.get("LOCUST_TEST_PASSWORD", "")
FRUIT = os.environ.get("LOCUST_FRUIT", "mandalina")

SAMPLE_IMAGE = Path(__file__).parent / "_sample.jpg"


@events.test_start.add_listener
def _check_env(environment, **kw):
    if not PASSWORD:
        raise RuntimeError(
            "LOCUST_TEST_PASSWORD is unset. Create a real account on staging and "
            "export LOCUST_TEST_USERNAME / LOCUST_TEST_PASSWORD before running."
        )
    if not SAMPLE_IMAGE.exists():
        raise RuntimeError(
            f"{SAMPLE_IMAGE} not found. Drop any small JPEG there for upload tests."
        )


class AuthenticatedUser(HttpUser):
    """Base class — performs login + CSRF handling once per simulated user."""
    abstract = True
    wait_time = between(2, 6)

    def on_start(self):
        resp = self.client.get("/accounts/login/")
        token = resp.cookies.get("csrftoken", "")
        login_resp = self.client.post(
            "/accounts/login/",
            data={
                "username": USERNAME,
                "password": PASSWORD,
                "csrfmiddlewaretoken": token,
            },
            headers={"Referer": f"{self.host}/accounts/login/"},
            name="POST /accounts/login/",
        )
        if "_auth_user_id" not in self.client.cookies.get_dict().get("sessionid", "") and login_resp.status_code not in (200, 302):
            login_resp.failure(f"Login failed: HTTP {login_resp.status_code}")


class BrowsingUser(AuthenticatedUser):
    """Mimics a logged-in user clicking around the dashboard. Cheap requests."""
    weight = 6

    @task(5)
    def dashboard(self):
        self.client.get("/dron-map/dashboard/", name="GET /dron-map/dashboard/")

    @task(3)
    def main_form(self):
        self.client.get("/detection/", name="GET /detection/")

    @task(2)
    def projects_list(self):
        self.client.get("/dron-map/projects/", name="GET /dron-map/projects/")

    @task(2)
    def reports_list(self):
        self.client.get("/reports/", name="GET /reports/")

    @task(1)
    def settings(self):
        self.client.get("/accounts/settings/", name="GET /accounts/settings/")

    @task(1)
    def system_monitoring(self):
        self.client.get("/detection/system-monitoring/", name="GET /detection/system-monitoring/")


class DetectionUploadUser(AuthenticatedUser):
    """Uploads an image to the async detection endpoint and watches the SSE stream
    until completion. This is the heavy path: a real Celery worker has to load the
    model and run inference per upload."""
    weight = 2

    @task
    def async_detection(self):
        csrftoken = self.client.cookies.get("csrftoken", "")
        with open(SAMPLE_IMAGE, "rb") as fh:
            resp = self.client.post(
                "/detection/async-detection/",
                data={
                    "meyve_grubu": FRUIT,
                    "agac_sayisi": "100",
                    "agac_yasi": "5",
                    "csrfmiddlewaretoken": csrftoken,
                },
                files={"file": ("sample.jpg", fh, "image/jpeg")},
                headers={"Referer": f"{self.host}/detection/"},
                name="POST /detection/async-detection/",
            )
        if resp.status_code != 202:
            return

        body = resp.json()
        stream_url = body.get("stream_url")
        if not stream_url:
            return

        started = time.time()
        with self.client.get(
            stream_url,
            stream=True,
            name="SSE /detection/task-stream/<id>/",
        ) as stream:
            for raw in stream.iter_lines(decode_unicode=False):
                if not raw:
                    continue
                if b'"status": "done"' in raw:
                    break
                if time.time() - started > 300:
                    stream.failure("SSE timeout >5min")
                    break


class ApiPollingUser(AuthenticatedUser):
    """Hits read-mostly REST endpoints — proxies the kind of traffic a mobile or
    dashboard client makes."""
    weight = 3

    @task(4)
    def detection_list(self):
        self.client.get("/api/detections/?ordering=-created_at", name="GET /api/detections/")

    @task(2)
    def detection_statistics(self):
        self.client.get("/api/detections/statistics/", name="GET /api/detections/statistics/")

    @task(2)
    def projects_list(self):
        self.client.get("/api/projects/", name="GET /api/projects/")

    @task(1)
    def health(self):
        self.client.get("/health/", name="GET /health/")
