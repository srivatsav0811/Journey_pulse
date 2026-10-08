"""The GitHub Pages demo rebuilds each dataset from aggregated counts; it must match the full pipeline exactly."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from backend.api import routes
from backend.services.workspace import Registry
import build_static_site


def _load_adapter():
    spec = importlib.util.spec_from_file_location("jp_static", ROOT / "demo" / "jp_static.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CALLS = [("GET", "/api/overview", {}), ("GET", "/api/timeline", {}), ("GET", "/api/validation", {}),
         ("GET", "/api/method", {}), ("POST", "/api/simulate", {"shifts": {"cart_to_purchase": 0.03}}),
         ("POST", "/api/optimize", {"budget_points": 5, "per_lever_points": 3, "objective": "revenue"}),
         ("POST", "/api/advisor", {"messages": [{"role": "user", "content": "How is my business doing?"}]})]


def test_browser_demo_matches_full_pipeline_on_synthetic():
    from backend import config
    old = (config.ANTHROPIC_API_KEY, config.GROQ_API_KEY)
    config.ANTHROPIC_API_KEY = config.GROQ_API_KEY = ""      # the demo has no hosted advisor
    try:
        real, adapter = Registry(), _load_adapter()
        adapter.install(json.dumps({"synthetic": build_static_site.dataset_bundle("synthetic")}))
        for method, path, body in CALLS:
            q = {"dataset": "synthetic"} if method == "GET" else {}
            b = {**body, "dataset": "synthetic"} if method == "POST" else {}
            want = json.dumps(routes.ROUTES[(method, path)](real, q, b), sort_keys=True, default=str)
            r = json.loads(adapter.handle(method, path, json.dumps(q), json.dumps(b)))
            assert r["status"] == 200, (path, r)
            assert json.dumps(r["data"], sort_keys=True, default=str) == want, path
    finally:
        config.ANTHROPIC_API_KEY, config.GROQ_API_KEY = old


def test_demo_reports_datasets_missing_from_the_bundle():
    adapter = _load_adapter()
    adapter.install(json.dumps({"synthetic": build_static_site.dataset_bundle("synthetic")}))
    r = json.loads(adapter.handle("GET", "/api/overview", json.dumps({"dataset": "cosmetics"}), "{}"))
    assert r["status"] == 404 and "not part of this browser demo" in r["data"]["error"]
