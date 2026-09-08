"""Request/response schemas for the locations temperature-statistics endpoint."""

from __future__ import annotations

from django.conf import settings
from rest_framework import serializers


class LocationQuerySerializer(serializers.Serializer):
    """Validates the '?days=' query parameter."""

    days = serializers.IntegerField(
        required=False,
        default=1,
        min_value=1,
        error_messages={"invalid": "days must be a whole number."},
    )

    def validate_days(self, value: int) -> int:
        max_days = settings.WEATHER_MAX_FORECAST_DAYS
        if value > max_days:
            raise serializers.ValidationError(
                f"days must be between 1 and {max_days} (the weather provider's forecast limit)."
            )
        return value


class TemperatureStatsSerializer(serializers.Serializer):
    """Successful summary temperature statistics in °C."""

    maximum = serializers.FloatField()
    minimum = serializers.FloatField()
    average = serializers.FloatField()
    median = serializers.FloatField()
