# FarmVision Architecture

## Overview

FarmVision is a modular agricultural analysis platform built on Django and PyTorch. It combines fruit detection on tree imagery with drone orthophoto analysis for yield estimation and health monitoring.

## Core Components

### 1. Backend API (Django + DRF)
- **Framework**: Django 4.2 with Django REST Framework (DRF)
- **Role**: Handles user authentication, project management, file uploads, and data serving.
- **Database**: PostgreSQL with PostGIS extension for spatial data storage (field boundaries, detection points).

### 2. Object Detection Engine (YOLOv7)
- **Location**: `detection/` app
- **Technology**: PyTorch implementation of YOLOv7
- **Function**: Processes uploaded images to detect and count fruits (mandarin, apple, pear, peach, pomegranate) and trees.
- **Execution**: Runs asynchronously via Celery workers to prevent blocking the main web server.

### 3. Drone Mapping & Analysis
- **Location**: `dron_map/` app
- **Function**: Manages drone orthophoto uploads and processing.
- **Integration**: Works with WebODM/NodeODM for photogrammetry (orthophoto generation).
- **Analysis**:
  - **Vegetation Indices**: Calculates NDVI, EVI, SAVI using `rasterio`.
  - **Stress Zones**: Identifies high/low stress areas based on index thresholds.
  - **Canopy Analysis**: Estimates canopy coverage and tree density.

### 4. Async Task Queue (Celery + Redis)
- **Broker**: Redis
- **Result Backend**: Redis
- **Workers**: Dedicated Celery workers handle long-running tasks:
  - Image inference (GPU accelerated)
  - Orthophoto processing (CPU intensive)
  - Report generation (PDF/Excel)

### 5. Caching & Performance
- **Cache**: Redis is used for caching API responses and heavy calculation results (e.g., vegetation index grids).
- **Optimization**: `numpy` and `rasterio` are used for efficient matrix operations on large geospatial datasets.

## Data Flow

1. **User Upload**: User uploads images (field photos or drone orthophotos) via REST API.
2. **Task Queueing**: API validates input and queues a Celery task.
3. **Processing**:
   - **Detection**: Worker loads YOLO model, runs inference, saves bounding boxes to DB.
   - **Mapping**: Worker processes GeoTIFF, calculates indices, generates tiles.
4. **Notification**: Task status is updated; user can poll or receive webhook (future).
5. **Visualization**: Frontend retrieves JSON data or map tiles for display (Leaflet/Chart.js).
