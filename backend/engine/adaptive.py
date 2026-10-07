"""
adaptive.py
===========
Adaptive transition-matrix updating: the model's matrix is revised every
time a new batch (month) of behaviour arrives, instead of being fitted once.

Pieces:
  * divergences (KL, Jensen-Shannon, total variation) between rows
  * drift detection: two-sample chi-square per row + Holm correction +
    a minimum effect size, so large real datasets don't flag trivial shifts
  * per-row adaptive blend weight alpha, driven by the measured shift
  * four update strategies (EWMA, adaptive EWMA, sliding window, Bayesian)
  * AdaptiveModel: replays batches and keeps every version of the matrix,
    so the simulator, optimiser and AI advisor can read the *live* version.

Fixes relative to the mid-review adaptive_engine.py:
  1. The old goodness-of-fit test treated the previous matrix as exact truth
     and ran 6 uncorrected tests -> ~50% false alarms on stable data. Now a
     two-sample test of homogeneity with Holm correction.
  2. alpha used tanh(4 * JSD); real JSD is ~0.01 so alpha barely moved. Now
     driven by total variation with a documented scale.
  3. Significance alone flags 0.001 shifts when rows have 100k+ observations,
     so a row must also clear MIN_DRIFT_TV.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np
from scipy.stats import chi2_contingency

from .. import config
from .markov import to_matrix, absorption, assert_row_stochastic
from .states import STATES, N, IDX, EXIT, TRANSIENT

EPS = 1e-12
STRATEGIES = ("adaptive_ewma", "ewma", "sliding_window", "bayesian")


# ---------------------------------------------------------------------------
# Divergences between two probability rows
# ---------------------------------------------------------------------------
def _clean(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, None)
    return p / p.sum()


def kl_divergence(p, q) -> float:
    p, q = _clean(p), _clean(q)
    return float(np.sum(p * np.log(p / q)))


def js_divergence(p, q) -> float:
    p, q = _clean(p), _clean(q)
    m = 0.5 * (p + q)
    return float(0.5 * kl_divergence(p, m) + 0.5 * kl_divergence(q, m))


def total_variation(p, q) -> float:
    return float(0.5 * np.abs(np.asarray(p, float) - np.asarray(q, float)).sum())


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------
@dataclass
class DriftResult:
    state: str
    tested: bool
    p_value: float
    p_holm: float
    tv: float
    js: float
    n_ref: int
    n_new: int
    significant: bool
    drift: bool
    biggest_change_to: str
    biggest_change: float
    note: str


def detect_drift(ref_counts: np.ndarray, new_counts: np.ndarray,
                 alpha: float = config.DRIFT_ALPHA,
                 min_tv: float = config.MIN_DRIFT_TV,
                 min_obs: int = config.MIN_OBSERVATIONS) -> Dict[str, DriftResult]:
    """
    For every transient row: are the reference-batch and new-batch
    transition counts plausibly drawn from the same distribution?

    Test: chi-square test of homogeneity on the 2 x k table
    [ref row counts; new row counts] (columns where both are zero dropped).
    Both samples are treated as noisy, unlike a goodness-of-fit test against
    the old matrix. p-values are Holm-corrected across rows because six rows
    are tested at once. A row is flagged as drift only if it is significant
    AND its total-variation shift is at least `min_tv`.
    """
    raw = []
    for i in TRANSIENT:
        r, c = ref_counts[i], new_counts[i]
        n_r, n_c = int(r.sum()), int(c.sum())
        pr = r / n_r if n_r else np.zeros(N)
        pc = c / n_c if n_c else np.zeros(N)
        delta = pc - pr
        j = int(np.argmax(np.abs(delta)))
        entry = {"i": i, "n_ref": n_r, "n_new": n_c, "tv": total_variation(pr, pc) if n_r and n_c else 0.0,
                 "js": js_divergence(pr, pc) if n_r and n_c else 0.0,
                 "to": STATES[j], "chg": float(delta[j]) if n_r and n_c else 0.0, "p": 1.0, "tested": False}
        if n_r >= min_obs and n_c >= min_obs:
            table = np.vstack([r, c])
            table = table[:, table.sum(axis=0) > 0]
            if table.shape[1] >= 2:
                entry["p"] = float(chi2_contingency(table)[1])
                entry["tested"] = True
        raw.append(entry)

    # Holm step-down adjustment over the tested rows
    tested = sorted([e for e in raw if e["tested"]], key=lambda e: e["p"])
    m = len(tested)
    running = 0.0
    for k, e in enumerate(tested):
        running = max(running, min(1.0, (m - k) * e["p"]))
        e["p_holm"] = running
    results = {}
    for e in raw:
        p_holm = e.get("p_holm", 1.0)
        significant = e["tested"] and p_holm <= alpha
        drift = significant and e["tv"] >= min_tv
        if not e["tested"]:
            note = f"not tested (n={e['n_ref']}/{e['n_new']} < {min_obs})"
        elif drift:
            note = f"drift: {e['to']} {e['chg']:+.3f}"
        elif significant:
            note = f"significant but small (TV {e['tv']:.3f} < {min_tv})"
        else:
            note = "stable"
        results[STATES[e["i"]]] = DriftResult(
            state=STATES[e["i"]], tested=e["tested"], p_value=e["p"], p_holm=p_holm,
            tv=e["tv"], js=e["js"], n_ref=e["n_ref"], n_new=e["n_new"],
            significant=significant, drift=drift, biggest_change_to=e["to"],
            biggest_change=e["chg"], note=note)
    return results


def adaptive_alpha(drift: Dict[str, DriftResult], base: float = config.BASE_ALPHA,
                   top: float = config.MAX_ALPHA, scale: float = config.ALPHA_TV_SCALE) -> Dict[str, float]:
    """
    Per-row weight on the new batch:
        alpha = base + (top - base) * tanh(TV / scale)   for drifted rows
        alpha = base                                      otherwise
    With scale 0.05: TV 0.02 -> 0.49, TV 0.05 -> 0.68, TV 0.15 -> 0.80.
    tanh keeps alpha below `top` however extreme one batch is.
    """
    if not 0.0 <= base <= top <= 1.0:
        raise ValueError("need 0 <= base <= top <= 1")
    out = {}
    for s, r in drift.items():
        out[s] = float(base + (top - base) * np.tanh(r.tv / scale)) if r.drift else float(base)
    return out


# ---------------------------------------------------------------------------
# Update strategies (all return a row-stochastic matrix)
# ---------------------------------------------------------------------------
def _blend(old: np.ndarray, batch_counts: np.ndarray, alpha_by_row: Dict[int, float]) -> np.ndarray:
    batch = to_matrix(batch_counts)
    new = old.copy()
    for i in TRANSIENT:
        if batch_counts[i].sum() > 0:
            a = alpha_by_row[i]
            new[i] = a * batch[i] + (1 - a) * old[i]
    new = new / new.sum(axis=1, keepdims=True)
    assert_row_stochastic(new, label="blend")
    return new


def ewma_update(old, batch_counts, alpha=config.BASE_ALPHA):
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be in [0, 1]")
    return _blend(old, batch_counts, {i: alpha for i in TRANSIENT})


def adaptive_ewma_update(old, batch_counts, alpha_by_state: Dict[str, float]):
    return _blend(old, batch_counts, {i: alpha_by_state.get(STATES[i], config.BASE_ALPHA) for i in TRANSIENT})


def sliding_window_update(history_counts: List[np.ndarray], window=config.WINDOW):
    if window < 1 or not history_counts:
        raise ValueError("need window >= 1 and at least one batch")
    return to_matrix(np.sum(history_counts[-window:], axis=0))


def bayesian_update(prior_counts, batch_counts, decay=config.BAYES_DECAY, prior_strength=1.0):
    """Dirichlet-multinomial: posterior = decay * prior + new; smoothed on transient rows."""
    if not 0 < decay <= 1:
        raise ValueError("decay must be in (0, 1]")
    posterior = decay * prior_counts + batch_counts
    smoothed = posterior.copy()
    for i in TRANSIENT:
        if smoothed[i].sum() > 0:
            smoothed[i] = smoothed[i] + prior_strength * (smoothed[i] > 0)   # smooth observed cells only
    return to_matrix(smoothed), posterior


# ---------------------------------------------------------------------------
# The live, self-updating model
# ---------------------------------------------------------------------------
@dataclass
class Version:
    version: int
    label: str
    strategy: str
    n_transitions: int
    matrix: np.ndarray
    batch_matrix: np.ndarray
    drift: Dict[str, DriftResult] = field(default_factory=dict)
    alpha: Dict[str, float] = field(default_factory=dict)
    kpis: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> Dict:
        return {
            "version": self.version, "label": self.label, "strategy": self.strategy,
            "n_transitions": self.n_transitions,
            "drift_states": [s for s, r in self.drift.items() if r.drift],
            "drift": {s: asdict(r) for s, r in self.drift.items()},
            "alpha": self.alpha, "kpis": self.kpis,
        }


def headline_kpis(matrix: np.ndarray) -> Dict[str, float]:
    ab = absorption(matrix, "Visitor")
    return {
        "p_first_order": ab["prob_ever"]["Purchase"],
        "p_repeat": ab["prob_ever"]["Repeat Purchase"],
        "p_loyal": ab["prob_ever"]["Loyal Customer"],
        "orders_per_visitor": ab["expected_orders"],
        "steps_to_exit": ab["steps_to_exit"],
        "cart_to_purchase": float(matrix[IDX["Add to Cart"], IDX["Purchase"]]),
        "view_to_cart": float(matrix[IDX["Product View"], IDX["Add to Cart"]]),
        "purchase_to_repeat": float(matrix[IDX["Purchase"], IDX["Repeat Purchase"]]),
        "repeat_to_loyal": float(matrix[IDX["Repeat Purchase"], IDX["Loyal Customer"]]),
    }


class AdaptiveModel:
    """
    Holds one matrix version per batch. `versions[k].matrix` is the model's
    belief after seeing batches 0..k. The dashboard's "live" matrix is the
    version the user has streamed up to; version 0 is the frozen snapshot a
    conventional one-time fit would keep using forever.
    """

    def __init__(self, strategy: str = config.DEFAULT_STRATEGY, alpha: float = config.BASE_ALPHA,
                 max_alpha: float = config.MAX_ALPHA, decay: float = config.BAYES_DECAY,
                 window: int = config.WINDOW):
        if strategy not in STRATEGIES:
            raise ValueError(f"strategy must be one of {STRATEGIES}")
        self.strategy, self.alpha, self.max_alpha = strategy, alpha, max_alpha
        self.decay, self.window = decay, window
        self.versions: List[Version] = []
        self.history_counts: List[np.ndarray] = []
        self.posterior: Optional[np.ndarray] = None

    @property
    def current(self) -> np.ndarray:
        if not self.versions:
            raise RuntimeError("model has no data yet")
        return self.versions[-1].matrix

    def initialise(self, counts: np.ndarray, label: str = "batch 0") -> Version:
        if counts.sum() <= 0:
            raise ValueError("initial batch has no transitions")
        m = to_matrix(counts)
        self.history_counts = [counts]
        self.posterior = counts.copy()
        v = Version(0, label, "initial fit", int(counts.sum()), m, m, kpis=headline_kpis(m))
        self.versions = [v]
        return v

    def update(self, counts: np.ndarray, label: str) -> Version:
        if not self.versions:
            raise RuntimeError("call initialise() first")
        if counts.sum() <= 0:
            raise ValueError("batch has no transitions")
        old = self.current
        drift = detect_drift(self.history_counts[-1], counts)
        alpha_used: Dict[str, float] = {}
        if self.strategy == "adaptive_ewma":
            alpha_used = adaptive_alpha(drift, self.alpha, self.max_alpha)
            new = adaptive_ewma_update(old, counts, alpha_used)
        elif self.strategy == "ewma":
            alpha_used = {STATES[i]: self.alpha for i in TRANSIENT}
            new = ewma_update(old, counts, self.alpha)
        elif self.strategy == "sliding_window":
            new = sliding_window_update(self.history_counts + [counts], self.window)
        else:
            new, self.posterior = bayesian_update(self.posterior, counts, self.decay)
        self.history_counts.append(counts)
        assert_row_stochastic(new, label=self.strategy)
        v = Version(len(self.versions), label, self.strategy, int(counts.sum()), new,
                    to_matrix(counts), drift, alpha_used, headline_kpis(new))
        self.versions.append(v)
        return v

    @classmethod
    def replay(cls, batches: List[np.ndarray], labels: List[str], **kw) -> "AdaptiveModel":
        model = cls(**kw)
        model.initialise(batches[0], labels[0])
        for c, lab in zip(batches[1:], labels[1:]):
            model.update(c, lab)
        return model
