"""Unit tests for pure statistics computation."""

from __future__ import annotations

import pytest

from weather_api.locations.services import NoTemperatureDataError, compute_temperature_stats


def test_computes_min_max_avg_median_for_typical_series():
    stats = compute_temperature_stats([10.0, 20.0, 30.0])

    assert stats == {"maximum": 30.0, "minimum": 10.0, "average": 20.0, "median": 20.0}


def test_median_of_even_length_series_is_averaged_midpoint():
    stats = compute_temperature_stats([10.0, 20.0, 30.0, 40.0])

    assert stats["median"] == 25.0


def test_single_value_series():
    stats = compute_temperature_stats([15.5])

    assert stats == {"maximum": 15.5, "minimum": 15.5, "average": 15.5, "median": 15.5}


def test_handles_negative_temperatures():
    stats = compute_temperature_stats([-10.0, 0.0, 10.0])

    assert stats == {"maximum": 10.0, "minimum": -10.0, "average": 0.0, "median": 0.0}


def test_rounds_to_two_decimal_places():
    stats = compute_temperature_stats([1.0, 2.0, 3.0])

    assert stats["average"] == 2.0
    assert isinstance(stats["average"], float)


def test_empty_series_raises():
    with pytest.raises(NoTemperatureDataError):
        compute_temperature_stats([])
