// What-if simulator — move a lever, see the effect on the LIVE matrix, and see how
// far the same scenario on the frozen snapshot would be from it.
import { api, state } from "../api.js";
import { h, liveBadge, frozenBadge, card, setFill, deltaSpan } from "../ui.js";
import { pct, money, signedPct, signedMoney } from "../format.js";
import { hbars } from "../charts.js";

const shifts = {};   // lever id -> points; kept across re-renders so a streamed month re-evaluates the same plan

const PRESETS = [
  ["Checkout +3 pts", { cart_to_purchase: 3 }],
  ["Retention +2 pts", { purchase_to_repeat: 2 }],
  ["Product pages +1 pt", { view_to_cart: 1 }],
  ["Everything +1 pt", { view_to_cart: 1, cart_to_purchase: 1, purchase_to_repeat: 1, repeat_to_loyal: 1 }],
];

export async function render(root) {
  const levers = state.meta.levers;
  levers.forEach((l) => { if (shifts[l.id] == null) shifts[l.id] = 0; });
  const first = await api("/api/simulate", { method: "POST", body: { shifts } });

  const controls = card("Pull the levers", "Each lever converts customers who would have left at that stage into customers who move forward.", { badge: liveBadge() });
  const sliderEls = {};
  const presetRow = h("div", { class: "chips" },
    ...PRESETS.map(([label, p]) => h("button", { class: "chip", onclick: () => { levers.forEach((l) => (shifts[l.id] = p[l.id] || 0)); syncSliders(); run(); } }, label)),
    h("button", { class: "chip", onclick: () => { levers.forEach((l) => (shifts[l.id] = 0)); syncSliders(); run(); } }, "Reset"));
  controls.body.append(presetRow);
  for (const l of levers) {
    const room = first.headroom[l.id];
    const input = h("input", { type: "range", min: -5, max: 10, step: 0.5, value: shifts[l.id], "aria-label": l.label });
    const out = h("strong", { class: "lever-val" });
    const now = h("span", { class: "tiny muted" });
    input.addEventListener("input", () => { shifts[l.id] = +input.value; paintSlider(); schedule(); });
    const paintSlider = () => {
      setFill(input);
      const target = Math.max(0, Math.min(room.current + room.max_up, room.current + shifts[l.id] / 100));
      out.textContent = `${shifts[l.id] >= 0 ? "+" : ""}${(+shifts[l.id]).toFixed(1)} pts`;
      now.textContent = `now ${pct(room.current)} → ${pct(target)} · max +${(room.max_up * 100).toFixed(1)} pts available`;
    };
    sliderEls[l.id] = { input, paint: paintSlider };
    controls.body.append(h("div", { class: "lever" },
      h("div", { class: "lever-head" }, h("div", {}, h("strong", {}, l.label), h("span", { class: "tiny muted" }, ` · ${l.business}`)), out),
      input, now));
    paintSlider();
  }
  function syncSliders() { levers.forEach((l) => { sliderEls[l.id].input.value = shifts[l.id]; sliderEls[l.id].paint(); }); }

  // results
  const results = card("Projected outcome", "Per 1,000 new visitors, over their whole journey until they churn.", { badge: liveBadge() });
  const tilesEl = h("div", { class: "tiles tiles-2" });
  const errEl = h("div", { class: "snapshot" });
  const barsEl = h("div");
  results.body.append(tilesEl, errEl, barsEl);

  function paint(r) {
    const L = r.live, F = r.frozen;
    const t = (label, key, fmt, dfmt) => h("div", { class: "glass tile" },
      h("span", { class: "label" }, label),
      h("span", { class: "value" }, fmt(L.scenario[key])),
      h("span", { class: "delta" }, deltaSpan(L.uplift[key], dfmt), h("span", { class: "muted" }, ` from ${fmt(L.baseline[key])}`)));
    tilesEl.replaceChildren(
      t("Revenue per 1,000 visitors", "revenue_per_1k", money, (x) => money(x)),
      t("Visitors who ever order", "p_first_order", pct, (x) => `${(x * 100).toFixed(2)} pts`),
      t("Visitors who order twice", "p_repeat", pct, (x) => `${(x * 100).toFixed(3)} pts`),
      t("Visitors who become loyal", "p_loyal", pct, (x) => `${(x * 100).toFixed(3)} pts`));
    const err = r.snapshot_error.revenue_per_1k;
    const rel = L.scenario.revenue_per_1k ? err / L.scenario.revenue_per_1k : 0;
    const any = Object.values(r.applied).some((v) => Math.abs(v) > 1e-9);
    errEl.replaceChildren(
      h("div", { class: "snap-col" }, liveBadge(`Live v${state.live.version}`), h("strong", { class: "snap-num" }, money(L.scenario.revenue_per_1k)),
        h("span", { class: "tiny muted" }, `uplift ${signedMoney(L.uplift.revenue_per_1k)} (${signedPct(L.baseline.revenue_per_1k ? L.uplift.revenue_per_1k / L.baseline.revenue_per_1k : 0)})`)),
      h("div", { class: "snap-col" }, frozenBadge(true), h("strong", { class: "snap-num" }, money(F.scenario.revenue_per_1k)),
        h("span", { class: "tiny muted" }, `uplift ${signedMoney(F.uplift.revenue_per_1k)} (${signedPct(F.baseline.revenue_per_1k ? F.uplift.revenue_per_1k / F.baseline.revenue_per_1k : 0)})`)),
      h("div", { class: "snap-col snap-err" }, h("span", { class: "eyebrow" }, "Snapshot error"),
        h("strong", { class: "snap-num" }, signedPct(rel)),
        h("span", { class: "tiny muted" }, state.live.version === 0
          ? "Live is still version 0, so both models agree. Stream a month to see them diverge."
          : Math.abs(rel) < 0.001 ? "The frozen model gives about the same answer here."
          : `The frozen model would ${rel < 0 ? "under" : "over"}-estimate this outcome by ${money(Math.abs(err))} per 1,000 visitors${any ? "" : ", even with no change applied"}.`)));
    barsEl.replaceChildren(h("p", { class: "tiny muted" }, "Chance a new visitor ever reaches each stage"),
      hbars(["p_first_order", "p_repeat", "p_loyal"].map((k) => ({
        label: { p_first_order: "First order", p_repeat: "Second order", p_loyal: "Loyal" }[k],
        values: { base: L.baseline[k], scen: L.scenario[k], froz: F.scenario[k] } })),
      { series: [{ key: "scen", name: "Scenario (live)", color: "var(--series-1)" }, { key: "froz", name: "Scenario (frozen)", color: "var(--series-2)" },
        { key: "base", name: "Today (live)", color: "var(--series-3)" }], fmt: pct, labelWidth: 110 }));
  }
  paint(first);

  let timer = null, seq = 0;
  function schedule() { clearTimeout(timer); timer = setTimeout(run, 110); }
  async function run() {
    const my = ++seq;
    results.classList.add("refreshing");
    try {
      const r = await api("/api/simulate", { method: "POST", body: { shifts } });
      if (my === seq) paint(r);
    } finally { if (my === seq) results.classList.remove("refreshing"); }
  }

  root.append(h("div", { class: "grid-2 whatif" }, controls, results));
  return () => clearTimeout(timer);
}
