// Budget optimiser — constrained non-linear optimisation (SLSQP, grid-verified) on the live matrix.
import { api, state, lever } from "../api.js";
import { h, liveBadge, frozenBadge, card, setFill, status } from "../ui.js";
import { pct, money, signedPct, num } from "../format.js";
import { hbars } from "../charts.js";

const opts = { budget: null, per: null, objective: "revenue" };

export async function render(root) {
  const meta = state.meta;
  opts.budget ??= meta.defaults.budget_points;
  opts.per ??= meta.defaults.per_lever_points;

  const controls = card("Your improvement budget", "How many percentage points of improvement can the business afford in total, and how much on any one lever?", { badge: liveBadge() });
  const mkRange = (label, key, min, max, step) => {
    const input = h("input", { type: "range", min, max, step, value: opts[key], "aria-label": label });
    const out = h("strong", {});
    const paint = () => { setFill(input); out.textContent = `${(+opts[key]).toFixed(1)} pts`; };
    input.addEventListener("input", () => { opts[key] = +input.value; paint(); schedule(); });
    paint();
    return h("div", { class: "lever" }, h("div", { class: "lever-head" }, h("strong", {}, label), out), input);
  };
  const objSeg = h("div", { class: "seg" }, ...Object.entries(meta.objectives).map(([id, label]) =>
    h("button", { class: id === opts.objective ? "on" : "", onclick: (e) => { opts.objective = id; [...objSeg.children].forEach((b) => b.classList.toggle("on", b === e.currentTarget)); schedule(0); } }, label)));
  controls.body.append(mkRange("Total budget", "budget", 1, 15, 0.5), mkRange("Max on one lever", "per", 0.5, 10, 0.5),
    h("div", { class: "field" }, h("span", {}, "Maximise"), objSeg),
    h("p", { class: "tiny muted" }, "Solved with SLSQP from several starting points, then checked against a brute-force grid. Optimisation on Markov customer models is established prior art (Pfeifer & Carraway, 2004); what's different here is that it always runs on the live, self-updating matrix."));

  const out = card("Recommended allocation", null, { badge: h("span", { class: "row gap8" }, liveBadge(), frozenBadge()) });
  root.append(h("div", { class: "grid-2 opt" }, controls, out));

  let timer = null, seq = 0;
  function schedule(ms = 160) { clearTimeout(timer); timer = setTimeout(run, ms); }
  async function run() {
    const my = ++seq;
    out.classList.add("refreshing");
    try {
      const r = await api("/api/optimize", { method: "POST", body: { budget_points: opts.budget, per_lever_points: opts.per, objective: opts.objective } });
      if (my === seq) paint(r);
    } catch (e) { out.body.replaceChildren(h("p", { class: "muted" }, e.message)); }
    finally { if (my === seq) out.classList.remove("refreshing"); }
  }

  function paint(r) {
    const L = r.live, F = r.frozen;
    const isRev = r.live.objective === "revenue";
    const fmtObj = (v) => (isRev ? money(v * r.aov * 1000) : pct(v));
    const unit = isRev ? "revenue per 1,000 visitors" : L.objective_label.toLowerCase();
    const rows = meta.levers.map((l) => ({ label: l.label, sub: l.business, values: { live: L.allocation[l.id] * 100, frozen: F.allocation[l.id] * 100 } }));
    const topL = lever(L.top_lever), same = L.top_lever === F.top_lever &&
      meta.levers.every((l) => Math.abs(L.allocation[l.id] - F.allocation[l.id]) < 0.0005);
    const staleRel = L.optimised ? r.cost_of_stale_plan / L.optimised : 0;
    const forecastErr = L.optimised ? (F.optimised - L.optimised) / L.optimised : 0;
    out.body.replaceChildren(
      h("div", { class: "tiles tiles-3" },
        h("div", { class: "glass tile" }, h("span", { class: "label" }, `Today (${unit})`), h("span", { class: "value" }, fmtObj(L.baseline))),
        h("div", { class: "glass tile" }, h("span", { class: "label" }, "With this plan"), h("span", { class: "value" }, fmtObj(L.optimised)),
          h("span", { class: "delta" }, h("span", { class: "up" }, `▲ ${signedPct(L.relative_uplift).replace("+", "")}`))),
        h("div", { class: "glass tile" }, h("span", { class: "label" }, "Put most budget into"), h("span", { class: "value value-sm" }, topL.label),
          h("span", { class: "delta muted" }, topL.business))),
      hbars(rows, { series: [{ key: "live", name: "Plan from the live model", color: "var(--series-1)" }, { key: "frozen", name: "Plan from the frozen snapshot", color: "var(--series-2)" }],
        fmt: (v) => `${num(v, 1)} pts`, max: Math.max(opts.per, 0.5), labelWidth: 170 }),
      h("div", { class: "verify" },
        L.grid.agrees ? status("ok", `Matches a brute-force grid search (${money(L.grid.points)} plans, step ${num(L.grid.step * 100, 0)} pt)`) : status("warn", "Grid search found a better plan — check constraints"),
        h("span", { class: "tiny muted" }, `Solver converged: ${L.solver_success ? "yes" : "no"}`)),
      h("div", { class: "snapshot" },
        h("div", { class: "snap-col" }, frozenBadge(true), h("strong", {}, same ? "Same plan" : "Different plan"),
          h("span", { class: "tiny muted" }, same ? "In this case the frozen model would pick the same split…" : "The frozen snapshot would spend the budget differently.")),
        h("div", { class: "snap-col" }, h("span", { class: "eyebrow" }, "Frozen model's forecast of its plan"), h("strong", {}, fmtObj(F.optimised)),
          h("span", { class: "tiny muted" }, `${signedPct(forecastErr)} vs the live model's forecast — a planning error in the budget case`)),
        h("div", { class: "snap-col snap-err" }, h("span", { class: "eyebrow" }, "Cost of the stale plan"), h("strong", {}, Math.abs(staleRel) < 0.0005 ? "0.0%" : signedPct(-staleRel)),
          h("span", { class: "tiny muted" }, same ? "No loss today: the split is the same, only its forecast is off." : `The frozen plan, run on today's behaviour, delivers ${fmtObj(r.frozen_plan_on_live)} instead of ${fmtObj(L.optimised)}.`))));
  }

  run();
  return () => clearTimeout(timer);
}
