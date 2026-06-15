from __future__ import annotations

import math
from datetime import timedelta

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import WastewaterMeasurement
from app.services.measurement_service import locations, query_location_series
from app.services.risk_service import risk_from_series
from app.utils.math_utils import moving_average, percent_change


CRITICAL_VIRAL_THRESHOLD = 1_000_000
HIGH_VIRAL_THRESHOLD = 100_000
MODERATE_VIRAL_THRESHOLD = 10_000


def _trend_label(value: float | None) -> str:
    if value is None:
        return "Sin datos"
    if value > 50:
        return "Crecimiento acelerado"
    if value > 15:
        return "Crecimiento moderado"
    if value < -15:
        return "Descenso"
    return "Estable"


def _risk_level_from_value(value: float | None) -> str:
    if value is None:
        return "Sin datos"
    if value >= CRITICAL_VIRAL_THRESHOLD:
        return "Crítico"
    if value >= HIGH_VIRAL_THRESHOLD:
        return "Alto"
    if value >= MODERATE_VIRAL_THRESHOLD:
        return "Moderado"
    return "Bajo"


def _forecast_recommendation(risk_level: str, growth_rate: float, critical_date: str | None, high_date: str | None) -> str:
    if critical_date:
        return f"La proyección cruza umbral crítico alrededor de {critical_date}. Conviene activar vigilancia intensiva y validar con muestreo adicional."
    if high_date:
        return f"La proyección cruza umbral alto alrededor de {high_date}. Conviene sostener monitoreo y preparar intervención preventiva."
    if risk_level in {"Alto", "Crítico"}:
        return "La carga viral proyectada se mantiene elevada. Revisar tendencia reciente, lluvias y casos clínicos rezagados."
    if growth_rate > 0.03:
        return "La tendencia proyectada crece con rapidez aunque todavía no supere umbrales críticos. Conviene monitorear próximos muestreos."
    if growth_rate < -0.01:
        return "La señal proyectada disminuye. Mantener control periódico para confirmar descenso."
    return "La proyección se mantiene estable dentro de la zona esperada."


def overview(db: Session) -> dict:
    total = db.query(func.count(WastewaterMeasurement.id)).scalar() or 0
    locs = locations(db)
    avg_viral = db.query(func.avg(WastewaterMeasurement.viral_concentration_gc_l)).scalar()
    risk_rows = risk_table(db)
    highest = max(risk_rows, key=lambda item: item["risk_score"], default=None)
    latest_risk = highest["risk_level"] if highest else "Sin datos"
    recent_values = [row.viral_concentration_gc_l for row in db.query(WastewaterMeasurement).order_by(WastewaterMeasurement.sample_date.desc()).limit(31).all()]
    recent_values = list(reversed(recent_values))
    trend_14d = percent_change(recent_values[-1], recent_values[-15]) if len(recent_values) >= 15 else None
    trend_30d = percent_change(recent_values[-1], recent_values[-31]) if len(recent_values) >= 31 else None
    critical_locations = sum(1 for row in risk_rows if row.get("risk_level") == "Crítico")
    high_locations = sum(1 for row in risk_rows if row.get("risk_level") in {"Alto", "Crítico"})
    early_warning_locations = sum(1 for row in risk_rows if row.get("early_warning"))
    return {
        "total_measurements": total,
        "active_locations": len(locs),
        "latest_risk_level": latest_risk,
        "highest_risk_location": highest["location_name"] if highest else None,
        "average_viral_load": float(avg_viral) if avg_viral is not None else None,
        "trend_14d": trend_14d,
        "trend_last_14_days": trend_14d,
        "trend_last_30_days": trend_30d,
        "trend_label": _trend_label(trend_14d),
        "critical_locations": critical_locations,
        "high_locations": high_locations,
        "early_warning_locations": early_warning_locations,
        "status_message": (
            "Sin mediciones cargadas. Generá datos demo para activar el monitoreo."
            if total == 0
            else f"{latest_risk}. {high_locations} ubicaciones en riesgo alto o crítico. {early_warning_locations} alertas tempranas activas."
        ),
    }


def location_analysis(db: Session, location_name: str) -> dict:
    rows = query_location_series(db, location_name)
    values = [row.viral_concentration_gc_l for row in rows]
    cases = [row.clinical_cases for row in rows]
    if not rows:
        return {
            "location_name": location_name,
            "series": [],
            "time_series": [],
            "moving_average_7d": [],
            "variation_7d": None,
            "variation_14d": None,
            "risk": risk_from_series([]),
            "early_warning": False,
            "explanation": "No hay mediciones para esta ubicación.",
            "thresholds": {"high": HIGH_VIRAL_THRESHOLD, "critical": CRITICAL_VIRAL_THRESHOLD},
        }
    risk = risk_from_series(values, cases)
    moving_7d = moving_average(values, 7)
    series = [
        {
            "sample_date": row.sample_date,
            "location_name": row.location_name,
            "city": row.city,
            "country": row.country,
            "viral_concentration_gc_l": row.viral_concentration_gc_l,
            "moving_average_7d": moving_7d[idx] if idx < len(moving_7d) else None,
            "clinical_cases": row.clinical_cases,
            "flow_rate_m3_day": row.flow_rate_m3_day,
            "rainfall_mm": row.rainfall_mm,
            "temperature_c": row.temperature_c,
        }
        for idx, row in enumerate(rows)
    ]
    variation_7d = percent_change(values[-1], values[-8]) if len(values) >= 8 else None
    variation_14d = percent_change(values[-1], values[-15]) if len(values) >= 15 else None
    return {
        "location_name": location_name,
        "series": series,
        "time_series": series,
        "moving_average_7d": moving_7d,
        "variation_7d": variation_7d,
        "variation_14d": variation_14d,
        "risk": risk,
        "early_warning": risk["early_warning"],
        "explanation": risk["explanation"],
        "thresholds": {"high": HIGH_VIRAL_THRESHOLD, "critical": CRITICAL_VIRAL_THRESHOLD},
    }


def forecast_location(db: Session, location_name: str, horizon: int = 21, window: int = 45) -> dict:
    horizon = max(7, min(int(horizon), 90))
    window = max(14, min(int(window), 180))
    rows = query_location_series(db, location_name)
    if len(rows) < 7:
        return {
            "location_name": location_name,
            "horizon_days": horizon,
            "window_days": window,
            "history": [],
            "forecast": [],
            "scenarios": [],
            "summary": {
                "status": "insufficient_data",
                "message": "Se necesitan al menos 7 mediciones para generar predicción.",
            },
            "thresholds": {"high": HIGH_VIRAL_THRESHOLD, "critical": CRITICAL_VIRAL_THRESHOLD},
        }

    selected = rows[-window:]
    first_date = selected[0].sample_date
    x = np.array([(row.sample_date - first_date).days for row in selected], dtype=float)
    y_raw = np.array([max(float(row.viral_concentration_gc_l or 0), 1.0) for row in selected], dtype=float)
    y_log = np.log(y_raw)

    if len(np.unique(x)) < 2:
        slope = 0.0
        intercept = float(y_log[-1])
        residual_std = 0.15
    else:
        slope, intercept = np.polyfit(x, y_log, 1)
        residuals = y_log - (slope * x + intercept)
        residual_std = float(np.std(residuals)) if len(residuals) > 2 else 0.15
        residual_std = max(residual_std, 0.08)

    last_date = selected[-1].sample_date
    last_x = float(x[-1])
    future_days = np.arange(1, horizon + 1, dtype=float)
    future_x = last_x + future_days
    prediction_log = slope * future_x + intercept
    lower_log = prediction_log - 1.96 * residual_std
    upper_log = prediction_log + 1.96 * residual_std

    predictions = np.exp(prediction_log)
    lower = np.exp(lower_log)
    upper = np.exp(upper_log)

    forecast = []
    high_crossing_date = None
    critical_crossing_date = None
    for idx, day in enumerate(future_days):
        forecast_date = last_date + timedelta(days=int(day))
        value = float(predictions[idx])
        if high_crossing_date is None and value >= HIGH_VIRAL_THRESHOLD:
            high_crossing_date = forecast_date.isoformat()
        if critical_crossing_date is None and value >= CRITICAL_VIRAL_THRESHOLD:
            critical_crossing_date = forecast_date.isoformat()
        forecast.append(
            {
                "sample_date": forecast_date.isoformat(),
                "predicted_viral_concentration_gc_l": value,
                "lower_bound": float(lower[idx]),
                "upper_bound": float(upper[idx]),
                "risk_level": _risk_level_from_value(value),
            }
        )

    scenario_configs = [
        ("Mitigación", slope * 0.55),
        ("Base", slope),
        ("Crecimiento alto", slope * 1.35 + (0.01 if slope >= 0 else 0.0)),
    ]
    scenarios = []
    for name, scenario_slope in scenario_configs:
        values = np.exp(scenario_slope * future_x + intercept)
        scenarios.append(
            {
                "name": name,
                "series": [
                    {
                        "sample_date": (last_date + timedelta(days=int(day))).isoformat(),
                        "predicted_viral_concentration_gc_l": float(values[idx]),
                    }
                    for idx, day in enumerate(future_days)
                ],
            }
        )

    max_forecast = float(np.max(predictions)) if len(predictions) else None
    final_forecast = float(predictions[-1]) if len(predictions) else None
    projected_change = percent_change(final_forecast, y_raw[-1]) if final_forecast is not None else None
    doubling_time_days = float(math.log(2) / slope) if slope > 0 else None
    risk_level = _risk_level_from_value(max_forecast)
    trend_label = "creciente" if slope > 0.01 else "descendente" if slope < -0.01 else "estable"

    history = [
        {
            "sample_date": row.sample_date.isoformat(),
            "viral_concentration_gc_l": float(row.viral_concentration_gc_l or 0),
            "clinical_cases": row.clinical_cases,
            "rainfall_mm": row.rainfall_mm,
        }
        for row in selected
    ]

    return {
        "location_name": location_name,
        "horizon_days": horizon,
        "window_days": window,
        "history": history,
        "forecast": forecast,
        "scenarios": scenarios,
        "thresholds": {"high": HIGH_VIRAL_THRESHOLD, "critical": CRITICAL_VIRAL_THRESHOLD},
        "summary": {
            "status": "ok",
            "trend": trend_label,
            "growth_rate_log_per_day": float(slope),
            "doubling_time_days": doubling_time_days,
            "projected_change_percent": projected_change,
            "max_predicted_viral_concentration_gc_l": max_forecast,
            "final_predicted_viral_concentration_gc_l": final_forecast,
            "forecast_risk_level": risk_level,
            "high_threshold_crossing_date": high_crossing_date,
            "critical_threshold_crossing_date": critical_crossing_date,
            "confidence_band_log_std": residual_std,
            "recommendation": _forecast_recommendation(risk_level, float(slope), critical_crossing_date, high_crossing_date),
        },
    }


def risk_table(db: Session) -> list[dict]:
    result = []
    for item in locations(db):
        rows = query_location_series(db, item["location_name"])
        values = [row.viral_concentration_gc_l for row in rows]
        cases = [row.clinical_cases for row in rows]
        risk = risk_from_series(values, cases)
        latest = rows[-1] if rows else None
        result.append(
            {
                "location_name": item["location_name"],
                "city": item["city"],
                "country": item["country"],
                "samples": item["samples"],
                "latest_sample_date": item["latest_sample_date"],
                "latest_viral_concentration_gc_l": latest.viral_concentration_gc_l if latest else None,
                "latest_clinical_cases": latest.clinical_cases if latest else None,
                "latest_rainfall_mm": latest.rainfall_mm if latest else None,
                **risk,
            }
        )
    return sorted(result, key=lambda row: row["risk_score"], reverse=True)
