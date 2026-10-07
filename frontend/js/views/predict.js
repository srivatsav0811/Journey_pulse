// Prediction — next-state and k-step distributions (rows of P and P^k) on the live matrix.
import { api, state } from "../api.js";
import { h, liveBadge, frozenBadge, card, stateColor, setFill } from "../ui.js";
import { pct } from "../format.js";
import { hbars, stackedColumns } from "../charts.js";

const sel = { state: "Product View", steps: 3 };

export async function render(root) {
  const stages = state.meta.states.filter((s) => s !== "Exit");
  const chips = h("div", { class: "chips" });
  const steps = h("input", { type: "range", min: 1, max: 12, step: 1, value: sel.steps, "aria-label": "Steps ahead" });
  const stepsOut = h("strong", {});
  const ctrl = card("Customer starting point", "Pick the stage a customer is at now and how many steps ahead to look.", { badge: liveBadge() });
  ctrl.body.append(chips, h("div", { class: "lever" }, h("div", { class: "lever-head" }, h("strong", {}, "Steps ahead"), stepsOut), steps));
  const dist = card("Where they'll be", null, { badge: h("span", { class: "row gap8" }, liveBadge(), frozenBadge()) });
  const traj = card("How the journey unfolds, step by step", "Share of these customers in each stage after k steps (rows of Pᵏ). Churn keeps growing because Exit is absorbing.");
  const trajEl = h("div");
  traj.body.append(trajEl);
  const path = card("Most likely path", "Greedy highest-probability next step, skipping stays, until churn.");
  root.append(h("div", { class: "grid-2" }, ctrl, path), h("div", { class: "grid-2" }, dist, traj));

  steps.addEventListener("input", () => { sel.steps = +steps.value; paintSteps(); load(); });
  const paintSteps = () => { setFill(steps); stepsOut.textContent = `${sel.steps} step${sel.steps > 1 ? "s" : ""}`; };
  paintSteps();

  async function load() {
    chips.replaceChildren(...stages.map((s) => h("button", { class: `chip ${s === sel.state ? "on" : ""}`, onclick: () => { sel.state = s; load(); } },
      h("i", { class: "sw", style: { background: stateColor(s) } }), s)));
    const r = await api("/api/predict", { method: "POST", body: { state: sel.state, steps: sel.steps } });
    const rows = state.meta.states.map((s) => ({ label: s, values: { live: r.k_step[s], frozen: r.k_step_frozen[s] } }))
      .filter((x) => x.values.live > 0.0005 || x.values.frozen > 0.0005);
    dist.querySelector("h3").textContent = `Where a customer at ${sel.state} will be after ${sel.steps} step${sel.steps > 1 ? "s" : ""}`;
    dist.body.replaceChildren(hbars(rows, { series: [{ key: "live", name: "Live model", color: "var(--series-1)" }, { key: "frozen", name: "Frozen snapshot", color: "var(--series-2)" }], fmt: pct, max: 1, labelWidth: 130 }));
    path.body.replaceChildren(h("div", { class: "path" }, r.path.map((s, i) => [i ? h("span", { class: "path-arrow", "aria-hidden": "true" }, "→") : null,
      h("span", { class: "path-node", style: { "--c": stateColor(s) } }, s)])));
    stackedColumns(trajEl, {
      x: r.trajectory.map((_, k) => String(k)),
      series: state.meta.states.map((s) => ({ name: s, color: stateColor(s), values: r.trajectory.map((d) => d[s]) })),
      yFmt: (v) => pct(v, 0), height: 260, label: "state occupancy by step",
    });
  }
  await load();
}
