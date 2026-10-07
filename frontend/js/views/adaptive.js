// Adaptive engine — the novelty in detail: every month is tested for drift per
// stage, and the live matrix is re-weighted row by row.
import { api } from "../api.js";
import { h, liveBadge, card, status, toast, stateColor } from "../ui.js";
import { pct, num } from "../format.js";
import { lineChart } from "../charts.js";

const RATES = [
  ["cart_to_purchase", "Checkout completion (cart → first order)"],
  ["view_to_cart", "Product page → cart"],
  ["purchase_to_repeat", "First order → second order"],
  ["repeat_to_loyal", "Second order → loyal"],
];
const STRAT = { adaptive_ewma: "Adaptive EWMA (per-stage α)", ewma: "Plain EWMA (fixed α)", sliding_window: "Sliding window (3 months)", bayesian: "Bayesian (Dirichlet, decay 0.9)" };
let rate = "cart_to_purchase";

export async function render(root) {
  const t = await api("/api/timeline");
  const live = t.live, V = t.versions, cfg = t.config;
  const cur = V[live.version];

  // ------------------------------------------------ timeline strip
  const strip = h("div", { class: "timeline" });
  V.forEach((v) => {
    const drift = v.drift_states;
    const isLive = v.version === live.version, future = v.version > live.version;
    strip.append(h("button", { class: `glass tl-node ${isLive ? "live" : ""} ${future ? "future" : ""}`, "aria-pressed": isLive ? "true" : "false",
      onclick: () => setVersion(v.version) },
      h("span", { class: "tl-v" }, `v${v.version}`),
      h("strong", {}, v.label),
      h("span", { class: "tiny muted" }, v.version === 0 ? "initial fit (frozen snapshot)" : `${num(v.n_transitions / 1000, 0)}k transitions`),
      v.version === 0 ? h("span", { class: "status info" }, "baseline")
        : drift.length ? status("warn", `Drift: ${drift.map(shortName).join(", ")}`) : status("ok", "Stable"),
      isLive ? h("span", { class: "tl-live" }, "LIVE") : null));
  });
  const stratSeg = h("div", { class: "seg" }, ...Object.entries(STRAT).map(([id, label]) =>
    h("button", { class: id === live.strategy ? "on" : "", onclick: () => setStrategy(id) }, label)));
  const tl = card("Stream months into the model", "Click a month to make it the live version. Everything else in the app re-computes on that version instantly.",
    { badge: liveBadge() });
  tl.body.append(strip, h("div", { class: "row gap12 wrap" }, h("span", { class: "tiny muted" }, "Update strategy"), stratSeg));

  // ------------------------------------------------ tracking chart
  const rateSeg = h("div", { class: "seg" }, ...RATES.map(([id, label]) => h("button", { class: id === rate ? "on" : "", onclick: () => { rate = id; draw(); } }, label.split(" (")[0])));
  const chartEl = h("div");
  const chartNote = h("p", { class: "tiny muted" });
  const track = card("Does the live model track real behaviour?", "What each model believed after every month, for one transition.", { right: rateSeg });
  track.body.append(chartEl, chartNote);
  function draw() {
    [...rateSeg.children].forEach((b, i) => b.classList.toggle("on", RATES[i][0] === rate));
    const series = [
      { name: "Live model", color: "var(--series-1)", values: V.map((v) => (v.version <= live.version ? v.kpis[rate] : null)) },
      { name: "Frozen snapshot", color: "var(--series-2)", values: V.map(() => t.frozen_kpis[rate]) },
      { name: "That month alone", color: "var(--series-3)", values: V.map((v) => v.batch_kpis[rate]) },
    ];
    if (t.truth && rate === "cart_to_purchase") {
      const tr = t.truth["Add to Cart->Purchase"];
      series.push({ name: "Planted truth", color: "var(--series-4)", values: V.map((v) => (v.version >= tr.shift_batch ? tr.after : tr.before)) });
    }
    lineChart(chartEl, { x: V.map((v) => v.label), series, yFmt: (v) => pct(v), height: 260, label: RATES.find((r) => r[0] === rate)[1] });
    chartNote.textContent = t.truth && rate === "cart_to_purchase"
      ? "Synthetic data: the true checkout rate was raised from 35% to 50% in February. The live model moves toward it; the frozen snapshot never does."
      : "'That month alone' is noisy; the live model blends it with history, weighting it more when the drift test says behaviour really changed.";
  }

  // ------------------------------------------------ drift table + alpha
  const dt = card(`Drift test: ${cur.label} vs the month before`, cur.version === 0
      ? "Version 0 is the initial fit — stream the next month to see a drift test."
      : `Two-sample χ² test of homogeneity per stage, Holm-corrected across ${Object.keys(cur.drift).length} stages at α = ${cfg.drift_alpha}, plus a minimum shift of TV ≥ ${cfg.min_tv}.`,
    { badge: liveBadge(`v${cur.version}`) });
  if (cur.version > 0) {
    const rows = Object.values(cur.drift);
    dt.body.append(h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Stage", "Transitions (prev / this)", "Shift (TV)", "Holm p-value", "Verdict", "Biggest change", "α applied"]
        .map((c, i) => h("th", { class: i && i !== 4 && i !== 5 ? "n" : "" }, c)))),
      h("tbody", {}, rows.map((r) => {
        const a = cur.alpha[r.state];
        return h("tr", {},
          h("td", {}, h("span", { class: "row gap8" }, h("i", { class: "sw", style: { background: stateColor(r.state) } }), r.state)),
          h("td", { class: "n" }, `${num(r.n_ref, 0)} / ${num(r.n_new, 0)}`),
          h("td", { class: "n" }, num(r.tv, 3)),
          h("td", { class: "n" }, r.tested ? (r.p_holm < 0.0001 ? "< 0.0001" : num(r.p_holm, 4)) : "–"),
          h("td", {}, r.drift ? status("warn", "Drift") : r.significant ? h("span", { class: "status info" }, "Significant, too small") : r.tested ? status("ok", "Stable") : h("span", { class: "status info" }, "Too few")),
          h("td", {}, r.drift || r.significant ? `→ ${r.biggest_change_to} ${r.biggest_change >= 0 ? "+" : ""}${(r.biggest_change * 100).toFixed(1)} pts` : "–"),
          h("td", { class: "n" }, a == null ? "–" : h("span", { class: "alpha-cell" },
            h("span", { class: "alpha-bar" }, h("i", { style: { width: `${(a / cfg.max_alpha) * 100}%`, background: a > cfg.base_alpha + 1e-6 ? "var(--series-1)" : "var(--axis)" } })),
            num(a, 2))));
      })))));
    if (live.strategy !== "adaptive_ewma") dt.body.append(h("p", { class: "tiny muted" }, `Strategy is ${STRAT[live.strategy]}: drift is still tested and reported, but α is ${live.strategy === "ewma" ? "fixed" : "not used"}.`));
  }

  const how = card("The update rule", "Plain-language version of what happens when a month arrives.");
  how.body.append(h("ol", { class: "steps-list" },
    h("li", {}, h("strong", {}, "Count "), "every transition that month (e.g. how many cart sessions ended in an order)."),
    h("li", {}, h("strong", {}, "Test each stage "), "against the previous month: is the difference bigger than sampling noise? (two-sample χ², Holm-corrected so six tests don't produce false alarms)."),
    h("li", {}, h("strong", {}, "Ignore trivial shifts: "), `with hundreds of thousands of rows everything is 'significant', so a stage must also move by at least ${cfg.min_tv} in total variation.`),
    h("li", {}, h("strong", {}, "Blend: "), "new row = α × this month + (1 − α) × current belief. Stable stages use α = ", num(cfg.base_alpha, 2),
      "; drifted stages get α = 0.30 + 0.50 · tanh(TV / ", num(cfg.alpha_scale, 2), "), up to ", num(cfg.max_alpha, 2), "."),
    h("li", {}, h("strong", {}, "Publish "), "the result as the new live version. The what-if simulator, optimiser, next-best actions and AI advisor all read it immediately.")),
    h("div", { class: "formula" }, "P", h("sub", {}, "new"), "[i] = α", h("sub", {}, "i"), " · P", h("sub", {}, "month"), "[i] + (1 − α", h("sub", {}, "i"), ") · P", h("sub", {}, "live"), "[i]"));

  root.append(tl, h("div", { class: "grid-2 wide-left" }, track, how), dt);
  draw();

  async function setVersion(v) {
    try { await api("/api/stream", { method: "POST", body: { action: "set", version: v } }); }
    catch (e) { toast("Could not change version", e.message); }
  }
  async function setStrategy(s) {
    try {
      await api("/api/stream", { method: "POST", body: { action: "set", version: live.version, strategy: s } });
      toast("Strategy changed", `${STRAT[s]} — every version was re-computed with it.`);
    } catch (e) { toast("Could not change strategy", e.message); }
  }
}

function shortName(s) {
  return { "Product View": "View", "Add to Cart": "Cart", "Repeat Purchase": "Repeat", "Loyal Customer": "Loyal" }[s] || s;
}
