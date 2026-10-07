import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from backend import config
from backend.api import routes
from backend.api.routes import ROUTES, ApiError
from backend.services import advisor
from backend.services.workspace import Registry
from tests.helpers import raises

REG = Registry()
WS = REG.get("synthetic")


def test_offline_advisor_answers_without_api_key():
    # regression: ai_assistant.py built the client at import time and crashed without a key
    old = config.ANTHROPIC_API_KEY
    config.ANTHROPIC_API_KEY = ""
    try:
        r = advisor.answer(WS, [{"role": "user", "content": "How is my business doing?"}])
    finally:
        config.ANTHROPIC_API_KEY = old
    assert r["source"] == "offline" and "Live model v" in r["reply"] and r["suggestions"]


def test_offline_what_if_parses_lever_and_points():
    r = advisor.offline_answer(WS, "What if checkout completion improves by 4 points?")
    assert r["intent"] == "what_if"
    assert r["tools"][0] == {"name": "simulate_change",
                             "input": {"changes": [{"lever": "cart_to_purchase", "points": 4.0}]}}


def test_offline_budget_question_goes_to_optimiser():
    r = advisor.offline_answer(WS, "How should we spend a 10 point budget to grow loyalty?")
    assert r["intent"] == "budget" and r["tools"][0]["input"] == {"budget_points": 10.0, "objective": "loyal"}


def test_claude_tool_loop_runs_tools_on_the_live_matrix():
    calls = []

    def fake(payload, key):
        calls.append(payload)
        if len(calls) == 1:
            return {"stop_reason": "tool_use", "content": [
                {"type": "text", "text": "Checking."},
                {"type": "tool_use", "id": "t1", "name": "get_business_snapshot", "input": {}}]}
        tool_result = payload["messages"][-1]["content"][0]
        assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "t1"
        assert json.loads(tool_result["content"])["live_model"]["version"] == WS.live_version
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Revenue is **fine**."}]}

    r = advisor.answer(WS, [{"role": "user", "content": "How are we doing?"}], transport=fake)
    assert r["source"] == "claude" and r["reply"] == "Revenue is **fine**."
    assert r["tools"] == [{"name": "get_business_snapshot", "input": {}}]
    assert "version" in calls[0]["system"] and len(calls[0]["tools"]) == len(advisor.TOOLS)


def test_claude_failure_falls_back_to_offline():
    def broken(payload, key):
        raise OSError("network down")
    r = advisor.answer(WS, [{"role": "user", "content": "Where are we losing customers?"}], transport=broken)
    assert r["source"] == "offline" and "notice" in r and r["reply"]


def test_every_route_returns_strict_json():
    body = {"dataset": "synthetic"}
    for (method, path), fn in ROUTES.items():
        q, b = ({"dataset": "synthetic", "stage": "Add to Cart"}, {}) if method == "GET" else ({}, dict(body))
        if path == "/api/simulate":
            b["shifts"] = {"cart_to_purchase": 5}
        if path == "/api/advisor":
            b["messages"] = [{"role": "user", "content": "what if checkout improves by 5 points"}]
        if path == "/api/stream":
            b["action"] = "latest"
        json.dumps(fn(REG, q, b), allow_nan=False)


def test_stream_moves_the_live_version_within_bounds():
    s = routes.stream(REG, {}, {"dataset": "synthetic", "action": "reset"})
    assert s["live"]["version"] == 0
    s = routes.stream(REG, {}, {"dataset": "synthetic", "action": "prev"})
    assert s["live"]["version"] == 0
    s = routes.stream(REG, {}, {"dataset": "synthetic", "action": "next"})
    assert s["live"]["version"] == 1
    routes.stream(REG, {}, {"dataset": "synthetic", "action": "latest"})


def test_what_if_uses_the_live_version():
    routes.stream(REG, {}, {"dataset": "synthetic", "action": "reset"})
    at_v0 = routes.simulate(REG, {}, {"dataset": "synthetic", "shifts": {"cart_to_purchase": 5}})
    routes.stream(REG, {}, {"dataset": "synthetic", "action": "latest"})
    at_latest = routes.simulate(REG, {}, {"dataset": "synthetic", "shifts": {"cart_to_purchase": 5}})
    assert at_v0["snapshot_error"]["revenue_per_1k"] == 0          # live == frozen at version 0
    assert at_latest["live"]["baseline"]["revenue_per_1k"] != at_v0["live"]["baseline"]["revenue_per_1k"]


def test_bad_input_is_rejected():
    raises(ApiError, routes.simulate, REG, {}, {"dataset": "synthetic", "shifts": {"nope": 1}})
    raises(ApiError, routes.outlook, REG, {"dataset": "synthetic", "stage": "Exit"}, {})
    raises(ApiError, routes.optimize, REG, {}, {"dataset": "synthetic", "objective": "profit"})
    raises(ApiError, routes.advise, REG, {}, {"dataset": "synthetic", "messages": []})


def test_http_server_serves_api_and_dashboard():
    from backend import server
    server.REGISTRY = REG
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        health = json.loads(urllib.request.urlopen(base + "/api/health").read())
        assert health["ok"]
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "<html" in page.lower()
        req = urllib.request.Request(base + "/api/predict", method="POST",
                                     data=json.dumps({"dataset": "synthetic", "state": "Visitor"}).encode())
        assert abs(sum(json.loads(urllib.request.urlopen(req).read())["k_step"].values()) - 1) < 1e-6
    finally:
        httpd.shutdown()
