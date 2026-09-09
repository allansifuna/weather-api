"""Exceptions raised by weather provider clients."""

from __future__ import annotations


class WeatherProviderError(Exception):
    """Base exception for all weather-provider related failures."""


class CityNotFoundError(WeatherProviderError):
    """The provider has no data for the requested city."""


class WeatherProviderAuthError(WeatherProviderError):
    """The provider rejected our API credentials."""


class WeatherProviderTimeoutError(WeatherProviderError):
    """The provider did not respond within the configured timeout."""


class WeatherProviderUnavailableError(WeatherProviderError):
    """Connection failure, 5xx response, or open circuit breaker."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class InvalidWeatherDataError(WeatherProviderError):
    """The provider's response could not be parsed into temperature data."""
