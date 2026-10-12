"""Bring-your-own-data: guessing, building, error messages, the routes and the data preview."""
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from backend.api import routes
from backend.data import custom, preprocess
from backend.engine.markov import assert_row_stochastic
from backend.services.workspace import Registry
from tests.helpers import raises

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = str(ROOT / "frontend" / "sample" / "business_sample.csv")
ROLE_MAP = {"Viewed product": "view", "Added to basket": "cart", "Removed from basket": "remove_from_cart",
            "Placed order": "purchase"}
MAPPING = {"time": "When", "user": "Customer", "event": "Action", "price": "Order value", "event_map": ROLE_MAP}


def _csv(df, d, name="data.csv"):
    p = str(Path(d) / name)
    df.to_csv(p, index=False)
    return p


def test_inspect_guesses_columns_and_actions_from_a_file_with_unfamiliar_names():
    ins = custom.inspect_csv(SAMPLE)
    assert ins["guess"] == {"time": "When", "user": "Customer", "event": "Action", "session": None, "price": "Order value"}
    roles = {e["value"]: e["role"] for e in ins["event_values"]}
    assert roles == ROLE_MAP
    assert ins["n_rows"] > 8000 and ins["time_check"]["parsed_share"] == 1.0
    assert len(ins["preview"]["rows"]) == 8


def test_guess_role_reads_common_action_labels():
    g = custom.guess_role
    assert [g(x) for x in ("add_to_cart", "Added to basket", "remove_from_cart", "Removed from bag")] == \
        ["cart", "cart", "remove_from_cart", "remove_from_cart"]
    assert [g(x) for x in ("purchase", "Placed order", "transaction", "Bought")] == ["purchase"] * 4
    assert [g(x) for x in ("view", "page_view", "Product Viewed", "click")] == ["view"] * 4
    assert [g(x) for x in ("Order cancelled", "refund", "checkout started", "newsletter")] == ["ignore"] * 4


def test_build_dataset_runs_the_full_pipeline_and_every_page_can_read_it():
    ds = custom.build_dataset(SAMPLE, {**MAPPING, "churn_days": 30, "loyal_at": 3}, "business_sample.csv")
    assert ds.name == "custom" and len(ds.batch_labels) >= 3 and ds.facts["batch_unit"] == "month"
    assert ds.facts["customers"] == 1400 and ds.facts["has_order_value"] and 30 < ds.aov < 60
    reg = Registry()
    reg.add_custom(ds)
    ws = reg.get("custom")
    for m in ws.model.versions:
        assert_row_stochastic(m.matrix)
    q = {"dataset": "custom"}
    for fn, body in ((routes.overview, {}), (routes.timeline, {}), (routes.validation, {}), (routes.method, {}),
                     (routes.simulate, {"shifts": {"cart_to_purchase": 0.02}}),
                     (routes.optimize, {"budget_points": 5, "per_lever_points": 3, "objective": "revenue"})):
        out = fn(reg, q, {**body, "dataset": "custom"})
        json.dumps(out, allow_nan=False)
    assert any(d["name"] == "custom" and d["custom"] for d in reg.datasets())
    assert reg.remove_custom() and not any(d["name"] == "custom" for d in reg.datasets())


def test_messy_formats_day_first_dates_epoch_times_odd_names_no_price_no_session():
    raw = pd.read_csv(SAMPLE)
    t = pd.to_datetime(raw["When"])
    with tempfile.TemporaryDirectory() as d:
        dayfirst = pd.DataFrame({"ts": t.dt.strftime("%d/%m/%Y %H:%M"), "uid": raw["Customer"],
                                 "evt": raw["Action"].map({"Viewed product": "PAGE", "Added to basket": "CART",
                                                           "Removed from basket": "UNCART", "Placed order": "BUY"})})
        p = _csv(dayfirst, d)
        ins = custom.inspect_csv(p)
        assert ins["guess"]["time"] == "ts" and ins["guess"]["user"] == "uid" and ins["guess"]["event"] == "evt"
        assert ins["time_check"]["dayfirst_suggested"] is True
        m = {**ins["guess"], "dayfirst": True, "aov": 30,
             "event_map": {"PAGE": "view", "CART": "cart", "UNCART": "remove_from_cart", "BUY": "purchase"}}
        ds = custom.build_dataset(p, m, "dayfirst.csv")
        ref = custom.build_dataset(SAMPLE, MAPPING, "ref.csv")
        assert ds.facts["customers"] == ref.facts["customers"] and ds.batch_labels == ref.batch_labels
        assert abs(ds.aov - 30) < 1e-9                                # no price column: the fallback value is used
        assert any("No order value" in w for w in ds.facts["warnings"])
        epoch = dayfirst.assign(ts=(t - pd.Timestamp("1970-01-01")).dt.total_seconds().astype(int))   # unit-safe across pandas versions
        p2 = _csv(epoch, d, "epoch.csv")
        assert custom.inspect_csv(p2)["guess"]["time"] == "ts"
        ds2 = custom.build_dataset(p2, {**m, "dayfirst": False}, "epoch.csv")
        assert ds2.facts["customers"] == ref.facts["customers"]


def test_purchase_only_exports_work_but_warn_that_the_funnel_is_missing():
    rng = np.random.default_rng(3)
    rows = []
    for c in range(400):
        day = rng.uniform(0, 100)
        for _ in range(int(rng.choice([1, 2, 3], p=[0.6, 0.3, 0.1]))):
            rows.append([pd.Timestamp("2026-01-01") + pd.Timedelta(days=float(day)), f"c{c}", "order", round(float(rng.uniform(10, 90)), 2)])
            day += rng.uniform(5, 40)
    df = pd.DataFrame(rows, columns=["date", "customer", "type", "amount"])
    with tempfile.TemporaryDirectory() as d:
        p = _csv(df, d)
        ins = custom.inspect_csv(p)
        assert ins["guess"]["price"] == "amount"
        ds = custom.build_dataset(p, {**ins["guess"], "event_map": {"order": "purchase"}}, "orders.csv")
        assert ds.facts["no_browsing_events"] and any("no browsing" in w for w in ds.facts["warnings"])
        reg = Registry()
        reg.add_custom(ds)
        json.dumps(routes.overview(reg, {"dataset": "custom"}, {}), allow_nan=False)


def test_friendly_errors():
    with tempfile.TemporaryDirectory() as d:
        empty = Path(d) / "empty.csv"
        empty.write_text("")
        assert raises(custom.UploadError, custom.inspect_csv, str(empty))
        two = _csv(pd.DataFrame({"a": [1, 2], "b": [3, 4]}), d, "two.csv")
        assert raises(custom.UploadError, custom.inspect_csv, two)
    with tempfile.TemporaryDirectory() as d:
        base = {**MAPPING}
        no_buy = {**base, "event_map": {k: v for k, v in ROLE_MAP.items() if v != "purchase"}}
        assert raises(custom.UploadError, custom.build_dataset, SAMPLE, no_buy)          # nothing marked as a purchase
        assert raises(custom.UploadError, custom.build_dataset, SAMPLE, {**base, "user": "Nope"})
        assert raises(custom.UploadError, custom.build_dataset, SAMPLE, {**base, "user": "When"})   # duplicate column
        assert raises(custom.UploadError, custom.build_dataset, SAMPLE, {**base, "event_map": {"Placed order": "bought"}})
        assert raises(custom.UploadError, custom.build_dataset, SAMPLE, {**base, "churn_days": 0})
        old = custom.MAX_ROWS
        custom.MAX_ROWS = 100
        try:
            assert raises(custom.UploadError, custom.build_dataset, SAMPLE, base)         # too many rows for this version
        finally:
            custom.MAX_ROWS = old
        raw = pd.read_csv(SAMPLE)
        short = raw[pd.to_datetime(raw["When"]) < "2026-02-10"]
        assert raises(custom.UploadError, custom.build_dataset, _csv(short, d, "short.csv"), base)   # too little history
        bad_dates = raw.assign(When="not a date")
        assert raises(custom.UploadError, custom.build_dataset, _csv(bad_dates, d, "bad.csv"), base)


def test_upload_and_preview_routes():
    reg = Registry()
    q = {"action": "inspect"}
    r = routes.upload(reg, q, {"path": SAMPLE})
    assert r["guess"]["event"] == "Action"
    assert raises(routes.ApiError, routes.upload, reg, {"action": "build", "mapping": "{}"}, {"path": SAMPLE})
    assert raises(routes.ApiError, routes.upload, reg, {"action": "inspect"}, {})
    assert raises(routes.ApiError, routes.upload, reg, {"action": "nope"}, {"path": SAMPLE})
    built = routes.upload(reg, {"action": "build", "name": "shop.csv", "mapping": json.dumps(MAPPING)}, {"path": SAMPLE})
    assert built["dataset"] == "custom" and built["summary"]["customers"] == 1400
    pv = routes.preview(reg, {"dataset": "custom"}, {})
    assert pv["sample"]["columns"][:3] == ["When", "Customer", "Action"] and len(pv["sample"]["rows"]) == 10
    assert len(pv["counts"]) == len(built["batches"]) and pv["journeys"]
    assert routes.upload(reg, {"action": "remove"}, {})["removed"] is True


def test_example_journeys_use_valid_state_names_and_show_different_outcomes():
    ds = preprocess.load_dataset("synthetic")
    js = preprocess.example_journeys(ds.events)
    assert js and {j["outcome"] for j in js} >= {"Only browsed"}
    from backend.engine.states import STATES
    assert all(s in STATES for j in js for s in j["steps"]) and all(3 <= len(j["steps"]) <= 12 for j in js)
