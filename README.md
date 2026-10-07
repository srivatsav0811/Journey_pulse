# JourneyPulse — adaptive Markov customer-journey intelligence

Group 12 · 23MAT204 Mathematics for Intelligent Systems 3
Srivatsav Reddy M · Chandramsuvu N · Rajneesh Samala · Sanjeev Singotam · Pranav Senthil

A web app that models how customers move through an online store
(Visitor → Product View → Add to Cart → Purchase → Repeat Purchase → Loyal Customer, with churn possible from every stage) as a first-order Markov chain, and keeps that model **current**:
every month of new data is tested for drift stage by stage, and the transition matrix is re-weighted where behaviour really changed.

**What is new here (stated deliberately modestly):** the what-if simulator, the budget optimiser, the next-best-action ranking and the AI business advisor all read the **live, self-updating matrix**, never a frozen snapshot, and every one of them shows how far a frozen, fit-once model would be from it.
Adaptive updating, what-if simulation and Markov optimisation each exist separately in the literature; the contribution is combining them around one live matrix for customer-journey decisions.

---

## 1. Run it (Windows)

1. Unzip this folder somewhere, e.g. `Documents\journeypulse`.
2. Put the Electronics file at `data\raw\electronics\events.csv` (unzip the Kaggle download; the zip you uploaded contains exactly this file).
3. Double-click **`run_windows.bat`**. It installs numpy/pandas/scipy (first time only), starts the server and opens `http://127.0.0.1:8000` when the data is ready.
   The first start builds a cache in `data\processed\` (about 15 seconds); later starts take under a second.

From a terminal instead (any OS):

```bash
pip install -r requirements.txt
python -m backend.server --open        # or ./run_mac_linux.sh
```

The synthetic dataset (`data/synthetic/`) is included and always available from the **Dataset** menu in the sidebar.

### Turn on a hosted model for the AI advisor (optional: Groq or Claude)

Without a key the advisor runs as the built-in **offline analyst**: it recognises common business questions and answers them from the same engine calls, so a demo never breaks.
To use a hosted model, set `GROQ_API_KEY` (Groq, default model `openai/gpt-oss-120b`) or `ANTHROPIC_API_KEY` (Claude) **before** starting the server. With both set, Claude is used unless `ADVISOR_PROVIDER=groq`. The examples below use Claude's variable; Groq works the same way:

```bat
:: Command Prompt
set ANTHROPIC_API_KEY=sk-ant-...
python -m backend.server --open
```
```powershell
# PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python -m backend.server --open
```

Or copy `.env.example` to `.env`, paste the key there, and use `run_windows.bat`. Never commit `.env`.
`GROQ_MODEL` / `ANTHROPIC_MODEL` switch the model. The key stays on the server; the browser never sees it.
If the API call fails for any reason (no internet, bad key), the advisor answers offline and says so.

### Add the Cosmetics dataset (optional)

Put the five monthly REES46 Cosmetics CSVs in `data/raw/cosmetics/` and restart. It appears in the Dataset menu automatically.
The loader keeps a 10% sample of **customers** (`user_id % 10 == 0`), never of rows, so every sampled journey is complete.
This path is written but was not run here (the file was too large to upload), so check its numbers the first time.

---

## 2. Demo script for the review (about 4 minutes)

1. **Overview.** Point at the journey field: every dot is a simulated customer whose next step is sampled from the live matrix; hover a node to see its live probabilities. Read the hero number and its gap to the frozen October model.
2. **Rewind** (⏮ in the top bar) to v0 — live and frozen are now identical.
3. **What-if simulator** → click *Checkout +3 pts*. The *snapshot error* is 0% because only October is known.
4. Press **Stream next month** three times. After each month a toast says which stages drifted; the what-if result updates by itself and the snapshot error grows (about −19% by January). *This is the novelty in one screen.*
5. **Adaptive engine**: the month cards, the drift-test table (Holm-corrected p-values, shift size, α actually applied), and the tracking chart. Switch the Dataset to *Synthetic* here to show the model following a planted jump from 35% to 50% while the frozen model stays flat.
6. **Budget optimiser**: allocation from the live model vs the frozen snapshot, verified against a brute-force grid.
7. **AI advisor**: ask “Where are we losing the most customers?” and “What if we improve checkout completion by 3 points?”. Each reply shows the live version it used and which tools ran.
8. **Model quality**: be upfront that on this real data drift is slow, so adaptive beats frozen only slightly on next-click prediction; the bigger effect is on the forecasts.

---

## 3. Project structure

```
journeypulse/
├── backend/                      Python, standard library + numpy/pandas/scipy
│   ├── config.py                 every tunable constant (churn days, loyalty threshold, drift and α settings, budget)
│   ├── server.py                 HTTP server: serves /api/* and the frontend from one process
│   ├── api/
│   │   └── routes.py             the REST API as plain functions + input validation
│   ├── data/
│   │   └── preprocess.py         dataset registry, clickstream → states, censoring, monthly batches, cache
│   ├── engine/                   the maths (dataset-agnostic)
│   │   ├── states.py             the 7 states and the 4 business levers
│   │   ├── markov.py             MLE matrix, k-step prediction, absorption analysis, evaluation
│   │   ├── adaptive.py           drift test, adaptive α, 4 update strategies, AdaptiveModel (versions)
│   │   ├── simulator.py          what-if shifts (clamped), business metrics, live vs frozen scenario
│   │   ├── optimizer.py          SLSQP budget allocation + brute-force grid check + lever sensitivity
│   │   └── actions.py            next-best actions: computed lever ranking + rule-based playbook
│   └── services/
│       ├── workspace.py          one live model per dataset; every analysis reads its live matrix
│       └── advisor.py            AI advisor: Claude tool-use loop over HTTPS + offline analyst
├── frontend/                     no build step, no external libraries (works offline)
│   ├── index.html                app shell, sidebar, top bar, advisor drawer
│   ├── css/
│   │   ├── tokens.css            colour tokens for dark and light themes (validated chart palette)
│   │   ├── base.css              layout, app shell, responsive rules
│   │   ├── components.css        flat cards, buttons, sliders, chat, tables
│   │   └── views.css             per-page layouts and chart styles
│   └── js/
│       ├── app.js                routing, navigation, dataset switch, streaming months, theme
│       ├── api.js                fetch wrapper + shared state (the live matrix version)
│       ├── effects.js            headline number count-up (the only animation)
│       ├── charts.js             dependency-free bar, line, heatmap and stacked-column charts
│       ├── chat.js               advisor conversation (drawer + full page)
│       ├── ui.js, format.js      safe DOM helpers, markdown subset, number formats
│       └── views/                overview, journey, adaptive, whatif, optimize, actions,
│                                 predict, advisor, validation, method
├── tests/                        39 tests; run with pytest or `python tests/run_tests.py`
├── data/
│   ├── synthetic/synthetic_customer_events.csv
│   ├── raw/electronics/events.csv   (you add this; git-ignored)
│   └── processed/                   (cache, git-ignored)
├── CLAUDE.md                     brief for future Claude Code sessions on this repo
├── requirements.txt, .env.example, .gitignore, run_windows.bat, run_mac_linux.sh
```

## 4. API

All responses are JSON. `dataset` defaults to Electronics (or the first available dataset).

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/health` | | advisor mode |
| GET | `/api/datasets` | | datasets, states, levers, objectives, defaults |
| GET | `/api/overview` | `dataset` | live + frozen KPIs, leak, top lever, live matrix |
| GET | `/api/matrix` | `dataset`, `version` | live / frozen / month-only / pooled matrices, absorption per start |
| GET | `/api/timeline` | `dataset` | every version: drift tests, α, KPIs |
| POST | `/api/stream` | `action`: next · prev · reset · latest · set, `version`, `strategy` | new live version |
| POST | `/api/simulate` | `shifts`: {lever: points} | scenario on live and frozen, snapshot error |
| POST | `/api/optimize` | `budget_points`, `per_lever_points`, `objective` | live and frozen plans, grid check, cost of stale plan |
| GET | `/api/outlook` | `stage` | next step, metrics, ranked levers with tactics |
| POST | `/api/predict` | `state`, `steps` | next / k-step distribution, trajectory, most likely path |
| GET | `/api/validation` | | held-out comparison and rolling month-ahead log-loss |
| GET | `/api/method` | | dataset facts and mapping settings |
| POST | `/api/advisor` | `messages`: [{role, content}] | reply, source (claude/offline), tools used, suggestions |

Levers: `view_to_cart`, `cart_to_purchase`, `purchase_to_repeat`, `repeat_to_loyal`. Each moves probability out of that stage's churn cell (clamped so no probability goes negative).

## 5. Method (what to write in the report)

**Data.** REES46 Electronics store (Kaggle, mkechinov): 885,129 events, 24 Sep 2020 – 28 Feb 2021, 407,237 customers, 490,633 sessions; view / cart / purchase events (no remove-from-cart in this store). 655 duplicate rows and 162 rows without a session removed.

**Events → states** (`backend/data/preprocess.py`):
- Each session starts with *Visitor*; `view` → Product View, `cart` → Add to Cart, `remove_from_cart` → Product View; all purchases in a session are one order.
- Before the first order a customer moves through the browsing funnel; a new session starts at Visitor again.
- From the first order on, the customer moves through **order stages** (1st → Purchase, 2nd → Repeat Purchase, 3rd+ → Loyal Customer). Browsing between orders is not re-entered into the funnel. *Why:* otherwise the chain contains Add to Cart → Loyal edges, and a memoryless chain would let a brand-new visitor jump from a cart straight to "Loyal", which makes P(Loyal) and the retention levers meaningless.
- **Exit = churn**: no activity for 30 days before the data ends. Customers active in the last 30 days are right-censored (no Exit).
- Only transitions whose starting event is ≥ 30 days before the end are used (their outcome is known). This leaves Oct–Jan; the one-week September is merged into October.
- Transitions are batched by the month of the **starting** event. (Batching by the destination month pushes every October churn into November, because Exit is dated 30 days after the last event, and makes every stage look drifted.)
- Customers get small integer codes. The raw user_ids are 19-digit numbers that float64 can't tell apart; an early prototype silently merged neighbouring customers because of this.

**Maths.** MLE transition matrix; k-step prediction π(k) = π(0)Pᵏ; absorption analysis with N = (I − Q)⁻¹ (expected visits, expected steps to churn t = N·1, probability of ever reaching j = N[i,j]/N[j,j], expected orders); revenue = expected orders × average order value.
Drift: per stage, a two-sample χ² test of homogeneity between last month's and this month's counts, Holm-corrected across stages at 0.05, and flagged only if the shift is also ≥ 0.02 in total variation (with 100k+ transitions everything is "significant").
Adaptive EWMA: P_new[i] = αᵢ P_month[i] + (1 − αᵢ) P_live[i], with αᵢ = 0.30 for stable stages and 0.30 + 0.50·tanh(TVᵢ/0.05) for drifted ones.
Optimiser: maximise expected orders (or P(loyal), P(first order)) subject to a total budget and per-lever caps, SLSQP from several starts, checked against a brute-force grid.

**Results on the Electronics data** (live model = through Jan 2021; frozen = October only):

| | Live | Frozen |
|---|---|---|
| Revenue per 1,000 visitors | 13,332 | 10,779 |
| Visitor ever places an order | 5.5% | 4.6% |
| First-time buyers who order again | 12.3% | 9.3% |
| Checkout completion (cart → order) | 35.0% | 37.7% |

- Drift detected: **Nov 2020** in Product View and Purchase; none in Dec; **Jan 2021** in Product View and Add to Cart. Most of the live–frozen gap comes from the Product View row (fewer product views end in churn: 54% → 49%).
- Held-out January: next-step accuracy 66.5% vs 58.1% for the always-guess-the-most-common-step baseline (47.9% vs 34.9% excluding the trivial first click); log-loss 0.747 vs 1.068.
- Adaptive vs frozen on next-step prediction is a small gain (log-loss 0.7467 vs 0.7498): real drift here is slow. The larger effect is on forecasts: for a +3-point checkout scenario, the frozen model under-states the outcome by about 19%; for the optimiser's plan it under-states the payoff by about 16%.
- Synthetic data (planted Cart → Purchase 0.35 → 0.50): drift is flagged in exactly the Add to Cart row in the first February batch, α rises to 0.80, and the live estimate moves from 36% to 53% (truth 50%) while the frozen model stays at 36%.

**Limitations.** First-order Markov assumption; left-censoring (a customer's "first" order in the data may not be their first ever); shorter observation windows for recent orders; levers only move the churn cell; playbook tactics are rule-based suggestions, not model output.

## 6. Tests

```bash
python tests/run_tests.py     # no extra packages needed
python -m pytest -q           # if pytest is installed
```

The suite includes a regression test for every bug fixed from the mid-review code: drift false alarms (stable batches ≤ 10% flagged), α actually rising on drift, the advisor working with no API key, clamped what-if shifts, absorption with an unobserved stage, no transitions across customers, and the optimiser matching a brute-force grid.

## 7. Troubleshooting

- **"Can't reach the JourneyPulse server"** — start it with `python -m backend.server` from the project folder and keep that window open.
- **Electronics missing from the Dataset menu** — the file must be exactly `data/raw/electronics/events.csv`.
- **Port in use** — `set PORT=9000` (PowerShell `$env:PORT=9000`) then start again.
- **Numbers look stale after editing preprocessing** — delete `data/processed/` to rebuild the cache.

Data: REES46 Marketing Platform (rees46.com), via Kaggle (mkechinov). Please keep this attribution in the report.
