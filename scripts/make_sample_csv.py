"""
Writes frontend/sample/business_sample.csv: a small, fictional online-shop event log for trying the
"Your data" page. Column and action names deliberately differ from the REES46 files so the column
matching step has something to do. Deterministic (fixed seed). Checkout gets better after mid-March.

    python scripts/make_sample_csv.py
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "frontend" / "sample" / "business_sample.csv"
rng = np.random.default_rng(2026)
START, END = datetime(2026, 1, 5), datetime(2026, 5, 31)
PRODUCTS = ["Running shoes", "Yoga mat", "Water bottle", "Backpack", "Headphones", "Desk lamp", "Notebook", "Sunglasses"]
rows = []

for i in range(1400):
    cid = f"C{1000 + i}"
    first = START + timedelta(days=float(rng.uniform(0, 110)))
    n_sessions = int(rng.choice([1, 2, 3, 4], p=[0.45, 0.30, 0.17, 0.08]))
    t = first
    ordered = 0
    for _ in range(n_sessions):
        if t > END:
            break
        t0 = t + timedelta(hours=float(rng.uniform(8, 22)))
        cart_p = 0.30 if ordered == 0 else 0.45
        buy_p = (0.38 if t0 < datetime(2026, 3, 15) else 0.52) * (1.4 if ordered else 1.0)
        for _v in range(int(rng.integers(1, 6))):
            t0 += timedelta(seconds=int(rng.integers(20, 240)))
            rows.append([t0, cid, "Viewed product", rng.choice(PRODUCTS), ""])
        if rng.random() < cart_p:
            t0 += timedelta(seconds=int(rng.integers(20, 180)))
            item = rng.choice(PRODUCTS)
            rows.append([t0, cid, "Added to basket", item, ""])
            if rng.random() < 0.12:
                t0 += timedelta(seconds=int(rng.integers(20, 120)))
                rows.append([t0, cid, "Removed from basket", item, ""])
            elif rng.random() < min(0.95, buy_p):
                t0 += timedelta(seconds=int(rng.integers(60, 400)))
                rows.append([t0, cid, "Placed order", item, f"{float(rng.lognormal(3.7, 0.45)):.2f}"])
                ordered += 1
        t = t0 + timedelta(days=float(rng.exponential(18)) + 1)

rows.sort(key=lambda r: r[0])
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["When", "Customer", "Action", "Product", "Order value"])
    for t, cid, act, prod, val in rows:
        w.writerow([t.strftime("%Y-%m-%d %H:%M:%S"), cid, act, prod, val])
print(f"wrote {OUT} ({len(rows)} rows, {len({r[1] for r in rows})} customers, {OUT.stat().st_size / 1e3:.0f} KB)")
