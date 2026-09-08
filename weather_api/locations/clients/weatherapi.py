"""Client for WeatherAPI.com's forecast endpoint.

Wraps the raw HTTP call with:
  - a request timeout (connect + read) so a slow upstream can't hang a worker
  - automatic retries with backoff for transient connection or 5xx failures
  - a cache-aside layer so repeat lookups for the same city/period don't hit
    the upstream API at all within the TTL
  - a circuit breaker so a sustained upstream outage fails fast instead of
    piling up slow, doomed requests
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

from weather_api.common.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from weather_api.common.http import build_session

from .exceptions import (
    CityNotFoundError,
    InvalidWeatherDataError,
    WeatherProviderAuthError,
    WeatherProviderTimeoutError,
    WeatherProviderUnavailableError,
)

logger = logging.getLogger(__name__)

FORECAST_ENDPOINT = "/v1/forecast.json"

# https://www.weatherapi.com/docs/#intro-error-codes
_CITY_NOT_FOUND_CODES = {1006}
_AUTH_ERROR_CODES = {1002, 2006, 2007, 2008, 2009}

# Only these upstream is unhealthy errors should trip the cirecuit breaker.
_CIRCUIT_TRIP_EXCEPTIONS = (WeatherProviderTimeoutError, WeatherProviderUnavailableError)


class WeatherApiClient:
    """A wrapper around WeatherAPI.com."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        connect_timeout: float,
        read_timeout: float,
        cache_ttl_seconds: int,
        session=None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = (connect_timeout, read_timeout)
        self._cache_ttl_seconds = cache_ttl_seconds
        self._session = session or build_session()
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            name="weatherapi",
            failure_threshold=settings.WEATHERAPI_CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=settings.WEATHERAPI_CIRCUIT_RECOVERY_SECONDS,
        )

    def get_hourly_temperatures(self, *, city: str, days: int) -> list[float]:
        """Return every hourly temperature (°C) forecast for city over days."""
        cache_key = f"weatherapi:forecast:{city.strip().lower()}:{days}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            payload = self._circuit_breaker.call(
                lambda: self._fetch_forecast(city, days),
                failure_exceptions=_CIRCUIT_TRIP_EXCEPTIONS,
            )
        except CircuitBreakerOpenError as exc:
            logger.warning("weatherapi circuit open: rejecting call for city=%r", city)
            raise WeatherProviderUnavailableError(str(exc), retry_after=exc.retry_after_seconds) from exc

        temperatures = self._extract_temperatures(payload)
        cache.set(cache_key, temperatures, timeout=self._cache_ttl_seconds)
        return temperatures

    def _fetch_forecast(self, city: str, days: int) -> dict[str, Any]:
        url = f"{self._base_url}{FORECAST_ENDPOINT}"
        params = {"key": self._api_key, "q": city, "days": days, "aqi": "no", "alerts": "no"}

        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
        except Timeout as exc:
            raise WeatherProviderTimeoutError(f"Timed out fetching forecast for {city!r}") from exc
        except RequestsConnectionError as exc:
            raise WeatherProviderUnavailableError(f"Could not reach weather provider: {exc}") from exc

        if response.status_code == 200:
            return response.json()
        self._raise_for_error_response(response, city)

    def _raise_for_error_response(self, response, city: str) -> None:
        try:
            error = response.json().get("error", {})
        except ValueError:
            error = {}
        code = error.get("code")
        message = error.get("message", "Unknown error from weather provider")

        if code in _CITY_NOT_FOUND_CODES:
            raise CityNotFoundError(f"No weather data found for city {city!r}")
        if code in _AUTH_ERROR_CODES or response.status_code in (401, 403):
            raise WeatherProviderAuthError(message)
        raise WeatherProviderUnavailableError(f"Weather provider returned {response.status_code}: {message}")

    @staticmethod
    def _extract_temperatures(payload: dict[str, Any]) -> list[float]:
        try:
            forecast_days = payload["forecast"]["forecastday"]
        except (KeyError, TypeError) as exc:
            raise InvalidWeatherDataError("Malformed forecast payload from weather provider") from exc

        if not forecast_days:
            raise InvalidWeatherDataError("Weather provider returned no forecast days")

        temperatures: list[float] = [
            float(hour["temp_c"]) for day in forecast_days for hour in day.get("hour", []) if "temp_c" in hour
        ]

        if not temperatures:
            raise InvalidWeatherDataError("Weather provider returned no hourly temperature readings")

        return temperatures


_client: WeatherApiClient | None = None


def get_weather_client() -> WeatherApiClient:
    """Return a process-wide singleton WeatherApiClient built from settings."""
    global _client
    if _client is None:
        _client = WeatherApiClient(
            api_key=settings.WEATHERAPI_KEY,
            base_url=settings.WEATHERAPI_BASE_URL,
            connect_timeout=settings.WEATHERAPI_CONNECT_TIMEOUT,
            read_timeout=settings.WEATHERAPI_READ_TIMEOUT,
            cache_ttl_seconds=settings.WEATHER_CACHE_TTL_SECONDS,
        )
    return _client


def reset_weather_client_cache() -> None:
    """Drop the cached singleton"""
    global _client
    _client = None
