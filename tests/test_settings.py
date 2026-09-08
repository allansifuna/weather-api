"""Test-time settings overrides: force locmem cache and deterministic weather config."""

from weather_api.config.settings import *  # noqa: F401,F403

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "weather-api-test-locmem",
    }
}

WEATHERAPI_KEY = "test-key"
WEATHERAPI_BASE_URL = "https://api.weatherapi.test"
WEATHER_MAX_FORECAST_DAYS = 3
WEATHER_CACHE_TTL_SECONDS = 600
WEATHERAPI_CIRCUIT_FAILURE_THRESHOLD = 3
WEATHERAPI_CIRCUIT_RECOVERY_SECONDS = 30
