"""Unit tests for the `days` query-parameter validation."""

from __future__ import annotations

from django.test import override_settings

from weather_api.locations.serializers import LocationQuerySerializer


def test_defaults_to_one_day_when_omitted():
    serializer = LocationQuerySerializer(data={})

    assert serializer.is_valid()
    assert serializer.validated_data["days"] == 1


def test_accepts_a_valid_days_value():
    serializer = LocationQuerySerializer(data={"days": "2"})

    assert serializer.is_valid()
    assert serializer.validated_data["days"] == 2


def test_rejects_zero_days():
    serializer = LocationQuerySerializer(data={"days": "0"})

    assert not serializer.is_valid()
    assert "days" in serializer.errors


def test_rejects_negative_days():
    serializer = LocationQuerySerializer(data={"days": "-1"})

    assert not serializer.is_valid()
    assert "days" in serializer.errors


def test_rejects_non_integer_days():
    serializer = LocationQuerySerializer(data={"days": "not-a-number"})

    assert not serializer.is_valid()
    assert "days" in serializer.errors


@override_settings(WEATHER_MAX_FORECAST_DAYS=3)
def test_rejects_days_beyond_configured_maximum():
    serializer = LocationQuerySerializer(data={"days": "4"})

    assert not serializer.is_valid()
    assert "days" in serializer.errors


@override_settings(WEATHER_MAX_FORECAST_DAYS=3)
def test_accepts_days_at_the_configured_maximum():
    serializer = LocationQuerySerializer(data={"days": "3"})

    assert serializer.is_valid()
