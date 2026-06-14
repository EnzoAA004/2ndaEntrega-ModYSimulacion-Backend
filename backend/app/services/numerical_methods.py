from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np


State = float | list[float] | np.ndarray
Derivative = Callable[[float, np.ndarray, dict[str, Any]], State]


def _as_array(value: State) -> np.ndarray:
    return np.asarray(value, dtype=float)


def _finalize(times: list[float], values: list[np.ndarray], scalar: bool) -> tuple[list[float], list[Any]]:
    if scalar:
        return times, [float(v.reshape(-1)[0]) for v in values]
    return times, [v.astype(float).tolist() for v in values]


def _clip_if_needed(y: np.ndarray, non_negative: bool) -> np.ndarray:
    return np.maximum(y, 0.0) if non_negative else y


def _time_grid(t0: float, tf: float, h: float) -> list[float]:
    if h <= 0 or tf <= t0:
        raise ValueError("Invalid integration interval or step")
    values = list(np.arange(t0, tf + h * 0.5, h, dtype=float))
    if values[-1] > tf:
        values[-1] = tf
    elif values[-1] < tf:
        values.append(tf)
    return [float(round(t, 12)) for t in values]


def euler(
    f: Derivative,
    y0: State,
    t0: float,
    tf: float,
    h: float,
    params: dict[str, Any] | None = None,
    non_negative: bool = True,
) -> tuple[list[float], list[Any]]:
    """Integrate y'=f(t,y) with explicit Euler for scalar or vector states."""
    params = params or {}
    y = _as_array(y0)
    scalar = y.ndim == 0
    y = y.reshape(1) if scalar else y
    times = _time_grid(t0, tf, h)
    values = [y.copy()]
    for current, nxt in zip(times[:-1], times[1:]):
        dt = nxt - current
        y = y + dt * _as_array(f(current, y.copy(), params))
        y = _clip_if_needed(y, non_negative)
        values.append(y.copy())
    return _finalize(times, values, scalar)


def heun(
    f: Derivative,
    y0: State,
    t0: float,
    tf: float,
    h: float,
    params: dict[str, Any] | None = None,
    non_negative: bool = True,
) -> tuple[list[float], list[Any]]:
    """Integrate y'=f(t,y) with the improved Euler/Heun method."""
    params = params or {}
    y = _as_array(y0)
    scalar = y.ndim == 0
    y = y.reshape(1) if scalar else y
    times = _time_grid(t0, tf, h)
    values = [y.copy()]
    for current, nxt in zip(times[:-1], times[1:]):
        dt = nxt - current
        k1 = _as_array(f(current, y.copy(), params))
        predictor = _clip_if_needed(y + dt * k1, non_negative)
        k2 = _as_array(f(nxt, predictor.copy(), params))
        y = y + 0.5 * dt * (k1 + k2)
        y = _clip_if_needed(y, non_negative)
        values.append(y.copy())
    return _finalize(times, values, scalar)


def rk4(
    f: Derivative,
    y0: State,
    t0: float,
    tf: float,
    h: float,
    params: dict[str, Any] | None = None,
    non_negative: bool = True,
) -> tuple[list[float], list[Any]]:
    """Integrate y'=f(t,y) with fourth-order Runge-Kutta."""
    params = params or {}
    y = _as_array(y0)
    scalar = y.ndim == 0
    y = y.reshape(1) if scalar else y
    times = _time_grid(t0, tf, h)
    values = [y.copy()]
    for current, nxt in zip(times[:-1], times[1:]):
        dt = nxt - current
        k1 = _as_array(f(current, y.copy(), params))
        k2 = _as_array(f(current + dt / 2, y + dt * k1 / 2, params))
        k3 = _as_array(f(current + dt / 2, y + dt * k2 / 2, params))
        k4 = _as_array(f(nxt, y + dt * k3, params))
        y = y + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6
        y = _clip_if_needed(y, non_negative)
        values.append(y.copy())
    return _finalize(times, values, scalar)


METHODS = {"euler": euler, "heun": heun, "rk4": rk4}

