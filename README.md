# Agrisynthia

Agricultural analysis platform for orchards. Counts fruit on trees from field and drone imagery using YOLOv7, tracks field health from drone orthophotos and Sentinel-2 satellite passes, estimates yield, and generates PDF and Excel reports.

The product interface is **Turkish first**. Source strings are Turkish and English is a translation, so a fresh install renders in Turkish without any translation catalog compiled.

## What it does

**Fruit detection.** Upload a photo of a tree, get a count. Six models: mandarin (`mandalina`), apple (`elma`), pear (`armut`), peach (`seftale`), pomegranate (`nar`), and tree counting (`agac`). Runs synchronously or as a background job with live progress over Server-Sent Events. Results cache in Redis keyed by image hash, so re-uploading the same photo is free.

**Drone mapping.** Upload orthophotos, or let NodeODM build one from raw flight images. Roughly 25 vegetation indices (NDVI, GLI, VARI, SAVI, EVI, NDRE and more) render as map layers. Stress zones and tree density come out as GeoJSON.

**Satellite monitoring.** Sentinel-2 NDVI pulled through the Earth Search STAC API, one reading per field per scene date, refreshed weekly. Email alerts fire when a field drops below a configured NDVI threshold.

**Yield and recommendations.** Detection counts, tree age, and NDVI feed a yield estimate. Stress zones turn into ranked agronomic actions.

**Reports.** PDF and Excel for detections and drone analyses, on demand or on a daily, weekly, or monthly email schedule.

**Accounts.** Registration, email verification, TOTP two-factor with backup codes, password reset, profile and notification settings.

**Public site.** Turkish marketing site with blog, pricing, KVKK and privacy pages, a newsletter signup, and a support chatbot backed by the Anthropic API. English is served under `/en/`.

## Requirements

- Docker 24+ and Docker Compose v2, or Python 3.10 for a local install
- NVIDIA GPU with CUDA 11.8+ for practical inference speed. The stack starts without one and falls back to CPU, which is very slow.
- NVIDIA Container Toolkit on the host, for the Docker path
- 8 GB+ GPU VRAM recommended
- About 3 GB of disk for model weights

## Quick start with Docker

```bash
git clone https://github.com/ChronoCoders/agrisynthia.git
cd agrisynthia
cp deploy/env.production.template .env    # or .env.example for a minimal set
```

`DATABASE_PASSWORD` is the only variable Compose refuses to start without. `DJANGO_SECRET_KEY` is enforced separately by Django at runtime, so set both:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Then:

```bash
docker compose up -d                                  # web, db, redis, worker, beat
docker compose --profile with-nginx up -d             # adds nginx on 80/443
docker compose --profile monitoring up -d             # adds prometheus, grafana, exporters
```

Place model weights before running inference. See [Model weights](#model-weights); the stack starts fine without them.

```bash
docker compose exec web python manage.py createsuperuser
```

Check it came up:

```
http://localhost:8000/health/     {"status": "ok", "version": "2.0.0", "database": "connected"}
http://localhost:8000/admin/
http://localhost:8000/docs/       Swagger UI (schema requires authentication)
```

For TLS in development, `bash scripts/generate-ssl.sh` writes a self-signed pair to `ssl/`. In production put real certificates at `ssl/cert.pem` and `ssl/key.pem`.

## Local install without Docker

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`torch` and `torchvision` are deliberately **not** in `requirements.txt`, because the Docker image inherits them from its base image. A local install needs them explicitly, matched to your CUDA version:

```bash
pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118
```

Then:

```bash
export DJANGO_ENVIRONMENT=development
export DJANGO_SECRET_KEY=dev-secret-key-not-for-production
export GEODJANGO_ENABLED=False        # see below

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

**`GEODJANGO_ENABLED` is a real decision, not boilerplate.** It defaults to `True`, which loads `django.contrib.gis` and requires GDAL and GEOS on the system. Without them, every management command fails with `Could not find the GDAL library`. Setting it to `False` swaps `Projects.field_polygon` from a PostGIS `PolygonField` to a plain `JSONField` and drops the spatial database backend, so a database created one way is not compatible with the other. Use `False` for local work without GDAL installed; use `True` in production against PostGIS.

Celery needs Redis even in development:

```bash
docker run -d -p 6379:6379 redis:7-alpine
celery -A agrisynthia worker -l info -Q detection,mapping,celery
```

The `-Q` flag is required. See [Background tasks](#background-tasks).

## Model weights

Weights are recorded in the database, not discovered on disk. `detection.models.ModelVersion` holds the path, version, active flag, and SHA-256 for each fruit type, and inference resolves the path from that row.

Place **all six** files, including `agac.pt` for tree counting, in `models/`:

```
models/mandalina.pt  models/elma.pt  models/armut.pt
models/seftale.pt    models/nar.pt   models/agac.pt
```

Then run, in this order:

```bash
python manage.py migrate                          # seeds one ModelVersion row per fruit type
python manage.py migrate_model_files              # moves flat .pt into models/<fruit>/v1/weights.pt
python manage.py verify_model_checksums --store   # records the SHA-256 of each file
```

**All three steps are required.** The seed migration always records the versioned path `models/<fruit>/v1/weights.pt`, so weights left in the flat layout are never found and inference fails with `Model weights not found`. `migrate_model_files` performs that move and is safe to re-run.

`MODEL_CHECKSUM_VERIFY` defaults to on outside development. Weights whose SHA-256 does not match the stored value are refused, and so are weights with **no** stored checksum, since there is nothing to verify against. That is why `--store` is not optional. To load without verification, set `MODEL_CHECKSUM_VERIFY=False`.

Activating a new `ModelVersion` evicts the in-process model cache automatically, so a version swap takes effect without a restart.

## Configuration

Every setting comes from environment variables, read from `.env` in the project root. **`.env.example` is the complete, authoritative list** and is kept in sync with the code. `deploy/env.production.template` is the same set annotated for a production host.

The variables that block startup or encode a decision:

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | none | Required outside development. Startup fails without it. |
| `DJANGO_ENVIRONMENT` | `development` | `production` enables SSL redirect, HSTS, secure cookies, and checksum verification. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Required in production. |
| `DATABASE_NAME` / `_USER` / `_PASSWORD` / `_HOST` / `_PORT` | none | There is no `DATABASE_URL`. If any of name, user, password, or host is missing the app **silently falls back to SQLite**, so verify the engine after deploying. |
| `GEODJANGO_ENABLED` | `True` | Changes the `field_polygon` column type and the database backend. See above. |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` / `REDIS_CACHE_URL` | localhost | There is no `REDIS_URL`. Broker and cache use separate logical databases. |
| `USE_R2` | `False` | Switches media storage to Cloudflare R2 with presigned URLs. |
| `MODEL_CHECKSUM_VERIFY` | on outside dev | Refuses unverified weights. |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | none | Without them, verification, password reset, and 2FA mail fail and only a warning is logged. |
| `ANTHROPIC_API_KEY` | none | Powers the marketing site chatbot. Blank disables the endpoint. |
| `SENTRY_DSN` | none | Blank disables error reporting. |
| `ODM_ENABLED` | `True` | Set `False` to skip NodeODM and use pre-processed orthophotos. |
| `RESULT_RETENTION_DAYS` | `30` | Age at which detection results and their media are deleted. |
| `GRAFANA_ADMIN_PASSWORD` | `agrisynthia` | Change it when running the monitoring profile. |

Verify the database engine is what you intended:

```bash
python manage.py shell -c "from django.db import connection; print(connection.settings_dict['ENGINE'])"
```

## Services

| Service | Port | Profile | Description |
|---|---|---|---|
| `web` | 127.0.0.1:8000 | default | Django and Gunicorn |
| `db` | 127.0.0.1:5432 | default | PostgreSQL 15 with PostGIS |
| `redis` | 127.0.0.1:6379 | default | Cache, Celery broker, rate limiting |
| `celery_worker` | none | default | Task worker |
| `celery_beat` | none | default | Periodic scheduler |
| `nginx` | 80, 443 | `with-nginx` | Reverse proxy and TLS |
| `prometheus` | 127.0.0.1:9090 | `monitoring` | Metrics |
| `grafana` | 127.0.0.1:3000 | `monitoring` | Dashboards |
| `redis_exporter` | none | `monitoring` | Redis metrics |
| `postgres_exporter` | none | `monitoring` | Postgres metrics |
| `celery_exporter` | none | `monitoring` | Celery metrics |

Everything except nginx binds to loopback, so nothing is reachable from outside the host without the nginx profile.

## Background tasks

Celery over Redis, with tasks routed across three queues:

| Queue | Tasks |
|---|---|
| `detection` | `detection.tasks.*` |
| `mapping` | `dron_map.tasks.*` |
| `celery` | `reports.tasks.*`, `website.tasks.*` |

**A worker started without `-Q` consumes only the default `celery` queue.** Detection and drone tasks then sit in Redis unconsumed: async detection never leaves `PENDING`, the progress stream hangs, and the ODM watchdog never runs. Always pass all three:

```bash
celery -A agrisynthia worker -l info -Q detection,mapping,celery
```

Run exactly one `celery beat` across the fleet. Two schedulers double every periodic task.

### Scheduled tasks

| Task | Interval | Purpose |
|---|---|---|
| `detection.tasks.check_model_health` | 24h | Alerts when mean confidence drops below 0.7 |
| `detection.tasks.cleanup_old_results` | 24h | Deletes results older than `RESULT_RETENTION_DAYS` |
| `dron_map.watchdog_stuck_odm_tasks` | 1h | Reaps hung NodeODM jobs |
| `dron_map.refresh_all_sentinel2_ndvi` | 7d | Pulls new Sentinel-2 scenes |
| `dron_map.send_ndvi_stress_alerts` | 7d | Emails fields below the stress threshold |
| `reports.tasks.send_scheduled_reports` | 1h | Dispatches due report schedules |
| `website.tasks.refresh_ndvi_hero` | 30d | Re-renders the homepage NDVI tile |

Manual invocation:

```bash
docker compose exec celery_worker celery -A agrisynthia call detection.tasks.check_model_health
docker compose exec celery_worker celery -A agrisynthia inspect active_queues
```

## API

Full schema at `/docs/` (Swagger) and `/redoc/`. **Every API endpoint requires authentication** via session cookie; only `/health/` is public. Anonymous callers are throttled to 10 requests per hour, authenticated to 100.

**Detections** `/api/detections/`

| Method | Path | Description |
|---|---|---|
| `GET` `POST` | `/api/detections/` | List and create |
| `GET` | `/api/detections/<id>/` | Retrieve |
| `GET` | `/api/detections/statistics/` | Aggregates |
| `GET` | `/api/detections/recent/` | Last 10 |
| `GET` | `/api/batches/` | Batch detections |
| `GET` | `/api/batches/<id>/summary/` | Batch summary |

**Projects and analysis** `/api/projects/`

| Method | Path | Description |
|---|---|---|
| `GET` `POST` | `/api/projects/` | List and create |
| `GET` | `/api/projects/<id>/summary/` | Project summary |
| `GET` | `/api/projects/<id>/density/` | Tree density grid, GeoJSON |
| `GET` | `/api/projects/<id>/stress-zones/` | NDVI stress zones, GeoJSON |
| `GET` | `/api/projects/<id>/decisions/` | Ranked agronomic recommendations |
| `GET` | `/api/projects/<id>/yield/` | Yield estimate |
| `GET` | `/api/projects/<id>/full-analysis/` | All of the above in one call |
| `GET` | `/api/projects/statistics/` | Aggregates |
| `GET` | `/api/projects/by_farm/` `by_state/` | Grouped listings |

**Detection UI** `/detection/`

| Method | Path | Description |
|---|---|---|
| `GET` `POST` | `/detection/` | Single image detection |
| `GET` `POST` | `/detection/mcti/` | Multi-image batch |
| `POST` | `/detection/async-detection/` | Queue a job, returns a task id |
| `GET` | `/detection/task-status/<id>/` | Poll job status |
| `GET` | `/detection/task-stream/<id>/` | Server-Sent Events progress stream |
| `GET` | `/detection/media/<path>` | Authenticated media proxy |
| `GET` | `/detection/system-monitoring/` | Resource dashboard |
| `POST` | `/detection/cache/invalidate/` | Clear prediction cache, staff only |

**Drone mapping** `/dron-map/`: `dashboard/`, `projects/`, `map/<id>/`, `overview/`, `yield/`, `projects/<id>/ndvi/`, `projects/<id>/odm-status/`

**Reports** `/reports/`: list, `request/detection/`, `request/drone/`, `download/<id>/`, `delete/<id>/`, `schedule/create/`, `schedule/<id>/toggle/`, `schedule/<id>/delete/`

**Accounts** `/accounts/`: `login/`, `logout/`, `register/`, `profile/`, `settings/`, `password-reset/`, `verify-email/<token>/`, `2fa/setup/`, `verify-2fa/`

**Public site**: `/` and `/en/`, with translated slugs (`/urun/` and `/en/product/`). Also `robots.txt`, `sitemap.xml`, `/health/`, `/metrics/`.

## Layout

| Path | Role |
|---|---|
| `agrisynthia/` | Settings, URLs, Celery app, vegetation indices, inference entry point |
| `detection/` | Detection models, views, tasks, and vendored YOLOv7 under `detection/yolo/` |
| `dron_map/` | Drone projects, ODM integration, Sentinel-2 ingest |
| `accounts/` | Registration, email verification, TOTP 2FA |
| `reports/` | PDF and Excel generation, scheduled email delivery |
| `website/` | Public marketing site, blog, chatbot |
| `spatial_analysis/` | Density grids and stress zones, plain Python |
| `decision_engine/` | Stress zones to recommendations, plain Python |
| `yield_prediction/` | Yield scoring, plain Python |
| `analysis_logger/` | Persists combined analysis runs, plain Python |
| `deploy/` | systemd units and production runbook |
| `monitoring/` | Prometheus config and Grafana dashboards |

The last four Python packages are not Django apps and are not in `INSTALLED_APPS`.

## Testing

```bash
pytest                                    # 165 tests
pytest detection/tests.py                 # one file
pytest -k "stress_zones"                  # by name
python manage.py test detection dron_map  # Django runner, 58 tests
```

Use pytest for full coverage. `spatial_analysis`, `decision_engine`, `yield_prediction`, and `analysis_logger` are not Django apps, so the Django test runner never discovers their tests.

Tests use `agrisynthia.test_settings`, which mocks Redis and runs Celery eagerly. They do not need a running broker. They do inherit the database configuration, so with `GEODJANGO_ENABLED=True` and no PostGIS available, set `GEODJANGO_ENABLED=False` first.

`detection/test_inference.py` runs real inference against real weights. Those tests skip when `models/mandalina/v1/weights.pt` is absent, so a checkout without weights stays green while a machine that can run inference still catches regressions.

## Translations

Turkish is the source language. Message ids are Turkish, so a fresh clone renders correctly in Turkish with nothing compiled. English lives at `locale/en/LC_MESSAGES/django.po` and is **complete**; the compiled `django.mo` is committed so production hosts do not need gettext at deploy time.

```bash
python manage.py makemessages -l en    # after changing templates or views
python manage.py compilemessages
```

Both need GNU gettext (`choco install gettext` on Windows, `apt install gettext` on Linux). A pre-commit hook recompiles `.mo` whenever a `.po` is staged. Enable it once per clone:

```bash
git config core.hooksPath hooks
```

## Deployment

`deploy/README.md` covers a bare metal install at `/opt/agrisynthia`: systemd units for web, worker, beat, and backups, plus the system packages and verification steps. For containers, use `docker-compose.yml` at the root. Do not mix the two on one host.

### Backups

Postgres dumps to Cloudflare R2 under the `backups/postgres/` prefix:

```bash
python scripts/backup_postgres.py backup            # dump, gzip, upload
python scripts/backup_postgres.py list              # newest first
python scripts/backup_postgres.py restore           # restore latest
python scripts/backup_postgres.py prune --days 30   # delete older than 30 days
```

Needs `pg_dump` and `psql` on `PATH` and R2 credentials in `.env`. Restore drops existing data and prompts for confirmation unless `-y` is passed. Schedule it with either the systemd timer in `deploy/systemd/` or a cron entry, never both.

### Logs

```bash
docker compose logs -f web
docker compose logs -f celery_worker
```

Files rotate at 10 MB in `logs/django.log` and `logs/django_errors.log`. The `detection` and `dron_map` loggers are set to WARNING by default.

### Updating

```bash
git pull origin main
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
```

## Security

- Never commit `.env`. It is gitignored and excluded from the Docker build context.
- All API endpoints require authentication. Only `/health/` is public.
- Media is served through an authenticated proxy using `X-Accel-Redirect`, or presigned R2 URLs when `USE_R2` is on. Direct `/media/` access is blocked at nginx.
- Model weights are refused unless their SHA-256 matches the recorded value.
- nginx enforces three rate limits: 10 req/s on `/api/`, 5 req/s on `/accounts/` and `/admin/`, 100 req/s elsewhere, plus 50 concurrent connections per IP. Django adds per-view limits on login, registration, 2FA, password reset, and uploads.
- Uploads are capped at 10 MB for detection images and 100 MB for drone imagery, and validated by magic bytes rather than file extension.
- CSP, HSTS, secure cookies, and SSL redirect activate automatically outside development.

## Load testing

```bash
pip install locust
export LOCUST_TEST_USERNAME=loadtest LOCUST_TEST_PASSWORD=...
locust -f scripts/locustfile.py --host https://staging.example.com
```

Three user classes at weights 6 / 2 / 3: browsing, uploading detections while watching the progress stream, and polling the REST API. Never point it at production; it enqueues Celery work on every iteration and holds streaming connections open. Drop a small JPEG at `scripts/_sample.jpg` first.

## License

Proprietary. Copyright (c) 2026 ChronoCoders. All rights reserved. Contact altug@bytus.io for licensing.
