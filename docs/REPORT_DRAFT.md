# JourneyPulse: adaptive Markov customer-journey intelligence

**Group 12, 23MAT204 Mathematics for Intelligent Systems 3**
Team: _(add names and roll numbers)_

> **Status of this draft.** Method, design decisions and the synthetic-data result are final. Numbers marked **[verify]** come from the Electronics reference run recorded in CLAUDE.md and README §5; re-run on the real data and confirm before submitting. §6.2 (Cosmetics) is a placeholder until that dataset has been run.

---

## 1. Abstract

We model customer journeys on an e-commerce site as a first-order Markov chain over seven states (Visitor, Product View, Add to Cart, Purchase, Repeat Purchase, Loyal Customer, Exit), with Exit absorbing and standing for churn. The transition matrix is not fitted once: it is re-estimated every month, with drift detected by a Holm-corrected two-sample χ² test and the update weight driven by the measured shift. A what-if simulator, a constrained optimiser and an AI advisor all read this live matrix, and the dashboard shows each answer next to what a frozen first-month model would have said. On the REES46 Electronics data the live model forecasts materially different business outcomes from the frozen one (revenue per 1,000 visitors 13,332 vs 10,779 **[verify]**), although the gain in next-step prediction accuracy is small.

## 2. Problem and motivation

A retailer wants to know where customers are lost, what a campaign is worth, and how to spend a limited improvement budget. A model fitted once goes stale as behaviour changes. We ask: if the model keeps itself current, how different are the decisions it supports?

## 3. Related work and novelty claim

Adaptive updating of transition probabilities appears in the control, Bayesian and Markov-decision-process literature. What-if simulation is standard in finance and business-process management. Optimisation on Markov customer models is established (Pfeifer & Carraway, 2004). We do **not** claim any of these alone is new. What we combine is a single live, adaptively updated matrix that the simulator, optimiser and AI advisor all read, applied to customer-journey decisions. This combination was **not found in the reviewed literature**.

_(Add the remaining references you reviewed here.)_

## 4. Data

REES46 Electronics store (Kaggle, mkechinov): 885,129 events, 24 Sep 2020 to 28 Feb 2021 **[verify]**. After removing 655 duplicate rows and 162 rows without a session: 407,237 customers, 490,633 sessions, average order value about 210.5 **[verify]**. Events are view, cart and purchase. Source: REES46 Marketing Platform (rees46.com), via Kaggle.

A synthetic dataset with a planted shift (Cart → Purchase moves from 0.35 to 0.50 in February) is used to test that drift detection finds a known change.

## 5. Method

### 5.1 From events to states
Each session starts at Visitor; view → Product View; cart → Add to Cart; remove-from-cart → Product View; all purchases in a session count as one order. Until a first order the customer moves through the browsing funnel. From the first order on they move through order stages: 1st order → Purchase, 2nd → Repeat Purchase, 3rd or later → Loyal Customer. Exit means 30 days with no activity.

Design decisions that differ from our earlier plan, with reasons:

1. **Order stages instead of re-entering the funnel.** Re-entering produced Add to Cart → Loyal edges, so a memoryless chain let a new visitor reach "Loyal" without buying.
2. **Batching by the month of the source event.** Exit is dated 30 days after the last event; batching by destination month pushed October churn into November and made every row look drifted.
3. **Censoring.** Only transitions whose source is at least 30 days before the end of the data are used, since the outcome of later ones is unknown. Electronics therefore uses October to January (the one-week September is merged into October); validation uses January.
4. **Integer customer codes.** Raw 19-digit user ids become indistinguishable as float64 after a pandas shift, silently merging neighbouring customers. Earlier preview numbers were contaminated by this.
5. **Default budget of 5 points, at most 3 per lever.** Product page → Cart is only about 6.5%, so +10 points was unrealistic.
6. **Standard-library server and no chart CDN**, so the system runs offline.

### 5.2 Estimation and prediction
Maximum-likelihood matrix `P[i][j] = n_ij / Σ_j n_ij`. A transient state never observed is sent to Exit (not a self-loop) so that `I − Q` stays invertible. The k-step distribution is the row of `P^k`.

### 5.3 Absorption analysis
With `Q` the transient block, `N = (I − Q)^-1`. From a start state: expected visits `N[s][j]`; expected steps to exit `Σ_j N[s][j]`; probability of ever reaching j `N[s][j]/N[j][j]`; expected orders = visits to Purchase, Repeat Purchase and Loyal Customer; revenue per 1,000 visitors = expected orders × AOV × 1000. A stationary distribution would be 100% Exit, so absorption quantities are the informative long-run measures.

### 5.4 Drift detection
For each transient row, a two-sample χ² test of homogeneity on the table [previous batch counts; new batch counts], p-values Holm-corrected across rows at 0.05, and a row is flagged only if it also moves by at least 0.02 in total variation `½ Σ|p_k − q_k|` (with 100,000+ transitions per row almost any shift is significant). An earlier prototype tested against the old matrix as exact truth and gave about 50% false alarms; the current test gives at most 10% on stable data.

### 5.5 Adaptive update
`P_new[i] = α_i P_month[i] + (1 − α_i) P_live[i]`, with `α_i = 0.30` for stable rows and `α_i = 0.30 + 0.50·tanh(TV_i/0.05)` for drifted rows (so α ≤ 0.80). Three alternatives are provided for comparison: fixed-α EWMA, a 3-month sliding window, and a Bayesian Dirichlet–multinomial update with decay 0.9. Every matrix passes a row-stochastic check after every update.

### 5.6 What-if simulator
Four levers (Product page → Cart, Cart → First order, First order → Second order, Second order → Loyal). Raising a lever by δ moves δ from that row's Exit cell, clamped to the row's Exit mass and to zero. Each scenario is evaluated on both the live and the frozen matrix, and the difference is reported as the snapshot error.

### 5.7 Optimiser
Maximise expected orders (or P(loyal), or P(first order)) subject to a total budget and per-lever caps. The objective is non-linear through `(I − Q)^-1`, so we use SLSQP with several starts and verify against a brute-force grid search at 1-point steps.

### 5.8 AI advisor
Claude uses tool calls into the same engine functions, so every number it quotes comes from the live matrix. Without an API key an offline analyst answers from the same engine. The key is read only from the environment.

## 6. Results

### 6.1 Electronics (churn 30 days, loyal at 3 orders) [verify all]

| | Live (v3) | Frozen (v0) |
|---|---|---|
| Revenue per 1,000 visitors | 13,332 | 10,779 |
| Visitor ever places an order | 5.5% | 4.6% |
| First-time buyers who order again | 12.3% | 9.3% |
| Checkout completion (Cart → order) | 35.0% | 37.7% |

Drift detected: November 2020 in Product View and Purchase; none in December; January 2021 in Product View and Add to Cart. Most of the live–frozen gap comes from the Product View row (fewer product views end in churn: 54% → 49%).

**Held-out January:** next-step accuracy 66.5% vs 58.1% for the most-common-step baseline (47.9% vs 34.9% excluding the trivial first click). Log-loss: adaptive 0.7467, frozen 0.7498, baseline 1.0685.

**Honest reading.** On next-step prediction the adaptive gain over the frozen model is small, because real drift in this store is slow. The larger effect is in forecasts: for a +3-point checkout scenario the frozen model under-states the outcome by about 19%, and for the optimiser's plan it under-states the payoff by about 16%.

### 6.2 Cosmetics (generalisation check)
_To be completed after running the Cosmetics dataset (10% customer sample). Record: rows, customers, batches, drift states, live vs frozen revenue per 1,000 visitors, held-out accuracy and log-loss. State whether the Electronics conclusions (small accuracy gain, larger forecast effect) hold._

### 6.3 Synthetic data with planted drift
Drift is flagged in exactly one row (Add to Cart) in the first February batch, α for that row rises to 0.80, and the live Cart → Purchase estimate rises from about 36% to 52.9% (truth 50%) while the frozen model stays at 36%.

### 6.4 Bugs found in the mid-review prototype, now fixed with regression tests
Drift false alarms (about 50% → 10% or less); α barely moving; the advisor crashing without an API key; an all-zero Exit row; negative probabilities from unclamped what-if shifts.

## 7. Limitations
First-order (memoryless) assumption. Left-censoring: a customer's first order in the data may not be their first ever. Recent orders have shorter observation windows. Levers move only the churn cell. Playbook tactics are rule-based suggestions, not model output. Results come from one retailer category (plus one more once Cosmetics is run).

## 8. Conclusion
Keeping the matrix live changes the business forecasts a decision-maker sees, even where next-step accuracy barely moves. The contribution is the integration of a live matrix with simulation, optimisation and advisory, not any single component.

## 9. Reproducibility
`python -m backend.server --open`; tests with `python tests/run_tests.py` (38 pass, 1 skipped without the real data). All tunable constants are in `backend/config.py`.

## References
- Pfeifer, P. E., & Carraway, R. L. (2004). Modeling customer relationships as Markov chains. _Journal of Interactive Marketing_.
- REES46 Marketing Platform. eCommerce events history (Electronics, Cosmetics). Kaggle, mkechinov.
- _(add the control / Bayesian / MDP / BPM sources you reviewed)_
