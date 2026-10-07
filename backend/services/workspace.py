"""
workspace.py
============
One Workspace per dataset. It owns the adaptive model and a pointer to the
LIVE version the dashboard is currently streamed up to. Every analysis
(what-if, optimiser, next-best actions, AI advisor) asks the workspace for
`live_matrix` -- this single source of truth is the project's novelty:
the simulator and optimiser never work on a stale, frozen snapshot.
"""

import threading
from typing import Dict, Optional

import numpy as np

from .. import config
from ..data.preprocess import load_dataset, available_datasets
from ..engine import actions, optimizer, simulator
from ..engine.adaptive import AdaptiveModel, STRATEGIES, headline_kpis
from ..engine.markov import (counts_from_pairs, to_matrix, absorption, evaluate, k_step,
                             most_likely_path, next_state, unobserved_states)
from ..engine.states import STATES, SHORT, IDX, LEVERS, TRANSIENT

SYNTHETIC_TRUTH = {"Add to Cart->Purchase": {"before": 0.35, "after": 0.50, "shift_batch": 2}}


def _r(x, d=6):
    """JSON-friendly rounding for floats nested in dicts/lists."""
    if isinstance(x, dict):
        return {k: _r(v, d) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r(v, d) for v in x]
    if isinstance(x, (float, np.floating)):
        return round(float(x), d)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.ndarray):
        return _r(x.tolist(), d)
    return x


class Workspace:
    def __init__(self, name: str, strategy: str = config.DEFAULT_STRATEGY):
        self.name = name
        self.ds = load_dataset(name)
        self.lock = threading.RLock()
        tr = self.ds.transitions
        self.batch_counts = [counts_from_pairs(g.a.to_numpy(), g.b.to_numpy())
                             for _, g in tr.groupby("batch", sort=True)]
        self.labels = self.ds.batch_labels
        self.aov = self.ds.aov
        self._validation: Optional[Dict] = None
        self.set_strategy(strategy)

    # ------------------------------------------------------------------ state
    def set_strategy(self, strategy: str):
        if strategy not in STRATEGIES:
            raise ValueError(f"strategy must be one of {STRATEGIES}")
        with self.lock:
            self.strategy = strategy
            self.model = AdaptiveModel.replay(self.batch_counts, self.labels, strategy=strategy)
            self.live_version = len(self.model.versions) - 1

    def set_version(self, version: int):
        with self.lock:
            self.live_version = int(np.clip(version, 0, len(self.model.versions) - 1))

    @property
    def live(self):
        return self.model.versions[self.live_version]

    @property
    def live_matrix(self) -> np.ndarray:
        return self.live.matrix

    @property
    def frozen_matrix(self) -> np.ndarray:
        return self.model.versions[0].matrix

    def live_tag(self) -> Dict:
        v = self.live
        return {"dataset": self.name, "version": v.version, "label": v.label,
                "latest": len(self.model.versions) - 1, "strategy": self.strategy,
                "frozen_label": self.model.versions[0].label}

    # --------------------------------------------------------------- overview
    def overview(self) -> Dict:
        live_m = simulator.business_metrics(self.live_matrix, self.aov)
        frozen_m = simulator.business_metrics(self.frozen_matrix, self.aov)
        leak = actions.biggest_leak(self.live_matrix)
        best = optimizer.leverage(self.live_matrix, "revenue")
        top = max(best, key=best.get)
        f = self.ds.facts
        return _r({
            "live": self.live_tag(),
            "dataset_label": self.ds.label,
            "kpis": live_m, "frozen_kpis": frozen_m,
            "aov": self.aov,
            "cart_abandonment": f.get("cart_abandonment"),
            "facts": {k: f.get(k) for k in ("customers", "sessions", "rows_used", "rows_raw", "start", "end",
                                           "orders", "buyers", "transitions_used")},
            "biggest_leak": leak,
            "top_lever": {"id": top, "label": next(l["label"] for l in LEVERS if l["id"] == top),
                          "revenue_per_1k_per_point": best[top] * self.aov * 1000},
            "matrix": self.live_matrix,
            "states": STATES, "short": SHORT,
        })

    # --------------------------------------------------------------- matrices
    def matrices(self, version: Optional[int] = None) -> Dict:
        k = self.live_version if version is None else int(np.clip(version, 0, len(self.model.versions) - 1))
        v = self.model.versions[k]
        pooled = to_matrix(np.sum(self.batch_counts[:k + 1], axis=0))
        return _r({
            "version": k, "label": v.label, "states": STATES, "short": SHORT,
            "live": v.matrix, "frozen": self.frozen_matrix, "batch": v.batch_matrix,
            "pooled": pooled, "counts": self.batch_counts[k],
            "unobserved": unobserved_states(self.batch_counts[k]),
            "absorption": {s: absorption(v.matrix, s) for s in STATES if s != "Exit"},
        })

    # --------------------------------------------------------------- timeline
    def timeline(self) -> Dict:
        rows = []
        for v in self.model.versions:
            s = v.summary()
            s["batch_kpis"] = {
                "cart_to_purchase": float(v.batch_matrix[IDX["Add to Cart"], IDX["Purchase"]]),
                "view_to_cart": float(v.batch_matrix[IDX["Product View"], IDX["Add to Cart"]]),
                "purchase_to_repeat": float(v.batch_matrix[IDX["Purchase"], IDX["Repeat Purchase"]]),
                "repeat_to_loyal": float(v.batch_matrix[IDX["Repeat Purchase"], IDX["Loyal Customer"]]),
            }
            s["revenue_per_1k"] = v.kpis["orders_per_visitor"] * self.aov * 1000
            rows.append(s)
        frozen = headline_kpis(self.frozen_matrix)
        return _r({"live": self.live_tag(), "versions": rows, "frozen_kpis": frozen,
                   "frozen_revenue_per_1k": frozen["orders_per_visitor"] * self.aov * 1000,
                   "truth": SYNTHETIC_TRUTH if self.name == "synthetic" else None,
                   "config": {"drift_alpha": config.DRIFT_ALPHA, "min_tv": config.MIN_DRIFT_TV,
                              "base_alpha": config.BASE_ALPHA, "max_alpha": config.MAX_ALPHA,
                              "alpha_scale": config.ALPHA_TV_SCALE}})

    # ---------------------------------------------------------------- what-if
    def simulate(self, shifts: Dict[str, float]) -> Dict:
        out = simulator.scenario(self.live_matrix, self.frozen_matrix, shifts, self.aov)
        out["headroom"] = simulator.headroom(self.live_matrix)
        out["frozen_headroom"] = simulator.headroom(self.frozen_matrix)
        out["live_tag"] = self.live_tag()
        return _r(out)

    def optimise(self, budget: float, per_max: float, objective: str) -> Dict:
        live = optimizer.optimise(self.live_matrix, budget, per_max, objective)
        frozen = optimizer.optimise(self.frozen_matrix, budget, per_max, objective)
        # evaluate the frozen model's recommended allocation on the live (current) matrix
        frozen_on_live_m, _ = simulator.apply_shifts(self.live_matrix, frozen["allocation"])
        frozen_on_live = optimizer.objective_value(frozen_on_live_m, objective)
        return _r({
            "live_tag": self.live_tag(), "live": live, "frozen": frozen,
            "frozen_plan_on_live": frozen_on_live,
            "cost_of_stale_plan": live["optimised"] - frozen_on_live,
            "aov": self.aov,
        })

    # ------------------------------------------------------------ next action
    def outlook(self, stage: str) -> Dict:
        live = actions.stage_outlook(self.live_matrix, stage, self.aov)
        frozen = actions.stage_outlook(self.frozen_matrix, stage, self.aov)
        return _r({"live_tag": self.live_tag(), "live": live,
                   "frozen_best": frozen["best"]["lever"] if frozen["best"] else None,
                   "frozen_metrics": frozen["metrics"]})

    def outlooks(self) -> Dict:
        return _r({"live_tag": self.live_tag(),
                   "stages": actions.all_stage_outlooks(self.live_matrix, self.aov)})

    # ---------------------------------------------------------------- predict
    def predict(self, state: str, steps: int) -> Dict:
        m = self.live_matrix
        return _r({"live_tag": self.live_tag(), "state": state, "steps": steps,
                   "next": next_state(m, state), "k_step": k_step(m, state, steps),
                   "k_step_frozen": k_step(self.frozen_matrix, state, steps),
                   "trajectory": [k_step(m, state, k) for k in range(0, 9)],
                   "path": most_likely_path(m, state)})

    # ------------------------------------------------------------- validation
    def validation(self) -> Dict:
        if self._validation is not None:
            return self._validation
        tr = self.ds.transitions
        last = int(tr.batch.max())
        test, train = tr[tr.batch == last], tr[tr.batch < last]
        marg = np.bincount(train.b, minlength=len(STATES)).astype(float)
        base_state = int(marg.argmax())
        a, b = test.a.to_numpy(), test.b.to_numpy()
        B = self.batch_counts
        models = {
            "Frozen snapshot (first month only)": to_matrix(B[0]),
            "Static (all training months pooled)": to_matrix(np.sum(B[:-1], axis=0)),
        }
        for st in STRATEGIES:
            models[f"Adaptive: {st.replace('_', ' ')}"] = AdaptiveModel.replay(
                B[:-1], self.labels[:-1], strategy=st).current
        holdout = []
        for name, M in models.items():
            e = evaluate(M, a, b, base_state, marg)
            holdout.append({"model": name, **e})
        # rolling one-step-ahead: predict month k with what each model knew after month k-1
        rolling = []
        adaptive = AdaptiveModel.replay(B, self.labels, strategy=config.DEFAULT_STRATEGY)
        for k in range(1, len(B)):
            g = tr[tr.batch == k]
            ak, bk = g.a.to_numpy(), g.b.to_numpy()
            rolling.append({
                "month": self.labels[k],
                "frozen": evaluate(to_matrix(B[0]), ak, bk)["log_loss"],
                "static": evaluate(to_matrix(np.sum(B[:k], axis=0)), ak, bk)["log_loss"],
                "adaptive": evaluate(adaptive.versions[k - 1].matrix, ak, bk)["log_loss"],
            })
        truth = None
        if self.name == "synthetic":
            ci, cj = IDX["Add to Cart"], IDX["Purchase"]
            truth = {"true_after": 0.50,
                     "estimates": {name: float(M[ci, cj]) for name, M in models.items()},
                     "live_final": float(adaptive.current[ci, cj])}
        self._validation = _r({
            "test_label": self.labels[last], "train_labels": self.labels[:last],
            "n_test": int(len(test)), "baseline_state": STATES[base_state],
            "holdout": holdout, "rolling": rolling, "truth": truth,
        })
        return self._validation

    # ----------------------------------------------------------------- method
    def method(self) -> Dict:
        return _r({"dataset": self.name, "label": self.ds.label, "facts": self.ds.facts,
                   "batches": [{"label": l, "transitions": int(c.sum())}
                               for l, c in zip(self.labels, self.batch_counts)],
                   "config": {"churn_days": config.CHURN_DAYS, "loyal_at": config.LOYAL_AT,
                              "min_batch_days": config.MIN_BATCH_DAYS},
                   "unobserved": unobserved_states(np.sum(self.batch_counts, axis=0)),
                   "transient": [STATES[i] for i in TRANSIENT]})


class Registry:
    """Lazily-built workspaces, one per dataset, shared by all requests."""

    def __init__(self):
        self._ws: Dict[str, Workspace] = {}
        self._lock = threading.Lock()

    def datasets(self):
        return available_datasets()

    def default_name(self) -> str:
        avail = [d["name"] for d in available_datasets() if d["available"]]
        for pref in ("electronics", "cosmetics", "synthetic"):
            if pref in avail:
                return pref
        raise FileNotFoundError("no dataset files found under data/")

    def get(self, name: Optional[str] = None) -> Workspace:
        name = name or self.default_name()
        with self._lock:
            if name not in self._ws:
                self._ws[name] = Workspace(name)
            return self._ws[name]
