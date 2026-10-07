import numpy as np

from backend.engine.adaptive import (detect_drift, adaptive_alpha, AdaptiveModel, ewma_update,
                                     bayesian_update, sliding_window_update, STRATEGIES, total_variation,
                                     js_divergence)
from backend.engine.markov import to_matrix, assert_row_stochastic
from backend.engine.states import IDX, N
from backend.data.preprocess import load_dataset
from backend.engine.markov import counts_from_pairs
from tests.helpers import toy_matrix, sample_counts, raises


def test_drift_false_alarm_rate_on_stable_batches_is_low():
    # regression: the old goodness-of-fit test flagged ~50% of stable batches
    rng = np.random.default_rng(7)
    P = toy_matrix()
    flagged = 0
    for _ in range(40):
        drift = detect_drift(sample_counts(P, 900, rng), sample_counts(P, 900, rng))
        flagged += any(r.drift for r in drift.values())
    assert flagged / 40 <= 0.10, flagged


def test_drift_detects_the_planted_checkout_shift_in_the_right_row():
    rng = np.random.default_rng(11)
    hits, wrong = 0, 0
    for _ in range(20):
        drift = detect_drift(sample_counts(toy_matrix(0.35), 3000, rng), sample_counts(toy_matrix(0.50), 3000, rng))  # ~600 cart rows per batch
        hits += drift["Add to Cart"].drift
        wrong += sum(r.drift for s, r in drift.items() if s != "Add to Cart")
    assert hits >= 18 and wrong <= 2


def test_tiny_shift_with_huge_sample_is_significant_but_not_drift():
    ref = np.zeros((N, N)); new = np.zeros((N, N))
    ref[IDX["Visitor"], [IDX["Product View"], IDX["Exit"]]] = [600_000, 400_000]
    new[IDX["Visitor"], [IDX["Product View"], IDX["Exit"]]] = [605_000, 395_000]
    r = detect_drift(ref, new)["Visitor"]
    assert r.significant and not r.drift and r.tv < 0.02


def test_alpha_rises_for_drifted_rows_only():
    rng = np.random.default_rng(3)
    drift = detect_drift(sample_counts(toy_matrix(0.35), 3000, rng), sample_counts(toy_matrix(0.55), 3000, rng))
    alpha = adaptive_alpha(drift)
    assert alpha["Add to Cart"] >= 0.5
    assert all(abs(a - 0.30) < 1e-12 for s, a in alpha.items() if not drift[s].drift)


def test_update_strategies_stay_row_stochastic():
    rng = np.random.default_rng(5)
    c1, c2 = sample_counts(toy_matrix(), 500, rng), sample_counts(toy_matrix(0.5), 500, rng)
    assert_row_stochastic(ewma_update(to_matrix(c1), c2, 0.4))
    assert_row_stochastic(sliding_window_update([c1, c2], 2))
    m, post = bayesian_update(c1, c2, 0.9)
    assert_row_stochastic(m) and np.allclose(post, 0.9 * c1 + c2)
    raises(ValueError, ewma_update, to_matrix(c1), c2, 1.5)


def test_model_replay_keeps_every_version_and_moves_toward_new_behaviour():
    rng = np.random.default_rng(9)
    batches = [sample_counts(toy_matrix(0.35), 1500, rng) for _ in range(2)] + \
              [sample_counts(toy_matrix(0.50), 1500, rng) for _ in range(3)]
    for strategy in STRATEGIES:
        m = AdaptiveModel.replay(batches, [f"b{i}" for i in range(5)], strategy=strategy)
        assert len(m.versions) == 5
        c2p = [v.matrix[IDX["Add to Cart"], IDX["Purchase"]] for v in m.versions]
        assert c2p[-1] > c2p[1] + 0.05, (strategy, c2p)


def test_synthetic_data_flags_add_to_cart_when_the_shift_arrives():
    ds = load_dataset("synthetic")
    B = [counts_from_pairs(g.a, g.b) for _, g in ds.transitions.groupby("batch")]
    m = AdaptiveModel.replay(B, ds.batch_labels)
    assert [s for s, r in m.versions[2].drift.items() if r.drift] == ["Add to Cart"]
    assert m.versions[2].alpha["Add to Cart"] > 0.6
    assert not any(r.drift for r in m.versions[1].drift.values())


def test_divergences_basic_properties():
    p, q = np.array([0.5, 0.5, 0]), np.array([0.1, 0.9, 0])
    assert abs(total_variation(p, q) - 0.4) < 1e-12
    assert js_divergence(p, p) < 1e-9 and 0 < js_divergence(p, q) <= np.log(2)
