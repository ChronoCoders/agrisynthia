# API Documentation

## Overview

FarmVision provides a RESTful API for all platform functionality. The API follows OpenAPI (Swagger) specifications.

### Interactive Documentation

When the development server is running (`python manage.py runserver` or Docker), interactive API documentation is available at:

- **Swagger UI**: [http://localhost:8000/docs/](http://localhost:8000/docs/)
- **ReDoc**: [http://localhost:8000/redoc/](http://localhost:8000/redoc/)
- **OpenAPI Schema**: [http://localhost:8000/api/schema/](http://localhost:8000/api/schema/)

## Authentication

All API endpoints (except login/registration) require authentication.

**Header**: `Authorization: Token <your_token>`

Obtain a token via `/api/auth/token/login/` (Djoser/DRF Token Auth).

## Key Resource Groups

### Detection (`/detection/`)
- Upload single/multiple images for fruit counting.
- Retrieve detection results (JSON bounding boxes).
- Download annotated images.

### Drone Mapping (`/dron-map/`)
- Manage farm projects (Create/List/Update/Delete).
- Upload orthophotos (GeoTIFF).
- Retrieve vegetation indices (NDVI, etc.) and stress zone data.

### Reports (`/reports/`)
- Generate PDF/Excel reports for detection and mapping projects.
- Download generated reports.

## Error Handling

Standard HTTP status codes are used:
- `200 OK`: Success
- `201 Created`: Resource created successfully
- `400 Bad Request`: Validation error (check response body for details)
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server-side issue
