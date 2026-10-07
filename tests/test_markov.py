import numpy as np

from backend.engine.markov import (to_matrix, absorption, k_step, evaluate, assert_row_stochastic,
                                   unobserved_states, counts_from_pairs, most_likely_path)
from backend.engine.states import IDX, N, EXIT, STATES
from tests.helpers import toy_matrix, raises


def test_to_matrix_is_row_stochastic_and_exit_absorbing():
    counts = np.random.default_rng(0).integers(0, 50, size=(N, N)).astype(float)
    M = to_matrix(counts)
    assert_row_stochastic(M)
    assert M[EXIT, EXIT] == 1.0 and M[EXIT].sum() == 1.0


def test_unobserved_transient_state_goes_to_exit_and_absorption_still_works():
    # regression: with loyalty threshold 2, Repeat Purchase never occurs; a self-loop made (I - Q) singular
    counts = np.zeros((N, N))
    counts[IDX["Visitor"], IDX["Product View"]] = 10
    counts[IDX["Product View"], EXIT] = 10
    M = to_matrix(counts)
    assert M[IDX["Repeat Purchase"], EXIT] == 1.0
    assert "Repeat Purchase" in unobserved_states(counts)
    ab = absorption(M, "Visitor")
    assert abs(ab["steps_to_exit"] - 2.0) < 1e-9


def test_absorption_matches_monte_carlo():
    P = toy_matrix()
    ab = absorption(P, "Visitor")
    rng = np.random.default_rng(1)
    runs, reached, steps, orders = 40_000, {s: 0 for s in STATES}, 0, 0
    for _ in range(runs):
        s, seen = IDX["Visitor"], set()
        while s != EXIT:
            seen.add(s)
            steps += 1
            orders += s in (IDX["Purchase"], IDX["Repeat Purchase"], IDX["Loyal Customer"])
            s = rng.choice(N, p=P[s])
        for x in seen:
            reached[STATES[x]] += 1
    assert abs(steps / runs - ab["steps_to_exit"]) < 0.03
    assert abs(orders / runs - ab["expected_orders"]) < 0.005
    for s in ("Add to Cart", "Purchase", "Loyal Customer"):
        assert abs(reached[s] / runs - ab["prob_ever"][s]) < 0.006, s


def test_k_step_equals_matrix_power():
    P = toy_matrix()
    d = k_step(P, "Product View", 3)
    assert abs(sum(d.values()) - 1) < 1e-12
    assert np.allclose(list(d.values()), np.linalg.matrix_power(P, 3)[IDX["Product View"]])


def test_evaluate_scores_perfect_and_baseline():
    P = np.eye(N)
    a = np.array([0, 1, 2])
    e = evaluate(P, a, a, baseline_state=0, marginal=np.ones(N))
    assert e["accuracy"] == 1.0 and abs(e["baseline_accuracy"] - 1 / 3) < 1e-12
    assert e["log_loss"] < e["baseline_log_loss"]


def test_row_stochastic_check_catches_bad_rows():
    M = toy_matrix()
    M[0, 0] = -0.1
    raises(ValueError, assert_row_stochastic, M)


def test_most_likely_path_moves_forward_and_ends():
    path = most_likely_path(toy_matrix(cart_to_purchase=0.7), "Add to Cart")
    assert path[0] == "Add to Cart" and path[1] == "Purchase" and path[-1] == "Exit"


def test_counts_from_pairs():
    c = counts_from_pairs(np.array([0, 0, 1]), np.array([1, 1, 6]))
    assert c[0, 1] == 2 and c[1, 6] == 1 and c.sum() == 3
