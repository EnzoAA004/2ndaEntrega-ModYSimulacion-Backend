from __future__ import annotations

import math

import numpy as np
from sqlalchemy.orm import Session

from app.schemas import CalibrationRequest
from app.services.measurement_service import query_location_series


def calibrate(db: Session, request: CalibrationRequest) -> dict:
    rows = query_location_series(db, request.location_name, request.date_from, request.date_to)
    if len(rows) < 3:
        raise ValueError("Se necesitan al menos 3 mediciones para calibrar.")

    viral = np.asarray([max(row.viral_concentration_gc_l or 0, 1.0) for row in rows], dtype=float)
    flow = np.asarray([max(row.flow_rate_m3_day or 1.0, 1.0) for row in rows], dtype=float)
    rainfall = np.asarray([row.rainfall_mm or 0 for row in rows], dtype=float)
    cases = np.asarray([row.clinical_cases or 0 for row in rows], dtype=float)

    log_growth = np.diff(np.log(np.maximum(viral, 1.0)))
    valid_growth = log_growth[np.isfinite(log_growth)]
    beta = float(max(0.001, np.nanmean(valid_growth[valid_growth > -2]) if valid_growth.size else 0.05))
    beta = float(min(max(beta + 0.08, 0.05), 0.8))

    avg_cases = float(max(np.nanmean(cases[cases > 0]) if np.any(cases > 0) else 100.0, 1.0))
    source_mean = float(max(np.nanmean(viral) * 0.12, 1.0))
    flow_ratio = flow / max(float(np.nanmean(flow)), 1.0)
    dilution = float(max(0.005, np.nanmean(flow_ratio) * 0.03 + np.nanmean(rainfall) / 1000))
    decay = 0.08
    gamma = float(max(0.03, min(0.25, beta * 0.45)))
    alpha = float(max(1.0, source_mean / avg_cases))
    K = float(max(10_000.0, avg_cases * 25, np.nanmax(cases) * 20 if np.any(cases > 0) else 100_000.0))
    v0 = float(viral[0])
    i0 = float(max(cases[0] if cases[0] > 0 else avg_cases * 0.25, 1.0))

    fitted_log = np.log(v0) + np.arange(len(viral)) * np.nanmean(valid_growth if valid_growth.size else [0])
    fitted = np.exp(fitted_log)
    rmse = float(np.sqrt(np.nanmean((viral - fitted) ** 2)))
    mape = float(np.nanmean(np.abs((viral - fitted) / np.maximum(viral, 1.0))) * 100)

    viral_decay_payload = {
        "S": source_mean,
        "k": decay,
        "d": dilution,
        "V0": v0,
        "t_final": 60,
        "step": 1,
        "method": "rk4",
        "save": True,
    }
    infection_payload = {
        "beta": beta,
        "K": K,
        "gamma": gamma,
        "alpha": alpha,
        "k": decay,
        "d": dilution,
        "I0": i0,
        "V0": v0,
        "t_final": 90,
        "step": 1,
        "method": "rk4",
        "save": True,
    }

    doubling_time = float(math.log(2) / beta) if beta > 0 else None

    return {
        "location_name": request.location_name,
        "model_type": request.model_type,
        "estimated_parameters": {
            "beta": beta,
            "S": source_mean,
            "d": dilution,
            "k": decay,
            "V0": v0,
            "I0": i0,
            "K": K,
            "alpha": alpha,
            "gamma": gamma,
            "doubling_time_days": doubling_time,
        },
        "fit_quality": {
            "rmse_viral_load": rmse,
            "mape_percent": mape,
            "data_points": len(rows),
        },
        "ready_to_run_payloads": {
            "viral_decay_1d": viral_decay_payload,
            "infection_wastewater_2d": infection_payload,
        },
        "data_points": len(rows),
        "date_range": {"from": rows[0].sample_date, "to": rows[-1].sample_date},
        "explanation": "Estimación inicial basada en crecimiento logarítmico de carga viral, caudal, lluvia y casos clínicos. Los payloads generados se pueden usar directamente en las simulaciones 1D y 2D.",
    }
