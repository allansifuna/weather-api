"""A cache-backed circuit breaker for guarding calls to a flaky external service.

The CB State is stored in cache rather than in-process memory,
so that it is shared across every worker process/thread instead of each worker tripping
its own independent breaker.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeVar

from django.core.cache import cache

T = TypeVar("T")

_KEY_PREFIX = "circuit_breaker"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""

    def __init__(self, name: str, retry_after_seconds: float):
        self.name = name
        self.retry_after_seconds = max(retry_after_seconds, 0.0)
        super().__init__(f"Circuit '{name}' is open; retry after {self.retry_after_seconds:.0f}s")


@dataclass(frozen=True)
class CircuitBreaker:
    """Trips open after 'failure_threshold' failures, rejecting calls for
    'recovery_timeout' seconds before allowing a single half-open trial call.

    Only exceptions passed in 'failure_exceptions' to `call()` count as
    failures. And only those can trip the circuit breaker.
    """

    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    failure_window: float = 60.0

    @property
    def _state_key(self) -> str:
        return f"{_KEY_PREFIX}:{self.name}:state"

    @property
    def _failures_key(self) -> str:
        return f"{_KEY_PREFIX}:{self.name}:failures"

    @property
    def _opened_at_key(self) -> str:
        return f"{_KEY_PREFIX}:{self.name}:opened_at"

    @property
    def state(self) -> CircuitState:
        return CircuitState(cache.get(self._state_key, CircuitState.CLOSED.value))

    def call(self, func: Callable[[], T], *, failure_exceptions: tuple = (Exception,)) -> T:
        """Invoke `func()`, guarded by the breaker. Raises `CircuitBreakerOpenError`
        without calling `func` at all while the circuit is open."""
        state = self.state

        if state == CircuitState.OPEN:
            opened_at = cache.get(self._opened_at_key)
            elapsed = time.time() - opened_at if opened_at is not None else self.recovery_timeout
            if elapsed < self.recovery_timeout:
                raise CircuitBreakerOpenError(self.name, self.recovery_timeout - elapsed)
            # Recovery window elapsed: let exactly one trial call through.
            self._transition(CircuitState.HALF_OPEN)

        try:
            result = func()
        except failure_exceptions:
            self._record_failure()
            raise
        else:
            self._record_success()
            return result

    def _record_success(self) -> None:
        if self.state != CircuitState.CLOSED:
            self._transition(CircuitState.CLOSED)
        cache.delete(self._failures_key)

    def _record_failure(self) -> None:
        failures = cache.get(self._failures_key, 0) + 1
        cache.set(self._failures_key, failures, timeout=self.failure_window)
        if failures >= self.failure_threshold:
            self._transition(CircuitState.OPEN)

    def _transition(self, state: CircuitState) -> None:
        cache.set(self._state_key, state.value, timeout=None)
        if state == CircuitState.OPEN:
            cache.set(self._opened_at_key, time.time(), timeout=None)
        elif state == CircuitState.CLOSED:
            cache.delete(self._opened_at_key)
