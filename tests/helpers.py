"""Shared test helpers (no pytest-specific features, so tests also run with tests/run_tests.py)."""

import numpy as np

from backend.engine.markov import counts_from_pairs
from backend.engine.states import IDX, N, EXIT


def raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return True
    raise AssertionError(f"expected {exc_type.__name__}")


def toy_matrix(cart_to_purchase=0.35):
    """A funnel-shaped chain similar to the synthetic data."""
    P = np.zeros((N, N))
    P[IDX["Visitor"], [IDX["Product View"], EXIT]] = [0.6, 0.4]
    P[IDX["Product View"], [IDX["Product View"], IDX["Add to Cart"], EXIT]] = [0.1, 0.3, 0.6]
    P[IDX["Add to Cart"], [IDX["Product View"], IDX["Purchase"], EXIT]] = [0.1, cart_to_purchase, 0.9 - cart_to_purchase]
    P[IDX["Purchase"], [IDX["Repeat Purchase"], EXIT]] = [0.2, 0.8]
    P[IDX["Repeat Purchase"], [IDX["Loyal Customer"], EXIT]] = [0.4, 0.6]
    P[IDX["Loyal Customer"], [IDX["Loyal Customer"], EXIT]] = [0.7, 0.3]
    P[EXIT, EXIT] = 1.0
    return P


def sample_counts(P, n_journeys, rng):
    """Simulates customer journeys from Visitor until Exit and returns transition counts."""
    a, b = [], []
    for _ in range(n_journeys):
        s = IDX["Visitor"]
        while s != EXIT:
            t = rng.choice(N, p=P[s])
            a.append(s)
            b.append(t)
            s = t
    return counts_from_pairs(np.array(a), np.array(b))
