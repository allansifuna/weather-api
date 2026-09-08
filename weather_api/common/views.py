"""Infrastructure-facing views (health checks) -- not part of the public API surface."""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

_CACHE_CHECK_KEY = "healthz:probe"


class HealthCheckView(APIView):
    """Liveness/readiness probe for load balancers and orchestrators.

    Checks that the database and cache are actually reachable rather than
    just returning a static 200 -- a process that's up but can't reach its
    dependencies isn't ready to serve traffic.
    """

    permission_classes = [AllowAny]
    throttle_classes: list = []

    @extend_schema(exclude=True)
    def get(self, request) -> Response:
        checks = {"database": self._check_database(), "cache": self._check_cache()}
        healthy = all(checks.values())
        status_code = 200 if healthy else 503
        body = {"status": "ok" if healthy else "unavailable", "checks": checks}
        return Response(body, status=status_code)

    @staticmethod
    def _check_database() -> bool:
        try:
            connection.ensure_connection()
            return True
        except Exception:
            logger.exception("Health check: database unreachable")
            return False

    @staticmethod
    def _check_cache() -> bool:
        try:
            cache.set(_CACHE_CHECK_KEY, "ok", timeout=5)
            return cache.get(_CACHE_CHECK_KEY) == "ok"
        except Exception:
            logger.exception("Health check: cache unreachable")
            return False
