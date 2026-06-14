from __future__ import annotations

from app.utils.math_utils import percent_change


LEVELS = ["Bajo", "Moderado", "Alto", "Crítico"]


def _base_level(viral_concentration_gc_l: float) -> int:
    if viral_concentration_gc_l < 10_000:
        return 0
    if viral_concentration_gc_l < 100_000:
        return 1
    if viral_concentration_gc_l < 1_000_000:
        return 2
    return 3


def _score(level_idx: int, viral_concentration_gc_l: float, trend_7d: float | None, trend_14d: float | None) -> float:
    normalized = min(viral_concentration_gc_l / 1_000_000, 1.5) / 1.5
    trend_bonus = max(trend_7d or 0, 0) / 200 + max(trend_14d or 0, 0) / 300
    return round(min(100.0, level_idx * 25 + normalized * 25 + trend_bonus * 20), 2)


def classify_risk(
    viral_concentration_gc_l: float,
    trend_7d: float | None = None,
    trend_14d: float | None = None,
    clinical_cases: int | None = None,
    viral_precedes_cases: bool = False,
) -> dict:
    level_idx = _base_level(max(viral_concentration_gc_l, 0))
    reasons = [f"Carga viral actual: {viral_concentration_gc_l:,.0f} gc/L."]
    if trend_7d is not None:
        reasons.append(f"Tendencia 7 días: {trend_7d:.1f}%.")
    if trend_14d is not None:
        reasons.append(f"Tendencia 14 días: {trend_14d:.1f}%.")
    if trend_7d is not None and trend_7d > 50:
        level_idx += 1
        reasons.append("Aumento mayor al 50% en 7 días.")
    if trend_14d is not None and trend_14d > 100:
        level_idx += 1
        reasons.append("Aumento mayor al 100% en 14 días.")

    early_warning = bool(viral_precedes_cases or ((trend_7d or 0) > 50 and not clinical_cases))
    if early_warning:
        reasons.append("Posible alerta temprana: la señal viral se acelera antes que los casos clínicos.")
    if clinical_cases and viral_concentration_gc_l < 10_000:
        reasons.append("Inconsistencia posible: hay casos clínicos con señal viral baja.")

    level_idx = min(level_idx, len(LEVELS) - 1)
    return {
        "risk_level": LEVELS[level_idx],
        "risk_score": _score(level_idx, viral_concentration_gc_l, trend_7d, trend_14d),
        "trend_7d": trend_7d,
        "trend_14d": trend_14d,
        "early_warning": early_warning,
        "explanation": " ".join(reasons),
    }


def risk_from_series(values: list[float], clinical_cases: list[int | None] | None = None) -> dict:
    if not values:
        return classify_risk(0)
    current = values[-1]
    trend_7d = percent_change(current, values[-8]) if len(values) >= 8 else None
    trend_14d = percent_change(current, values[-15]) if len(values) >= 15 else None
    recent_cases = None
    if clinical_cases:
        recent_cases = next((case for case in reversed(clinical_cases) if case is not None), None)
    viral_precedes = bool((trend_7d or 0) > 50 and (recent_cases is None or recent_cases < 5))
    return classify_risk(current, trend_7d, trend_14d, recent_cases, viral_precedes)

