from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView, TemplateView
from django.http import JsonResponse
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from agrisynthia.api_views import health_check

urlpatterns = [
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("sitemap.xml", TemplateView.as_view(
        template_name="sitemap.xml",
        content_type="application/xml",
        extra_context={
            "routes": [
                {"name": "website:home",    "changefreq": "weekly",  "priority": "1.0"},
                {"name": "website:product", "changefreq": "monthly", "priority": "0.8"},
                {"name": "website:pricing", "changefreq": "monthly", "priority": "0.9"},
                {"name": "website:about",   "changefreq": "monthly", "priority": "0.6"},
                {"name": "website:blog",    "changefreq": "weekly",  "priority": "0.8"},
                {"name": "website:contact", "changefreq": "yearly",  "priority": "0.6"},
                {"name": "website:privacy", "changefreq": "yearly",  "priority": "0.3"},
                {"name": "website:terms",   "changefreq": "yearly",  "priority": "0.3"},
                {"name": "website:kvkk",    "changefreq": "yearly",  "priority": "0.3"},
            ],
            "blog_slugs": [
                "ndvi-nedir-nasil-okunur",
                "drone-ortofoto-nasil-olusturulur",
                "meyve-tespitinde-yapay-zeka",
                "verim-tahmini-agronomi-modeli",
                "turk-tariminda-dijital-donusum",
                "sentinel-2-ucretsiz-uydu-verisi",
            ],
        },
    )),
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
    path("i18n/", include("django.conf.urls.i18n")),
    path("api/", include("agrisynthia.api_urls")),
    path("health/", health_check, name="health-check"),
    path("metrics/", include("django_prometheus.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

urlpatterns += i18n_patterns(
    path("", include("website.urls", namespace="website")),
    prefix_default_language=False,
)

if settings.DEBUG or settings.IS_DEVELOPMENT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
