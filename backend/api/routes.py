"""
routes.py
=========
The HTTP API as plain functions: each takes (registry, query, body) and
returns a JSON-able dict. Keeping routes framework-free means the same
handlers are unit-tested directly and served by backend/server.py.

    GET  /api/health
    GET  /api/datasets
    GET  /api/overview        ?dataset=
    GET  /api/matrix          ?dataset=&version=
    GET  /api/timeline        ?dataset=
    POST /api/stream          {dataset, action: next|prev|reset|latest|set, version?, strategy?}
    POST /api/simulate        {dataset, shifts: {lever_id: points}}
    POST /api/optimize        {dataset, budget_points, per_lever_points, objective}
    GET  /api/outlook         ?dataset=&stage=
    GET  /api/outlooks        ?dataset=
    POST /api/predict         {dataset, state, steps}
    GET  /api/validation      ?dataset=
    GET  /api/method          ?dataset=
    POST /api/advisor         {dataset, messages: [{role, content}]}
"""

from typing import Dict

from .. import config
from ..engine.adaptive import STRATEGIES
from ..engine.optimizer import OBJECTIVES
from ..engine.states import STATES, SHORT, LEVERS
from ..services import advisor


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _ws(reg, q, b):
    name = (b or {}).get("dataset") or (q or {}).get("dataset")
    try:
        return reg.get(name)
    except FileNotFoundError as exc:
        raise ApiError(404, str(exc))
    except ValueError as exc:
        raise ApiError(400, str(exc))


def _num(value, lo, hi, name):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ApiError(400, f"{name} must be a number")
    if not lo <= v <= hi:
        raise ApiError(400, f"{name} must be between {lo} and {hi}")
    return v


def _stage(value, allow_exit=False):
    if value not in STATES or (value == "Exit" and not allow_exit):
        raise ApiError(400, f"stage must be one of {[s for s in STATES if allow_exit or s != 'Exit']}")
    return value


def health(reg, q, b):
    return {"ok": True, "advisor_mode": "claude" if config.ANTHROPIC_API_KEY else "offline",
            "model": config.ANTHROPIC_MODEL if config.ANTHROPIC_API_KEY else None}


def datasets(reg, q, b):
    return {"datasets": reg.datasets(), "default": reg.default_name(),
            "states": STATES, "short": SHORT, "levers": LEVERS,
            "strategies": list(STRATEGIES), "objectives": OBJECTIVES,
            "defaults": {"budget_points": config.DEFAULT_BUDGET * 100,
                         "per_lever_points": config.DEFAULT_PER_LEVER_MAX * 100}}


def overview(reg, q, b):
    return _ws(reg, q, b).overview()


def matrix(reg, q, b):
    ws = _ws(reg, q, b)
    v = q.get("version")
    return ws.matrices(None if v in (None, "") else int(_num(v, 0, 999, "version")))


def timeline(reg, q, b):
    return _ws(reg, q, b).timeline()


def stream(reg, q, b):
    ws = _ws(reg, q, b)
    if b.get("strategy"):
        if b["strategy"] not in STRATEGIES:
            raise ApiError(400, f"strategy must be one of {list(STRATEGIES)}")
        keep = ws.live_version
        ws.set_strategy(b["strategy"])
        ws.set_version(keep)
    action = b.get("action", "latest")
    latest = len(ws.model.versions) - 1
    if action == "next":
        ws.set_version(ws.live_version + 1)
    elif action == "prev":
        ws.set_version(ws.live_version - 1)
    elif action == "reset":
        ws.set_version(0)
    elif action == "latest":
        ws.set_version(latest)
    elif action == "set":
        ws.set_version(int(_num(b.get("version"), 0, latest, "version")))
    else:
        raise ApiError(400, "action must be next, prev, reset, latest or set")
    return {"live": ws.live_tag(), "summary": ws.live.summary()}


def simulate(reg, q, b):
    ws = _ws(reg, q, b)
    raw = b.get("shifts") or {}
    ids = {lv["id"] for lv in LEVERS}
    shifts = {}
    for k, v in raw.items():
        if k not in ids:
            raise ApiError(400, f"unknown lever '{k}'")
        shifts[k] = _num(v, -100, 100, k) / 100.0
    return ws.simulate(shifts)


def optimize(reg, q, b):
    ws = _ws(reg, q, b)
    budget = _num(b.get("budget_points", config.DEFAULT_BUDGET * 100), 0.5, 60, "budget_points") / 100
    per = _num(b.get("per_lever_points", config.DEFAULT_PER_LEVER_MAX * 100), 0.5, 40, "per_lever_points") / 100
    objective = b.get("objective", "revenue")
    if objective not in OBJECTIVES:
        raise ApiError(400, f"objective must be one of {list(OBJECTIVES)}")
    return ws.optimise(budget, per, objective)


def outlook(reg, q, b):
    return _ws(reg, q, b).outlook(_stage(q.get("stage", "Add to Cart")))


def outlooks(reg, q, b):
    return _ws(reg, q, b).outlooks()


def predict(reg, q, b):
    ws = _ws(reg, q, b)
    return ws.predict(_stage(b.get("state", "Visitor")), int(_num(b.get("steps", 3), 1, 20, "steps")))


def validation(reg, q, b):
    return _ws(reg, q, b).validation()


def method(reg, q, b):
    return _ws(reg, q, b).method()


def advise(reg, q, b):
    ws = _ws(reg, q, b)
    msgs = b.get("messages")
    if not isinstance(msgs, list) or not msgs:
        raise ApiError(400, "messages must be a non-empty list")
    clean = []
    for m in msgs[-20:]:
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"].strip():
            clean.append({"role": m["role"], "content": m["content"][:4000]})
    if not clean or clean[-1]["role"] != "user":
        raise ApiError(400, "the last message must be from the user")
    return advisor.answer(ws, clean)


ROUTES: Dict = {
    ("GET", "/api/health"): health,
    ("GET", "/api/datasets"): datasets,
    ("GET", "/api/overview"): overview,
    ("GET", "/api/matrix"): matrix,
    ("GET", "/api/timeline"): timeline,
    ("POST", "/api/stream"): stream,
    ("POST", "/api/simulate"): simulate,
    ("POST", "/api/optimize"): optimize,
    ("GET", "/api/outlook"): outlook,
    ("GET", "/api/outlooks"): outlooks,
    ("POST", "/api/predict"): predict,
    ("GET", "/api/validation"): validation,
    ("GET", "/api/method"): method,
    ("POST", "/api/advisor"): advise,
}
