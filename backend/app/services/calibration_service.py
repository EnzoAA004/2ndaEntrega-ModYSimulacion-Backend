from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.schemas import CalibrationRequest
from app.services.measurement_service import query_location_series


def calibrate(db: Session, request: CalibrationRequest) -> dict:
    rows = query_location_series(db, request.location_name, request.date_from, request.date_to)
    if len(rows) < 3:
        raise ValueError("Se necesitan al menos 3 mediciones para calibrar.")
    viral = np.asarray([row.viral_concentration_gc_l for row in rows], dtype=float)
    flow = np.asarray([row.flow_rate_m3_day for row in rows], dtype=float)
    rainfall = np.asarray([row.rainfall_mm or 0 for row in rows], dtype=float)
    log_growth = np.diff(np.log(np.maximum(viral, 1.0)))
    beta = float(max(0.001, np.nanmean(log_growth[log_growth > -2]) if log_growth.size else 0.05))
    source_mean = float(np.nanmean(viral) * 0.12)
    dilution = float(np.nanmean(flow / np.nanmean(flow)) * 0.03 + np.nanmean(rainfall) / 1000)
    decay = 0.08
    return {
        "location_name": request.location_name,
        "model_type": request.model_type,
        "estimated_parameters": {
            "beta": beta,
            "S": source_mean,
            "d": dilution,
            "k": decay,
            "V0": float(viral[0]),
            "alpha": float(source_mean / max(1.0, np.nanmean([row.clinical_cases or 1 for row in rows]))),
            "gamma": 0.05,
        },
        "data_points": len(rows),
        "date_range": {"from": rows[0].sample_date, "to": rows[-1].sample_date},
        "explanation": "Estimación inicial basada en crecimiento logarítmico de carga viral, caudal y lluvia.",
    }
