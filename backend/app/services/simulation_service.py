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
from app.services.stability_service import analyze_iv_model_equilibria, classify_1d_equilibrium
from app.utils.json_utils import dumps, loads


METHOD_LABELS = {"euler": "Euler", "heun": "Heun", "rk4": "Runge-Kutta 4"}


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


def _comparison_scalar(f, y0: float, t_final: float, step: float, params: dict[str, Any]) -> dict:
    rows = []
    for method, solver in METHODS.items():
        t, values = solver(f, y0, 0, t_final, step, params)
        max_idx = int(np.argmax(values)) if values else 0
        rows.append(
            {
                "method": method,
                "label": METHOD_LABELS[method],
                "final_value": float(values[-1]) if values else 0.0,
                "max_value": float(max(values)) if values else 0.0,
                "max_time": float(t[max_idx]) if t else 0.0,
                "series": values,
            }
        )
    return {"type": "scalar", "rows": rows}


def _comparison_vector(f, y0: list[float], t_final: float, step: float, params: dict[str, Any]) -> dict:
    rows = []
    for method, solver in METHODS.items():
        t, values = solver(f, y0, 0, t_final, step, params)
        I_values = [float(row[0]) for row in values]
        V_values = [float(row[1]) for row in values]
        max_i_idx = int(np.argmax(I_values)) if I_values else 0
        max_v_idx = int(np.argmax(V_values)) if V_values else 0
        rows.append(
            {
                "method": method,
                "label": METHOD_LABELS[method],
                "final_I": float(I_values[-1]) if I_values else 0.0,
                "final_V": float(V_values[-1]) if V_values else 0.0,
                "max_I": float(max(I_values)) if I_values else 0.0,
                "max_I_time": float(t[max_i_idx]) if t else 0.0,
                "max_V": float(max(V_values)) if V_values else 0.0,
                "max_V_time": float(t[max_v_idx]) if t else 0.0,
                "series": {"I": I_values, "V": V_values},
            }
        )
    return {"type": "vector", "rows": rows}


def _lyapunov_payload(time: list[float], I_values: list[float], V_values: list[float], I_safe: float, V_safe: float) -> dict:
    values = [float(max(0, i - I_safe) ** 2 + 1e-8 * max(0, v - V_safe) ** 2) for i, v in zip(I_values, V_values)]
    if len(values) < 2:
        trend = "stable"
    elif values[-1] > values[0] * 1.05:
        trend = "increasing"
    elif values[-1] < values[0] * 0.95:
        trend = "decreasing"
    else:
        trend = "stable"
    violations = sum(1 for i, v in zip(I_values, V_values) if i > I_safe or v > V_safe)
    return {
        "time": time,
        "values": values,
        "trend": trend,
        "increasing": trend == "increasing",
        "safe_region_violations": violations,
        "I_safe": I_safe,
        "V_safe": V_safe,
        "explanation": "V_risk mide excesos respecto de una región segura definida por I_safe y V_safe.",
    }


def viral_decay_1d(request: ViralDecayRequest, db: Session | None = None) -> dict:
    def f(_t, y, p):
        return np.array([p["S"] - (p["k"] + p["d"]) * y[0]])

    params = request.model_dump(exclude={"name", "save"})
    t, values = METHODS[request.method](f, request.V0, 0, request.t_final, request.step, params)
    equilibrium = request.S / (request.k + request.d)
    stability = {
        "classification": classify_1d_equilibrium(-(request.k + request.d)),
        "explanation": "V* es estable porque k + d > 0; la carga viral converge al equilibrio S/(k+d).",
    }
    risk = risk_from_series(values)
    comparison = _comparison_scalar(f, request.V0, request.t_final, request.step, params)
    result = {
        "model_type": "viral-decay-1d",
        "parameters": params,
        "initial_conditions": {"V0": request.V0},
        "time": t,
        "series": {"V": values},
        "equilibria": [{"values": {"V": equilibrium}, "stable": True, "classification": stability["classification"]}],
        "stability": stability,
        "risk": risk,
        "interpretation": "Modelo 1D con aporte viral, decaimiento y dilución hidráulica. Permite observar convergencia a un equilibrio estable.",
        "method_used": request.method,
        "method_comparison": comparison,
        "max_viral_load": float(max(values)) if values else 0.0,
        "max_viral_load_time": t[int(np.argmax(values))] if values else 0.0,
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
        "explanation": "La estabilidad local se clasifica a partir de autovalores del jacobiano en el equilibrio relevante.",
    }
    comparison = _comparison_vector(f, [request.I0, request.V0], request.t_final, request.step, params)
    lyapunov = _lyapunov_payload(t, I_values, V_values, I_safe=request.K * 0.05, V_safe=100_000)
    result = {
        "model_type": "infection-wastewater-2d",
        "parameters": params,
        "initial_conditions": {"I0": request.I0, "V0": request.V0},
        "time": t,
        "series": {"I": I_values, "V": V_values, "risk_score": risk_by_time},
        "equilibria": equilibria,
        "stability": stability,
        "risk": {**risk_from_series(V_values), "risk_by_time": risk_by_time},
        "lyapunov": lyapunov,
        "method_comparison": comparison,
        "interpretation": "Modelo acoplado infección-carga viral. Si beta supera gamma, aparece un equilibrio positivo asociado a circulación persistente.",
        "max_infected": float(max(I_values)) if I_values else 0.0,
        "max_infection_time": t[int(np.argmax(I_values))] if I_values else 0.0,
        "max_viral_load": float(max(V_values)) if V_values else 0.0,
        "max_viral_load_time": t[int(np.argmax(V_values))] if V_values else 0.0,
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
        "interpretation": f"Evento {request.event_type} aplicado a la fuente o dilución. Permite estudiar forzamientos externos y shocks temporales.",
        "method_used": request.method,
        "method_comparison": _comparison_scalar(f, request.V0, request.t_final, request.step, params),
        "event_window": [request.shock_start or request.rainfall_start or 0, request.shock_end or request.rainfall_end or 0],
        "max_viral_load": float(max(values)) if values else 0.0,
        "saved_simulation_id": None,
    }
    if request.save:
        result["saved_simulation_id"] = _save_run(db, request.name or "Non homogeneous event", "non-homogeneous-event", params, {"V0": request.V0}, result)
    return result


def bifurcation(request: BifurcationRequest) -> dict:
    values = np.linspace(request.parameter_min, request.parameter_max, request.steps)
    flat_points = []
    equilibria = []
    stability = []
    for value in values:
        beta = float(value) if request.parameter_name == "beta" else request.beta
        gamma = float(value) if request.parameter_name == "gamma" else request.gamma
        current_points = [
            {
                "parameter_value": float(value),
                "equilibrium_value": 0.0,
                "branch": "libre de brote",
                "stable": beta <= gamma,
                "stability": "stable" if beta <= gamma else "unstable",
            }
        ]
        if beta > gamma:
            endemic = float(request.K * (1 - gamma / beta))
            current_points.append(
                {
                    "parameter_value": float(value),
                    "equilibrium_value": endemic,
                    "branch": "brote persistente",
                    "stable": True,
                    "stability": "stable",
                }
            )
        flat_points.extend(current_points)
        equilibria.append(current_points)
        stability.append("outbreak_possible" if beta > gamma else "disease_free_stable")
    threshold_value = request.gamma if request.parameter_name == "beta" else request.beta
    return {
        "model_type": "bifurcation",
        "parameters": {**request.model_dump(), "threshold": threshold_value},
        "initial_conditions": {},
        "time": [],
        "series": {},
        "equilibria": equilibria,
        "stability": {"classification": "threshold", "values": stability},
        "risk": {"risk_level": "Analítico", "risk_score": 0, "explanation": "Diagrama de bifurcación del umbral beta = gamma."},
        "interpretation": "El cambio de régimen ocurre cuando beta supera gamma: aparece una rama positiva de infectados.",
        "parameter_values": [float(v) for v in values],
        "bifurcation_points": flat_points,
        "threshold_info": {"condition": "beta > gamma", "threshold": threshold_value, "message": "Existe umbral de brote cuando beta supera gamma."},
    }


def phase_diagram(request: PhaseDiagramRequest) -> dict:
    I_values = np.linspace(request.I_min, request.I_max, request.grid_size)
    V_values = np.linspace(request.V_min, request.V_max, request.grid_size)
    phase_points = []
    for I in I_values:
        for V in V_values:
            dI = request.beta * I * (1 - I / request.K) - request.gamma * I
            dV = request.alpha * I - (request.k + request.d) * V
            magnitude = float(np.sqrt(dI**2 + dV**2))
            phase_points.append({"I": float(I), "V": float(V), "dI": float(dI), "dV": float(dV), "magnitude": magnitude})
    endemic_I = request.K * (1 - request.gamma / request.beta) if request.beta > request.gamma else None
    equilibria_analysis = analyze_iv_model_equilibria(request.beta, request.K, request.gamma, request.alpha, request.k, request.d)
    equilibrium_points = []
    for eq in equilibria_analysis:
        values = eq.get("values", {})
        if "I" in values and "V" in values:
            equilibrium_points.append({"I": float(values["I"]), "V": float(values["V"]), "classification": eq.get("classification", "equilibrium")})
    nullcline_v = [{"I": float(i), "V": float(request.alpha * i / (request.k + request.d))} for i in I_values]
    nullcline_i = []
    if endemic_I is not None:
        nullcline_i = [{"I": float(endemic_I), "V": float(v)} for v in V_values]
    return {
        "model_type": "phase-diagram",
        "parameters": request.model_dump(),
        "initial_conditions": {},
        "time": [],
        "series": {},
        "equilibria": equilibrium_points,
        "stability": {"classification": "phase_portrait", "equilibria_analysis": equilibria_analysis},
        "risk": {"risk_level": "Analítico", "risk_score": 0, "explanation": "Retrato de fase del sistema I-V."},
        "interpretation": "El diagrama de fase muestra dirección del campo vectorial, nulclinas y equilibrios del modelo infección-carga viral.",
        "phase_points": phase_points,
        "nullclines": {
            "dI_dt": [{"I": 0.0}, {"I": float(endemic_I)}] if endemic_I is not None else [{"I": 0.0}],
            "dV_dt": {"formula": "V = alpha I / (k + d)"},
        },
        "nullcline_points": {"dV_dt": nullcline_v, "dI_dt": nullcline_i},
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
        "values": risk_values,
        "risk_trend": trend,
        "increasing": trend == "increasing",
        "safe_region_violations": len(violations),
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
