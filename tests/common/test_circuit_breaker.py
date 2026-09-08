"""Unit tests for the cache-backed circuit breaker."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from weather_api.common.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState


class BoomError(Exception):
    pass


@pytest.fixture
def breaker() -> CircuitBreaker:
    return CircuitBreaker(name="test-breaker", failure_threshold=3, recovery_timeout=10, failure_window=60)


def test_starts_closed(breaker):
    assert breaker.state == CircuitState.CLOSED


def test_successful_calls_stay_closed(breaker):
    for _ in range(10):
        assert breaker.call(lambda: "ok") == "ok"
    assert breaker.state == CircuitState.CLOSED


def test_opens_after_threshold_failures(breaker):
    for _ in range(breaker.failure_threshold):
        with pytest.raises(BoomError):
            breaker.call(_raise(BoomError), failure_exceptions=(BoomError,))
    assert breaker.state == CircuitState.OPEN


def test_open_circuit_rejects_calls_without_invoking_func(breaker):
    _trip(breaker)

    calls = []
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(lambda: calls.append(1), failure_exceptions=(BoomError,))
    assert calls == []


def test_half_open_after_recovery_timeout_and_closes_on_success(breaker):
    _trip(breaker)
    future_time = _future_time(breaker)

    with patch("weather_api.common.circuit_breaker.time.time") as mock_time:
        mock_time.return_value = future_time
        result = breaker.call(lambda: "recovered", failure_exceptions=(BoomError,))

    assert result == "recovered"
    assert breaker.state == CircuitState.CLOSED


def test_half_open_reopens_on_repeat_failure(breaker):
    _trip(breaker)
    future_time = _future_time(breaker)

    with patch("weather_api.common.circuit_breaker.time.time") as mock_time:
        mock_time.return_value = future_time
        with pytest.raises(BoomError):
            breaker.call(_raise(BoomError), failure_exceptions=(BoomError,))

    assert breaker.state == CircuitState.OPEN


def test_unrelated_exceptions_do_not_trip_the_breaker(breaker):
    class ClientInputError(Exception):
        pass

    for _ in range(10):
        with pytest.raises(ClientInputError):
            breaker.call(_raise(ClientInputError), failure_exceptions=(BoomError,))

    assert breaker.state == CircuitState.CLOSED


def _raise(exc_type):
    def _fn():
        raise exc_type("boom")

    return _fn


def _trip(breaker: CircuitBreaker) -> None:
    for _ in range(breaker.failure_threshold):
        with pytest.raises(BoomError):
            breaker.call(_raise(BoomError), failure_exceptions=(BoomError,))
    assert breaker.state == CircuitState.OPEN


def _future_time(breaker: CircuitBreaker) -> float:
    import time

    return time.time() + breaker.recovery_timeout + 1
