# -*- coding: utf-8 -*-
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status, serializers
from django.db import connection
from drf_spectacular.utils import extend_schema, OpenApiResponse

logger = logging.getLogger(__name__)


class HealthCheckResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    version = serializers.CharField()
    database = serializers.CharField()


@extend_schema(
    summary="Health Check",
    description="Check the health status of the FarmVision API and database connectivity.",
    responses={
        200: OpenApiResponse(
            response=HealthCheckResponseSerializer, description="Service is healthy"
        ),
        503: OpenApiResponse(
            response=HealthCheckResponseSerializer, description="Service is degraded"
        ),
    },
    tags=["System"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    health_status = {
        "status": "ok",
        "version": "2.0.0",
    }

    try:
        connection.ensure_connection()
        health_status["database"] = "connected"
    except Exception as e:
        # Log the actual error for debugging, but don't expose it to users
        logger.error("Database connection error: %s", str(e))
        health_status["database"] = "connection_error"
        health_status["status"] = "degraded"
        return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response(health_status, status=status.HTTP_200_OK)
