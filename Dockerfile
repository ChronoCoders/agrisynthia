FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    DJANGO_ENVIRONMENT=production

WORKDIR /app

# Install system dependencies
# GDAL version matches what Ubuntu 22.04 ships, so no version mismatch
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    libgdal-dev \
    gdal-bin \
    libproj-dev \
    libgeos-dev \
    libspatialindex-dev \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL config to match the installed system version (not hardcoded)
ENV GDAL_CONFIG=/usr/bin/gdal-config

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install GDAL Python binding pinned to system version
RUN pip install --no-cache-dir GDAL==$(gdal-config --version)

# Install remaining dependencies (torch/torchvision NOT in requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# No CUDA check here. docker build has no GPU access, so a build-time assert on
# torch.cuda.is_available() can only pass by accident of daemon configuration.
# The web and worker entrypoints run `manage.py check_gpu` instead, which
# reports what actually matters: whether the running container sees a device.

# Copy project
COPY . .

# Create runtime directories
RUN mkdir -p /app/media /app/static /app/staticfiles /app/logs /app/results

# Collect static files.
# .dockerignore keeps .env out of the image, so settings.py has no secret key
# to load here. These two values exist only to let settings import during the
# build; the real ones come from .env at runtime. No `|| true`: a failure here
# means the image ships without admin and DRF assets, which should fail loudly.
RUN DJANGO_SECRET_KEY=build-time-only-never-used-at-runtime \
    DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

# Non-root user
RUN useradd -m -u 1000 farmvision && \
    chown -R farmvision:farmvision /app

USER farmvision

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

CMD ["gunicorn", "agrisynthia.wsgi:application", "--config", "gunicorn_config.py"]
