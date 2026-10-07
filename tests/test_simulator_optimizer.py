import numpy as np

from backend.engine.simulator import apply_shifts, scenario, headroom, business_metrics
from backend.engine.optimizer import optimise, leverage, objective_value
from backend.engine.actions import stage_outlook, biggest_leak
from backend.engine.markov import assert_row_stochastic
from backend.engine.states import IDX, EXIT
from tests.helpers import toy_matrix


def test_shifts_are_clamped_and_rows_stay_stochastic():
    # regression: the mid-review _apply_shifts could make probabilities negative
    P = toy_matrix()
    M, applied = apply_shifts(P, {"cart_to_purchase": 0.9, "view_to_cart": -0.9})
    assert_row_stochastic(M)
    assert abs(applied["cart_to_purchase"] - P[IDX["Add to Cart"], EXIT]) < 1e-12
    assert M[IDX["Add to Cart"], EXIT] == 0.0 and M[IDX["Product View"], IDX["Add to Cart"]] == 0.0


def test_scenario_reports_live_frozen_and_snapshot_error():
    live, frozen = toy_matrix(0.5), toy_matrix(0.35)
    s = scenario(live, frozen, {"purchase_to_repeat": 0.05}, aov=100)
    assert s["live"]["uplift"]["revenue_per_1k"] > 0
    assert s["snapshot_error"]["revenue_per_1k"] < 0     # frozen model under-states revenue here


def test_optimiser_matches_brute_force_grid_and_respects_budget():
    P = toy_matrix()
    for objective in ("revenue", "loyal", "first_order"):
        r = optimise(P, budget=0.15, per_lever_max=0.10, objective=objective)
        assert r["grid"]["agrees"], objective
        assert sum(r["allocation"].values()) <= 0.15 + 1e-6
        assert r["optimised"] >= r["baseline"]


def test_optimiser_never_exceeds_headroom():
    P = toy_matrix()
    P[IDX["Add to Cart"], IDX["Purchase"]] += P[IDX["Add to Cart"], EXIT] - 0.01
    P[IDX["Add to Cart"], EXIT] = 0.01
    r = optimise(P, budget=0.2, per_lever_max=0.1)
    assert r["allocation"]["cart_to_purchase"] <= 0.01 + 1e-9


def test_leverage_is_zero_for_levers_behind_the_customer():
    lev = leverage(toy_matrix(), "revenue", start="Purchase")
    assert lev["view_to_cart"] == 0.0 and lev["cart_to_purchase"] == 0.0
    assert lev["purchase_to_repeat"] > 0


def test_stage_outlook_ranks_levers_and_attaches_playbook():
    o = stage_outlook(toy_matrix(), "Add to Cart", aov=50)
    assert o["best"]["lever"] == "cart_to_purchase"
    assert len(o["best"]["actions"]) >= 2
    assert abs(sum(o["next"].values()) - 1) < 1e-9


def test_metrics_and_leak():
    m = business_metrics(toy_matrix(), aov=10)
    assert abs(m["revenue_per_1k"] - m["orders_per_visitor"] * 10 * 1000) < 1e-9
    assert biggest_leak(toy_matrix())["stage"] == "Purchase"
    assert headroom(toy_matrix())["cart_to_purchase"]["max_up"] == toy_matrix()[IDX["Add to Cart"], EXIT]
    assert objective_value(toy_matrix(), "first_order") == business_metrics(toy_matrix(), 1)["p_first_order"]
