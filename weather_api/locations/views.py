"""View for the temperature stats."""

from __future__ import annotations

import logging

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from weather_api.common.exceptions import ServiceUnavailable, UpstreamServiceError, UpstreamTimeoutError

from .clients.exceptions import (
    CityNotFoundError,
    InvalidWeatherDataError,
    WeatherProviderAuthError,
    WeatherProviderTimeoutError,
    WeatherProviderUnavailableError,
)
from .clients.weatherapi import get_weather_client
from .serializers import LocationQuerySerializer, TemperatureStatsSerializer
from .services import compute_temperature_stats

logger = logging.getLogger(__name__)


class LocationTemperatureStatsView(APIView):
    """Returns aggregate temperature stats for a city over a period of days."""

    permission_classes = [AllowAny]
    throttle_scope = "locations"

    @extend_schema(
        summary="Get temperature statistics for a city",
        description=(
            "Fetches the weather forecast for `city` over `days` days and returns the "
            "minimum, maximum, average and median temperature (°C) computed across "
            "every hourly reading in that period."
        ),
        parameters=[
            OpenApiParameter(
                name="city",
                location=OpenApiParameter.PATH,
                type=str,
                description="City name, e.g. `Nairobi` or `London`.",
            ),
            OpenApiParameter(
                name="days",
                location=OpenApiParameter.QUERY,
                type=int,
                required=False,
                description="Number of forecast days to include, starting today (default: 1).",
            ),
        ],
        responses={200: TemperatureStatsSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={"maximum": 27.4, "minimum": 18.1, "average": 22.6, "median": 22.9},
                response_only=True,
            ),
        ],
    )
    def get(self, request, city: str) -> Response:
        query = LocationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        days = query.validated_data["days"]

        temperatures = self._fetch_temperatures(city, days)
        stats = compute_temperature_stats(temperatures)
        return Response(TemperatureStatsSerializer(stats).data)

    @staticmethod
    def _fetch_temperatures(city: str, days: int) -> list[float]:
        client = get_weather_client()
        try:
            return client.get_hourly_temperatures(city=city, days=days)
        except CityNotFoundError as exc:
            raise NotFound(str(exc)) from exc
        except WeatherProviderAuthError as exc:
            logger.error("Weather provider rejected our credentials: %s", exc)
            raise ServiceUnavailable("The weather service is misconfigured.") from exc
        except WeatherProviderTimeoutError as exc:
            raise UpstreamTimeoutError(str(exc)) from exc
        except WeatherProviderUnavailableError as exc:
            raise ServiceUnavailable(str(exc), retry_after=exc.retry_after) from exc
        except InvalidWeatherDataError as exc:
            raise UpstreamServiceError(str(exc)) from exc
