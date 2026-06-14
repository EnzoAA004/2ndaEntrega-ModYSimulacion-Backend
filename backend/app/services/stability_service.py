from __future__ import annotations

import numpy as np


def classify_1d_equilibrium(derivative_value: float) -> str:
    if derivative_value < 0:
        return "stable"
    if derivative_value > 0:
        return "unstable"
    return "non_hyperbolic"


def compute_eigenvalues(matrix) -> list[complex]:
    return [complex(value) for value in np.linalg.eigvals(np.asarray(matrix, dtype=float))]


def eigenvalues_json(eigenvalues: list[complex]) -> list[dict[str, float]]:
    return [{"real": float(v.real), "imag": float(v.imag)} for v in eigenvalues]


def classify_linear_2d(eigenvalues: list[complex]) -> str:
    real_parts = [v.real for v in eigenvalues]
    imag_parts = [abs(v.imag) for v in eigenvalues]
    eps = 1e-9
    if any(abs(r) <= eps for r in real_parts):
        if all(abs(r) <= eps for r in real_parts) and any(i > eps for i in imag_parts):
            return "center"
        return "non_hyperbolic"
    if real_parts[0] * real_parts[1] < 0:
        return "saddle"
    if all(r < 0 for r in real_parts):
        return "stable_focus" if any(i > eps for i in imag_parts) else "stable_node"
    if all(r > 0 for r in real_parts):
        return "unstable_focus" if any(i > eps for i in imag_parts) else "unstable_node"
    return "inconclusive"


def jacobian_iv_model(I: float, V: float, beta: float, K: float, gamma: float, alpha: float, k: float, d: float):
    return np.array(
        [
            [beta - 2 * beta * I / K - gamma, 0.0],
            [alpha, -(k + d)],
        ],
        dtype=float,
    )


def analyze_iv_model_equilibria(beta: float, K: float, gamma: float, alpha: float, k: float, d: float):
    equilibria = [{"I": 0.0, "V": 0.0}]
    if beta > gamma:
        I_star = K * (1 - gamma / beta)
        V_star = alpha * I_star / (k + d)
        equilibria.append({"I": float(I_star), "V": float(V_star)})

    analyzed = []
    for point in equilibria:
        matrix = jacobian_iv_model(point["I"], point["V"], beta, K, gamma, alpha, k, d)
        eig = compute_eigenvalues(matrix)
        analyzed.append(
            {
                "values": point,
                "jacobian": matrix.tolist(),
                "eigenvalues": eigenvalues_json(eig),
                "classification": classify_linear_2d(eig),
            }
        )
    return analyzed

