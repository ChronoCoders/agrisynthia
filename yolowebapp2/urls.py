# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView
from django.http import JsonResponse
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from yolowebapp2.api_views import health_check

urlpatterns = [
    path("", RedirectView.as_view(url="/detection/", permanent=False)),
    path("admin/", admin.site.urls),
    path("detection/", include("detection.urls")),
    path("dron-map/", include("dron_map.urls")),
    path("reports/", include("reports.urls")),
    path(
        ".well-known/appspecific/com.chrome.devtools.json",
        lambda request: JsonResponse({}),
    ),
    path(
        "favicon.ico", RedirectView.as_view(url="/static/favicon.ico", permanent=True)
    ),
    # Backwards compatibility redirects
    path("mcti/", RedirectView.as_view(url="/detection/mcti/", permanent=False)),
    path("mcti", RedirectView.as_view(url="/detection/mcti/", permanent=False)),
    path("index/", RedirectView.as_view(url="/detection/", permanent=False)),
    path("index", RedirectView.as_view(url="/detection/", permanent=False)),
    path(
        "system-monitoring/",
        RedirectView.as_view(url="/detection/system-monitoring/", permanent=False),
    ),
    path(
        "system-monitoring",
        RedirectView.as_view(url="/detection/system-monitoring/", permanent=False),
    ),
    path("accounts/", include("accounts.urls")),
    path("api/", include("yolowebapp2.api_urls")),
    path("health/", health_check, name="health-check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG or settings.IS_DEVELOPMENT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
