"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def clear_cache():
    """Prevent cache state -- including circuit breaker state -- leaking between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


def make_forecast_payload(*, days: int = 1, hourly_temps: list[float] | None = None) -> dict:
    """Build a minimal WeatherAPI.com forecast response for `days` days.

    Each day gets 3 hourly readings by default (enough to exercise min/max/
    median without hand-writing 24 values per test).
    """
    hourly_temps = hourly_temps if hourly_temps is not None else [18.0, 22.5, 27.0]
    return {
        "location": {"name": "London"},
        "forecast": {
            "forecastday": [
                {
                    "date": f"2026-09-{8 + day:02d}",
                    "day": {"maxtemp_c": max(hourly_temps), "mintemp_c": min(hourly_temps)},
                    "hour": [
                        {"time": f"2026-09-{8 + day:02d} {h:02d}:00", "temp_c": t}
                        for h, t in enumerate(hourly_temps)
                    ],
                }
                for day in range(days)
            ]
        },
    }
