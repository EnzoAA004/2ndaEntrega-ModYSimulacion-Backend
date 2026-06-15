from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import WastewaterMeasurement
from app.services.measurement_service import locations, query_location_series
from app.services.risk_service import risk_from_series
from app.utils.math_utils import moving_average, percent_change


CRITICAL_VIRAL_THRESHOLD = 1_000_000
HIGH_VIRAL_THRESHOLD = 100_000


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
