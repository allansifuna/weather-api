"""URL configuration for weather_api."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from weather_api.common.views import HealthCheckView

api_patterns = [
    path("locations/", include("weather_api.locations.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", HealthCheckView.as_view(), name="healthz"),
    path("api/", include(api_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
