from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import WastewaterMeasurement
from app.services.measurement_service import locations, query_location_series
from app.services.risk_service import risk_from_series
from app.utils.math_utils import moving_average, percent_change


def overview(db: Session) -> dict:
    total = db.query(func.count(WastewaterMeasurement.id)).scalar() or 0
    locs = locations(db)
    avg_viral = db.query(func.avg(WastewaterMeasurement.viral_concentration_gc_l)).scalar()
    risk_rows = risk_table(db)
    highest = max(risk_rows, key=lambda item: item["risk_score"], default=None)
    latest_risk = highest["risk_level"] if highest else "Sin datos"
    recent_values = [row.viral_concentration_gc_l for row in db.query(WastewaterMeasurement).order_by(WastewaterMeasurement.sample_date.desc()).limit(31).all()]
    recent_values = list(reversed(recent_values))
    return {
        "total_measurements": total,
        "active_locations": len(locs),
        "latest_risk_level": latest_risk,
        "highest_risk_location": highest["location_name"] if highest else None,
        "average_viral_load": float(avg_viral) if avg_viral is not None else None,
        "trend_last_14_days": percent_change(recent_values[-1], recent_values[-15]) if len(recent_values) >= 15 else None,
        "trend_last_30_days": percent_change(recent_values[-1], recent_values[-31]) if len(recent_values) >= 31 else None,
    }


def location_analysis(db: Session, location_name: str) -> dict:
    rows = query_location_series(db, location_name)
    values = [row.viral_concentration_gc_l for row in rows]
    cases = [row.clinical_cases for row in rows]
    if not rows:
        return {
            "location_name": location_name,
            "time_series": [],
            "moving_average_7d": [],
            "variation_7d": None,
            "variation_14d": None,
            "risk": risk_from_series([]),
            "early_warning": False,
        }
    risk = risk_from_series(values, cases)
    return {
        "location_name": location_name,
        "time_series": [
            {
                "sample_date": row.sample_date,
                "viral_concentration_gc_l": row.viral_concentration_gc_l,
                "clinical_cases": row.clinical_cases,
                "flow_rate_m3_day": row.flow_rate_m3_day,
                "rainfall_mm": row.rainfall_mm,
            }
            for row in rows
        ],
        "moving_average_7d": moving_average(values, 7),
        "variation_7d": percent_change(values[-1], values[-8]) if len(values) >= 8 else None,
        "variation_14d": percent_change(values[-1], values[-15]) if len(values) >= 15 else None,
        "risk": risk,
        "early_warning": risk["early_warning"],
    }


def risk_table(db: Session) -> list[dict]:
    result = []
    for item in locations(db):
        rows = query_location_series(db, item["location_name"])
        values = [row.viral_concentration_gc_l for row in rows]
        cases = [row.clinical_cases for row in rows]
        risk = risk_from_series(values, cases)
        result.append(
            {
                "location_name": item["location_name"],
                "city": item["city"],
                "country": item["country"],
                "samples": item["samples"],
                "latest_sample_date": item["latest_sample_date"],
                **risk,
            }
        )
    return sorted(result, key=lambda row: row["risk_score"], reverse=True)

