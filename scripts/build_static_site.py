"""
Builds the GitHub Pages demo into site/ (git-ignored):

  site/index.html, css/, js/      the frontend, with root-absolute URLs made relative
  site/js/worker.js, static-api.js  from demo/  (Python-in-the-browser plumbing)
  site/py/                        backend/*.py + demo/jp_static.py, loaded into Pyodide
  site/data/datasets.json         AGGREGATED counts only: per dataset, one 7x7 transition
                                  count matrix per monthly batch, plus labels, AOV and facts.
                                  No raw events, user ids or sessions are published.

Run from the project root (needs the datasets you want to publish under data/raw/):
    python scripts/build_static_site.py
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.data.preprocess import available_datasets, load_dataset   # noqa: E402
from backend.engine.markov import counts_from_pairs                     # noqa: E402

SITE = ROOT / "site"
SKIP_PY = {"server.py"}                                               # the HTTP server is replaced by demo/jp_static.py


def jsonable(x):
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x


def dataset_bundle(name):
    ds = load_dataset(name)
    tr = ds.transitions
    counts = [counts_from_pairs(g.a.to_numpy(), g.b.to_numpy()) for _, g in tr.groupby("batch", sort=True)]
    return {"label": ds.label, "labels": list(ds.batch_labels), "aov": float(ds.aov),
            "facts": jsonable(ds.facts), "batch_counts": [c.astype(int).tolist() for c in counts]}


def main():
    SITE.mkdir(exist_ok=True)
    for child in SITE.iterdir():                  # empty the folder but keep it (a dev server may be serving it)
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    # frontend, with absolute /css and /js URLs turned into relative ones (Pages serves under /<repo>/)
    shutil.copytree(ROOT / "frontend", SITE, ignore=shutil.ignore_patterns(".DS_Store"), dirs_exist_ok=True)
    html = (SITE / "index.html").read_text()
    html = html.replace('href="/css/', 'href="css/').replace('src="/js/', 'src="js/')
    html = html.replace("<title>JourneyPulse</title>",
                        "<title>JourneyPulse</title>\n  <script>window.JP_STATIC = true;</script>")
    html = html.replace('Mathematics for Intelligent Systems 3</p>',
                        'Mathematics for Intelligent Systems 3</p>\n        <p class="tiny muted">Browser demo: Python runs in this tab. '
                        '<a href="https://github.com/srivatsav0811/Journey_pulse" style="text-decoration:underline">Source</a></p>')
    (SITE / "index.html").write_text(html)
    shutil.copy(ROOT / "demo" / "worker.js", SITE / "js" / "worker.js")
    shutil.copy(ROOT / "demo" / "static-api.js", SITE / "js" / "static-api.js")

    # backend python files for Pyodide
    files = []
    for p in sorted((ROOT / "backend").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if p.name in SKIP_PY:
            continue
        dest = SITE / "py" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(p, dest)
        files.append(rel)
    shutil.copy(ROOT / "demo" / "jp_static.py", SITE / "py" / "jp_static.py")
    files.append("jp_static.py")
    (SITE / "py" / "manifest.json").write_text(json.dumps(files))

    # aggregated data
    bundle = {}
    for d in available_datasets():
        if d["available"]:
            bundle[d["name"]] = dataset_bundle(d["name"])
            print(f"  {d['name']}: {len(bundle[d['name']]['batch_counts'])} batches")
    (SITE / "data").mkdir()
    (SITE / "data" / "datasets.json").write_text(json.dumps(bundle, separators=(",", ":")))
    (SITE / ".nojekyll").write_text("")
    size = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"built {SITE} ({size / 1e6:.2f} MB, {len(bundle)} datasets)")


if __name__ == "__main__":
    main()
