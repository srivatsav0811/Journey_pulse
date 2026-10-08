"""
jp_static.py
============
Runs inside Pyodide (Python in the browser) for the GitHub Pages demo.

GitHub Pages can only serve static files, so there is no Python server. Instead
the real backend/ package is loaded into the browser and this adapter plays the
part of backend/server.py: it answers the same /api/* calls by calling the same
route functions.

Only *aggregated* data is shipped: for each dataset, the 7x7 transition count
matrix of every monthly batch (plus labels, average order value and summary
facts). That is all the engine ever reads. The transitions table that Workspace
expects is rebuilt from those counts, so every number matches the full app.
The hosted-model advisor is not available here (a browser cannot keep an API key
secret); the offline analyst answers instead.
"""

import json

import numpy as np
import pandas as pd

from backend.api import routes
from backend.data import preprocess
from backend.services import workspace

_BUNDLE = {}


def _transitions_from_counts(batch_counts) -> pd.DataFrame:
    a, b, batch = [], [], []
    for k, counts in enumerate(batch_counts):
        counts = np.asarray(counts, dtype=np.int64)
        rows, cols = np.nonzero(counts)
        reps = counts[rows, cols].astype(np.intp)      # wasm32 numpy indexes with 32-bit ints; repeat() needs intp
        a.append(np.repeat(rows, reps))
        b.append(np.repeat(cols, reps))
        batch.append(np.full(int(reps.sum()), k))
    return pd.DataFrame({"a": np.concatenate(a).astype(np.int8),
                         "b": np.concatenate(b).astype(np.int8),
                         "batch": np.concatenate(batch).astype(np.int8)})


def demo_load_dataset(name, use_cache=True):
    if name not in preprocess.REGISTRY:
        raise ValueError(f"unknown dataset '{name}'. Known: {list(preprocess.REGISTRY)}")
    if name not in _BUNDLE:
        raise FileNotFoundError(f"The '{name}' dataset is not part of this browser demo.")
    d = _BUNDLE[name]
    return preprocess.Dataset(name=name, label=d["label"], events=pd.DataFrame(),
                              transitions=_transitions_from_counts(d["batch_counts"]),
                              batch_labels=d["labels"], aov=d["aov"], facts=d["facts"])


def demo_available_datasets():
    return [{"name": n, "label": spec["label"], "available": n in _BUNDLE,
             "source": spec["source"], "files": []} for n, spec in preprocess.REGISTRY.items()]


REGISTRY = None


def install(bundle_json: str):
    """Called once by the worker after the backend files are on the Pyodide file system."""
    global REGISTRY
    _BUNDLE.clear()
    _BUNDLE.update(json.loads(bundle_json))
    workspace.load_dataset = demo_load_dataset
    workspace.available_datasets = demo_available_datasets
    REGISTRY = workspace.Registry()


def handle(method: str, path: str, query_json: str, body_json: str) -> str:
    """One API call. Returns JSON text: {"status": int, "data": ...}."""
    handler = routes.ROUTES.get((method, path))
    if handler is None:
        return json.dumps({"status": 404, "data": {"error": f"no route {method} {path}"}})
    query, body = json.loads(query_json or "{}"), json.loads(body_json or "{}")
    try:
        data = handler(REGISTRY, query, body)
        return json.dumps({"status": 200, "data": data}, allow_nan=False)
    except routes.ApiError as exc:
        return json.dumps({"status": exc.status, "data": {"error": exc.message}})
    except Exception as exc:  # same behaviour as the HTTP server: report, do not crash the worker
        return json.dumps({"status": 500, "data": {"error": f"{type(exc).__name__}: {exc}"}})
