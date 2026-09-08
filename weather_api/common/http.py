"""Shared HTTP session factory with sane timeout and retry defaults for outbound calls."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_RETRY_TOTAL = 2
DEFAULT_BACKOFF_FACTOR = 0.3
RETRY_STATUS_FORCELIST = (502, 503, 504)


def build_session(
    retry_total: int = DEFAULT_RETRY_TOTAL,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
) -> requests.Session:
    """Return a `requests.Session` that retries transient failures with backoff.

    Only GET requests are retried (they're idempotent), and only for connection
    errors or 502/503/504 responses. 4xx client errors (bad city, bad API key)
    are never retried since retrying an identical request cannot change them.
    A caller-supplied `timeout` on each request still bounds the total wait.
    """
    session = requests.Session()
    retry = Retry(
        total=retry_total,
        connect=retry_total,
        read=retry_total,
        backoff_factor=backoff_factor,
        status_forcelist=RETRY_STATUS_FORCELIST,
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
