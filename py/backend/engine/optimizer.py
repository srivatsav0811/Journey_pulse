"""
optimizer.py
============
Constrained optimisation: how should a limited improvement budget be split
across the business levers to maximise a long-run objective?

    maximise   f(P + sum_l x_l * E_l)
    subject to sum_l x_l <= budget,   0 <= x_l <= min(per_lever_max, headroom_l)

f is nonlinear in x because it goes through (I - Q)^-1, so this is solved
with SLSQP (multiple starts) and then checked against a brute-force grid.
Optimisation on Markov customer models is established prior art (e.g.
Pfeifer & Carraway 2004); what this project adds is that the optimiser
always runs on the live, self-updating matrix.
"""

import itertools
from typing import Dict

import numpy as np
from scipy.optimize import minimize

from .. import config
from .simulator import apply_shifts, headroom
from .states import IDX, TRANSIENT, ORDER_STATES, LEVERS

OBJECTIVES = {
    "revenue": "Expected orders per visitor (revenue)",
    "loyal": "P(visitor ever becomes Loyal)",
    "first_order": "P(visitor ever places a first order)",
}
_T = {s: TRANSIENT.index(s) for s in TRANSIENT}


def _objective_from_N(Nrow: np.ndarray, Ndiag: np.ndarray, objective: str) -> np.ndarray:
    """Objective value(s) from the start row of the fundamental matrix (vectorised)."""
    if objective == "revenue":
        return sum(Nrow[..., _T[o]] for o in ORDER_STATES)
    target = IDX["Loyal Customer"] if objective == "loyal" else IDX["Purchase"]
    t = _T[target]
    return Nrow[..., t] / Ndiag[..., t]


def objective_value(matrix: np.ndarray, objective: str, start: str = "Visitor") -> float:
    Q = matrix[np.ix_(TRANSIENT, TRANSIENT)]
    Nm = np.linalg.inv(np.eye(len(TRANSIENT)) - Q)
    s = _T[IDX[start]]
    return float(_objective_from_N(Nm[s], np.diag(Nm), objective))


def _bounds(matrix, per_max):
    room = headroom(matrix)
    return [(0.0, max(0.0, min(per_max, room[lv["id"]]["max_up"]))) for lv in LEVERS]


def _grid_check(matrix, budget, bounds, objective, start):
    """Brute-force search over a grid; batched matrix inverses keep it fast."""
    step = config.GRID_STEP
    while True:
        axes = [np.round(np.arange(0.0, hi + 1e-9, step), 6) for _, hi in bounds]
        if np.prod([len(a) for a in axes]) <= 80_000:
            break
        step *= 2
    combos = np.array([c for c in itertools.product(*axes) if sum(c) <= budget + 1e-9])
    Q0 = matrix[np.ix_(TRANSIENT, TRANSIENT)]
    Qs = np.repeat(Q0[None], len(combos), axis=0)
    for k, lv in enumerate(LEVERS):
        i, j = _T[IDX[lv["from"]]], _T[IDX[lv["to"]]]
        Qs[:, i, j] += combos[:, k]
    Ns = np.linalg.inv(np.eye(len(TRANSIENT))[None] - Qs)
    s = _T[IDX[start]]
    vals = _objective_from_N(Ns[:, s, :], np.diagonal(Ns, axis1=1, axis2=2), objective)
    best = int(np.argmax(vals))
    return combos[best], float(vals[best]), step, len(combos)


def optimise(matrix: np.ndarray, budget: float = config.DEFAULT_BUDGET,
             per_lever_max: float = config.DEFAULT_PER_LEVER_MAX,
             objective: str = "revenue", start: str = "Visitor") -> Dict:
    if objective not in OBJECTIVES:
        raise ValueError(f"objective must be one of {list(OBJECTIVES)}")
    bounds = _bounds(matrix, per_lever_max)

    def f(x):
        M, _ = apply_shifts(matrix, {lv["id"]: v for lv, v in zip(LEVERS, x)})
        return -objective_value(M, objective, start)

    cons = [{"type": "ineq", "fun": lambda x: budget - np.sum(x)}]
    starts = [np.array([min(budget / len(LEVERS), hi) for _, hi in bounds])]
    for k in range(len(LEVERS)):
        x0 = np.zeros(len(LEVERS))
        x0[k] = min(budget, bounds[k][1])
        starts.append(x0)
    best = None
    for x0 in starts:
        res = minimize(f, x0, method="SLSQP", bounds=bounds, constraints=cons,
                       options={"ftol": 1e-12, "maxiter": 300})
        if best is None or res.fun < best.fun:
            best = res
    x = np.clip(best.x, [b[0] for b in bounds], [b[1] for b in bounds])
    base = objective_value(matrix, objective, start)
    opt = -f(x)
    grid_x, grid_val, grid_step, n_grid = _grid_check(matrix, budget, bounds, objective, start)
    alloc = {lv["id"]: float(v) for lv, v in zip(LEVERS, x)}
    return {
        "objective": objective, "objective_label": OBJECTIVES[objective],
        "budget": budget, "per_lever_max": per_lever_max,
        "allocation": alloc,
        "top_lever": max(alloc, key=alloc.get),
        "baseline": base, "optimised": opt, "uplift": opt - base,
        "relative_uplift": (opt - base) / base if base else 0.0,
        "solver_success": bool(best.success),
        "grid": {"allocation": {lv["id"]: float(v) for lv, v in zip(LEVERS, grid_x)},
                 "value": grid_val, "step": grid_step, "points": n_grid,
                 "agrees": bool(opt >= grid_val - 1e-6)},
        "bounds": {lv["id"]: b[1] for lv, b in zip(LEVERS, bounds)},
    }


def leverage(matrix: np.ndarray, objective: str = "revenue", start: str = "Visitor",
             step: float = 0.01) -> Dict[str, float]:
    """
    Marginal value of each lever: objective gain from +1 percentage point
    (finite difference, clamped to headroom). This is the sensitivity that
    ranks next-best actions.
    """
    base = objective_value(matrix, objective, start)
    out = {}
    for lv in LEVERS:
        M, applied = apply_shifts(matrix, {lv["id"]: step})
        d = applied.get(lv["id"], 0.0)
        out[lv["id"]] = (objective_value(M, objective, start) - base) / d * 0.01 if d > 0 else 0.0
    return out
