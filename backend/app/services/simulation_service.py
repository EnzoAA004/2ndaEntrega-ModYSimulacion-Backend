from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.models import SimulationRun
from app.schemas import (
    BifurcationRequest,
    InfectionWastewaterRequest,
    LyapunovRiskRequest,
    NonHomogeneousEventRequest,
    PhaseDiagramRequest,
    ViralDecayRequest,
)
from app.services.numerical_methods import METHODS
from app.services.risk_service import classify_risk, risk_from_series
from app.services.stability_service import analyze_iv_model_equilibria, classify_1d_equilibrium, eigenvalues_json
from app.utils.json_utils import dumps, loads


def _save_run(
    db: Session | None,
    name: str,
    model_type: str,
    parameters: dict,
    initial_conditions: dict,
    result: dict,
) -> int | None:
    if db is None:
        return None
    row = SimulationRun(
        name=name,
        model_type=model_type,
        location_name=parameters.get("location_name"),
        parameters_json=dumps(parameters),
        initial_conditions_json=dumps(initial_conditions),
        result_json=dumps(result),
        equilibrium_json=dumps(result.get("equilibria")),
        stability_json=dumps(result.get("stability")),
        risk_json=dumps(result.get("risk")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def viral_decay_1d(request: ViralDecayRequest, db: Session | None = None) -> dict:
    def f(_t, y, p):
        return np.array([p["S"] - (p["k"] + p["d"]) * y[0]])

    params = request.model_dump(exclude={"name", "save"})
    t, values = METHODS[request.method](f, request.V0, 0, request.t_final, request.step, params)
    equilibrium = request.S / (request.k + request.d)
    stability = {
        "classification": classify_1d_equilibrium(-(request.k + request.d)),
        "explanation": "V* es estable porque k + d > 0.",
    }
    risk = risk_from_series(values)
    result = {
        "model_type": "viral-decay-1d",
        "parameters": params,
        "initial_conditions": {"V0": request.V0},
        "time": t,
        "series": {"V": values},
        "equilibria": [{"values": {"V": equilibrium}, "stable": True, "classification": stability["classification"]}],
        "stability": stability,
        "risk": risk,
        "interpretation": "Modelo 1D con aporte viral, decaimiento y dilución hidráulica.",
        "method_used": request.method,
        "saved_simulation_id": None,
    }
    if request.save:
        result["saved_simulation_id"] = _save_run(db, request.name or "Viral decay 1D", "viral-decay-1d", params, {"V0": request.V0}, result)
    return result


def infection_wastewater_2d(request: InfectionWastewaterRequest, db: Session | None = None) -> dict:
    def f(_t, y, p):
        I, V = y
        dI = p["beta"] * I * (1 - I / p["K"]) - p["gamma"] * I
        dV = p["alpha"] * I - (p["k"] + p["d"]) * V
        return np.array([dI, dV])

    params = request.model_dump(exclude={"name", "save"})
    t, values = METHODS[request.method](f, [request.I0, request.V0], 0, request.t_final, request.step, params)
    I_values = [float(row[0]) for row in values]
    V_values = [float(row[1]) for row in values]
    equilibria = analyze_iv_model_equilibria(request.beta, request.K, request.gamma, request.alpha, request.k, request.d)
    chosen = equilibria[-1]
    risk_by_time = [classify_risk(v)["risk_score"] for v in V_values]
    stability = {
        "classification": chosen["classification"],
        "eigenvalues": chosen["eigenvalues"],
        "equilibria_analysis": equilibria,
    }
    result = {
        "model_type": "infection-wastewater-2d",
        "parameters": params,
        "initial_conditions": {"I0": request.I0, "V0": request.V0},
        "time": t,
        "series": {"I": I_values, "V": V_values},
        "equilibria": equilibria,
        "stability": stability,
        "risk": {**risk_from_series(V_values), "risk_by_time": risk_by_time},
        "interpretation": "Modelo acoplado infección-carga viral con equilibrio positivo si beta > gamma.",
        "max_infection_time": t[int(np.argmax(I_values))],
        "max_viral_load_time": t[int(np.argmax(V_values))],
        "method_used": request.method,
        "saved_simulation_id": None,
    }
    if request.save:
        result["saved_simulation_id"] = _save_run(db, request.name or "Infection wastewater 2D", "infection-wastewater-2d", params, {"I0": request.I0, "V0": request.V0}, result)
    return result


def non_homogeneous_event(request: NonHomogeneousEventRequest, db: Session | None = None) -> dict:
    def source(t: float, p: dict[str, Any]) -> float:
        if p["event_type"] == "sinusoidal":
            return max(0.0, p["base_source"] + p["amplitude"] * np.sin(2 * np.pi * p["frequency"] * t))
        if p["event_type"] == "outbreak_shock" and p.get("shock_start") is not None and p["shock_start"] <= t <= (p.get("shock_end") or p["shock_start"]):
            return p["base_source"] + p["shock_magnitude"]
        return p["base_source"]

    def f(t, y, p):
        removal = p["k"] + p["d"]
        if p["event_type"] == "rainfall_dilution" and p.get("rainfall_start") is not None and p["rainfall_start"] <= t <= (p.get("rainfall_end") or p["rainfall_start"]):
            removal *= p["dilution_multiplier"]
        return np.array([source(t, p) - removal * y[0]])

    params = request.model_dump(exclude={"name", "save"})
    t, values = METHODS[request.method](f, request.V0, 0, request.t_final, request.step, params)
    event_source = [source(item, params) for item in t]
    result = {
        "model_type": "non-homogeneous-event",
        "parameters": params,
        "initial_conditions": {"V0": request.V0},
        "time": t,
        "series": {"V": values, "S_t": event_source},
        "equilibria": [],
        "stability": {"classification": "time_dependent", "explanation": "Sistema no autónomo con fuente/evento externo."},
        "risk": risk_from_series(values),
        "interpretation": f"Evento {request.event_type} aplicado a la fuente o dilución.",
        "method_used": request.method,
        "saved_simulation_id": None,
    }
    if request.save:
        result["saved_simulation_id"] = _save_run(db, request.name or "Non homogeneous event", "non-homogeneous-event", params, {"V0": request.V0}, result)
    return result


def bifurcation(request: BifurcationRequest) -> dict:
    values = np.linspace(request.parameter_min, request.parameter_max, request.steps)
    equilibria = []
    stability = []
    for value in values:
        beta = float(value) if request.parameter_name == "beta" else request.beta
        gamma = float(value) if request.parameter_name == "gamma" else request.gamma
        points = [{"I": 0.0, "branch": "disease_free", "stable": beta <= gamma}]
        if beta > gamma:
            points.append({"I": float(request.K * (1 - gamma / beta)), "branch": "endemic", "stable": True})
        equilibria.append(points)
        stability.append("outbreak_possible" if beta > gamma else "disease_free_stable")
    return {
        "parameter_values": [float(v) for v in values],
        "equilibria": equilibria,
        "stability": stability,
        "threshold_info": {"condition": "beta > gamma", "message": "Existe umbral de brote cuando beta supera gamma."},
    }


def phase_diagram(request: PhaseDiagramRequest) -> dict:
    I_values = np.linspace(request.I_min, request.I_max, request.grid_size)
    V_values = np.linspace(request.V_min, request.V_max, request.grid_size)
    grid_points = []
    vectors = []
    for I in I_values:
        for V in V_values:
            dI = request.beta * I * (1 - I / request.K) - request.gamma * I
            dV = request.alpha * I - (request.k + request.d) * V
            grid_points.append({"I": float(I), "V": float(V)})
            vectors.append({"dI": float(dI), "dV": float(dV)})
    endemic_I = request.K * (1 - request.gamma / request.beta) if request.beta > request.gamma else None
    return {
        "grid_points": grid_points,
        "vectors": vectors,
        "nullclines": {
            "dI_dt": [{"I": 0.0}, {"I": float(endemic_I)}] if endemic_I is not None else [{"I": 0.0}],
            "dV_dt": {"formula": "V = alpha I / (k + d)"},
        },
        "equilibria": analyze_iv_model_equilibria(request.beta, request.K, request.gamma, request.alpha, request.k, request.d),
    }


def lyapunov_risk(request: LyapunovRiskRequest) -> dict:
    if request.parameters:
        sim = infection_wastewater_2d(request.parameters, None)
        I_values = sim["series"]["I"]
        V_values = sim["series"]["V"]
        time = sim["time"]
    else:
        I_values = request.I_values or []
        V_values = request.V_values or []
        time = list(range(min(len(I_values), len(V_values))))
    n = min(len(I_values), len(V_values))
    risk_values = [
        float(request.a * max(0, I_values[i] - request.I_safe) ** 2 + request.b * max(0, V_values[i] - request.V_safe) ** 2)
        for i in range(n)
    ]
    if len(risk_values) < 2:
        trend = "stable"
    elif risk_values[-1] > risk_values[0] * 1.05:
        trend = "increasing"
    elif risk_values[-1] < risk_values[0] * 0.95:
        trend = "decreasing"
    else:
        trend = "stable"
    violations = [idx for idx in range(n) if I_values[idx] > request.I_safe or V_values[idx] > request.V_safe]
    return {
        "time": time[:n],
        "V_risk": risk_values,
        "risk_trend": trend,
        "safe_region_violations": violations,
        "interpretation": "Función tipo Lyapunov basada en excesos sobre umbrales seguros.",
    }


def list_simulations(db: Session) -> list[dict]:
    rows = db.query(SimulationRun).order_by(SimulationRun.created_at.desc()).all()
    return [simulation_to_read(row) for row in rows]


def simulation_to_read(row: SimulationRun) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "model_type": row.model_type,
        "location_name": row.location_name,
        "parameters": loads(row.parameters_json, {}),
        "initial_conditions": loads(row.initial_conditions_json, {}),
        "result": loads(row.result_json, {}),
        "equilibria": loads(row.equilibrium_json, None),
        "stability": loads(row.stability_json, None),
        "risk": loads(row.risk_json, None),
        "created_at": row.created_at,
    }
