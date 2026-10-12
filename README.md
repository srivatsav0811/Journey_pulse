# JourneyPulse: adaptive Markov customer-journey intelligence

Group 12 · 23MAT204 Mathematics for Intelligent Systems 3
Srivatsav Reddy M · Chandramsuvu N · Rajneesh Samala · Sanjeev Singotam · Pranav Senthil

A web app that models how customers move through an online store as a **Markov chain**, and keeps that model **current**: every month of new data is tested for behaviour change ("drift"), and the model is updated more strongly only where behaviour really changed.

**What you can do with it**

- See where customers drop out of the journey (visit → product view → cart → purchase → repeat → loyal) and how that has **changed month by month**.
- **Test a change before building it** (e.g. "what if checkout completion rises 3 points?") and see the answer next to what an out-of-date model would have said.
- Find the **best use of a limited improvement budget** across the four levers, with a ranked playbook of next best actions.
- **Ask an AI advisor** in plain words; every number it quotes is computed by the engine, not guessed.
- **Look inside the data** (raw rows, real customer journeys, the monthly counts) and **upload your own customer data** to get all of the above for your business.

| I want to… | Go to |
|---|---|
| Try it now, nothing to install | https://srivatsav0811.github.io/Journey_pulse/ (a browser demo; the Python runs in your tab) |
| Use it on my own business data | the **Your data** page; guide in [C6](#c6-use-your-own-data-business-users) |
| Run it myself, with the real datasets and an AI key | [Part B](#part-b-replicate-it-step-by-step) |
| Understand the maths | [A1](#a1-the-idea-in-plain-words), [C3](#c3-method-in-detail) and `docs/FORMULAS_EXPLAINED.md` |

**Status.** Built and tested (54 tests). The Electronics numbers reproduce from the raw Kaggle files and the Cosmetics run is recorded with its caveats in A3. Still open: the report and slides (see `docs/REMAINING_CHECKLIST.md`).

The browser demo runs the real engine in the visitor's tab (first visit downloads about 21 MB of numpy/scipy/pandas, then it is cached). It includes the three datasets as aggregated transition counts, so its numbers match the full app. It has no hosted-model advisor (a browser cannot keep an API key secret), so the offline analyst answers. A file uploaded there is processed inside the tab and never leaves it.

> **How to read this README.** Part A explains the project and shows the results. Part B is a step-by-step guide to run it yourself, including downloading the datasets and getting an API key. Parts C and D are reference material.

## Contents

- **Part A: the project**: [The idea](#a1-the-idea-in-plain-words) · [What is new](#a2-what-is-new-stated-modestly) · [Results](#a3-results)
- **Part B: replicate it**: [Prerequisites](#b0-what-you-need) · [1 Get the code](#b1-get-the-code) · [2 Install](#b2-install) · [3 First run](#b3-first-run-no-downloads-needed) · [4 Electronics data](#b4-download-the-electronics-dataset) · [5 Cosmetics data](#b5-download-the-cosmetics-dataset-optional) · [6 Verify](#b6-check-that-you-reproduce-our-numbers) · [7 AI advisor key](#b7-turn-on-the-ai-advisor-api-key) · [8 Tour](#b8-a-4-minute-tour-of-the-app)
- **Part C: reference**: [Structure](#c1-project-structure) · [API](#c2-api) · [Method](#c3-method-in-detail) · [Tests](#c4-tests) · [Browser demo](#c5-the-github-pages-browser-demo) · [Your own data](#c6-use-your-own-data-business-users)
- **Part D**: [Troubleshooting](#d1-troubleshooting) · [Data licence](#d2-data-and-licence) · [More docs](#d3-more-documents)

---

# Part A: the project

## A1. The idea in plain words

Imagine every visitor to an online shop is always in one of 7 **states**:

`Visitor → Product View → Add to Cart → Purchase → Repeat Purchase → Loyal Customer`, and **Exit** (the customer has gone quiet for 30 days, which we call churn).

From any state there is some probability of moving to each other state next. Put those probabilities in a table (a **transition matrix**, one row per state, each row adding to 100%) and you have a **first-order Markov chain**: where you go next depends only on where you are now.

With that matrix you can compute useful things with plain linear algebra, for example the chance that a new visitor ever places an order, or the expected number of orders per visitor, and therefore **revenue per 1,000 visitors**.

The catch: customer behaviour changes. A matrix fitted once on the first month goes stale. So JourneyPulse:

1. **Re-estimates** the matrix every month from new data.
2. **Tests each stage for drift** (a statistical test per row, corrected for testing six rows at once, and ignoring trivially small changes).
3. **Updates stages that changed a lot more strongly** than stages that didn't (an adaptive weight α between 0.30 and 0.80).
4. Feeds this **live matrix** into the what-if simulator, the optimiser, the action ranking and the AI advisor, and always shows the answer a **frozen, fit-once model** would have given, so you can see what staleness costs.

## A2. What is new (stated modestly)

Adaptive updating, what-if simulation and optimisation on Markov customer models each exist separately in the literature (for example Pfeifer & Carraway, 2004, for optimisation). We do **not** claim any one of them is new. The contribution is **combining them around one live, self-updating matrix** for customer-journey decisions. This combination was *not found in the reviewed literature*.

## A3. Results

Settings for all runs: churn = 30 days of inactivity, "loyal" = 3rd order or later. **Live** = the model after streaming all months; **Frozen** = the first month only, never updated.

### Electronics store (REES46, Oct 2020 – Jan 2021)

885,129 events, 407,237 customers, 490,633 sessions, 1,042,339 usable transitions, average order value 210.49.

| | Live | Frozen |
|---|---|---|
| Revenue per 1,000 visitors | 13,332 | 10,779 |
| Visitor ever places an order | 5.5% | 4.6% |
| First-time buyers who order again | 12.3% | 9.3% |
| Checkout completion (cart → order) | 35.0% | 37.7% |

- **Drift found:** Nov 2020 in Product View and Purchase; none in Dec; Jan 2021 in Product View and Add to Cart.
- **Held-out January:** next-step accuracy 66.5% vs 58.1% for "always guess the most common step". Log-loss 0.7467 (adaptive), 0.7498 (frozen), 1.0685 (baseline).
- **Honest reading:** adaptive beats frozen only *slightly* at predicting the next click, because real drift here is slow. The bigger effect is on **forecasts**: for a "+3 points checkout completion" scenario, the frozen model understates the outcome by about 19%.

### Cosmetics shop (REES46, Oct 2019 – Jan 2020, 10% customer sample)

164,284 customers, 455,341 sessions, 1,415,837 usable transitions, average order value 40.61.

| | Live | Frozen |
|---|---|---|
| Revenue per 1,000 visitors | 4,560 | 12,952 |
| First-time buyers who order again | 20.8% | 36.7% |
| Second order → loyal | 49.4% | 65.0% |

- **Drift found:** Nov in Add to Cart and Purchase; Dec in Product View, Purchase and Repeat Purchase; Jan in Loyal Customer.
- **Held-out January:** accuracy 63.0% for every model vs a 54.7% baseline; log-loss 0.9611 (adaptive), 0.9730 (frozen), 1.2081 (baseline).
- **Same conclusion as Electronics:** accuracy barely moves, forecasts differ a lot. The frozen model's error goes the *other* way here (it overstates), so the claim is "a frozen model is wrong", not "wrong in a fixed direction".
- **Cautions:** (1) this shop has very many cart events per session, so the chain is at event level (Cart → Purchase is only 1.1% per step) and Electronics-sized "+3 point" levers do not transfer; (2) the data starts in Oct 2019, so some early "first orders" are probably returning customers, which may exaggerate the live-versus-frozen gap (a hypothesis, not tested); (3) only one 10% sample was run.

### Synthetic data (planted change)

We generate data where Cart → Purchase jumps from 35% to 50% in February. The drift test flags exactly the Add to Cart row in the first February batch, α rises to 0.80, and the live estimate moves from 36% to 53% (truth 50%) while the frozen model stays at 36%. This shows the drift detector finds a known change.

### Sample business file (fictional, for trying "Your data")

`frontend/sample/business_sample.csv`: 8,688 rows, 1,400 customers, 318 orders over Jan to May 2026, with column and action names different from REES46 and a checkout improvement planted in mid-March. Uploaded with the default settings it gives 4 monthly periods and a live model that picks up the change.

| | Live | Frozen |
|---|---|---|
| Revenue per 1,000 visitors | 10,008 | 7,505 |
| Checkout completion (cart → order) | 36.8% | 27.9% |

This is a demonstration of the upload flow on made-up data, not a result about any real shop.

---

# Part B: replicate it step by step

## B0. What you need

- **Python 3.10 or newer** (we developed on 3.13). Check with `python3 --version` (Mac/Linux) or `python --version` (Windows). Install from python.org if missing, and on Windows tick "Add Python to PATH".
- **Git** (optional; you can download a ZIP instead).
- **A web browser** (Chrome, Edge, Firefox or Safari).
- **Disk space:** about 0.5 GB for Electronics, about 2.5 GB for Cosmetics (optional). 8 GB of RAM is comfortable for Cosmetics.
- **Free accounts:** [Kaggle](https://www.kaggle.com) (to download the datasets) and [Groq](https://console.groq.com) (for the AI advisor key; optional).

You can do steps 1 to 3 and use the whole app **with no downloads and no API key**: it ships with a synthetic dataset and a built-in offline advisor.

## B1. Get the code

```bash
git clone https://github.com/srivatsav0811/Journey_pulse.git
cd Journey_pulse
```

No git? On the GitHub page click **Code → Download ZIP**, unzip it, and open a terminal inside the unzipped folder.

## B2. Install

Use a virtual environment so nothing touches your system Python.

**Mac / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

(If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process Bypass` first, or use Command Prompt and `.venv\Scripts\activate.bat`.)

This installs numpy, pandas, scipy and pytest. Nothing else is needed: the server uses only the Python standard library and the frontend needs no build step and no internet.

## B3. First run (no downloads needed)

```bash
python -m backend.server --open
```

Your browser opens at **http://127.0.0.1:8000**. In the sidebar, the **Dataset** menu will show "Synthetic (planted drift)" as available and the two real datasets as "not downloaded". Pick Synthetic and click around, or open **Your data** and press *Try the sample file*. Stop the server with `Ctrl+C`.

> The server reads the port from the `PORT` environment variable (default 8000); it has no `--port` option. To use another port: `PORT=9000 python -m backend.server` (Mac/Linux) or `$env:PORT=9000; python -m backend.server` (PowerShell).

## B4. Download the Electronics dataset

This is the main dataset used in the results.

1. Sign in at [kaggle.com](https://www.kaggle.com) (free).
2. Open **https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-electronics-store** and click **Download**. You get a zip containing one file, `events.csv` (about 100 MB unzipped; 885,130 lines including the header).
3. Unzip it and place the file **exactly here**:

   ```
   data/raw/electronics/events.csv
   ```

   The `data/raw/` folders are git-ignored, so a fresh clone does not have them. Create the folder first: `mkdir -p data/raw/electronics` (Windows: `mkdir data\raw\electronics`).
4. **Restart the server.** Electronics now appears in the Dataset menu and becomes the default.

The first load builds a cache in `data/processed/` and takes roughly 15 seconds. Later starts take under a second. To rebuild the cache, delete the `data/processed/` folder.

*Optional, command-line download:* install the Kaggle CLI (`pip install kaggle`), create an API token in your Kaggle account settings, then run `kaggle datasets download -d mkechinov/ecommerce-events-history-in-electronics-store --unzip -p data/raw/electronics`.

## B5. Download the Cosmetics dataset (optional)

1. On Kaggle open **https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop** and click **Download**. It is a much larger download (about 2.4 GB once unzipped).
2. Unzip. You should have five monthly files:

   ```
   2019-Oct.csv  2019-Nov.csv  2019-Dec.csv  2020-Jan.csv  2020-Feb.csv
   ```
3. Create the folder (`mkdir -p data/raw/cosmetics`; Windows: `mkdir data\raw\cosmetics`) and put all five **directly inside** it:

   ```
   data/raw/cosmetics/2019-Oct.csv
   data/raw/cosmetics/2019-Nov.csv
   ...
   ```

   **Common mistake:** unzipping often creates a nested `cosmetics/cosmetics/` folder. If the dataset still says "not downloaded", move the CSVs up one level.
4. Restart the server. The loader keeps a **10% sample of customers** (`user_id % 10 == 0`, never a sample of rows, so each sampled journey is complete). It loaded in about 12 seconds on our Mac.

## B6. Check that you reproduce our numbers

Run the tests first:

```bash
python tests/run_tests.py
```

With both datasets present you should see `54 passed, 0 failed, 0 skipped`. Without a real dataset, the tests that need one are skipped, which is fine.

Then open **Overview** with the Electronics dataset selected and click the **last-month button (⏭)** in the top bar so the live model is **v3 · Jan 2021**. You should see:

| Check | Expected |
|---|---|
| Revenue per 1,000 visitors (live) | **13,332**, and about 23.7% above frozen (10,779) |
| Chance a visitor ever orders | 5.5% |
| Checkout completion | 35.0% |
| **Model quality** page, held-out Jan accuracy | 66.5% (baseline 58.1%) |
| **Data & method** page | 885,129 rows, 407,237 customers, 490,633 sessions |

For Cosmetics (v3 · Jan 2020): revenue per 1,000 visitors **4,560**, 164,284 customers, accuracy 63.0%.

If a number is slightly different, check the dataset files are the original, unedited Kaggle files and that you did not change `backend/config.py`. Small differences in a *different* Python/pandas version are not expected; tell us if you see any.

## B7. Turn on the AI advisor (API key)

The advisor works in three modes:

| Mode | When | Quality |
|---|---|---|
| **Offline analyst** | No key set (default) | Recognises common business questions and answers from the same engine; never fails in a demo |
| **Groq** | `GROQ_API_KEY` set | A hosted language model that calls the engine's tools; free tier available |
| **Claude** | `ANTHROPIC_API_KEY` set | Same, using Anthropic's Claude (paid account needed) |

In every mode the numbers come from the engine's functions on the live matrix, not from the language model's memory.

### Get a free Groq key

1. Go to **https://console.groq.com** and sign up (Google or GitHub login works).
2. Open **API Keys** in the left menu and click **Create API Key**. Give it a name such as `journeypulse`.
3. **Copy the key now.** It starts with `gsk_` and is shown only once. Keep it private.

*(Claude instead: create a key at https://console.anthropic.com → API Keys; it starts with `sk-ant-` and needs billing credits.)*

### Put the key in your `.env` file

In the project folder copy the template:

```bash
cp .env.example .env          # Windows: copy .env.example .env
```

Open `.env` in any text editor and paste your key after the `=` with **no quotes and no spaces**:

```
GROQ_API_KEY=gsk_your_key_here
ANTHROPIC_API_KEY=
```

Save the file. The `.env` file is listed in `.gitignore`, so git will not publish it.

### Start the app so it loads `.env`

The Python code reads real environment variables only, and **only the launcher scripts load `.env`**, so start with:

```bash
./run_mac_linux.sh          # Mac / Linux (run `chmod +x run_mac_linux.sh` once if needed)
```

or double-click / run **`run_windows.bat`** on Windows.

> The launcher scripts run whichever `python3`/`python` is first on your path, so **activate the virtual environment from B2 before running them** (on macOS an un-activated system Python may refuse the install). Or skip the launcher and set the variable by hand:
> Mac/Linux: `export GROQ_API_KEY=gsk_...` then `python -m backend.server --open`.
> PowerShell: `$env:GROQ_API_KEY = "gsk_..."` then `python -m backend.server --open`.

### Confirm it works

The sidebar footer should read **"Advisor: Groq (openai/gpt-oss-120b)"** instead of "offline analyst". Open **AI advisor** and ask: *"What if we improve checkout completion by 3 points?"*. The reply should mention the live model version, and the small chip under the message shows which model and tools were used.

### Choosing the model or provider

- **`GROQ_MODEL`**: default `openai/gpt-oss-120b` (a tool-calling model). Groq retires models from time to time. If you see "Groq unavailable (HTTPError)" and a "model not found" error, list the models your key can use and pick one that supports tools:
  ```bash
  curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"
  ```
  then set `GROQ_MODEL=<id>` in `.env`.
- **`ANTHROPIC_MODEL`**: default `claude-haiku-4-5-20251001`.
- **`ADVISOR_PROVIDER=groq`** forces Groq if both keys are set. By default Claude is used when its key is present.
- If a hosted call fails for any reason (no internet, bad or expired key, rate limit), the advisor **falls back to the offline analyst and says so** in the reply.

### Key safety (please read)

- Never paste the key into code, the report, a chat, a screenshot or a commit. Only `.env` or your terminal.
- The key stays on the server; the browser never receives it.
- If a key is ever exposed, delete it in the Groq/Anthropic console and make a new one.

## B8. A 4-minute tour of the app

Use the Electronics dataset.

1. **Overview.** The headline number is expected revenue per 1,000 visitors from the **live** model, with how far it is above the frozen first-month model.
2. **Rewind** with ⏮ in the top bar to **v0**. Live and frozen are now identical.
3. **What-if simulator** → click *Checkout +3 pts*. The *snapshot error* is 0% because only October is known.
4. Click **Next month** three times. After each month a message tells you which stages drifted. The what-if result updates by itself and the snapshot error grows (about −19% by January). *This is the whole idea in one screen.*
5. **Adaptive engine.** See the month cards, the drift-test table (corrected p-values, size of shift, α actually applied) and the tracking chart. Switch the **Dataset** to Synthetic to watch the model follow a planted jump from 35% to 50% while the frozen model stays flat.
6. **Datasets.** Open the *Datasets* page to see where the data comes from, its size and period, how it was sampled and cleaned, and a side-by-side table of all datasets. At the bottom, **Look inside the data** shows the actual raw rows, a few real customers' journeys step by step, and the monthly counts the model learns from.
7. **Journey map.** The live transition matrix as a heatmap; switch between live, frozen, month-only and change-since-frozen.
8. **Budget optimiser.** Best split of a 5-point improvement budget across four levers, for the live and frozen models, verified against a brute-force grid search.
9. **Next best actions**, **Prediction** (where a customer is likely to be in *k* steps) and **AI advisor**. Ask *"Where are we losing the most customers?"*.
10. **Model quality.** Be upfront that adaptive beats frozen only slightly on next-click prediction; the bigger effect is on forecasts.

**Your data** (top of the sidebar) lets you upload your own customer activity and get all of the above for your business: see [C6](#c6-use-your-own-data-business-users).

The sun/moon button switches between light and dark themes.

---

# Part C: reference

## C1. Project structure

```
Journey_pulse/
├── backend/                      Python: standard library + numpy/pandas/scipy
│   ├── config.py                 every tunable constant (churn days, loyalty threshold, drift and α, budget, AI keys)
│   ├── server.py                 HTTP server: serves /api/* and the frontend from one process
│   ├── api/routes.py             the REST API as plain functions + input validation
│   ├── data/preprocess.py        dataset registry, clickstream → states, censoring, monthly batches, cache
│   ├── data/custom.py            bring-your-own-data: column guessing, action mapping, builds a Dataset from an uploaded CSV
│   ├── engine/                   the maths (dataset-agnostic)
│   │   ├── states.py             the 7 states and the 4 business levers
│   │   ├── markov.py             MLE matrix, k-step prediction, absorption analysis, evaluation
│   │   ├── adaptive.py           drift test, adaptive α, 4 update strategies, versioned AdaptiveModel
│   │   ├── simulator.py          what-if shifts (clamped), business metrics, live vs frozen scenario
│   │   ├── optimizer.py          SLSQP budget allocation + brute-force grid check
│   │   └── actions.py            next-best actions: computed lever ranking + rule-based playbook
│   └── services/
│       ├── workspace.py          one live model per dataset; every analysis reads its live matrix
│       └── advisor.py            AI advisor: Groq / Claude tool-use loop over HTTPS + offline analyst
├── frontend/                     no build step, no external libraries (works offline)
│   ├── index.html, css/, js/     app shell, flat minimal UI, hand-drawn SVG charts, 12 views in js/views/
│   └── sample/business_sample.csv  a fictional shop's event log for trying the upload (made by scripts/make_sample_csv.py)
├── demo/                         browser-demo plumbing (Pyodide worker, adapter for the API)
├── scripts/                      build_static_site.py, deploy_pages.sh (GitHub Pages), make_sample_csv.py
├── tests/                        54 tests; run with pytest or `python tests/run_tests.py`
├── data/
│   ├── synthetic/                included
│   ├── raw/electronics/          you add events.csv  (git-ignored)
│   ├── raw/cosmetics/            you add 5 CSVs      (git-ignored)
│   └── processed/                cache               (git-ignored)
├── docs/                         formula notes, report draft, remaining-work checklist
├── CLAUDE.md                     brief for AI coding sessions on this repo (decisions and reference numbers)
├── requirements.txt, .env.example, .gitignore, run_mac_linux.sh, run_windows.bat
```

## C2. API

All responses are JSON. `dataset` defaults to Electronics (or the first available dataset).

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/health` | | advisor mode (`groq`, `claude` or `offline`) and model |
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
| GET | `/api/preview` | `dataset`, `rows` | sample raw rows, example journeys and the monthly transition counts |
| POST | `/api/upload` | query `action`: inspect · build · remove; `name`, `mapping` (JSON); body = the raw CSV | column guesses and preview / builds the `custom` dataset / removes it |
| POST | `/api/advisor` | `messages`: [{role, content}] | reply, source (groq / claude / offline), tools used, suggestions |

Levers: `view_to_cart`, `cart_to_purchase`, `purchase_to_repeat`, `repeat_to_loyal`. Each moves probability out of that stage's churn cell (clamped so no probability goes negative).

## C3. Method in detail

**Events → states** (`backend/data/preprocess.py`):
- Each session starts with *Visitor*; `view` → Product View, `cart` → Add to Cart, `remove_from_cart` → Product View; all purchases in a session count as one order.
- Before the first order a customer moves through the browsing funnel; a new session starts at Visitor again.
- From the first order on, the customer moves through **order stages** (1st → Purchase, 2nd → Repeat Purchase, 3rd+ → Loyal Customer). Browsing between orders is not re-entered into the funnel. *Why:* otherwise the chain contains Add to Cart → Loyal edges, and a memoryless chain would let a brand-new visitor jump from a cart straight to "Loyal".
- **Exit = churn**: no activity for 30 days. Customers active in the last 30 days of the data are right-censored (no Exit).
- Only transitions whose starting event is at least 30 days before the data ends are used (their outcome is known).
- Transitions are batched by the month of the **starting** event (batching by destination month pushes every October churn into November and makes everything look drifted).
- Customers get small integer codes; raw 19-digit user ids lose precision as floating point and an early prototype silently merged neighbouring customers.

**Maths.**
- Maximum-likelihood transition matrix `P[i][j] = n_ij / Σ_j n_ij`; k-step prediction `π(k) = π(0)·Pᵏ`.
- Absorption analysis with `N = (I − Q)⁻¹`: expected visits, expected steps to churn, probability of ever reaching a state `N[i,j]/N[j,j]`, expected orders; revenue = expected orders × average order value.
- Drift: per stage, a two-sample χ² test of homogeneity between last month's and this month's counts, Holm-corrected across stages at 0.05, flagged only if the shift is also at least 0.02 in total variation.
- Adaptive EWMA: `P_new[i] = αᵢ·P_month[i] + (1 − αᵢ)·P_live[i]`, with αᵢ = 0.30 for stable stages and `0.30 + 0.50·tanh(TVᵢ/0.05)` for drifted ones (so at most 0.80). Alternatives: plain EWMA, sliding window, Bayesian (Dirichlet) update.
- Optimiser: maximise expected orders (or P(loyal), P(first order)) subject to a total budget and per-lever caps, SLSQP from several starts, checked against a brute-force grid.

**Limitations.** First-order (memoryless) assumption; left-censoring (a customer's "first" order in the data may not be their first ever); shorter observation windows for recent orders; levers only move the churn cell; playbook tactics are rule-based suggestions, not model output.

For a plain-language walkthrough of every formula (written for teammates preparing for the viva) see `docs/FORMULAS_EXPLAINED.md`.

## C4. Tests

```bash
python tests/run_tests.py     # no extra packages needed
python -m pytest -q           # if pytest is installed
```

The suite includes a regression test for every bug fixed from the mid-review code: drift false alarms (stable batches at most 10% flagged), α actually rising on drift, the advisor working with no API key, the Groq tool loop and fallback, clamped what-if shifts, absorption with an unobserved stage, no transitions across customers, and the optimiser matching a brute-force grid. Other groups: the REES46 loader refactor, `tests/test_custom_upload.py` (column guessing, messy date and column formats, purchase-only exports, every friendly error, the upload and preview routes), `tests/test_static_demo.py` (the browser demo returns the same JSON as the full app, including for uploads), and a regression test that a fresh clone finds the synthetic data.

## C5. The GitHub Pages browser demo

GitHub Pages can only serve static files, so it cannot run `backend/server.py`. The demo instead runs the **real `backend/` package in the browser** using [Pyodide](https://pyodide.org) (Python compiled to WebAssembly, with numpy, scipy and pandas), in a Web Worker so the page stays responsive.

How it fits together:

| Piece | Role |
|---|---|
| `demo/jp_static.py` | Plays the part of `server.py`: answers the same `/api/*` calls by calling the same route functions |
| `demo/worker.js`, `demo/static-api.js` | Boot Pyodide, load the backend files, and pass API calls between the page and Python |
| `frontend/js/api.js` | When `window.JP_STATIC` is set, sends API calls (and uploaded files) to the worker instead of `fetch` |
| `scripts/build_static_site.py` | Builds `site/`: the frontend, the backend `.py` files, and `data/datasets.json` (aggregated counts; for the synthetic dataset also sample rows and journeys) |
| `scripts/deploy_pages.sh` | Builds and pushes `site/` to the `gh-pages` branch |

**What is published:** only *aggregated* data: for each dataset, one 7×7 transition-count matrix per month, plus labels, average order value and summary facts (only about 7 KB for all three datasets; the whole site is under 1 MB). No raw events, user ids or sessions. Because the engine only ever reads those counts, the demo returns exactly the same JSON as the full app (`tests/test_static_demo.py` checks this). The datasets remain subject to their original terms (Kaggle lists both REES46 datasets as "Data files © Original Authors"); attribution is shown in the app on the Datasets page. Publishing only aggregated counts is a judgement call: check the Kaggle pages and, if in doubt, deploy with only the synthetic dataset.

**Rebuild and redeploy** (needs the datasets under `data/raw/` for the real ones to be included). By default the demo's data viewer shows raw rows and example journeys only for the synthetic dataset (it is ours); add `--real-samples` to also publish 10 raw rows and a few example journeys of the REES46 datasets, which is your call to make given their terms:

```bash
PYTHON=.venv/bin/python ./scripts/deploy_pages.sh                    # aggregated counts (+ synthetic rows)
PYTHON=.venv/bin/python ./scripts/deploy_pages.sh --real-samples     # also 10 REES46 rows per dataset
```

Then in GitHub: Settings → Pages → Source: *Deploy from a branch* → `gh-pages` / `(root)`. To preview locally: `python scripts/build_static_site.py && python -m http.server 8200 --directory site`.

**Limits of the demo:** the first visit takes a while (about 21 MB of downloads and a few seconds to start Python); each visitor has their own in-browser model (stream position resets on reload); and there is no hosted-model advisor.

## C6. Use your own data (business users)

The **Your data** page turns a business's own customer activity into the same live model, what-if simulator, optimiser, recommendations and advisor that the built-in datasets get.

**What your file needs.** One row per customer action, as a CSV:

| Needed | Example column | Example value |
|---|---|---|
| Who (customer id) | `Customer` | `C1113` |
| When (date and time) | `When` | `2026-01-06 05:37` |
| What they did | `Action` | `Viewed product`, `Added to basket`, `Placed order` |
| *Optional:* session id | `Session` | `s-8841` |
| *Optional:* order value | `Order value` | `10.51` |

You need roughly **three months** of history (about seven weeks at the very least with the default 30-day *lost* window, because the model needs three weeks left to learn from after that window) and a few thousand rows, because the model compares periods. Up to 3 million rows locally and about 400,000 in the web demo. A ready-made example is in `frontend/sample/business_sample.csv` (also behind the **Try the sample file** button).

**The four steps on the page**

1. **Choose your file** (or press *Try the sample file*).
2. **Check how we read it.** The page guesses which column is the customer, the date, the action, the session and the order value, and what each action means (looked at a product, added to cart, removed from cart, bought something, or ignore). It shows the first rows and how the first date was read. Fix anything that is wrong. Day-first dates (31/01/2026) have a tick-box.
3. **Two business settings:** after how many days of silence a customer counts as *lost* (default 30; use 90 or more for things people buy rarely) and from which order a customer is *loyal* (default 3). If your file has no order value column, enter an average order value.
4. **Analyse my data.** The whole dashboard switches to your data (it appears in the sidebar's Dataset menu as "Your data (file name)"). The **Datasets** page shows how it was cleaned.

**What happens to your data.** In the **web demo** the file is read and processed inside your browser tab (Python runs in the tab) and is **never uploaded anywhere**; closing the tab discards it. In the **local app** the file is sent only to the JourneyPulse program on your own computer, held in a temporary file while it is processed, then deleted; the resulting dataset lives in memory until you remove it or restart. Nothing is written to `data/`.

**Honest limits.**
- Sessions are inferred from 30-minute gaps when there is no session column.
- If the file has **only purchases** (no browsing or cart actions) you still get repeat-purchase and loyalty results, but the product-page and checkout levers have nothing to work with, and the page says so.
- With only two periods of history, the drift tests and validation are weak, and the page warns you.
- The model is a first-order Markov chain on customer journeys: it describes behaviour in your data, it does not prove that a campaign will cause a given lift.
- Order value is summed per visit; a customer who buys twice in one visit counts as one order.

**For developers.** The upload goes through the same pipeline as the REES46 data (`preprocess.assemble_dataset`), so the reference numbers cannot differ between built-in and uploaded data. Guessing and building live in `backend/data/custom.py`; the routes are `POST /api/upload` and `GET /api/preview`; the front end is `frontend/js/views/upload.js`. Tests: `tests/test_custom_upload.py`.

---

# Part D

## D1. Troubleshooting

| Problem | Fix |
|---|---|
| "Can't reach the JourneyPulse server" | Start it with `python -m backend.server` from the project folder and keep that terminal open. |
| `ModuleNotFoundError: No module named 'pandas'` | Activate the virtual environment (B2) and run `pip install -r requirements.txt`. |
| macOS: `externally-managed-environment` when installing | Use the virtual environment in B2. |
| Electronics still "not downloaded" | The file must be exactly `data/raw/electronics/events.csv`. Restart the server after adding it. |
| Cosmetics still "not downloaded" | The five CSVs must sit directly in `data/raw/cosmetics/`, not in a nested `cosmetics/cosmetics/` folder. Restart the server. |
| The page looks unchanged after an update | Hard-reload the browser (Ctrl/Cmd + Shift + R). |
| Port already in use | `PORT=9000 python -m backend.server` (PowerShell: `$env:PORT=9000`). |
| Numbers look stale after editing preprocessing | Delete `data/processed/` to rebuild the cache. |
| Sidebar still says "offline analyst" after adding a key | The server only reads the key at startup and only the launcher scripts load `.env`. Restart using `./run_mac_linux.sh` / `run_windows.bat`, or set the variable in the terminal first. Check there are no quotes or spaces around the key in `.env`. |
| Reply says "Groq unavailable (HTTPError)" | Usually a retired model name (see B7: list models and set `GROQ_MODEL`), a mistyped or revoked key, or the rate limit. The answer is still given offline. |
| `Permission denied: ./run_mac_linux.sh` | `chmod +x run_mac_linux.sh` |
| Upload says it could not read the dates | Pick the right date column; tick *day first* if your dates look like 31/01/2026; text like "yesterday" cannot be read. |
| Upload says none of your actions is a purchase | In step 2 mark the action that means a sale as *Bought something*. |
| Upload says there is too little history | Export at least three months (about seven weeks is the bare minimum) or lower the *lost after* days. |
| Upload is too large in the web demo | Use the local app, or filter to fewer customers (keep every row of each sampled customer). |

## D2. Data and licence

Data: REES46 Marketing Platform (rees46.com), via Kaggle (mkechinov), published on Kaggle with the licence shown as **"Data files © Original Authors"** (check each dataset's Kaggle page for the current terms). The datasets are **not included** in this repository; download them from Kaggle as described in B4 and B5, and keep the attribution in any report or slides.

## D3. More documents

- `docs/FORMULAS_EXPLAINED.md`: every formula in plain words, with viva questions.
- `docs/REPORT_DRAFT.md`: the report draft with the full results and caveats.
- `docs/REMAINING_CHECKLIST.md`: what is still left to do.
- `CLAUDE.md`: design decisions and the reference numbers the code must reproduce.
