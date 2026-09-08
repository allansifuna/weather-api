"""Unit tests for WeatherApiClient: caching, error mapping, and circuit-breaker wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from tests.conftest import make_forecast_payload
from weather_api.common.circuit_breaker import CircuitBreaker
from weather_api.locations.clients.exceptions import (
    CityNotFoundError,
    InvalidWeatherDataError,
    WeatherProviderAuthError,
    WeatherProviderTimeoutError,
    WeatherProviderUnavailableError,
)
from weather_api.locations.clients.weatherapi import WeatherApiClient


def _make_client(session) -> WeatherApiClient:
    return WeatherApiClient(
        api_key="test-key",
        base_url="https://api.weatherapi.test",
        connect_timeout=1,
        read_timeout=1,
        cache_ttl_seconds=600,
        session=session,
        circuit_breaker=CircuitBreaker(name="test-weatherapi", failure_threshold=3, recovery_timeout=5),
    )


def _mock_response(status_code=200, json_data=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    return response


def test_get_hourly_temperatures_success():
    session = MagicMock()
    session.get.return_value = _mock_response(
        200, make_forecast_payload(days=1, hourly_temps=[18.0, 22.5, 27.0])
    )
    client = _make_client(session)

    temps = client.get_hourly_temperatures(city="London", days=1)

    assert temps == [18.0, 22.5, 27.0]
    session.get.assert_called_once()


def test_second_call_is_served_from_cache():
    session = MagicMock()
    session.get.return_value = _mock_response(200, make_forecast_payload(days=1))
    client = _make_client(session)

    client.get_hourly_temperatures(city="London", days=1)
    client.get_hourly_temperatures(city="London", days=1)

    session.get.assert_called_once()


def test_cache_key_is_case_and_whitespace_insensitive():
    session = MagicMock()
    session.get.return_value = _mock_response(200, make_forecast_payload(days=1))
    client = _make_client(session)

    client.get_hourly_temperatures(city="London", days=1)
    client.get_hourly_temperatures(city="  LONDON  ", days=1)

    session.get.assert_called_once()


def test_city_not_found_raises_city_not_found_error():
    session = MagicMock()
    session.get.return_value = _mock_response(
        400, {"error": {"code": 1006, "message": "No matching location found."}}
    )
    client = _make_client(session)

    with pytest.raises(CityNotFoundError):
        client.get_hourly_temperatures(city="Nowhereville", days=1)


def test_invalid_api_key_raises_auth_error():
    session = MagicMock()
    session.get.return_value = _mock_response(
        401, {"error": {"code": 2006, "message": "API key is invalid."}}
    )
    client = _make_client(session)

    with pytest.raises(WeatherProviderAuthError):
        client.get_hourly_temperatures(city="London", days=1)


def test_unrecognized_error_response_raises_unavailable():
    session = MagicMock()
    session.get.return_value = _mock_response(500, {"error": {"message": "Internal error"}})
    client = _make_client(session)

    with pytest.raises(WeatherProviderUnavailableError):
        client.get_hourly_temperatures(city="London", days=1)


def test_non_json_error_response_still_raises_unavailable():
    session = MagicMock()
    response = MagicMock(status_code=500)
    response.json.side_effect = ValueError("not json")
    session.get.return_value = response
    client = _make_client(session)

    with pytest.raises(WeatherProviderUnavailableError):
        client.get_hourly_temperatures(city="London", days=1)


def test_timeout_raises_timeout_error():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.Timeout("timed out")
    client = _make_client(session)

    with pytest.raises(WeatherProviderTimeoutError):
        client.get_hourly_temperatures(city="London", days=1)


def test_connection_error_raises_unavailable_error():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.ConnectionError("no route to host")
    client = _make_client(session)

    with pytest.raises(WeatherProviderUnavailableError):
        client.get_hourly_temperatures(city="London", days=1)


def test_malformed_payload_raises_invalid_data_error():
    session = MagicMock()
    session.get.return_value = _mock_response(200, {"unexpected": "shape"})
    client = _make_client(session)

    with pytest.raises(InvalidWeatherDataError):
        client.get_hourly_temperatures(city="London", days=1)


def test_empty_forecast_days_raises_invalid_data_error():
    session = MagicMock()
    session.get.return_value = _mock_response(200, {"forecast": {"forecastday": []}})
    client = _make_client(session)

    with pytest.raises(InvalidWeatherDataError):
        client.get_hourly_temperatures(city="London", days=1)


def test_forecast_days_present_but_missing_temp_c_raises_invalid_data_error():
    session = MagicMock()
    payload = {"forecast": {"forecastday": [{"hour": [{"time": "2026-09-08 00:00", "condition": "sunny"}]}]}}
    session.get.return_value = _mock_response(200, payload)
    client = _make_client(session)

    with pytest.raises(InvalidWeatherDataError):
        client.get_hourly_temperatures(city="London", days=1)


def test_circuit_open_error_carries_retry_after_seconds():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.Timeout("timed out")
    client = _make_client(session)

    for _ in range(3):
        with pytest.raises(WeatherProviderTimeoutError):
            client.get_hourly_temperatures(city="London", days=1)

    with pytest.raises(WeatherProviderUnavailableError) as exc_info:
        client.get_hourly_temperatures(city="London", days=1)

    assert exc_info.value.retry_after is not None
    assert exc_info.value.retry_after > 0


def test_repeated_timeouts_trip_the_circuit_breaker_and_stop_calling_session():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.Timeout("timed out")
    client = _make_client(session)

    for _ in range(3):
        with pytest.raises(WeatherProviderTimeoutError):
            client.get_hourly_temperatures(city="London", days=1)

    call_count_before = session.get.call_count
    with pytest.raises(WeatherProviderUnavailableError):
        client.get_hourly_temperatures(city="London", days=1)

    assert session.get.call_count == call_count_before  # circuit rejected the call outright


def test_city_not_found_does_not_trip_the_circuit_breaker():
    session = MagicMock()
    session.get.return_value = _mock_response(400, {"error": {"code": 1006, "message": "not found"}})
    client = _make_client(session)

    for _ in range(10):
        with pytest.raises(CityNotFoundError):
            client.get_hourly_temperatures(city="Nowhereville", days=1)

    # A healthy-but-wrong-input city should never open the breaker.
    assert client._circuit_breaker.state.value == "closed"


def test_get_weather_client_is_a_singleton():
    from weather_api.locations.clients import weatherapi

    weatherapi.reset_weather_client_cache()
    first = weatherapi.get_weather_client()
    second = weatherapi.get_weather_client()

    assert first is second

    weatherapi.reset_weather_client_cache()
    third = weatherapi.get_weather_client()

    assert third is not first
