"""
markov.py
=========
Core first-order Markov chain maths: estimation, prediction, absorption
analysis and evaluation. Everything here works on count matrices or
probability matrices, never on raw event logs, so it is dataset-agnostic.
"""

from typing import Dict, Optional

import numpy as np

from .states import STATES, N, IDX, EXIT, TRANSIENT, ORDER_STATES

EPS = 1e-12


# ---------------------------------------------------------------------------
# Estimation
# ---------------------------------------------------------------------------
def counts_from_pairs(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Transition count matrix from arrays of (from-state, to-state) indices."""
    counts = np.zeros((N, N))
    if len(a):
        np.add.at(counts, (np.asarray(a, dtype=int), np.asarray(b, dtype=int)), 1.0)
    return counts


def to_matrix(counts: np.ndarray) -> np.ndarray:
    """
    Maximum-likelihood transition matrix: P[i, j] = n_ij / sum_j n_ij.

    Two rows need a rule because they have no observed outgoing transitions:
      * Exit is absorbing, so it gets a self-loop (P = 1 of staying).
      * A transient state that never occurred in this data (e.g. Repeat
        Purchase when the loyalty threshold is 2) is sent straight to Exit.
        Giving it a self-loop instead would make (I - Q) singular and crash
        the absorption analysis.
    """
    counts = np.asarray(counts, dtype=float)
    matrix = np.zeros((N, N))
    for i in range(N):
        total = counts[i].sum()
        if i == EXIT:
            matrix[i, EXIT] = 1.0
        elif total <= 0:
            matrix[i, EXIT] = 1.0
        else:
            matrix[i] = counts[i] / total
    assert_row_stochastic(matrix)
    return matrix


def unobserved_states(counts: np.ndarray) -> list:
    """Transient states with no outgoing transitions in `counts`."""
    return [STATES[i] for i in TRANSIENT if counts[i].sum() <= 0]


def assert_row_stochastic(matrix: np.ndarray, tol: float = 1e-9, label: str = "matrix") -> None:
    """Raises unless every entry is >= 0 and every row sums to 1."""
    if matrix.shape != (N, N):
        raise ValueError(f"{label}: expected shape {(N, N)}, got {matrix.shape}")
    if np.any(matrix < -tol):
        raise ValueError(f"{label}: negative probability at {np.argwhere(matrix < -tol).tolist()}")
    sums = matrix.sum(axis=1)
    if not np.allclose(sums, 1.0, atol=tol):
        raise ValueError(f"{label}: row sums {dict(zip(STATES, sums.round(6)))}")


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
def next_state(matrix: np.ndarray, state: str) -> Dict[str, float]:
    return dict(zip(STATES, matrix[IDX[state]].tolist()))


def k_step(matrix: np.ndarray, state: str, k: int) -> Dict[str, float]:
    """Distribution over states k transitions ahead: row of P^k."""
    return dict(zip(STATES, np.linalg.matrix_power(matrix, int(k))[IDX[state]].tolist()))


def most_likely_path(matrix: np.ndarray, state: str, max_len: int = 8) -> list:
    """Greedy highest-probability path until Exit (or max_len steps)."""
    path, i = [state], IDX[state]
    for _ in range(max_len):
        if i == EXIT:
            break
        row = matrix[i].copy()
        if row.sum() - row[i] > 0:
            row[i] = 0.0            # skip self-loops so the path moves forward
        i = int(np.argmax(row))
        path.append(STATES[i])
    return path


# ---------------------------------------------------------------------------
# Absorption analysis (the long-run view of a chain with Exit absorbing)
# ---------------------------------------------------------------------------
def fundamental_matrix(matrix: np.ndarray) -> np.ndarray:
    """N = (I - Q)^-1, where Q is the transient-to-transient block."""
    Q = matrix[np.ix_(TRANSIENT, TRANSIENT)]
    return np.linalg.inv(np.eye(len(TRANSIENT)) - Q)


def absorption(matrix: np.ndarray, start: str = "Visitor") -> Dict:
    """
    From `start`, before the customer exits:
      expected_visits[j] = N[s, j]
      steps_to_exit      = sum_j N[s, j]
      prob_ever[j]       = N[s, j] / N[j, j]   (probability j is ever reached)
      expected_orders    = visits to Purchase + Repeat Purchase + Loyal Customer
    A plain stationary distribution would be 100% Exit, so these are the
    informative long-run quantities.
    """
    Nm = fundamental_matrix(matrix)
    s = TRANSIENT.index(IDX[start])
    visits = Nm[s]
    names = [STATES[i] for i in TRANSIENT]
    prob_ever = {}
    for j, name in enumerate(names):
        prob_ever[name] = 1.0 if j == s else float(visits[j] / Nm[j, j])
    orders = float(sum(visits[TRANSIENT.index(o)] for o in ORDER_STATES))
    return {
        "start": start,
        "expected_visits": dict(zip(names, visits.tolist())),
        "steps_to_exit": float(visits.sum()),
        "prob_ever": prob_ever,
        "expected_orders": orders,
    }


# ---------------------------------------------------------------------------
# Evaluation on held-out transitions
# ---------------------------------------------------------------------------
def evaluate(matrix: np.ndarray, a: np.ndarray, b: np.ndarray,
             baseline_state: Optional[int] = None, marginal: Optional[np.ndarray] = None,
             smoothing: float = 1e-4) -> Dict:
    """
    Top-1 accuracy and log-loss of `matrix` on observed transitions a -> b.

    Accuracy only checks the single most likely next state. Log-loss scores
    the whole predicted distribution, so it shows whether a model's
    probabilities are well calibrated even when its top guess is unchanged.
    """
    a = np.asarray(a, dtype=int)
    b = np.asarray(b, dtype=int)
    if len(a) == 0:
        return {"n": 0}
    P = (matrix + smoothing) / (matrix + smoothing).sum(axis=1, keepdims=True)
    pred = matrix.argmax(axis=1)[a]
    out = {
        "n": int(len(a)),
        "accuracy": float(np.mean(pred == b)),
        "log_loss": float(-np.mean(np.log(P[a, b] + EPS))),
    }
    non_visitor = a != IDX["Visitor"]
    if non_visitor.any():
        out["accuracy_excl_visitor"] = float(np.mean(pred[non_visitor] == b[non_visitor]))
    if baseline_state is not None:
        out["baseline_accuracy"] = float(np.mean(b == baseline_state))
        if non_visitor.any():
            out["baseline_accuracy_excl_visitor"] = float(np.mean(b[non_visitor] == baseline_state))
    if marginal is not None:
        m = (marginal + smoothing) / (marginal + smoothing).sum()
        out["baseline_log_loss"] = float(-np.mean(np.log(m[b] + EPS)))
    return out
