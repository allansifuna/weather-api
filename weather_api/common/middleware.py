"""Structured access logging with a per-request correlation id.

Every request gets an id (taken from an inbound `X-Request-ID` header if the
caller/load balancer already set one, otherwise generated) that is echoed
back in the response and included in the access log line, so a single
request can be traced through logs even behind a proxy that fans out to
multiple workers.
"""

from __future__ import annotations

import logging
import time
import uuid

logger = logging.getLogger("weather_api.access")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.id = request_id

        started_at = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - started_at) * 1000

        response[REQUEST_ID_HEADER] = request_id
        logger.info(
            "%s %s %s %.1fms request_id=%s",
            request.method,
            request.get_full_path(),
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
