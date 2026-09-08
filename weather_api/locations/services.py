"""Pure statistics helpers for turning raw temperature readings into the API response."""

from __future__ import annotations

import statistics
from typing import Sequence


class NoTemperatureDataError(ValueError):
    """Raised when there is no temperature data to summarize."""


def compute_temperature_stats(temperatures: Sequence[float]) -> dict[str, float]:
    """Return the maximum, minimum, average and median of temperatures rounded off to 2dp."""
    if not temperatures:
        raise NoTemperatureDataError("Cannot compute statistics over an empty temperature series")

    return {
        "maximum": round(max(temperatures), 2),
        "minimum": round(min(temperatures), 2),
        "average": round(statistics.fmean(temperatures), 2),
        "median": round(statistics.median(temperatures), 2),
    }
