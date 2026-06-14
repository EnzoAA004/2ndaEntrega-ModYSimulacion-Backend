from __future__ import annotations

from typing import Sequence

import numpy as np


def percent_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * 100.0


def moving_average(values: Sequence[float], window: int = 7) -> list[float | None]:
    arr = np.asarray(values, dtype=float)
    result: list[float | None] = []
    for idx in range(len(arr)):
        start = max(0, idx - window + 1)
        chunk = arr[start : idx + 1]
        result.append(float(np.nanmean(chunk)) if len(chunk) else None)
    return result


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default

