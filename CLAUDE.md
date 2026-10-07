# CLAUDE.md — JourneyPulse (Group 12, 23MAT204)

Brief for any Claude Code session working on this repo. Read it fully before changing code.

## 1. What this is

Customer-journey prediction with a first-order Markov chain over 7 states
(Visitor, Product View, Add to Cart, Purchase, Repeat Purchase, Loyal Customer, Exit; Exit absorbing = churn),
served as a web app: Python backend (`backend/`, stdlib HTTP server + numpy/pandas/scipy) and a
no-build vanilla-JS frontend (`frontend/`). Run: `python -m backend.server --open`.

**Novelty claim — keep it modest everywhere (code comments, UI text, docs):** combining adaptive
transition-matrix updating with a what-if simulator, optimiser and AI advisor that always read the
**live** matrix rather than a frozen snapshot, for customer-journey decisions. Adaptive updating
(control/Bayesian/MDP literature), what-if simulation (finance/BPM) and optimisation on Markov customer
models (Pfeifer & Carraway 2004) each exist separately; do not claim any of them alone is new, and never
write "never been done" — write "not found in the reviewed literature".

## 2. Status: built and tested

All of the original build plan is done. 39 tests pass (`python tests/run_tests.py`, or pytest).

| Area | File | Notes |
|---|---|---|
| States, levers | `backend/engine/states.py` | 4 levers, each moves mass out of its row's Exit cell |
| Core maths | `backend/engine/markov.py` | unobserved transient rows go to Exit (not self-loop) so (I−Q) stays invertible |
| Adaptive layer | `backend/engine/adaptive.py` | two-sample χ² + Holm + `MIN_DRIFT_TV`; α from TV; 4 strategies; versioned model |
| What-if | `backend/engine/simulator.py` | shifts clamped to headroom; always live vs frozen |
| Optimiser | `backend/engine/optimizer.py` | SLSQP multi-start + batched brute-force grid check |
| Next best actions | `backend/engine/actions.py` | computed ranking + labelled rule-based playbook |
| Data | `backend/data/preprocess.py` | registry: electronics, cosmetics (untested, 10% customer sample), synthetic |
| Live model | `backend/services/workspace.py` | one per dataset; `live_matrix` is the single source of truth |
| AI advisor | `backend/services/advisor.py` | Claude tool-use over urllib (key from env only) + offline analyst fallback |
| API | `backend/api/routes.py`, `backend/server.py` | framework-free route functions; see README §4 |
| Dashboard | `frontend/` | 10 views; flat minimal UI, light/dark; hand-drawn SVG charts (no CDN) |

The mid-review files (`markov_engine.py`, `markov_engine_core.py`, `adaptive_engine.py`, `ai_assistant.py`,
`app.py`, `demo_adaptive.py`) are superseded and not part of this repo. Their bugs are fixed here with
regression tests: drift false alarms (~50% → ≤10%), α barely moving, advisor crashing without a key,
Exit row all zeros, negative probabilities from unclamped shifts.

## 3. Decisions that differ from the earlier plan (keep them; explain them in the report)

1. **Order stages instead of re-entering the funnel.** After a customer's first order, their browsing is not
   re-entered as Visitor/View/Cart; they move Purchase → Repeat → Loyal (or → Exit). The earlier rule created
   Add to Cart → Loyal edges, so the memoryless chain let a new visitor reach "Loyal" without buying first.
2. **Batch by the source event's month**, not the destination's (Exit is dated +30 days, which pushed October
   churn into November and made every row look drifted).
3. **Censoring rule:** use only transitions whose source is ≥ `CHURN_DAYS` before the data ends. Electronics
   therefore uses Oct–Jan (Sep week merged into Oct); validation tests on January.
4. **Integer customer codes.** Raw REES46 user_ids are 19-digit; comparing them after a pandas `shift` turns
   them into float64 and merges neighbouring customers. The earlier preview numbers were contaminated by this.
5. **Default budget 5 points, 3 per lever.** Product page → Cart is only ~6.5%, so +10 points was unrealistic.
6. **Stdlib server instead of FastAPI/Streamlit**, and no chart CDN: fewer installs, works offline in the viva.

## 4. Reference numbers (Electronics, churn 30d, loyalty 3) — code must reproduce these

- 885,129 rows; 655 duplicates + 162 null-session rows removed; 407,237 customers; 490,633 sessions;
  1,042,339 transitions used of 1,216,213; batches Oct 2020 · Nov 2020 · Dec 2020 · Jan 2021; AOV ≈ 210.5.
- Live (v3) vs frozen (v0): revenue per 1k visitors 13,332 vs 10,779; P(first order) 5.5% vs 4.6%;
  Purchase → Repeat 12.3% vs 9.3%; Cart → Purchase 35.0% vs 37.7%.
- Drift: Nov {Product View, Purchase}; Dec none; Jan {Product View, Add to Cart}.
- Held-out Jan: accuracy 66.5% vs baseline 58.1%; log-loss adaptive 0.7467, frozen 0.7498, baseline 1.0685.
- Synthetic: drift only in Add to Cart at batch 2 (Feb 1–7), α 0.80; live Cart→Purchase ends 52.9% (truth 50%).

If a change moves these, find out why before accepting it. Report results honestly: on Electronics the
adaptive gain in next-step accuracy is small; the larger effect is in scenario/optimiser forecasts.

## 5. Rules

- Every matrix must pass `assert_row_stochastic` after every update or shift.
- Maths stays in `backend/engine/`; `workspace.py` wires it; routes validate input; the frontend only displays.
- Dataset-specific code lives only in `preprocess.py`. Never pool datasets into one matrix.
- Frontend inserts data with `textContent` (the `h()` helper); only constant icon strings use innerHTML.
- Chart colours: series-1 = live, series-2 = frozen, series-3 = month-only; text never in series colour.
- Never hard-code or log an API key; never commit `data/raw/`, `data/processed/` or `.env`.
- Run the full test suite before every commit.

## 6. Still to do (not code)

- Run the Cosmetics dataset once (put the CSVs in `data/raw/cosmetics/`) and record its numbers; it becomes the
  generalisation comparison with Electronics.
- Report, slides and the "formulas explained simply" notes for teammates. Slide fixes still pending: slide 6
  "never" → "not found in the reviewed literature"; slides 9–10 "steady-state" → "absorption analysis";
  slide 9 "Real dataset" box → "REES46 Electronics (Kaggle)"; recommendation box → "AI advisor (Claude + offline analyst)".
