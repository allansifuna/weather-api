"""Tests for the /healthz/ liveness/readiness probe."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.urls import reverse


def _url() -> str:
    return reverse("healthz")


@pytest.mark.django_db
def test_healthy_when_database_and_cache_are_reachable(api_client):
    response = api_client.get(_url())

    assert response.status_code == 200
    assert response.data == {"status": "ok", "checks": {"database": True, "cache": True}}


@patch("weather_api.common.views.connection")
def test_unhealthy_when_database_is_unreachable(mock_connection, api_client):
    mock_connection.ensure_connection.side_effect = Exception("db down")

    response = api_client.get(_url())

    assert response.status_code == 503
    assert response.data["checks"]["database"] is False


@patch("weather_api.common.views.cache")
def test_unhealthy_when_cache_is_unreachable(mock_cache, api_client):
    mock_cache.set.side_effect = Exception("cache down")

    response = api_client.get(_url())

    assert response.status_code == 503
    assert response.data["checks"]["cache"] is False


@patch("weather_api.common.views.cache")
def test_unhealthy_when_cache_roundtrip_returns_wrong_value(mock_cache, api_client):
    mock_cache.get.return_value = "not-ok"

    response = api_client.get(_url())

    assert response.status_code == 503
    assert response.data["checks"]["cache"] is False
