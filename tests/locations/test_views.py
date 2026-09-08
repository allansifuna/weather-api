"""Integration tests for GET /api/locations/{city}/ through the full request pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.urls import reverse

from weather_api.locations.clients.exceptions import (
    CityNotFoundError,
    InvalidWeatherDataError,
    WeatherProviderAuthError,
    WeatherProviderTimeoutError,
    WeatherProviderUnavailableError,
)

URL_NAME = "location-temperature-stats"


def _url(city: str) -> str:
    return reverse(URL_NAME, kwargs={"city": city})


@patch("weather_api.locations.views.get_weather_client")
def test_returns_statistics_for_a_valid_city(mock_get_client, api_client):
    mock_client = MagicMock()
    mock_client.get_hourly_temperatures.return_value = [18.0, 22.5, 27.0]
    mock_get_client.return_value = mock_client

    response = api_client.get(_url("London"), {"days": 1})

    assert response.status_code == 200
    assert response.data == {"maximum": 27.0, "minimum": 18.0, "average": 22.5, "median": 22.5}
    mock_client.get_hourly_temperatures.assert_called_once_with(city="London", days=1)


@patch("weather_api.locations.views.get_weather_client")
def test_defaults_days_to_one_when_not_provided(mock_get_client, api_client):
    mock_client = MagicMock()
    mock_client.get_hourly_temperatures.return_value = [20.0]
    mock_get_client.return_value = mock_client

    api_client.get(_url("London"))

    mock_client.get_hourly_temperatures.assert_called_once_with(city="London", days=1)


def test_invalid_days_returns_400(api_client):
    response = api_client.get(_url("London"), {"days": "not-a-number"})

    assert response.status_code == 400
    assert response.data["error"]["code"] == "invalid"


def test_days_beyond_maximum_returns_400(api_client, settings):
    settings.WEATHER_MAX_FORECAST_DAYS = 3

    response = api_client.get(_url("London"), {"days": 10})

    assert response.status_code == 400
    assert "error" in response.data


@patch("weather_api.locations.views.get_weather_client")
def test_unknown_city_returns_404(mock_get_client, api_client):
    mock_client = MagicMock()
    mock_client.get_hourly_temperatures.side_effect = CityNotFoundError("no such city")
    mock_get_client.return_value = mock_client

    response = api_client.get(_url("Nowhereville"))

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"


@patch("weather_api.locations.views.get_weather_client")
def test_provider_auth_error_returns_503_without_leaking_detail(mock_get_client, api_client):
    mock_client = MagicMock()
    mock_client.get_hourly_temperatures.side_effect = WeatherProviderAuthError("bad api key")
    mock_get_client.return_value = mock_client

    response = api_client.get(_url("London"))

    assert response.status_code == 503
    assert "bad api key" not in response.data["error"]["message"]


@patch("weather_api.locations.views.get_weather_client")
def test_provider_unavailable_with_retry_after_sets_header(mock_get_client, api_client):
    mock_client = MagicMock()
    mock_client.get_hourly_temperatures.side_effect = WeatherProviderUnavailableError(
        "circuit open", retry_after=15.0
    )
    mock_get_client.return_value = mock_client

    response = api_client.get(_url("London"))

    assert response.status_code == 503
    assert response["Retry-After"] == "16"


@patch("weather_api.locations.views.get_weather_client")
def test_provider_timeout_returns_504(mock_get_client, api_client):
    mock_client = MagicMock()
    mock_client.get_hourly_temperatures.side_effect = WeatherProviderTimeoutError("timed out")
    mock_get_client.return_value = mock_client

    response = api_client.get(_url("London"))

    assert response.status_code == 504
    assert response.data["error"]["code"] == "gateway_timeout"


@patch("weather_api.locations.views.get_weather_client")
def test_provider_unavailable_returns_503(mock_get_client, api_client):
    mock_client = MagicMock()
    mock_client.get_hourly_temperatures.side_effect = WeatherProviderUnavailableError("down")
    mock_get_client.return_value = mock_client

    response = api_client.get(_url("London"))

    assert response.status_code == 503
    assert response.data["error"]["code"] == "service_unavailable"


@patch("weather_api.locations.views.get_weather_client")
def test_invalid_upstream_data_returns_502(mock_get_client, api_client):
    mock_client = MagicMock()
    mock_client.get_hourly_temperatures.side_effect = InvalidWeatherDataError("garbage payload")
    mock_get_client.return_value = mock_client

    response = api_client.get(_url("London"))

    assert response.status_code == 502
    assert response.data["error"]["code"] == "bad_gateway"


def test_swagger_docs_are_served(api_client):
    response = api_client.get("/api/docs/")

    assert response.status_code == 200


def test_openapi_schema_is_served(api_client):
    response = api_client.get("/api/schema/")

    assert response.status_code == 200
