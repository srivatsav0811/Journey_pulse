"""
simulator.py
============
What-if simulation on a transition matrix, plus the business metrics every
screen reports. The simulator is always handed a specific matrix version;
the workspace passes it the *live* matrix and, alongside, the frozen
snapshot, so the dashboard can show how far apart their answers are.
"""

from typing import Dict, Tuple

import numpy as np

from .markov import absorption, assert_row_stochastic
from .states import IDX, EXIT, LEVERS, LEVER_BY_ID


def lever_cells(lever_id: str) -> Tuple[int, int]:
    lv = LEVER_BY_ID[lever_id]
    return IDX[lv["from"]], IDX[lv["to"]]


def headroom(matrix: np.ndarray) -> Dict[str, Dict[str, float]]:
    """How far each lever can move: up by the row's Exit mass, down by its own mass."""
    out = {}
    for lv in LEVERS:
        i, j = IDX[lv["from"]], IDX[lv["to"]]
        out[lv["id"]] = {"current": float(matrix[i, j]), "max_up": float(matrix[i, EXIT]),
                         "max_down": float(matrix[i, j])}
    return out


def apply_shifts(matrix: np.ndarray, shifts: Dict[str, float]) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Raises (or lowers) each lever's probability by `delta`, moving the same
    mass out of (or into) that row's Exit cell, so rows still sum to 1.

    Each delta is clamped to what the row can give: a lever can't take more
    than the row's current Exit probability, and can't go below zero. The
    mid-review version did not clamp and could produce negative probabilities
    on real data. Returns (new_matrix, the deltas actually applied).
    """
    M = matrix.copy()
    applied = {}
    for lever_id, delta in shifts.items():
        if lever_id not in LEVER_BY_ID or not delta:
            continue
        i, j = lever_cells(lever_id)
        d = float(np.clip(delta, -M[i, j], M[i, EXIT]))
        M[i, j] += d
        M[i, EXIT] -= d
        applied[lever_id] = d
    M = np.clip(M, 0.0, None)
    assert_row_stochastic(M, label="what-if")
    return M, applied


def business_metrics(matrix: np.ndarray, aov: float, start: str = "Visitor") -> Dict[str, float]:
    """The numbers a business user reads, for customers starting at `start`."""
    ab = absorption(matrix, start)
    return {
        "p_first_order": ab["prob_ever"]["Purchase"],
        "p_repeat": ab["prob_ever"]["Repeat Purchase"],
        "p_loyal": ab["prob_ever"]["Loyal Customer"],
        "orders_per_visitor": ab["expected_orders"],
        "revenue_per_1k": ab["expected_orders"] * aov * 1000.0,
        "steps_to_exit": ab["steps_to_exit"],
    }


def scenario(live: np.ndarray, frozen: np.ndarray, shifts: Dict[str, float], aov: float) -> Dict:
    """
    Runs the same what-if on the live matrix and on the frozen snapshot.
    `snapshot_error` is how wrong the frozen model's answer would be, taking
    the live model as the up-to-date reference.
    """
    live_s, applied = apply_shifts(live, shifts)
    frozen_s, applied_frozen = apply_shifts(frozen, shifts)
    base_l, scen_l = business_metrics(live, aov), business_metrics(live_s, aov)
    base_f, scen_f = business_metrics(frozen, aov), business_metrics(frozen_s, aov)
    keys = base_l.keys()
    return {
        "applied": applied,
        "applied_frozen": applied_frozen,
        "live": {"baseline": base_l, "scenario": scen_l,
                 "uplift": {k: scen_l[k] - base_l[k] for k in keys}},
        "frozen": {"baseline": base_f, "scenario": scen_f,
                   "uplift": {k: scen_f[k] - base_f[k] for k in keys}},
        "snapshot_error": {k: scen_f[k] - scen_l[k] for k in keys},
        "scenario_matrix": live_s.tolist(),
    }
