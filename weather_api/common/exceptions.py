"""Custom DRF exceptions and a uniform JSON exception handler.

Every error response from this API has the shape:

    {"error": {"code": "<machine_readable_code>", "message": "<human readable>"}}

so clients can branch on `code` without parsing message strings.
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class UpstreamServiceError(APIException):
    """The upstream provider responded, but with something we can't use (502)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "The weather provider returned an invalid response."
    default_code = "bad_gateway"


class UpstreamTimeoutError(APIException):
    """The upstream provider did not respond in time (504)."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_detail = "The weather provider timed out."
    default_code = "gateway_timeout"


class ServiceUnavailable(APIException):
    """We deliberately refused to call the upstream provider, or it is down (503)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The service is temporarily unavailable, please try again shortly."
    default_code = "service_unavailable"

    def __init__(self, detail=None, code=None, retry_after: float | None = None):
        super().__init__(detail=detail, code=code)
        self.retry_after = retry_after


def custom_exception_handler(exc, context):
    """Normalize every DRF exception into `{"error": {"code", "message"}}`.

    DRF's own `exception_handler` already converts `django.http.Http404` and
    `django.core.exceptions.PermissionDenied` into `NotFound`/`PermissionDenied`
    APIExceptions before we ever see them here, so there is no separate branch
    for those -- anything reaching the `response is None` fallback below is a
    genuinely unexpected, unhandled exception.
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        code = getattr(exc, "default_code", None) or exc.__class__.__name__.lower()
        detail = (
            response.data.get("detail", response.data) if isinstance(response.data, dict) else response.data
        )
        response.data = {"error": {"code": code, "message": _flatten(detail)}}
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is not None:
            response["Retry-After"] = str(int(retry_after) + 1)
        return response

    logger.exception("Unhandled exception while processing API request", exc_info=exc)
    return Response(
        {"error": {"code": "internal_error", "message": "Something went wrong on the server."}},
        status=500,
    )


def _flatten(detail) -> str:
    """Collapse DRF's (possibly nested list/dict) error detail into one string."""
    if isinstance(detail, list):
        return " ".join(_flatten(item) for item in detail)
    if isinstance(detail, dict):
        return " ".join(f"{key}: {_flatten(value)}" for key, value in detail.items())
    return str(detail)
