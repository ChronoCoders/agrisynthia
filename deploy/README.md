# Deployment

Bare-metal / VM deploy at `/opt/agrisynthia` with a virtualenv at
`/opt/agrisynthia/venv`, running as an unprivileged `agrisynthia` user behind
nginx. For the container path use `docker-compose.yml` at the repo root instead;
do not mix the two on one host.

## Layout these units assume

```
/opt/agrisynthia/            checkout (WorkingDirectory)
/opt/agrisynthia/venv/       virtualenv
/opt/agrisynthia/.env        filled-in copy of env.production.template, mode 600
/opt/agrisynthia/logs/       django.log, django_errors.log
/opt/agrisynthia/media/      local uploads (unused when USE_R2=True)
/opt/agrisynthia/staticfiles/  collectstatic output, served by nginx
/var/lib/agrisynthia/        celerybeat-schedule (StateDirectory)
```

## First install

```bash
sudo useradd --system --home /opt/agrisynthia --shell /usr/sbin/nologin agrisynthia
sudo install -d -o agrisynthia -g agrisynthia /opt/agrisynthia /var/lib/agrisynthia

# checkout + venv
sudo -u agrisynthia git clone https://github.com/ChronoCoders/agrisynthia.git /opt/agrisynthia
sudo -u agrisynthia python3.10 -m venv /opt/agrisynthia/venv
sudo -u agrisynthia /opt/agrisynthia/venv/bin/pip install -r /opt/agrisynthia/requirements.txt

# environment
sudo install -o agrisynthia -g agrisynthia -m 600 \
    /opt/agrisynthia/deploy/env.production.template /opt/agrisynthia/.env
sudo -u agrisynthia editor /opt/agrisynthia/.env     # fill in every <PLACEHOLDER>

# database
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS postgis;" agrisynthia
sudo -u agrisynthia /opt/agrisynthia/venv/bin/python manage.py migrate
sudo -u agrisynthia /opt/agrisynthia/venv/bin/python manage.py collectstatic --noinput
sudo -u agrisynthia /opt/agrisynthia/venv/bin/python manage.py compilemessages
sudo -u agrisynthia /opt/agrisynthia/venv/bin/python manage.py createsuperuser

# model weights, then record their checksums
sudo -u agrisynthia /opt/agrisynthia/venv/bin/python manage.py verify_model_checksums --store

# units
sudo cp /opt/agrisynthia/deploy/systemd/*.service /opt/agrisynthia/deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now agrisynthia-web agrisynthia-worker agrisynthia-beat
sudo systemctl enable --now agrisynthia-backup.timer
```

## Verifying it actually works

```bash
systemctl status agrisynthia-web agrisynthia-worker agrisynthia-beat
curl -s localhost:8000/health/            # {"status": "ok", "database": "connected"}

# The database is Postgres, not the SQLite fallback. An incomplete DATABASE_*
# block in .env silently falls back to SQLite, so check this explicitly.
sudo -u agrisynthia /opt/agrisynthia/venv/bin/python manage.py shell \
    -c "from django.db import connection; print(connection.settings_dict['ENGINE'])"

# The worker is listening on all three queues. If "detection" or "mapping" is
# missing, async detection and every drone task will hang in PENDING forever.
sudo -u agrisynthia /opt/agrisynthia/venv/bin/celery -A agrisynthia inspect active_queues

# Backup path works end to end before trusting the timer.
sudo systemctl start agrisynthia-backup.service
sudo -u agrisynthia /opt/agrisynthia/venv/bin/python scripts/backup_postgres.py list
```

## Notes

- **Queue routing.** `settings.CELERY_TASK_ROUTES` splits tasks across
  `detection`, `mapping`, and the default `celery` queue. The worker unit passes
  `--queues detection,mapping,celery` for that reason. A bare
  `celery -A agrisynthia worker` consumes only `celery` and silently drops the
  other two on the floor. `docker-compose.yml` currently has this bug.
- **Exactly one beat.** Two schedulers double every periodic task: duplicate
  NDVI alerts, duplicate reports, two cleanup passes.
- **No `EnvironmentFile=`.** `settings.py` calls `load_dotenv()` on `.env`
  itself. Pointing systemd at the same file makes it re-parse under stricter
  quoting rules, which breaks values with spaces such as `DEFAULT_FROM_EMAIL`.
- **Gunicorn bind.** `gunicorn_config.py` binds `0.0.0.0:8000` for Docker; the
  web unit overrides to `127.0.0.1:8000` so only nginx can reach it.
- **GPU.** The worker sets `PrivateDevices=false` so CUDA can see the NVIDIA
  device nodes. Concurrency is 2 because inference pins a model in GPU memory.
- **Upgrades.** Four bundled third-party files under `static/` were hand-edited;
  re-apply after upgrading those libraries. See the repo-local notes.

## Deploying an update

```bash
sudo -u agrisynthia git -C /opt/agrisynthia pull
sudo -u agrisynthia /opt/agrisynthia/venv/bin/pip install -r /opt/agrisynthia/requirements.txt
sudo -u agrisynthia /opt/agrisynthia/venv/bin/python manage.py migrate
sudo -u agrisynthia /opt/agrisynthia/venv/bin/python manage.py collectstatic --noinput
sudo systemctl reload agrisynthia-web          # SIGHUP, graceful worker recycle
sudo systemctl restart agrisynthia-worker agrisynthia-beat
```
