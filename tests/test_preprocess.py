import unittest

import numpy as np
import pandas as pd

from backend import config
from backend.data.preprocess import (map_clickstream, transitions_from_events, monthly_batches,
                                     load_dataset, available_datasets)
from backend.engine.states import STATES, IDX

# Two customers whose 19-digit IDs are neighbours: float64 cannot tell them apart.
A_ID, B_ID = 1515915625519388267, 1515915625519388268


def _log(rows):
    df = pd.DataFrame(rows, columns=["t", "event_type", "price", "user_id", "user_session"])
    df["t"] = pd.to_datetime(df.t)
    df["uid"] = pd.factorize(df.user_id)[0]
    df["sid"] = pd.factorize(df.user_session)[0]
    return df


def _seqs(events):
    return {c: [STATES[s] for s in g.state] for c, g in events.groupby("customer")}


LOG = [
    # customer A: browses, buys (two items = one order), keeps browsing, returns and buys again, then churns
    ("2021-01-01 10:00:00", "view", 10.0, A_ID, "s1"),
    ("2021-01-01 10:01:00", "view", 10.0, A_ID, "s1"),
    ("2021-01-01 10:02:00", "cart", 10.0, A_ID, "s1"),
    ("2021-01-01 10:05:00", "purchase", 10.0, A_ID, "s1"),
    ("2021-01-01 10:05:01", "purchase", 5.0, A_ID, "s1"),
    ("2021-01-01 10:06:00", "view", 7.0, A_ID, "s1"),
    ("2021-01-06 09:00:00", "view", 20.0, A_ID, "s2"),
    ("2021-01-06 09:03:00", "purchase", 20.0, A_ID, "s2"),
    # customer B: two sessions, removes from cart, still active near the end -> censored (no Exit)
    ("2021-01-02 12:00:00", "view", 3.0, B_ID, "s3"),
    ("2021-01-02 12:01:00", "cart", 3.0, B_ID, "s3"),
    ("2021-01-02 12:02:00", "remove_from_cart", 3.0, B_ID, "s3"),
    ("2021-03-01 08:00:00", "view", 3.0, B_ID, "s4"),
]
END = pd.Timestamp("2021-03-10 00:00:00")


def test_state_mapping_on_hand_written_log():
    ev = map_clickstream(_log(LOG), END, churn_days=30, loyal_at=3)
    seqs = _seqs(ev)
    assert seqs[0] == ["Visitor", "Product View", "Product View", "Add to Cart", "Purchase", "Repeat Purchase", "Exit"]
    assert seqs[1] == ["Visitor", "Product View", "Add to Cart", "Product View", "Visitor", "Product View"]
    # order value = both purchase rows of the session
    first_order = ev[(ev.customer == 0) & (ev.state == IDX["Purchase"])]
    assert first_order.value.iloc[0] == 15.0


def test_transitions_never_cross_customers():
    # regression: comparing float64-shifted IDs merged neighbouring customers
    ev = map_clickstream(_log(LOG), END, churn_days=30, loyal_at=3)
    tr = transitions_from_events(ev)
    assert len(tr) == (7 - 1) + (6 - 1)
    assert not ((tr.a == IDX["Exit"]).any())


def test_loyalty_threshold_and_orders():
    rows = [(f"2021-01-{d:02d} 10:00:00", e, 1.0, A_ID, f"s{d}") for d in (1, 5, 9, 13)
            for e in ("view", "purchase")]
    ev = map_clickstream(_log(rows), END, churn_days=30, loyal_at=3)
    assert _seqs(ev)[0] == ["Visitor", "Product View", "Purchase", "Repeat Purchase",
                            "Loyal Customer", "Loyal Customer", "Exit"]
    ev2 = map_clickstream(_log(rows), END, churn_days=30, loyal_at=2)
    assert "Repeat Purchase" not in _seqs(ev2)[0]


def test_short_first_month_is_merged():
    tr = pd.DataFrame({"src_time": pd.to_datetime(["2020-09-27", "2020-10-05", "2020-11-10", "2020-12-01"]),
                       "a": 0, "b": 1})
    out, labels = monthly_batches(tr, pd.Timestamp("2020-09-24"), pd.Timestamp("2020-12-20"))
    assert labels == ["Oct 2020", "Nov 2020", "Dec 2020"]
    assert out.batch.tolist() == [0, 0, 1, 2]


def test_synthetic_dataset_loads_into_four_batches():
    ds = load_dataset("synthetic")
    assert ds.batch_labels == ["Jan 1–7", "Jan 8–15", "Feb 1–7", "Feb 8–15"]
    assert set(ds.transitions.batch) == {0, 1, 2, 3}
    assert ds.transitions.a.isin(range(len(STATES))).all()


def test_real_electronics_data_if_present():
    if not any(d["name"] == "electronics" and d["available"] for d in available_datasets()):
        raise unittest.SkipTest("electronics CSV not downloaded")
    ds = load_dataset("electronics")
    tr = ds.transitions
    cutoff = pd.Timestamp(ds.facts["end"]) - pd.Timedelta(days=config.CHURN_DAYS)
    assert (tr.src_time <= cutoff).all()
    assert not (tr.a == IDX["Exit"]).any()
    assert ds.batch_labels[0] == "Oct 2020" and len(ds.batch_labels) == 4
    assert ds.facts["duplicates_removed"] == 655
    # lifecycle states only come from order stages: no browsing state leads straight to Repeat/Loyal
    funnel = tr.a.isin([IDX["Visitor"], IDX["Product View"], IDX["Add to Cart"]])
    assert not tr[funnel].b.isin([IDX["Repeat Purchase"], IDX["Loyal Customer"]]).any()
    assert 150 < ds.aov < 300


def test_synthetic_dataset_is_found_without_a_raw_data_folder():
    # regression: a fresh clone has no data/raw/, and glob could not resolve "raw/../synthetic"
    import tempfile
    from pathlib import Path
    from backend import config
    from backend.data import preprocess
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "synthetic").mkdir()
        (root / "synthetic" / "synthetic_customer_events.csv").write_text("x\n")
        old = config.RAW_DIR
        config.RAW_DIR = root / "raw"          # does not exist, like a fresh clone
        try:
            files = preprocess._files("synthetic")
        finally:
            config.RAW_DIR = old
    assert [f.name for f in files] == ["synthetic_customer_events.csv"]
