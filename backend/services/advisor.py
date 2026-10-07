"""
advisor.py
==========
The AI business advisor. A business user asks a question in plain words;
the advisor answers with numbers computed on the LIVE adaptive matrix and
suggests how to move customers forward.

Two modes, same response shape:
  * "claude"  - Claude (Anthropic Messages API, called over HTTPS with the
                standard library) with tools that run the engine. The model
                never sees or invents a probability it did not get from a tool.
  * "offline" - a deterministic analyst that recognises common business
                questions and answers them from the same engine calls.
                Used when there is no ANTHROPIC_API_KEY, no network, or the
                API call fails, so a live demo never breaks.

The API key is read from the environment only and never sent to the browser.
"""

import json
import re
import urllib.request
from typing import Callable, Dict, List, Optional

from .. import config
from ..engine.states import STATES, LEVERS, LEVER_BY_ID

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def pct(x: float) -> str:
    x = float(x) * 100
    return f"{x:.2f}%" if abs(x) < 1 else f"{x:.1f}%"


def pts(x: float) -> str:
    return f"{float(x) * 100:+.1f} pts"


def money(x: float) -> str:
    return f"{float(x):,.0f}"


# ---------------------------------------------------------------------------
# Tools (shared by both modes)
# ---------------------------------------------------------------------------
STAGE_ENUM = [s for s in STATES if s != "Exit"]
LEVER_ENUM = [lv["id"] for lv in LEVERS]

TOOLS = [
    {"name": "get_business_snapshot",
     "description": "Headline KPIs from the live model: chance a visitor ever places a first order, "
                    "second order, becomes loyal; orders and revenue per 1,000 visitors; biggest leak; "
                    "top lever; and the same KPIs from the frozen first-month snapshot for comparison.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_stage_outlook",
     "description": "For customers currently at one stage: where they go next, their chance of "
                    "ordering / becoming loyal, and levers ranked by value per +1 point, with tactics.",
     "input_schema": {"type": "object", "properties": {"stage": {"type": "string", "enum": STAGE_ENUM}},
                      "required": ["stage"]}},
    {"name": "simulate_change",
     "description": "What-if: raise (or lower, negative points) one or more levers by percentage points "
                    "and get the effect on first orders, repeat, loyalty and revenue, computed on the live "
                    "matrix and on the frozen snapshot.",
     "input_schema": {"type": "object", "properties": {"changes": {"type": "array", "items": {
         "type": "object", "properties": {"lever": {"type": "string", "enum": LEVER_ENUM},
                                          "points": {"type": "number", "description": "percentage points, e.g. 5"}},
         "required": ["lever", "points"]}}}, "required": ["changes"]}},
    {"name": "optimise_budget",
     "description": "Split an improvement budget (total percentage points across levers) to maximise an "
                    "objective. Also reports how much a plan made on the frozen snapshot would lose today.",
     "input_schema": {"type": "object", "properties": {
         "budget_points": {"type": "number", "description": "total points, default 15"},
         "objective": {"type": "string", "enum": ["revenue", "loyal", "first_order"]}}}},
    {"name": "get_drift_report",
     "description": "Month-by-month: which journey stages changed significantly (drift), how much the "
                    "adaptive model re-weighted them, and how key rates moved.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "predict_journey",
     "description": "Probability of each stage a given number of steps ahead for a customer at a stage, "
                    "plus the most likely path.",
     "input_schema": {"type": "object", "properties": {"stage": {"type": "string", "enum": STAGE_ENUM},
                                                       "steps": {"type": "integer", "minimum": 1, "maximum": 12}},
                      "required": ["stage"]}},
    {"name": "get_model_quality",
     "description": "How well the model predicts held-out behaviour versus a naive baseline, and how "
                    "adaptive updating compares with static and frozen models.",
     "input_schema": {"type": "object", "properties": {}}},
]


def run_tool(ws, name: str, args: Dict) -> Dict:
    """Executes a tool against the workspace's live model. Returns compact JSON-able data."""
    if name == "get_business_snapshot":
        o = ws.overview()
        return {"live_model": o["live"], "kpis": o["kpis"], "frozen_snapshot_kpis": o["frozen_kpis"],
                "average_order_value": o["aov"], "cart_abandonment_sessions": o["cart_abandonment"],
                "biggest_leak": o["biggest_leak"], "top_lever": o["top_lever"]}
    if name == "get_stage_outlook":
        o = ws.outlook(args.get("stage", "Add to Cart"))
        live = o["live"]
        return {"live_model": o["live_tag"], "stage": live["stage"], "metrics": live["metrics"],
                "next_step": live["next"], "p_exit_next": live["p_exit_next"],
                "ranked_levers": [{k: r[k] for k in ("lever", "label", "business", "gain_per_point",
                                                     "revenue_gain_per_1k_per_point", "current", "headroom", "actions")}
                                  for r in live["ranked_levers"]],
                "frozen_snapshot_best_lever": o["frozen_best"]}
    if name == "simulate_change":
        shifts = {}
        for ch in args.get("changes", []):
            if ch.get("lever") in LEVER_BY_ID:
                shifts[ch["lever"]] = shifts.get(ch["lever"], 0.0) + float(ch.get("points", 0)) / 100.0
        s = ws.simulate(shifts)
        return {"live_model": s["live_tag"], "applied_points": {k: v * 100 for k, v in s["applied"].items()},
                "live": s["live"], "frozen_snapshot": s["frozen"], "snapshot_error": s["snapshot_error"]}
    if name == "optimise_budget":
        budget = float(args.get("budget_points", config.DEFAULT_BUDGET * 100)) / 100.0
        o = ws.optimise(budget, config.DEFAULT_PER_LEVER_MAX, args.get("objective", "revenue"))
        return {"live_model": o["live_tag"], "objective": o["live"]["objective_label"],
                "allocation_points": {k: v * 100 for k, v in o["live"]["allocation"].items()},
                "baseline": o["live"]["baseline"], "optimised": o["live"]["optimised"],
                "relative_uplift": o["live"]["relative_uplift"],
                "grid_verified": o["live"]["grid"]["agrees"],
                "frozen_snapshot_allocation_points": {k: v * 100 for k, v in o["frozen"]["allocation"].items()},
                "frozen_snapshot_forecast_of_its_plan": o["frozen"]["optimised"],
                "cost_of_stale_plan": o["cost_of_stale_plan"], "average_order_value": o["aov"]}
    if name == "get_drift_report":
        t = ws.timeline()
        return {"live_model": t["live"], "months": [
            {"month": v["label"], "drift_states": v["drift_states"],
             "alpha": {k: a for k, a in v["alpha"].items() if a > config.BASE_ALPHA + 1e-6},
             "biggest_changes": {s: d["note"] for s, d in v["drift"].items() if d["drift"]},
             "live_rates": {k: v["kpis"][k] for k in ("cart_to_purchase", "view_to_cart", "purchase_to_repeat")},
             "month_only_rates": v["batch_kpis"]} for v in t["versions"]]}
    if name == "predict_journey":
        p = ws.predict(args.get("stage", "Visitor"), int(args.get("steps", 3)))
        return {"live_model": p["live_tag"], "stage": p["state"], "steps": p["steps"],
                "distribution": p["k_step"], "most_likely_path": p["path"]}
    if name == "get_model_quality":
        v = ws.validation()
        return {"test_month": v["test_label"], "holdout": v["holdout"], "rolling_log_loss": v["rolling"]}
    raise ValueError(f"unknown tool {name}")


# ---------------------------------------------------------------------------
# Claude mode
# ---------------------------------------------------------------------------
def system_prompt(ws) -> str:
    tag = ws.live_tag()
    levers = "\n".join(f"- {lv['id']}: {lv['label']} ({lv['business']})" for lv in LEVERS)
    return f"""You are the business advisor inside JourneyPulse, an adaptive customer-journey analytics tool.
You are talking to a business owner or manager of: {ws.ds.label}. Average order value: {ws.aov:,.2f}.

How the numbers work: customers move through Visitor -> Product View -> Add to Cart -> Purchase (first order)
-> Repeat Purchase (second order) -> Loyal Customer (third+), and can Exit (churn: 30 days inactive) from any stage.
A Markov transition matrix estimates the chance of each move. The matrix is ADAPTIVE: it is re-estimated every
month, with stronger updates where a statistical drift test finds that behaviour changed. The live model is
version {tag['version']} (data through {tag['label']}). Every tool reads this live matrix, never a frozen snapshot;
tools also report what the frozen first-month snapshot ({tag['frozen_label']}) would have said.

Levers the business can pull (ids for tools):
{levers}

Rules:
- Never state a number you did not get from a tool in this conversation. Call tools whenever you need figures.
- Answer the question asked, in plain business language. Avoid matrix jargon unless the user asks for it.
- When asked what to do, give: the lever to prioritise, its computed impact (simulate_change or optimise_budget),
  and 2-3 concrete tactics from the tool's playbook. Say the ranking is computed and the tactics are suggestions.
- If the frozen snapshot would give a materially different answer, say so briefly: it shows why the live model matters.
- Percentages to 1 decimal place (2 if under 1%). Revenue as per 1,000 visitors. Under 180 words.
- Use short paragraphs and '-' bullets; **bold** for the key number. No tables, no headings."""


def _post(payload: Dict, api_key: str) -> Dict:
    req = urllib.request.Request(
        config.ANTHROPIC_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=config.ADVISOR_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode())


def ask_claude(ws, history: List[Dict], api_key: str,
               transport: Optional[Callable[[Dict, str], Dict]] = None) -> Dict:
    """Tool-use loop: Claude requests tools, we run them on the live matrix, until it answers."""
    transport = transport or _post
    messages = [{"role": m["role"], "content": m["content"]} for m in history if m.get("content")]
    used = []
    for _ in range(config.ADVISOR_MAX_TOOL_ROUNDS + 1):
        resp = transport({"model": config.ANTHROPIC_MODEL, "max_tokens": 900, "system": system_prompt(ws),
                          "tools": TOOLS, "messages": messages}, api_key)
        content = resp.get("content", [])
        if resp.get("stop_reason") != "tool_use":
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
            return {"reply": text, "tools": used}
        messages.append({"role": "assistant", "content": content})
        results = []
        for block in content:
            if block.get("type") != "tool_use":
                continue
            used.append({"name": block["name"], "input": block.get("input", {})})
            try:
                out = run_tool(ws, block["name"], block.get("input", {}))
                results.append({"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps(out)})
            except Exception as exc:  # report tool errors back to the model rather than crashing
                results.append({"type": "tool_result", "tool_use_id": block["id"],
                                "content": f"error: {exc}", "is_error": True})
        messages.append({"role": "user", "content": results})
    raise RuntimeError("too many tool rounds")


# ---------------------------------------------------------------------------
# Offline analyst
# ---------------------------------------------------------------------------
LEVER_PATTERNS = {
    "cart_to_purchase": r"checkout|abandon|cart\W+(?:to\W+)?(?:purchase|order|buy|conver)|complete (?:the )?(?:purchase|order)",
    "view_to_cart": r"(?:product page|product|view|page)\W+(?:to\W+)?cart(?:\W+(?:conver\w*|rate))?|add[- ]to[- ]cart|product page|browse",
    "purchase_to_repeat": r"repeat|second order|come back|coming back|return(?:ing)? (?:customer|buyer)|retention|re-?order|buy again",
    "repeat_to_loyal": r"loyal|loyalty|third order|vip",
}
STAGE_PATTERNS = [
    ("Add to Cart", r"\bcart"), ("Product View", r"\bview|product page|brows"),
    ("Repeat Purchase", r"repeat|second order"), ("Loyal Customer", r"loyal"),
    ("Purchase", r"first order|purchase|bought|buyer"), ("Visitor", r"visitor|new (?:user|customer)|land"),
]
SUGGESTIONS = [
    "Where are we losing the most customers?",
    "What if we improve checkout completion by 5 points?",
    "How should we spend a 5-point improvement budget?",
    "What should we do for customers who added to cart but didn't buy?",
    "What changed in customer behaviour over the last months?",
    "How do we turn first-time buyers into loyal customers?",
    "How accurate is this model?",
]


def _levers_in(text: str) -> List[str]:
    """Levers mentioned in the text; a matched phrase is removed so it can't also match a later pattern."""
    found = []
    for lid in ("view_to_cart", "purchase_to_repeat", "repeat_to_loyal", "cart_to_purchase"):
        m = re.search(LEVER_PATTERNS[lid], text)
        if m:
            found.append(lid)
            text = text[:m.start()] + " " + text[m.end():]
    return found


def _stage_in(text: str) -> Optional[str]:
    for stage, pat in STAGE_PATTERNS:
        if re.search(pat, text):
            return stage
    return None


def _points_in(text: str) -> Optional[float]:
    m = re.search(r"(-?\d+(?:\.\d+)?)[\s-]*(?:%|percent|per cent|pts?\b|points?|pp\b)", text) or \
        re.search(r"\bby\s+(-?\d+(?:\.\d+)?)\b", text)
    if not m:
        return None
    v = float(m.group(1))
    if re.search(r"drop|fall|decreas|lower|reduc|worse|declin|lose", text) and v > 0 and "exit" not in text:
        v = -v
    return v


def _tactics(actions_list, n=3):
    return "\n".join(f"- **{a['title']}** — {a['detail']}" for a in actions_list[:n])


def offline_answer(ws, question: str) -> Dict:
    q = question.lower().strip()
    tag = ws.live_tag()
    live_note = f"_Live model v{tag['version']} · data through {tag['label']}._"
    tools = []

    def use(name, args=None):
        tools.append({"name": name, "input": args or {}})
        return run_tool(ws, name, args or {})

    levers = _levers_in(q)
    points = _points_in(q)
    stage = _stage_in(q)

    # 1. budget / prioritisation (before what-if: 'spend 20 points' is not a scenario)
    if re.search(r"budget|invest|allocat|spend|priorit|where should|best use|focus on|biggest impact|most impact|optimi", q):
        budget = points if points and points > 0 else config.DEFAULT_BUDGET * 100
        objective = "loyal" if "loyal" in q else "first_order" if re.search(r"first order|conver|acquisi", q) else "revenue"
        o = use("optimise_budget", {"budget_points": budget, "objective": objective})
        alloc = sorted(o["allocation_points"].items(), key=lambda kv: -kv[1])
        lines = "\n".join(f"- {LEVER_BY_ID[k]['label']}: **{v:.1f} pts**" for k, v in alloc if v > 0.05)
        top = alloc[0][0]
        cost = o["cost_of_stale_plan"] / max(o["optimised"], 1e-12)
        fc = (o["frozen_snapshot_forecast_of_its_plan"] - o["optimised"]) / max(o["optimised"], 1e-12)
        used = sum(v for _, v in alloc)
        if used < budget - 0.05:
            lines += (f"\n\n_Only {used:.1f} of the {budget:.0f} points can be used: each lever is capped at "
                      f"{config.DEFAULT_PER_LEVER_MAX * 100:.0f} points (change the cap on the Budget optimiser page)._")
        stale = (f"A plan made on the frozen snapshot would deliver {cost:.1%} less today." if cost > 0.0005 else
                 f"The frozen snapshot would pick the same split, but its forecast of the result is off by {fc:+.1%}.")
        outl = run_tool(ws, "get_stage_outlook", {"stage": LEVER_BY_ID[top]["from"]})
        acts = next((r["actions"] for r in outl["ranked_levers"] if r["lever"] == top), [])
        reply = (f"Best split of a **{budget:.0f}-point** budget to maximise {o['objective'].lower()}:\n{lines}\n\n"
                 f"That lifts the objective by **{o['relative_uplift']:+.1%}** (grid-checked: {'yes' if o['grid_verified'] else 'no'}). "
                 f"{stale}\n\n"
                 f"Suggested tactics for the top lever ({LEVER_BY_ID[top]['business']}):\n{_tactics(acts, 2)}\n\n{live_note}")
        return {"reply": reply, "tools": tools, "intent": "budget"}

    # 2. what-if
    if re.search(r"what if|what happens|if we|suppose|imagine|scenario|simulat", q) or \
            (points is not None and levers and re.search(r"increas|improv|rais|boost|grow|lift|drop|fall|decreas|reduc", q)):
        lever_ids = levers or ["cart_to_purchase"]
        p = points if points is not None else 5.0
        s = use("simulate_change", {"changes": [{"lever": l, "points": p} for l in lever_ids]})
        lv, up = s["live"], s["live"]["uplift"]
        names = ", ".join(LEVER_BY_ID[l]["label"] for l in lever_ids)
        applied = ", ".join(f"{LEVER_BY_ID[k]['label']} {v:+.1f} pts" for k, v in s["applied_points"].items()) or "no change possible"
        err = s["snapshot_error"]["revenue_per_1k"]
        reply = (f"If **{names}** moves by {p:+.1f} percentage points (applied: {applied}):\n"
                 f"- Revenue per 1,000 visitors: {money(lv['baseline']['revenue_per_1k'])} → **{money(lv['scenario']['revenue_per_1k'])}** "
                 f"({up['revenue_per_1k'] / max(lv['baseline']['revenue_per_1k'], 1e-9):+.1%})\n"
                 f"- Chance a visitor places a first order: {pct(lv['baseline']['p_first_order'])} → {pct(lv['scenario']['p_first_order'])}\n"
                 f"- Chance a visitor becomes loyal: {pct(lv['baseline']['p_loyal'])} → {pct(lv['scenario']['p_loyal'])}\n\n"
                 f"The same scenario on the frozen {tag['frozen_label']} snapshot would predict "
                 f"{money(s['frozen_snapshot']['scenario']['revenue_per_1k'])} per 1,000 visitors "
                 f"({'+' if err >= 0 else ''}{money(err)} vs the live model).\n\n{live_note}")
        return {"reply": reply, "tools": tools, "intent": "what_if"}

    # 3. drift / trends
    if re.search(r"chang|trend|drift|over time|lately|recent|month|season|black friday|holiday|november|december|january|evolv", q):
        d = use("get_drift_report")
        lines = []
        for m in d["months"][1:]:
            if m["biggest_changes"]:
                ch = "; ".join(f"{s}: {note.replace('drift: ', '→ ')}" for s, note in m["biggest_changes"].items())
                al = ", ".join(f"{s} α={a:.2f}" for s, a in m["alpha"].items())
                lines.append(f"- **{m['month']}**: {ch} (model re-weighted {al})")
            else:
                lines.append(f"- **{m['month']}**: no meaningful change — model updated gently (α={config.BASE_ALPHA:.2f})")
        first, last = d["months"][0], d["months"][-1]
        reply = (f"Month by month, the adaptive model tested each stage for a real behaviour change:\n" + "\n".join(lines) +
                 f"\n\nCheckout completion (Cart → first order) in the live model: {pct(first['live_rates']['cart_to_purchase'])} "
                 f"({first['month']}) → **{pct(last['live_rates']['cart_to_purchase'])}** ({last['month']}).\n\n{live_note}")
        return {"reply": reply, "tools": tools, "intent": "drift"}

    # 4. accuracy / trust
    if re.search(r"accura|trust|reliab|valid|how good|confiden|correct", q):
        v = use("get_model_quality")
        best = min(v["holdout"], key=lambda r: r["log_loss"])
        h0 = v["holdout"][0]
        reply = (f"Tested on **{v['test_month']}**, which the model never saw:\n"
                 f"- Next-step accuracy: **{pct(best['accuracy'])}** vs {pct(best['baseline_accuracy'])} for a naive always-guess-the-most-common-step baseline\n"
                 f"- Excluding the trivial first click: {pct(best['accuracy_excl_visitor'])} vs {pct(best['baseline_accuracy_excl_visitor'])}\n"
                 f"- Best-calibrated model: {best['model']} (log-loss {best['log_loss']:.4f}; frozen snapshot {h0['log_loss']:.4f})\n\n"
                 f"On this data behaviour drifts slowly, so adaptive and static models score close; the adaptive model matters most after real shifts.\n\n{live_note}")
        return {"reply": reply, "tools": tools, "intent": "quality"}

    # 5. loyalty / retention
    if re.search(r"loyal|retain|retention|repeat|come back|second order|lifetime", q):
        o = use("get_stage_outlook", {"stage": "Purchase"})
        r2 = o["ranked_levers"]
        m = o["metrics"]
        top = r2[0] if r2 else None
        reply = (f"Of customers who place a first order, **{pct(o['next_step']['Repeat Purchase'])}** come back for a second; "
                 f"from a first order the chance of eventually becoming loyal is **{pct(m['p_loyal'])}**.\n")
        if top:
            reply += (f"\nThe strongest lever from here is **{top['label']}**: each +1 point adds "
                      f"{money(top['revenue_gain_per_1k_per_point'])} revenue per 1,000 first-time buyers.\n"
                      f"Suggested tactics:\n{_tactics(top['actions'])}\n")
        reply += f"\n{live_note}"
        return {"reply": reply, "tools": tools, "intent": "loyalty"}

    # 6. prediction
    if re.search(r"predict|where will|likely|next step|forecast|future|in \d+ steps", q):
        steps = int(re.search(r"(\d+)\s*step", q).group(1)) if re.search(r"(\d+)\s*step", q) else 3
        p = use("predict_journey", {"stage": stage or "Visitor", "steps": min(max(steps, 1), 12)})
        top = sorted(p["distribution"].items(), key=lambda kv: -kv[1])[:4]
        reply = (f"For a customer at **{p['stage']}**, {p['steps']} steps ahead:\n" +
                 "\n".join(f"- {s}: {pct(v)}" for s, v in top) +
                 f"\n\nMost likely path: {' → '.join(p['most_likely_path'])}.\n\n{live_note}")
        return {"reply": reply, "tools": tools, "intent": "predict"}

    # 7. stage-specific "how do we move them forward"
    if stage and re.search(r"customer|people|user|shopper|who|stuck|forward|nudge|push|convert|do for|help", q):
        o = use("get_stage_outlook", {"stage": stage})
        r2 = o["ranked_levers"]
        reply = (f"Customers at **{stage}**: next step is {pct(o['p_exit_next'])} likely to be churn; "
                 f"their chance of an eventual first order is {pct(o['metrics']['p_first_order'])} and they are worth "
                 f"**{money(o['metrics']['revenue_per_1k'])}** per 1,000 customers today.\n")
        if r2:
            top = r2[0]
            reply += (f"\nBest move forward: **{top['label']}** ({top['business']}) — +1 point adds "
                      f"{money(top['revenue_gain_per_1k_per_point'])} per 1,000 of these customers.\nTactics:\n{_tactics(top['actions'])}\n")
            if o["frozen_snapshot_best_lever"] and o["frozen_snapshot_best_lever"] != top["lever"]:
                reply += f"\nNote: the frozen snapshot would have prioritised {LEVER_BY_ID[o['frozen_snapshot_best_lever']]['label']} instead.\n"
        reply += f"\n{live_note}"
        return {"reply": reply, "tools": tools, "intent": "stage"}

    # 8. leaks / problems
    if re.search(r"drop|leak|los(e|ing)|bottleneck|abandon|weak|problem|churn|exit|fail|wrong|worst", q) or levers:
        s = use("get_business_snapshot")
        leak = s["biggest_leak"]
        top = s["top_lever"]
        outl = run_tool(ws, "get_stage_outlook", {"stage": LEVER_BY_ID[top["id"]]["from"]})
        acts = next((r["actions"] for r in outl["ranked_levers"] if r["lever"] == top["id"]), [])
        reply = (f"The biggest leak is **{leak['stage']}**: {pct(leak['p_exit'])} of customers there leave instead of moving forward. "
                 f"Cart abandonment (sessions with a cart but no order) is {pct(s['cart_abandonment_sessions'] or 0)}.\n\n"
                 f"The most valuable fix is **{top['label']}**: every +1 point is worth about "
                 f"**{money(top['revenue_per_1k_per_point'])}** more revenue per 1,000 visitors.\n"
                 f"Suggested tactics:\n{_tactics(acts)}\n\n{live_note}")
        return {"reply": reply, "tools": tools, "intent": "leak"}

    # 9. overview (also the default)
    s = use("get_business_snapshot")
    k, fz = s["kpis"], s["frozen_snapshot_kpis"]
    greeting = bool(re.search(r"^(hi|hello|hey|help|what can you)", q))
    intro = ("I'm your journey advisor. Ask me what-ifs, where to invest, which customers to nudge, or what changed.\n\n"
             if greeting else "")
    reply = (intro + f"Here's the business right now (live model):\n"
             f"- Revenue per 1,000 visitors: **{money(k['revenue_per_1k'])}** (frozen snapshot said {money(fz['revenue_per_1k'])})\n"
             f"- Chance a visitor ever orders: **{pct(k['p_first_order'])}**; orders again: {pct(k['p_repeat'])}; becomes loyal: {pct(k['p_loyal'])}\n"
             f"- Biggest leak: {s['biggest_leak']['stage']} ({pct(s['biggest_leak']['p_exit'])} leave instead of moving forward)\n"
             f"- Most valuable lever: **{s['top_lever']['label']}**\n\n{live_note}")
    return {"reply": reply, "tools": tools, "intent": "overview"}


def _suggest(intent: str) -> List[str]:
    order = {"what_if": [2, 3, 5], "budget": [1, 3, 5], "drift": [1, 2, 6], "quality": [0, 4, 2],
             "loyalty": [2, 1, 3], "stage": [1, 2, 5], "predict": [0, 3, 2], "leak": [1, 3, 2],
             "overview": [0, 1, 2]}.get(intent, [0, 1, 2])
    return [SUGGESTIONS[i] for i in order]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def answer(ws, history: List[Dict], transport=None) -> Dict:
    """
    history: [{"role": "user"|"assistant", "content": str}, ...], last one from the user.
    Always returns a reply; Claude is tried first when a key is configured.
    """
    if not history or history[-1].get("role") != "user":
        raise ValueError("history must end with a user message")
    question = str(history[-1]["content"])[:2000]
    intent = offline_answer_intent(question)
    base = {"live_tag": ws.live_tag(), "suggestions": _suggest(intent)}
    key = config.ANTHROPIC_API_KEY
    if key or transport:
        try:
            out = ask_claude(ws, history[-12:], key, transport)
            if out["reply"]:
                return {**base, **out, "source": "claude", "model": config.ANTHROPIC_MODEL}
        except Exception as exc:  # any failure (network, auth, bad reply) falls back so the demo never breaks
            fallback = offline_answer(ws, question)
            return {**base, **fallback, "source": "offline", "model": "offline analyst",
                    "notice": f"Claude unavailable ({type(exc).__name__}); answered offline."}
    out = offline_answer(ws, question)
    return {**base, **out, "source": "offline", "model": "offline analyst"}


def offline_answer_intent(question: str) -> str:
    """Cheap intent guess used only to pick follow-up suggestions."""
    q = question.lower()
    for intent, pat in [("what_if", r"what if|suppose|imagine|scenario"), ("budget", r"budget|invest|spend|priorit"),
                        ("drift", r"chang|trend|drift|month"), ("quality", r"accura|trust|reliab"),
                        ("loyalty", r"loyal|retention|repeat"), ("leak", r"drop|leak|los|abandon|churn")]:
        if re.search(pat, q):
            return intent
    return "overview"
