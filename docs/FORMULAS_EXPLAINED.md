# JourneyPulse: the formulas explained simply

For teammates who need to explain any part of the project in the viva. Each section says what the idea is, the formula, a plain-words reading, and where it lives in the code.

---

## 1. The Markov chain

**Idea.** A customer is always in one of 7 states: Visitor, Product View, Add to Cart, Purchase, Repeat Purchase, Loyal Customer, Exit. The chain says: *where you go next depends only on where you are now*, not on how you got there. This is the **first-order Markov (memoryless) property**.

**Transition matrix P.** `P[i][j] = probability of going from state i to state j in one step`. Each row sums to 1 (row-stochastic). Exit is **absorbing**: once a customer exits they stay out (`P[Exit][Exit] = 1`), and Exit means churn.

**Estimating P from data (maximum likelihood).**

    P[i][j] = n_ij / (n_i1 + n_i2 + ... + n_i7)

Count how many times customers went i → j and divide by how many times they left i. *Code:* `engine/markov.py: to_matrix`.

**Edge case.** If a state never appears in the data, its row would be 0/0. We send it to Exit instead of giving it a self-loop. A self-loop would make `(I − Q)` singular (not invertible) and the absorption maths would crash.

---

## 2. Predicting ahead

**One step:** read row `i` of P.
**k steps:** read row `i` of `P^k` (matrix power). If `π(0)` is where the customer starts, then `π(k) = π(0)·P^k`.
*Code:* `markov.py: next_state, k_step`.

A plain "steady state" is useless here, because with Exit absorbing every customer ends in Exit with probability 1. That is why we use **absorption analysis** instead (next section). (The slides must say "absorption analysis", not "steady-state".)

---

## 3. Absorption analysis (the most important maths)

Split P into blocks. `Q` = the transient-to-transient part (everything except Exit).

**Fundamental matrix:**

    N = (I − Q)^(-1)

**Reading N.** `N[i][j]` = expected number of visits to state j before the customer exits, if they start in i. It comes from the geometric series `I + Q + Q² + ...`, which converges to `(I − Q)^-1` because customers eventually leave.

What we compute from it (`markov.py: absorption`):

| Quantity | Formula | Meaning |
|---|---|---|
| Steps to exit | sum of row `i` of N | How long a customer stays in the journey |
| P(ever reach j) | `N[i][j] / N[j][j]` | Chance a visitor ever gets to j (e.g. ever buys) |
| Expected orders | visits to Purchase + Repeat + Loyal | Average orders per visitor |
| Revenue per 1,000 visitors | expected orders × AOV × 1000 | The headline business number |

*Why divide by `N[j][j]`?* `N[j][j]` counts the visit that starts at j plus any returns to j. Dividing removes the returns, leaving the probability of reaching j at all.

---

## 4. Drift detection: "has behaviour changed?"

Every month we get new counts. We ask, for each state's row: **are last month's and this month's transition counts from the same distribution?**

1. **Two-sample χ² test of homogeneity** on the 2×k table [old counts; new counts] (`scipy.stats.chi2_contingency`). It treats both months as noisy samples. The earlier prototype tested against the old matrix as if it were exact truth, which gave about 50% false alarms.
2. **Holm correction.** We test 6 rows at once, so the chance of at least one false alarm grows. Holm's step-down method sorts the p-values and multiplies the k-th smallest by `(m − k)`, keeping the overall error at 5%. It is uniformly more powerful than Bonferroni.
3. **Minimum effect size.** With 100,000+ transitions per row, tiny differences are "statistically significant" but meaningless. So a row is flagged only if it is **significant AND its total variation ≥ 0.02**.

**Total variation (TV):** `TV(p, q) = ½ Σ |p_k − q_k|`. It is the largest probability you could redistribute between the two rows: 0 means identical, 1 means disjoint.

Also computed for display: **KL divergence** `Σ p log(p/q)` and **Jensen–Shannon** (a symmetric, bounded version of KL).

*Code:* `engine/adaptive.py: detect_drift`.

---

## 5. Adaptive updating: how the matrix "re-learns"

**EWMA (exponentially weighted moving average) blend**, per row:

    P_new[i] = α_i · P_month[i] + (1 − α_i) · P_live[i]

α is the weight on the new month. High α means forget the past faster.

**Adaptive α.** Stable rows get α = 0.30. Drifted rows get more:

    α = 0.30 + 0.50 · tanh(TV / 0.05)

`tanh` saturates, so α can never exceed 0.80 however extreme one month is. Examples: TV 0.02 → α ≈ 0.49, TV 0.05 → α ≈ 0.68, TV 0.15 → α ≈ 0.80. The earlier prototype used `tanh(4·JSD)`, but real JSD is about 0.01, so α barely moved.

**The four strategies** (`adaptive.py`): adaptive EWMA (default), plain EWMA with fixed α, sliding window (re-fit on the last 3 months), and Bayesian (Dirichlet–multinomial: `posterior = 0.9·prior + new counts`, so old evidence decays).

Every updated matrix must pass `assert_row_stochastic` (non-negative entries, rows sum to 1).

---

## 6. Live versus frozen

- **Frozen** = version 0, the matrix fitted once on the first month and never updated (what a conventional model does).
- **Live** = the latest version after streaming through all the months.

The simulator, optimiser and AI advisor always read the live matrix. The dashboard also shows the frozen answer, so the gap, the cost of a stale model, is visible.

---

## 7. What-if simulator

A **lever** is a transition a campaign can push up, e.g. Cart → Purchase (checkout completion). Raising it by `δ` moves `δ` of probability out of that row's **Exit** cell:

    P[i][j] += δ        P[i][Exit] −= δ

so the row still sums to 1. `δ` is **clamped**: it cannot exceed the row's current Exit probability (the headroom) or push a cell below 0. The old version had no clamp and produced negative probabilities.

Then we recompute N and the business metrics on the scenario matrix. `snapshot_error` = frozen answer − live answer.
*Code:* `engine/simulator.py`.

---

## 8. Optimiser

**Question:** given a budget of improvement (default 5 percentage points total, max 3 per lever), how should it be split across the 4 levers?

    maximise   f(P + Σ x_l · E_l)       f = expected orders, P(loyal) or P(first order)
    subject to Σ x_l ≤ budget,   0 ≤ x_l ≤ min(per-lever cap, headroom_l)

`f` goes through `(I − Q)^-1`, so it is non-linear in `x`. We use **SLSQP** (sequential least-squares quadratic programming) from several starting points, then check the answer against a **brute-force grid** at 1-point steps. A test confirms they agree. The optimiser is established prior art (Pfeifer & Carraway 2004); our contribution is running it on the live matrix.
*Code:* `engine/optimizer.py`.

---

## 9. Validation

Train on October–December, test on **held-out January transitions**.

- **Accuracy**: does the single most likely next state match what happened? Compared against a baseline that always guesses the most common next state.
- **Log-loss** `−mean(log P[a][b])`: scores the full predicted probabilities, so it rewards a well-calibrated model even if its top guess doesn't change. Lower is better. (Probabilities are lightly smoothed by 1e-4 so a zero never gives infinite loss.)

**Honest result:** adaptive barely beats frozen on next-step prediction (log-loss 0.7467 vs 0.7498), because real behaviour drifts slowly. The big difference shows up in **scenario and optimiser forecasts**.

---

## 10. Data to states (the decisions you must be able to defend)

1. **Order stages.** After a first order, customers move Purchase → Repeat → Loyal, not back through the browsing funnel. Otherwise the chain has Cart → Loyal edges and a brand-new visitor could reach "Loyal" without buying.
2. **Batch by the source event's month.** Exit is dated 30 days after the last event, so batching by destination month pushes every October churn into November and makes everything look drifted.
3. **Censoring.** Only transitions whose source is at least 30 days before the data ends are used, because we can't yet know whether recent customers churned. Hence Oct–Jan for Electronics.
4. **Integer customer codes.** Raw 19-digit user_ids lose precision as float64 after a pandas `shift`, merging neighbouring customers.
5. **Churn = 30 days of inactivity; Loyal = 3rd order or more.** Both are in `config.py`.
6. **Budget 5 points, 3 per lever.** Product page → Cart is only about 6.5%, so +10 points was unrealistic.

---

## 11. Novelty, said modestly

Adaptive updating, what-if simulation and optimisation on Markov customer models each exist already. What we combine is a **single live, self-updating matrix that the simulator, optimiser and AI advisor all read**, for customer-journey decisions. Say "**not found in the reviewed literature**". Never say "never been done".

---

## Likely viva questions

- *Why first-order?* Simplicity and interpretability; the limitation is that real customers have longer memory. Higher-order chains need exponentially more data.
- *Why is a steady state not used?* Exit is absorbing, so it would be 100% Exit.
- *Why two-sample χ² and not goodness-of-fit?* The old matrix is itself estimated, not exact truth.
- *Why Holm and the TV threshold?* Multiple testing, and huge samples make trivial shifts significant.
- *Why does adaptive barely beat frozen on accuracy?* Drift is slow and top-1 accuracy ignores probability calibration; the gain shows in forecasts.
- *What are the limits?* Memoryless assumption, left-censoring, levers only move the churn cell, playbook tactics are rule-based.
- *Is the AI advisor making up numbers?* No. It calls the same engine functions as tools; the offline analyst uses the same engine without a model.
