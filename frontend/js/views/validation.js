// Model quality — held-out evaluation, reported honestly even when adaptive doesn't win by much.
import { api, state } from "../api.js";
import { h, card, tile } from "../ui.js";
import { pct, num, money } from "../format.js";
import { lineChart, hbars } from "../charts.js";

export async function render(root) {
  const v = await api("/api/validation");
  const H = v.holdout;
  const best = H.reduce((a, b) => (b.log_loss < a.log_loss ? b : a));
  const frozen = H[0];

  root.append(h("div", { class: "tiles" },
    tile(`Next-step accuracy on ${v.test_label}`, pct(best.accuracy), h("span", {}, "vs ", h("strong", {}, pct(best.baseline_accuracy)), ` always guessing “${v.baseline_state}”`)),
    tile("Accuracy excluding the first click", pct(best.accuracy_excl_visitor), h("span", {}, "vs ", h("strong", {}, pct(best.baseline_accuracy_excl_visitor)), " baseline")),
    tile("Log-loss (lower is better)", num(best.log_loss, 4), h("span", {}, "baseline ", h("strong", {}, num(best.baseline_log_loss, 4)))),
    tile("Held-out transitions", money(v.n_test), h("span", { class: "muted" }, `trained on ${v.train_labels.join(", ")}`))));

  const tbl = card("Every model on the same held-out month", `Trained on months before ${v.test_label}, tested on ${v.test_label}, which none of them saw.`);
  tbl.body.append(h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ["Model", "Accuracy", "Excl. first click", "Log-loss"].map((c, i) => h("th", { class: i ? "n" : "" }, c)))),
    h("tbody", {}, H.map((r) => h("tr", { class: r === best ? "best" : "" },
      h("td", {}, r.model, r === best ? h("span", { class: "tiny muted" }, "  · best calibrated") : null),
      h("td", { class: "n" }, pct(r.accuracy)), h("td", { class: "n" }, pct(r.accuracy_excl_visitor)), h("td", { class: "n" }, num(r.log_loss, 4))))),
  )), h("p", { class: "tiny muted" }, "Accuracy only checks the single most likely next step, which rarely changes between models. Log-loss scores the whole predicted distribution, so it shows whether the probabilities themselves are right — that is what the what-if simulator and optimiser use."));

  const roll = card("Month-ahead forecast error", "Each month is predicted using only what each model knew at the end of the previous month.");
  const rollEl = h("div");
  roll.body.append(rollEl, h("p", { class: "tiny muted" }, gapSentence(v, frozen, best)));

  const blocks = [h("div", { class: "grid-2" }, tbl, roll)];
  if (v.truth) {
    const tr = card("Recovering a known shift (synthetic data)",
      `The data was generated with checkout completion raised from 35% to 50% in February. Distance of each model's estimate from the true ${pct(v.truth.true_after)} (lower is better).`);
    const rows = Object.entries(v.truth.estimates).map(([k, x]) => ({ label: k.replace("Adaptive: ", "Adaptive · "), sub: `estimate ${pct(x)}`, values: { err: Math.abs(x - v.truth.true_after) } }));
    rows.push({ label: "Live model, all months", sub: `estimate ${pct(v.truth.live_final)}`, values: { err: Math.abs(v.truth.live_final - v.truth.true_after) } });
    tr.body.append(hbars(rows, { series: [{ key: "err", name: "Distance from the truth", color: "var(--series-1)" }], fmt: (x) => `${(x * 100).toFixed(1)} pts`, labelWidth: 220 }),
      h("p", { class: "tiny muted" }, `All but the last row were trained through ${v.train_labels[v.train_labels.length - 1]}. The frozen snapshot never sees the shift; the adaptive models move most of the way to the truth (per-stage α can overshoot on one noisy week, then settles).`));
    blocks.push(tr);
  }
  root.append(...blocks);

  lineChart(rollEl, {
    x: v.rolling.map((r) => r.month),
    series: [
      { name: "Adaptive (live)", color: "var(--series-1)", values: v.rolling.map((r) => r.adaptive) },
      { name: "Frozen snapshot", color: "var(--series-2)", values: v.rolling.map((r) => r.frozen) },
      { name: "Static, all history", color: "var(--series-3)", values: v.rolling.map((r) => r.static) },
    ],
    yFmt: (x) => num(x, 3), height: 230, label: "month-ahead log-loss",
  });
}

function gapSentence(v, frozen, best) {
  const d = frozen.log_loss - best.log_loss;
  if (state.dataset === "synthetic") {
    return `The held-out batch is small (${money(v.n_test)} transitions), so log-loss differences of ${num(d, 4)} are within noise here. `
      + "The clearer evidence on synthetic data is the recovery test below, where the true shift is known.";
  }
  return `On this real data the best model's log-loss is ${num(d, 4)} lower than the frozen snapshot's on ${v.test_label}. `
    + (d < 0.01 ? "That is a small gain: behaviour drifts slowly here, so the value of adapting shows up mostly in the what-if and optimiser forecasts (see the snapshot error on those pages) rather than in next-click accuracy."
      : "Adapting clearly pays off here.");
}
