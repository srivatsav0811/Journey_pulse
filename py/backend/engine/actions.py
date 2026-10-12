"""
actions.py
==========
Next-best actions: for a customer at a given stage, which lever moves them
forward most, and what can the business actually do about it?

Two layers, kept deliberately separate:
  * the MATHS ranks levers by marginal value on the live matrix
    (optimizer.leverage) -- this part is computed, not assumed;
  * the PLAYBOOK maps each lever to common e-commerce tactics -- this part
    is a rule-based suggestion list, and is labelled as such in the UI.
"""

from typing import Dict

import numpy as np

from .optimizer import leverage
from .simulator import business_metrics, headroom
from .markov import next_state
from .states import STATES, IDX, EXIT, LEVERS, LEVER_BY_ID

PLAYBOOK = {
    "view_to_cart": [
        {"title": "Richer product pages", "detail": "More photos, specs and a comparison table on high-traffic products.", "channel": "Merchandising"},
        {"title": "Social proof at the decision point", "detail": "Show ratings, reviews and 'X bought this today' near the Add-to-Cart button.", "channel": "UX"},
        {"title": "Personalised recommendations", "detail": "'Frequently bought together' and similar-item carousels on product pages.", "channel": "Personalisation"},
    ],
    "cart_to_purchase": [
        {"title": "Cart-abandonment recovery", "detail": "Email or push reminder within 1–4 hours, with the cart contents.", "channel": "CRM"},
        {"title": "Remove checkout friction", "detail": "Guest checkout, fewer form fields, more payment options, show delivery cost early.", "channel": "UX"},
        {"title": "Targeted incentive", "detail": "Free-shipping threshold or a small time-limited discount for high-value carts.", "channel": "Pricing"},
    ],
    "purchase_to_repeat": [
        {"title": "Post-purchase journey", "detail": "Order-follow-up emails, setup guides and accessory suggestions in the first 2 weeks.", "channel": "CRM"},
        {"title": "Second-order voucher", "detail": "A voucher valid for 30 days, sent with the delivery confirmation.", "channel": "Pricing"},
        {"title": "Replenishment / upgrade reminders", "detail": "Remind buyers when accessories or consumables typically run out.", "channel": "CRM"},
    ],
    "repeat_to_loyal": [
        {"title": "Loyalty programme", "detail": "Points or tier status that unlocks after the second order.", "channel": "Loyalty"},
        {"title": "VIP treatment", "detail": "Early access to sales, priority support, extended warranty for repeat buyers.", "channel": "Service"},
        {"title": "Win-back before churn", "detail": "Trigger an offer when a repeat buyer is inactive for 3+ weeks.", "channel": "CRM"},
    ],
}


def stage_outlook(matrix: np.ndarray, stage: str, aov: float, objective: str = "revenue") -> Dict:
    """Where a customer currently at `stage` is heading, and what would move them."""
    if stage == "Exit":
        raise ValueError("Exit is absorbing; there is nothing to move forward")
    metrics = business_metrics(matrix, aov, start=stage)
    nxt = next_state(matrix, stage)
    lev = leverage(matrix, objective, start=stage)
    room = headroom(matrix)
    ranked = []
    for lever_id, gain in sorted(lev.items(), key=lambda kv: -kv[1]):
        if gain <= 0:
            continue
        lv = LEVER_BY_ID[lever_id]
        ranked.append({
            "lever": lever_id, "label": lv["label"], "business": lv["business"],
            "gain_per_point": gain,
            "revenue_gain_per_1k_per_point": gain * aov * 1000 if objective == "revenue" else None,
            "current": room[lever_id]["current"], "headroom": room[lever_id]["max_up"],
            "actions": PLAYBOOK[lever_id],
        })
    # "forward" = deeper into the journey (a later stage); for Loyal it is another order (its self-loop)
    i = IDX[stage]
    forward = {s: p for s, p in nxt.items() if (IDX[s] > i and IDX[s] != EXIT) or (stage == "Loyal Customer" and s == stage)}
    return {
        "stage": stage,
        "metrics": metrics,
        "next": nxt,
        "p_exit_next": nxt["Exit"],
        "p_forward_next": float(sum(forward.values())),
        "most_likely_next": max((s for s in STATES if s != stage), key=lambda s: nxt[s]),
        "ranked_levers": ranked,
        "best": ranked[0] if ranked else None,
    }


def all_stage_outlooks(matrix: np.ndarray, aov: float) -> Dict[str, Dict]:
    return {s: stage_outlook(matrix, s, aov) for s in STATES if s != "Exit"}


def biggest_leak(matrix: np.ndarray) -> Dict:
    """The transient row (excluding Visitor) that loses the most customers straight to Exit."""
    rows = [(s, float(matrix[IDX[s], EXIT])) for s in STATES if s not in ("Exit", "Visitor")]
    s, p = max(rows, key=lambda r: r[1])
    return {"stage": s, "p_exit": p}


def lever_by_stage():
    return {lv["from"]: lv["id"] for lv in LEVERS}
