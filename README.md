# FarmVision

AI-powered fruit detection and agricultural analysis platform. Detects fruit on trees from drone and field imagery using YOLO-based models, estimates yield, and generates field health reports from multispectral orthophotos.

## Features

- Fruit detection (mandarin, apple, pear, peach, pomegranate, and tree counting) with confidence scoring
- Batch multi-image detection
- Drone orthophoto processing with vegetation index analysis (NDVI, EVI, SAVI and 20+ others)
- Yield prediction and decision engine recommendations
- Async task processing via Celery
- REST API with OpenAPI documentation
- System monitoring dashboard
- Comprehensive test suite

## Requirements

- Docker 24+ and Docker Compose v2
- NVIDIA GPU with CUDA 11.8+ (required for inference)
- NVIDIA Container Toolkit installed on host
- 8GB+ GPU VRAM recommended
- SSL certificate (for production)

## Quick Start (Docker)

**1. Clone and configure environment**
```bash
git clone https://github.com/ChronoCoders/farmvision.git
cd farmvision
cp .env.example .env
```

Edit `.env` and fill in all required values. At minimum:
DJANGO_SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DATABASE_PASSWORD=<strong password>

**2. Generate SSL certificate**

For development (self-signed):
```bash
bash scripts/generate-ssl.sh
```

For production, place your certificate files at:
ssl/cert.pem
ssl/key.pem

**3. Start services**
```bash
# Without nginx (direct gunicorn access on port 8000)
docker compose up -d

# With nginx (recommended for production, ports 80/443)
docker compose --profile with-nginx up -d
```

**4. Create superuser**
```bash
docker compose exec web python manage.py createsuperuser
```

**5. Verify**
http://localhost:8000/health/     → {"status": "ok", "database": "connected"}
http://localhost:8000/admin/      → Django admin
http://localhost:8000/docs/       → Swagger UI

## Development & Testing

**Running Tests**

The project includes a comprehensive test suite. To run all tests without external dependencies (Redis/Celery mocked):

```bash
# Using Django test runner
python manage.py test --settings=yolowebapp2.test_settings

# Using pytest (recommended)
pytest
```

**Local Setup (Without Docker)**

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: .\venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run migrations:
   ```bash
   python manage.py migrate
   ```

4. Start development server:
   ```bash
   python manage.py runserver
   ```

## Environment Variables

All variables are read from `.env` in the project root. See `.env.example` for the full template.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | — | Django secret key. Generate with `get_random_secret_key()`. |
| `DJANGO_ENVIRONMENT` | Yes | `production` | `production` or `development` |
| `DJANGO_DEBUG` | No | `False` | Set `True` only in development. |
| `DJANGO_ALLOWED_HOSTS` | Yes | `localhost` | Comma-separated list of allowed hostnames. |
| `DATABASE_NAME` | No | `farmvision` | PostgreSQL database name. |
| `DATABASE_USER` | No | `farmvision_user` | PostgreSQL username. |
| `DATABASE_PASSWORD` | Yes | — | PostgreSQL password. |
| `DATABASE_HOST` | No | `db` | Database host (Docker service name). |
| `DATABASE_PORT` | No | `5432` | Database port. |
| `CELERY_BROKER_URL` | No | `redis://redis:6379/0` | Celery broker URL. |
| `CELERY_RESULT_BACKEND` | No | `redis://redis:6379/0` | Celery result backend URL. |
| `REDIS_CACHE_URL` | No | `redis://redis:6379/1` | Redis cache URL (separate DB from broker). |
| `REDIS_PASSWORD` | No | — | Redis password. Leave empty if Redis has no auth. |
| `CORS_ALLOWED_ORIGINS` | No | — | Comma-separated CORS origins, e.g. `https://app.example.com` |
| `ALERT_WEBHOOK_URL` | No | — | Slack/Teams/Discord webhook for model degradation alerts. |
| `ALERT_EMAIL_RECIPIENTS` | No | — | Comma-separated email addresses for degradation alerts. |
| `ALERT_COOLDOWN_SECONDS` | No | `3600` | Minimum time between duplicate alerts. |

## Services

| Service | Port | Description |
|---|---|---|
| `web` | 8000 | Django + Gunicorn |
| `db` | 5432 (localhost only) | PostgreSQL 15 with PostGIS |
| `redis` | 6379 (localhost only) | Redis 7 (broker + cache) |
| `celery_worker` | — | Celery task worker |
| `celery_beat` | — | Celery periodic task scheduler |
| `nginx` | 80, 443 | Reverse proxy (profile: `with-nginx`) |

## YOLO Models

Place model weight files in the `models/` directory before starting:
models/
├── mandalina.pt
├── elma.pt
├── armut.pt
├── seftale.pt
└── nar.pt

The application will not perform inference if the corresponding `.pt` file is missing.

## API Endpoints

Full interactive documentation available at `/docs/` (Swagger) and `/redoc/` (ReDoc) after startup.

**Detection**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/detections/` | List detection results |
| `POST` | `/api/detections/` | Create detection result |
| `GET` | `/api/detections/statistics/` | Aggregate statistics |
| `GET` | `/api/detections/recent/` | Last 10 results |
| `GET` | `/api/batches/` | List batch detections |

**Web Endpoints (session auth)**

| Method | Endpoint | Description |
|---|---|---|
| `GET/POST` | `/detection/` | Single image detection |
| `GET/POST` | `/detection/mcti/` | Multi-image batch detection |
| `POST` | `/detection/async-detection/` | Async detection (returns task ID) |
| `GET` | `/detection/task-status/<task_id>/` | Check async task status |
| `GET` | `/detection/system-monitoring/` | System resource dashboard |
| `POST` | `/detection/cache/invalidate/` | Invalidate prediction cache (admin only) |
| `GET` | `/detection/cache/statistics/` | Cache hit/miss statistics (admin only) |

**Drone Mapping**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/dron-map/projects/` | Project list |
| `GET/POST` | `/dron-map/projects/<slug>/` | Create/edit project |
| `GET` | `/dron-map/map/<id>/` | Interactive map view |
| `GET` | `/api/projects/` | REST API project list |
| `GET` | `/api/projects/statistics/` | Project statistics |

**System**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health/` | Health check (no auth required) |
| `GET` | `/api/schema/` | OpenAPI schema |
| `GET` | `/docs/` | Swagger UI |
| `GET` | `/redoc/` | ReDoc UI |

## Celery Tasks

Periodic tasks run automatically via `celery_beat`. Manual execution:
```bash
# Run model health check immediately
docker compose exec celery_worker celery -A yolowebapp2 call detection.tasks.check_model_health

# Run cleanup immediately (removes results older than 30 days)
docker compose exec celery_worker celery -A yolowebapp2 call detection.tasks.cleanup_old_results --kwargs='{"days_old": 30}'

# Monitor active tasks
docker compose exec celery_worker celery -A yolowebapp2 inspect active
```

| Task | Schedule | Description |
|---|---|---|
| `check_model_health` | Every 24h | Checks model confidence degradation. Sends alerts if below threshold (0.7). |
| `cleanup_old_results` | Every 24h | Deletes detection records and media files older than 30 days. |

## Running Tests
```bash
# Run all tests
docker compose exec web python manage.py test detection dron_map

# Run with pytest (includes yield_prediction and decision_engine tests)
docker compose exec web pytest

# Run specific app
docker compose exec web python manage.py test detection

# With coverage
docker compose exec web coverage run manage.py test && coverage report
```

## Development Setup (without Docker)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Use SQLite for local dev (no DATABASE_* env vars needed)
export DJANGO_ENVIRONMENT=development
export DJANGO_SECRET_KEY=dev-secret-key-not-for-production

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

For async tasks in development, Redis is still required:
```bash
# Start Redis locally
docker run -d -p 6379:6379 redis:7-alpine

# Start Celery worker
celery -A yolowebapp2 worker -l info
```

## Logs
```bash
# Application logs
docker compose logs web
docker compose logs celery_worker

# Follow in real time
docker compose logs -f web

# Log files inside container
docker compose exec web tail -f /app/logs/django.log
```

## Backup
```bash
# Database backup
docker compose exec db pg_dump -U farmvision_user farmvision > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T db psql -U farmvision_user farmvision < backup_20240101.sql
```

## Updating
```bash
git pull origin main
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
```

## Security Notes

- Never commit `.env` to version control
- `DATABASE_PASSWORD` and `REDIS_PASSWORD` are required in production
- SSL must be enabled in production (see nginx.conf)
- The `/detection/cache/invalidate/` endpoint requires Django staff (`is_staff=True`) privileges
- Media files are served through authenticated proxy — direct `/media/` access requires login
- Rate limiting is enforced at nginx level (10 req/s for API, 100 req/s general)

## License

Proprietary. All rights reserved.
