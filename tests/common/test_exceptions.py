"""Unit tests for the uniform DRF exception handler."""

from __future__ import annotations

from rest_framework.exceptions import NotFound

from weather_api.common.exceptions import ServiceUnavailable, custom_exception_handler


def test_maps_api_exception_to_error_envelope():
    response = custom_exception_handler(NotFound("no such city"), {})

    assert response.status_code == 404
    assert response.data == {"error": {"code": "not_found", "message": "no such city"}}


def test_adds_retry_after_header_when_present():
    exc = ServiceUnavailable("circuit open", retry_after=12.3)

    response = custom_exception_handler(exc, {})

    assert response.status_code == 503
    assert response["Retry-After"] == "13"


def test_no_retry_after_header_when_absent():
    response = custom_exception_handler(ServiceUnavailable("down"), {})

    assert "Retry-After" not in response


def test_unhandled_exception_returns_generic_500():
    response = custom_exception_handler(ValueError("something broke"), {})

    assert response.status_code == 500
    assert response.data == {
        "error": {"code": "internal_error", "message": "Something went wrong on the server."}
    }
