// Data & method — what the data is, how events become states, the maths, and the limits.
import { api } from "../api.js";
import { h, card, tile } from "../ui.js";
import { pct, money, int, date } from "../format.js";

export async function render(root) {
  const m = await api("/api/method");
  const f = m.facts;
  const real = !f.complete_journeys;

  root.append(h("div", { class: "tiles" },
    tile("Customers", int(f.customers), h("span", { class: "muted" }, f.sample_rule)),
    tile(real ? "Sessions" : "Events", int(real ? f.sessions : f.rows_raw), h("span", { class: "muted" }, `${int(f.rows_raw)} raw rows`)),
    tile("Transitions used", int(f.transitions_used), h("span", { class: "muted" }, real ? `of ${int(f.transitions_total)} (censoring rule)` : "complete journeys")),
    tile("Period", h("span", { class: "value-sm" }, `${date(f.start)} – ${date(f.end)}`), h("span", { class: "muted" }, `${m.batches.length} batches: ${m.batches.map((b) => b.label).join(", ")}`))));

  const data = card("The dataset", m.label);
  const dl = h("dl", { class: "facts" });
  const add = (k, v) => dl.append(h("dt", {}, k), h("dd", {}, v));
  if (real) {
    add("Events", Object.entries(f.event_counts).map(([k, v]) => `${k} ${int(v)}`).join(" · "));
    add("Cleaning", `${int(f.duplicates_removed)} duplicate rows and ${int(f.null_session_rows_removed)} rows without a session removed`);
    add("Orders", `${int(f.orders)} orders from ${int(f.buyers)} buyers; ${int(f.buyers_2plus)} ordered twice, ${int(f.buyers_3plus)} three or more times`);
    add("Average order value", `${money(f.aov)} (price field as provided in the dataset)`);
    add("Cart abandonment", `${pct(f.cart_abandonment)} of sessions with a cart had no order`);
    add("Orders without a cart event", int(f.order_sessions_without_cart));
    add("Still active at the end", `${pct(f.censored_share)} of customers (right-censored: no Exit appended)`);
  } else {
    add("Events", Object.entries(f.event_counts).map(([k, v]) => `${k} ${int(v)}`).join(" · "));
    add("Order value", `${money(f.aov)} — ${f.aov_note}`);
  }
  add("Source", h("a", { href: f.source.startsWith("http") ? f.source : null, target: "_blank", rel: "noopener" }, f.source));
  add("Attribution", f.attribution);
  data.body.append(dl);

  const map = card("From clicks to journey states", "Exactly as implemented in backend/data/preprocess.py.");
  map.body.append(h("ol", { class: "steps-list" },
    h("li", {}, "Each session starts with ", h("strong", {}, "Visitor"), " (inferred, not logged)."),
    h("li", {}, h("code", {}, "view"), " → Product View, ", h("code", {}, "cart"), " → Add to Cart, ", h("code", {}, "remove_from_cart"), " → Product View."),
    h("li", {}, "All purchase events in one session are ", h("strong", {}, "one order"), "."),
    h("li", {}, "Before the first order, a new session starts at Visitor again (e.g. View → Visitor = came back later)."),
    h("li", {}, "From the first order on, customers move through ", h("strong", {}, "order stages"), `: 1st → Purchase, 2nd → Repeat Purchase, ${m.config.loyal_at}rd+ → Loyal Customer. Browsing between orders isn't re-entered into the funnel, otherwise a memoryless chain would let a new visitor jump from a cart straight to "Loyal".`),
    h("li", {}, h("strong", {}, "Exit = churn"), `: appended when a customer is inactive for ${m.config.churn_days} days before the data ends; customers active later are right-censored.`),
    h("li", {}, `Only transitions whose starting event is at least ${m.config.churn_days} days before the end are used — for later events the outcome isn't known yet.`),
    h("li", {}, "Transitions are batched by the month of their starting event; a first or last month with under ", String(m.config.min_batch_days), " days of data is merged into its neighbour.")));

  const maths = card("The maths", "Everything the dashboard shows comes from these formulas.");
  maths.body.append(h("div", { class: "formulas" },
    fm("Transition matrix (maximum likelihood)", "P[i, j] = n(i→j) / Σₖ n(i→k)"),
    fm("k steps ahead", "π(k) = π(0) · Pᵏ"),
    fm("Fundamental matrix", "N = (I − Q)⁻¹, Q = transient-to-transient block"),
    fm("Expected steps before churn", "t = N · 1"),
    fm("Chance of ever reaching j from i", "h(i, j) = N[i, j] / N[j, j]"),
    fm("Expected orders & revenue", "orders = N[s, Purchase] + N[s, Repeat] + N[s, Loyal];  revenue = orders × AOV"),
    fm("Drift test (per stage)", "χ² homogeneity on [last month; this month] counts, Holm-corrected, flagged if also TV ≥ 0.02"),
    fm("Adaptive update", "Pₙₑw[i] = αᵢ Pₘₒₙₜₕ[i] + (1 − αᵢ) Pₗᵢᵥₑ[i],  αᵢ = 0.30 + 0.50·tanh(TVᵢ / 0.05) if drift"),
    fm("Optimiser", "max f(P + Σ xₗEₗ)  s.t.  Σ xₗ ≤ B, 0 ≤ xₗ ≤ min(cap, headroomₗ)  — SLSQP, grid-verified")));

  const lim = card("Limitations to state in the report", null);
  lim.body.append(h("ul", { class: "read-list" },
    h("li", {}, "First-order Markov assumption: the next step depends only on the current stage. Order stages carry the purchase history the funnel would otherwise forget."),
    h("li", {}, "Left-censoring: a customer's first order in the data may not be their first order ever (the data starts mid-life for some customers)."),
    h("li", {}, "Right-censoring shortens the observation window for recent orders, so month-to-month changes in the repeat rate should be read with care."),
    h("li", {}, "Levers move probability out of a stage's churn cell. Real campaigns may also change other cells; the simulator shows the direct effect only."),
    h("li", {}, "Playbook tactics are rule-based suggestions mapped to each lever; the model ranks levers, it does not know about discounts or emails."),
    h("li", {}, "Novelty claim (kept deliberately modest): combining adaptive transition updating with a what-if simulator and optimiser that always read the live matrix, applied to customer journeys. Each piece exists separately in the literature.")));

  root.append(h("div", { class: "grid-2" }, data, map), h("div", { class: "grid-2" }, maths, lim));
}

function fm(label, expr) {
  return h("div", { class: "fm" }, h("span", { class: "tiny muted" }, label), h("code", {}, expr));
}
