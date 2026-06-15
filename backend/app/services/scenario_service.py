from __future__ import annotations

import numpy as np

from app.services.numerical_methods import METHODS
from app.services.risk_service import risk_from_series


DEFAULT_SCENARIOS = [
    {"name": "Base", "beta_multiplier": 1.0, "gamma_multiplier": 1.0, "alpha_multiplier": 1.0},
    {"name": "Menor transmisión", "beta_multiplier": 0.75, "gamma_multiplier": 1.0, "alpha_multiplier": 1.0},
    {"name": "Mayor recuperación", "beta_multiplier": 1.0, "gamma_multiplier": 1.35, "alpha_multiplier": 1.0},
    {"name": "Intervención combinada", "beta_multiplier": 0.7, "gamma_multiplier": 1.3, "alpha_multiplier": 0.9},
    {"name": "Shock de brote", "beta_multiplier": 1.4, "gamma_multiplier": 0.9, "alpha_multiplier": 1.15},
]


def scenario_compare(payload: dict) -> dict:
    base = {
        "beta": float(payload.get("beta", 0.35)),
        "K": float(payload.get("K", 100000)),
        "gamma": float(payload.get("gamma", 0.12)),
        "alpha": float(payload.get("alpha", 25)),
        "k": float(payload.get("k", 0.15)),
        "d": float(payload.get("d", 0.05)),
        "I0": float(payload.get("I0", 100)),
        "V0": float(payload.get("V0", 5000)),
        "t_final": float(payload.get("t_final", 90)),
        "step": float(payload.get("step", 0.5)),
        "method": str(payload.get("method", "rk4")),
    }
    scenarios = payload.get("scenarios") or DEFAULT_SCENARIOS
    method = base["method"] if base["method"] in METHODS else "rk4"

    def f(_t, y, p):
        I, V = y
        dI = p["beta"] * I * (1 - I / p["K"]) - p["gamma"] * I
        dV = p["alpha"] * I - (p["k"] + p["d"]) * V
        return np.array([dI, dV])

    combined_series: dict[str, list[float]] = {}
    scenario_results = []
    common_time: list[float] = []

    for scenario in scenarios:
        params = {
            **base,
            "beta": base["beta"] * float(scenario.get("beta_multiplier", 1)),
            "gamma": base["gamma"] * float(scenario.get("gamma_multiplier", 1)),
            "alpha": base["alpha"] * float(scenario.get("alpha_multiplier", 1)),
        }
        t, values = METHODS[method](f, [base["I0"], base["V0"]], 0, base["t_final"], base["step"], params)
        common_time = t
        I_values = [float(row[0]) for row in values]
        V_values = [float(row[1]) for row in values]
        name = str(scenario.get("name", "Escenario"))
        combined_series[f"{name} I"] = I_values
        combined_series[f"{name} V"] = V_values
        scenario_results.append(
            {
                "name": name,
                "params": params,
                "final_I": I_values[-1] if I_values else 0,
                "final_V": V_values[-1] if V_values else 0,
                "max_I": max(I_values) if I_values else 0,
                "max_V": max(V_values) if V_values else 0,
                "max_I_time": t[int(np.argmax(I_values))] if I_values else 0,
                "max_V_time": t[int(np.argmax(V_values))] if V_values else 0,
                "risk": risk_from_series(V_values),
            }
        )

    best = min(scenario_results, key=lambda item: item["max_V"], default=None)
    worst = max(scenario_results, key=lambda item: item["max_V"], default=None)
    return {
        "model_type": "scenario-compare",
        "parameters": base,
        "initial_conditions": {"I0": base["I0"], "V0": base["V0"]},
        "time": common_time,
        "series": combined_series,
        "equilibria": [],
        "stability": {"classification": "scenario_analysis", "explanation": "Comparación de escenarios con variación de beta, gamma y alpha."},
        "risk": {"risk_level": "Analítico", "risk_score": 0, "explanation": "Comparación de riesgo relativo entre escenarios."},
        "interpretation": "El comparador evalúa cómo cambian infectados y carga viral bajo estrategias alternativas de intervención o shock.",
        "scenarios": scenario_results,
        "best_scenario": best,
        "worst_scenario": worst,
    }
