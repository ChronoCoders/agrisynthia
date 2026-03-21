FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    DJANGO_ENVIRONMENT=production

WORKDIR /app

# Install system dependencies
# GDAL version matches what Ubuntu 22.04 ships — no version mismatch
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

# Verify CUDA is available — fail build immediately if not
RUN python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available — check base image or driver'; print('CUDA OK:', torch.version.cuda)"

# Copy project
COPY . .

# Create runtime directories
RUN mkdir -p /app/media /app/static /app/logs /app/results

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Non-root user
RUN useradd -m -u 1000 farmvision && \
    chown -R farmvision:farmvision /app

USER farmvision

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

CMD ["gunicorn", "yolowebapp2.wsgi:application", "--config", "gunicorn_config.py"]
