// Overview — the business at a glance, with the novelty made visible:
// the journey field is sampled from the live matrix, and every KPI shows how far
// a frozen snapshot would be from it.
import { api, state, lever } from "../api.js";
import { h, liveBadge, frozenBadge, tile, deltaSpan, card } from "../ui.js";
import { pct, money, signedPct } from "../format.js";
import { JourneyField } from "../hero.js";
import { countTo } from "../effects.js";
import { lineChart, hbars } from "../charts.js";

export async function render(root) {
  const [o, t] = await Promise.all([api("/api/overview"), api("/api/timeline")]);
  const k = o.kpis, f = o.frozen_kpis, live = o.live;

  // ---------------------------------------------------------------- hero
  const canvas = h("canvas", { class: "field", "aria-label": "Animated customer journey sampled from the live transition matrix" });
  const lens = h("div", { class: "lens", "aria-hidden": "true" });
  const heroNum = h("span", { class: "hero-num" }, "0");
  const simFirst = h("strong", {}, "–"), simCount = h("strong", {}, "0"), simLoyal = h("strong", {}, "–");
  const gap = (k.revenue_per_1k - f.revenue_per_1k) / f.revenue_per_1k;

  const hero = h("section", { class: "glass hero" },
    h("div", { class: "hero-copy" },
      h("div", { class: "row gap8 wrap" }, liveBadge(), h("span", { class: "eyebrow" }, o.dataset_label)),
      h("h2", { class: "hero-title" }, "A customer-journey model that ", h("span", { class: "grad" }, "re-learns itself"), " every month."),
      h("p", { class: "soft" }, "Each glowing dot is a simulated customer moving through your store. Its next step is drawn from the ",
        h("strong", {}, "live"), " transition matrix — the one that just absorbed ", live.label,
        ". The what-if simulator, the optimiser and the AI advisor all read this same live matrix, never a frozen snapshot."),
      h("div", { class: "hero-figure" },
        h("span", { class: "label" }, "Expected revenue per 1,000 visitors"),
        heroNum,
        h("span", { class: "delta" }, deltaSpan(gap, (x) => signedPct(x).replace("+", "")),
          h("span", { class: "muted" }, ` vs frozen ${live.frozen_label} model (${money(f.revenue_per_1k)})`))),
      h("div", { class: "row gap8 wrap" },
        h("a", { class: "btn btn-primary", href: "#/whatif", "data-magnetic": "" }, "Run a what-if"),
        h("a", { class: "btn", href: "#/adaptive" }, "See how it adapts"))),
    h("div", { class: "hero-field" }, canvas, lens,
      h("div", { class: "sim-stats glass" },
        h("div", {}, h("span", { class: "tiny muted" }, "Simulated visitors"), simCount),
        h("div", {}, h("span", { class: "tiny muted" }, "Finished journeys with an order"), simFirst),
        h("div", {}, h("span", { class: "tiny muted" }, "Maths says"), h("strong", {}, pct(k.p_first_order))),
        h("div", {}, h("span", { class: "tiny muted" }, "Became loyal"), simLoyal))));

  // ---------------------------------------------------------------- KPI tiles
  const vs = (a, b, fmt) => h("span", {}, deltaSpan(a - b, fmt), h("span", { class: "muted" }, " vs frozen"));
  const tiles = h("div", { class: "tiles" },
    tile("Chance a visitor ever orders", pct(k.p_first_order), vs(k.p_first_order, f.p_first_order, (x) => `${(x * 100).toFixed(2)} pts`)),
    tile("First-time buyers who order again", pct(o.matrix[3][4]), vs(o.matrix[3][4], t.frozen_kpis.purchase_to_repeat, (x) => `${(x * 100).toFixed(1)} pts`)),
    tile("Chance a visitor becomes loyal", pct(k.p_loyal), vs(k.p_loyal, f.p_loyal, (x) => `${(x * 100).toFixed(3)} pts`)),
    tile("Checkout completion (cart → order)", pct(o.matrix[2][3]), vs(o.matrix[2][3], t.frozen_kpis.cart_to_purchase, (x) => `${(x * 100).toFixed(1)} pts`)),
    tile("Average order value", money(o.aov), h("span", { class: "muted" }, `${money(o.facts.orders)} orders in the data`)));

  // ---------------------------------------------------------------- novelty: live vs frozen + pipeline
  const kp = [
    { label: "Revenue / 1k visitors", live: k.revenue_per_1k, frozen: f.revenue_per_1k, fmt: money },
    { label: "Visitor → first order", live: k.p_first_order, frozen: f.p_first_order, fmt: pct },
    { label: "Visitor → second order", live: k.p_repeat, frozen: f.p_repeat, fmt: pct },
    { label: "Visitor → loyal", live: k.p_loyal, frozen: f.p_loyal, fmt: pct },
  ];
  const cmp = card("Live model vs a frozen snapshot", "The same maths, fitted once in the first month and never updated, versus the adaptive model.",
    { badge: h("span", { class: "row gap8" }, liveBadge(`Live v${live.version}`), frozenBadge()) });
  const cmpBody = h("div", { class: "cmp-grid" });
  for (const r of kp) {
    const d = r.live ? (r.frozen - r.live) / r.live : 0;      // how wrong the frozen model is today
    cmpBody.append(h("div", { class: "cmp-row" },
      h("span", { class: "soft" }, r.label),
      h("span", { class: "cmp-live" }, h("i", { class: "sw", style: { background: "var(--series-1)" } }), r.fmt(r.live)),
      h("span", { class: "cmp-frozen" }, h("i", { class: "sw", style: { background: "var(--series-2)" } }), r.fmt(r.frozen)),
      h("span", { class: "cmp-gap" }, signedPct(d))));
  }
  cmp.body.append(h("div", { class: "cmp-head tiny muted" }, h("span", {}, "Metric"), h("span", {}, "Live"), h("span", {}, "Frozen"), h("span", {}, "Frozen is off by")), cmpBody,
    h("p", { class: "tiny muted" }, "A business planning on the frozen model would be working from these outdated numbers. The adaptive layer re-estimates the matrix each month and re-weights only the stages whose behaviour really changed."));

  const pipe = card("How the live matrix stays current", "One source of truth feeds every decision tool.", { cls: "pipe-card" });
  const lastDrift = [...t.versions].reverse().find((v) => v.drift_states.length);
  pipe.body.append(h("div", { class: "pipeline" },
    step("1", "New month arrives", `${money(t.versions[live.version].n_transitions)} transitions in ${live.label}`),
    step("2", "Drift test per stage", "Two-sample χ² + Holm correction, and at least a 0.02 shift"),
    step("3", "Adaptive weight α", lastDrift ? `${lastDrift.label}: ${lastDrift.drift_states.join(", ")} re-weighted` : "Stable rows update gently (α 0.30)"),
    step("4", `Live matrix v${live.version}`, "Row-stochastic, checked after every update", true),
    h("div", { class: "pipe-out" },
      h("a", { href: "#/whatif", class: "pipe-leaf" }, "What-if simulator"),
      h("a", { href: "#/optimize", class: "pipe-leaf" }, "Budget optimiser"),
      h("a", { href: "#/actions", class: "pipe-leaf" }, "Next best actions"),
      h("a", { href: "#/advisor", class: "pipe-leaf" }, "AI advisor"))));

  // ---------------------------------------------------------------- leak + lever + trend
  const top = lever(o.top_lever.id);
  const leak = card("Where customers leave", "The stage with the largest share of customers who leave instead of moving forward.", { badge: liveBadge(`Live v${live.version}`) });
  const leakRows = ["Product View", "Add to Cart", "Purchase", "Repeat Purchase", "Loyal Customer"].map((s) => {
    const i = state.meta.states.indexOf(s);
    return { label: s, values: { live: o.matrix[i][6] } };
  });
  leak.body.append(hbars(leakRows, { series: [{ key: "live", name: "Leaves next step", color: "var(--series-1)" }], fmt: pct, max: 1, labelWidth: 130 }),
    h("div", { class: "callout" },
      h("span", { class: "eyebrow" }, "Most valuable fix"),
      h("strong", {}, top.label),
      h("span", { class: "soft" }, `Every +1 point is worth about ${money(o.top_lever.revenue_per_1k_per_point)} more revenue per 1,000 visitors.`),
      h("a", { class: "btn", href: "#/actions" }, "See the playbook")));

  const trend = card("Revenue per 1,000 visitors, month by month", "What the live model believed after each month, against the frozen first-month model.");
  const chartEl = h("div");
  trend.body.append(chartEl);

  root.append(hero, tiles, h("div", { class: "grid-2" }, cmp, pipe), h("div", { class: "grid-2" }, leak, trend));

  lineChart(chartEl, {
    x: t.versions.map((v) => v.label),
    series: [
      { name: "Live model", color: "var(--series-1)", values: t.versions.map((v) => v.revenue_per_1k) },
      { name: "Frozen snapshot", color: "var(--series-2)", values: t.versions.map(() => t.frozen_revenue_per_1k) },
    ],
    yFmt: (v) => money(v, { compact: true }), height: 230,
  });

  // start the field after it is in the DOM
  const field = new JourneyField(canvas, {
    onStats: (s) => {
      simCount.textContent = money(s.spawned);
      simFirst.textContent = s.finished > 40 ? pct(s.finishedFirst / s.finished) : "–";
      simLoyal.textContent = s.spawned > 50 ? money(s.loyal) : "–";
    },
  });
  field.setMatrix(o.matrix);
  countTo(heroNum, k.revenue_per_1k, (v) => money(v));
  return () => field.destroy();
}

function step(n, title, text, hot = false) {
  return h("div", { class: `pipe-step ${hot ? "hot" : ""}` },
    h("span", { class: "pipe-n" }, n), h("div", {}, h("strong", {}, title), h("p", { class: "tiny muted" }, text)));
}
