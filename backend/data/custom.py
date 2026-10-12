"""
custom.py
=========
Bring your own data. Turns a business's own event log (a CSV) into the same
Dataset the built-in datasets produce, so every page, the simulator, the
optimiser and the advisor work on it unchanged.

What the file needs: one row per customer action with
  * who      a customer id (any text or number)
  * when     a date/time
  * what     an action (e.g. "Viewed product", "Added to basket", "Placed order")
and, optionally, a session id and an order value.

Two steps, both pure functions of a file path (the route layer handles upload):
  inspect_csv(path, ...)   column guesses, a preview and the distinct actions
  build_dataset(path, m)   the full pipeline, via preprocess.assemble_dataset

The file is read, used and discarded; nothing here writes it anywhere.
"""

import os
import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import preprocess as P
from .. import config

CUSTOM_NAME = "custom"
ROLES = ("view", "cart", "remove_from_cart", "purchase", "ignore")
MAX_ROWS = int(os.environ.get("JP_MAX_UPLOAD_ROWS", "3000000"))     # the browser demo lowers this
SESSION_GAP = pd.Timedelta(minutes=30)
MAX_DISTINCT_ACTIONS = 60
CHUNK = 500_000


class UploadError(ValueError):
    """A problem a person can fix, worded for a non-technical reader."""


# ---------------------------------------------------------------------------
# Guessing
# ---------------------------------------------------------------------------
def guess_role(value) -> str:
    """Which journey step does an action label mean? Conservative: unknown -> ignore."""
    v = re.sub(r"[^a-z]+", " ", str(value).lower()).strip()
    if re.search(r"cancel|refund|return|fail|declin|reject", v):
        return "ignore"
    if re.search(r"remov|delet|abandon|drop|empt", v) and re.search(r"cart|basket|bag", v):
        return "remove_from_cart"
    if re.search(r"cart|basket|bag", v):
        return "cart"
    if re.search(r"purchas|order|buy|bought|transaction|paid|payment|sale|conversion|checkout (complete|success)|complete", v):
        return "purchase"
    if re.search(r"view|click|product|page|visit|browse|detail|impression|search|open|seen|\bsee\b", v):
        return "view"
    return "ignore"


def _parse_time(s: pd.Series, dayfirst: bool = False) -> pd.Series:
    """Datetime values from text or epoch numbers; unparseable -> NaT. Always timezone-naive UTC."""
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().mean() > 0.9:
        v = num.dropna()
        if len(v) and v.between(1e9, 4e9).all():
            return pd.to_datetime(num, unit="s", errors="coerce")
        if len(v) and v.between(1e12, 4e12).all():
            return pd.to_datetime(num, unit="ms", errors="coerce")
        return pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")   # plain numbers are ids, not dates
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = pd.to_datetime(s, errors="coerce", utc=True, dayfirst=dayfirst)
    return t.dt.tz_localize(None)


_NAME = {
    "time": r"time|date|stamp|created|occurred|when|\bts\b|datetime",
    "event": r"event|action|type|activity|behaviou?r|step|stage|interaction|what",
    "user": r"user|customer|client|visitor|member|shopper|buyer|account|cust|person|contact",
    "session": r"session|visit",
    "price": r"price|amount|value|revenue|total|spend|sales?|cost|paid|gmv",
}


def _guess_columns(head: pd.DataFrame) -> Dict[str, Optional[str]]:
    cols = list(head.columns)
    n = max(1, len(head))
    info = {}
    for c in cols:
        s = head[c]
        filled = s.dropna()          # an "order value" column is empty on non-purchase rows, so judge the filled cells only
        num = float(pd.to_numeric(filled, errors="coerce").notna().mean()) if len(filled) else 0.0
        info[c] = {"low": c.lower(), "num": num, "card": int(s.nunique(dropna=True)),
                   "time": max(float(_parse_time(filled, df).notna().mean()) for df in (False, True)) if len(filled) else 0.0}
    hit = lambda role, c: bool(re.search(_NAME[role], info[c]["low"]))
    out: Dict[str, Optional[str]] = {r: None for r in ("time", "user", "event", "session", "price")}
    taken = set()

    def pick(role, ok):
        cand = [c for c in cols if c not in taken and ok(c)]
        cand.sort(key=lambda c: (-int(hit(role, c)), cols.index(c)))
        if cand:
            out[role] = cand[0]
            taken.add(cand[0])

    pick("time", lambda c: info[c]["time"] >= 0.8)
    pick("event", lambda c: info[c]["num"] < 0.5 and info[c]["card"] <= MAX_DISTINCT_ACTIONS
         and (info[c]["card"] >= 2 or hit("event", c)))
    pick("user", lambda c: hit("user", c) and not re.search(r"product|item|sku|categor|brand|order|session", info[c]["low"])
         and info[c]["card"] >= min(20, n // 2))
    if out["user"] is None:     # no obvious name: the remaining id-like column with the most distinct values
        rest = [c for c in cols if c not in taken and info[c]["card"] >= min(20, n // 2)
                and not re.search(r"product|item|sku|categor|brand|order|price|amount", info[c]["low"])]
        rest.sort(key=lambda c: -info[c]["card"])
        if rest:
            out["user"] = rest[0]
            taken.add(rest[0])
    pick("session", lambda c: hit("session", c))
    pick("price", lambda c: hit("price", c) and info[c]["num"] >= 0.8)
    return out


def _count_rows(path: str) -> int:
    n = 0
    with open(path, "rb") as fh:
        while True:
            block = fh.read(1 << 20)
            if not block:
                break
            n += block.count(b"\n")
    return max(0, n - 1)


def _read_header(path: str) -> pd.DataFrame:
    try:
        head = pd.read_csv(path, nrows=3000, dtype=str, keep_default_na=True, encoding_errors="replace")
    except pd.errors.EmptyDataError:
        raise UploadError("The file is empty.")
    except Exception as exc:
        raise UploadError(f"This does not look like a CSV file ({type(exc).__name__}). Export your data as CSV and try again.")
    if head.shape[1] < 3:
        raise UploadError("The file needs at least three columns: who, when and what the customer did.")
    head.columns = [str(c).strip() for c in head.columns]
    return head


def event_values(path: str, column: str) -> List[Dict]:
    """Distinct actions in `column` with counts and a guessed role for each."""
    counts = pd.Series(dtype="int64")
    for chunk in pd.read_csv(path, usecols=[column], dtype=str, chunksize=CHUNK, encoding_errors="replace",
                             skipinitialspace=True):
        counts = counts.add(chunk[column].dropna().str.strip().value_counts(), fill_value=0)
    if len(counts) > MAX_DISTINCT_ACTIONS:
        raise UploadError(f"The column '{column}' has {len(counts)} different values, so it does not look like an "
                          "action column. Choose the column that says what the customer did (viewed, added to cart, bought).")
    counts = counts.sort_values(ascending=False)
    return [{"value": str(k), "count": int(v), "role": guess_role(k)} for k, v in counts.items()]


def inspect_csv(path: str, mapping: Optional[Dict] = None) -> Dict:
    head = _read_header(path)
    guess = _guess_columns(head)
    chosen = {**guess, **{k: v for k, v in (mapping or {}).items() if k in guess and v in head.columns}}
    preview = head.head(8).fillna("").astype(str)
    out = {
        "columns": list(head.columns),
        "preview": {"columns": list(head.columns),
                    "rows": [[c[:60] for c in r] for r in preview.values.tolist()]},
        "n_rows": _count_rows(path),
        "guess": guess,
        "event_values": event_values(path, chosen["event"]) if chosen.get("event") else [],
    }
    if chosen.get("time"):
        s = head[chosen["time"]].dropna()
        t0, t1 = _parse_time(s, False), _parse_time(s, True)
        out["time_check"] = {"parsed_share": float(t0.notna().mean()),
                             "example": str(s.iloc[0]) if len(s) else "",
                             "read_as": str(t0.dropna().iloc[0]) if t0.notna().any() else "",
                             "dayfirst_suggested": bool(t1.notna().mean() > t0.notna().mean() + 0.2)}
    return out


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def _clean_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce").fillna(0.0)


def _need(m: Dict, key: str, label: str, header: List[str]) -> str:
    v = m.get(key)
    if not v:
        raise UploadError(f"Choose the column that holds the {label}.")
    if v not in header:
        raise UploadError(f"The column '{v}' ({label}) is not in your file.")
    return v


def build_dataset(path: str, m: Dict, file_name: str = "your file") -> P.Dataset:
    header = list(_read_header(path).columns)
    t_col = _need(m, "time", "date and time", header)
    u_col = _need(m, "user", "customer id", header)
    e_col = _need(m, "event", "action", header)
    s_col = m.get("session") or None
    p_col = m.get("price") or None
    for opt, label in ((s_col, "session id"), (p_col, "order value")):
        if opt and opt not in header:
            raise UploadError(f"The column '{opt}' ({label}) is not in your file.")
    if len({c for c in (t_col, u_col, e_col, s_col, p_col) if c}) != len([c for c in (t_col, u_col, e_col, s_col, p_col) if c]):
        raise UploadError("Each of customer, date, action, session and order value needs its own column.")
    role_map = {str(k).strip(): v for k, v in (m.get("event_map") or {}).items()}
    bad = set(role_map.values()) - set(ROLES)
    if bad:
        raise UploadError(f"Unknown step type {sorted(bad)}; use one of {list(ROLES)}.")
    if "purchase" not in role_map.values():
        raise UploadError("None of your actions is marked as a purchase. Mark the action that means a customer bought something.")
    try:
        churn_days = config.CHURN_DAYS if m.get("churn_days") in (None, "") else int(m["churn_days"])
        loyal_at = config.LOYAL_AT if m.get("loyal_at") in (None, "") else int(m["loyal_at"])
    except (TypeError, ValueError):
        raise UploadError("'Lost after' and 'loyal after' must be whole numbers.")
    if not 1 <= churn_days <= 365 or not 2 <= loyal_at <= 20:
        raise UploadError("'Lost after' must be 1-365 days and 'loyal after' 2-20 orders.")
    dayfirst = bool(m.get("dayfirst"))
    fallback_aov = float(m.get("aov") or 0)

    n_total = _count_rows(path)
    if n_total > MAX_ROWS:
        raise UploadError(f"Your file has {n_total:,} rows; this version handles up to {MAX_ROWS:,}. "
                          "Use a shorter date range or a sample of your customers (all rows for each sampled customer).")

    usecols = [c for c in (t_col, u_col, e_col, s_col, p_col) if c]
    parts, n_raw, ignored = [], 0, 0
    for chunk in pd.read_csv(path, usecols=usecols, dtype=str, chunksize=CHUNK, encoding_errors="replace",
                             skipinitialspace=True):
        n_raw += len(chunk)
        role = chunk[e_col].astype(str).str.strip().map(role_map)
        keep = role.notna() & (role != "ignore")
        ignored += int((~keep).sum())
        chunk, role = chunk[keep], role[keep]
        df = pd.DataFrame({"t": _parse_time(chunk[t_col], dayfirst), "event_type": role.astype(str),
                           "user": chunk[u_col].astype(str).str.strip()})
        df.loc[chunk[u_col].isna().to_numpy(), "user"] = np.nan
        df["price"] = _clean_number(chunk[p_col]) if p_col else 0.0
        if s_col:
            df["session"] = chunk[s_col]
        parts.append(df)
    if not parts:
        raise UploadError("No rows could be read from the file.")
    raw = pd.concat(parts, ignore_index=True)
    n_valid_actions = len(raw)
    raw = raw.dropna(subset=["t", "user"])
    invalid = n_valid_actions - len(raw)
    if raw.empty:
        raise UploadError("No usable rows: check that the date column is read correctly (see the preview) "
                          "and that the customer column is filled in.")
    dedupe_cols = ["t", "event_type", "user", "price"] + (["session"] if s_col else [])
    dups = int(raw.duplicated(subset=dedupe_cols).sum())
    raw = raw.drop_duplicates(subset=dedupe_cols)
    null_sess = 0
    if s_col:
        null_sess = int(raw.session.isna().sum())
        raw = raw.dropna(subset=["session"])
    raw = raw.reset_index(drop=True)
    raw["uid"] = pd.factorize(raw.user)[0]
    if s_col:
        raw["sid"] = pd.factorize(raw.session.astype(str))[0]
    else:                                   # no session column: a new session after 30 quiet minutes
        raw = raw.sort_values(["uid", "t"], kind="mergesort").reset_index(drop=True)
        gap = raw.t.diff() > SESSION_GAP
        new = gap | (raw.uid != raw.uid.shift())
        raw["sid"] = new.cumsum().astype(int)
    raw = raw[["t", "event_type", "price", "uid", "sid"]]

    start, end = raw.t.min(), raw.t.max()
    cutoff = end - pd.Timedelta(days=churn_days)
    span_days = (end - start).days
    if cutoff <= start:
        raise UploadError(f"Your data covers {span_days} days, which is shorter than the {churn_days}-day 'lost after' window. "
                          "Use a shorter 'lost after' value or a longer export.")
    n_months = len(pd.period_range(start, cutoff, freq="M"))
    freq = "M" if n_months >= 3 else "W"
    if freq == "W" and (cutoff - start).days < 21:
        raise UploadError(f"After allowing {churn_days} days to see who comes back, only {(cutoff - start).days} days of "
                          "history are left to learn from. The model needs at least three weeks (ideally three months). "
                          "Try a smaller 'lost after' value or a longer export.")
    et = raw.event_type
    extra = {
        "custom": True, "file_name": file_name, "rows_ignored": ignored, "rows_dropped_invalid": int(invalid),
        "sessionised": not bool(s_col), "batch_unit": "month" if freq == "M" else "week",
        "no_browsing_events": bool(not et.isin(["view", "cart"]).any()),
        "has_order_value": bool(p_col),
        "sample": _sample_rows(path),
    }
    label = f"Your data ({file_name})"
    try:
        ds = P.assemble_dataset(
            CUSTOM_NAME, label, raw, n_raw=n_raw, dups=dups, null_sess=null_sess,
            sample_rule="all rows of your file", sampled=False, source=f"Uploaded file: {file_name}",
            attribution="Your own data, processed on your own device and not stored.",
            churn_days=churn_days, loyal_at=loyal_at, freq=freq,
            fallback_aov=fallback_aov if fallback_aov > 0 else 50.0, extra_facts=extra)
    except (ValueError, KeyError, IndexError) as exc:
        raise UploadError(f"Could not build journeys from this file ({type(exc).__name__}: {exc}). "
                          "Check that it has purchases and activity on several different days.")
    if len(ds.batch_labels) < 2:
        raise UploadError("Your data spans too little time to compare periods. Include at least three months of activity "
                          "(or about seven weeks), after allowing for the 'lost after' window.")
    ds.facts["warnings"] = _warnings(ds, fallback_aov, bool(p_col))
    return ds


def _sample_rows(path: str, n: int = 10) -> Dict:
    s = pd.read_csv(path, nrows=n, dtype=str, encoding_errors="replace").fillna("")
    s.columns = [str(c).strip() for c in s.columns]
    return {"columns": list(s.columns), "rows": [[c[:60] for c in r] for r in s.astype(str).values.tolist()]}


def _warnings(ds: P.Dataset, fallback_aov: float, has_price: bool) -> List[str]:
    f, w = ds.facts, []
    if f.get("no_browsing_events"):
        w.append("Your file has no browsing or cart actions, so the model only sees purchases. Repeat-purchase and loyalty "
                 "results are meaningful, but the product-page and checkout levers have nothing to work with.")
    if not has_price:
        w.append(f"No order value column: revenue figures use an average order value of {ds.aov:,.2f}, which you can change by re-uploading.")
    if len(ds.batch_labels) < 3:
        w.append("Only two periods of history: drift tests and validation are weak with so little data.")
    if f.get("buyers", 0) < 100:
        w.append(f"Only {f.get('buyers', 0)} customers bought in this data, so percentages will be noisy.")
    if f.get("sessionised"):
        w.append("No session column: sessions were inferred from 30-minute gaps in each customer's activity.")
    return w
