// Journey map — the transition matrix itself, plus the long-run (absorption) view.
import { api } from "../api.js";
import { h, liveBadge, card, stateColor } from "../ui.js";
import { pct, num } from "../format.js";
import { heatmap, hbars } from "../charts.js";

export async function render(root) {
  const m = await api("/api/matrix");
  const S = m.short, names = m.states;
  let mode = "live", start = "Visitor";

  const matCard = card("Transition matrix", "Row = where the customer is now, column = where they go next. Each row sums to 100%.",
    { badge: liveBadge() });
  const seg = h("div", { class: "seg", role: "tablist" });
  const modes = [["live", "Live model"], ["frozen", "Frozen snapshot"], ["diff", "Change since frozen"], ["batch", `${m.label} only`]];
  modes.forEach(([id, label]) => seg.append(h("button", { class: id === mode ? "on" : "", role: "tab", onclick: () => { mode = id; paint(); } }, label)));
  const heatEl = h("div", { class: "heat-wrap" });
  const note = h("p", { class: "tiny muted" });
  matCard.body.append(seg, heatEl, note);

  function paint() {
    [...seg.children].forEach((b, i) => b.classList.toggle("on", modes[i][0] === mode));
    const rows = S.slice(0, 6);
    let vals, fmt, md = "seq";
    const pick = (M) => M.slice(0, 6);
    if (mode === "diff") {
      vals = pick(m.live).map((r, i) => r.map((v, j) => v - m.frozen[i][j]));
      fmt = (v) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}`; md = "div";
      note.textContent = "Percentage-point change from the frozen first-month matrix to the live one. Blue = more likely now, red = less likely.";
    } else {
      vals = pick(mode === "live" ? m.live : mode === "frozen" ? m.frozen : m.batch);
      fmt = (v) => (v * 100).toFixed(v < 0.1 ? 1 : 0);
      note.textContent = mode === "batch"
        ? `Estimated from ${m.label} alone. The live model blends this with its history, more strongly for rows where drift was detected.`
        : "Cell values are percentages; the stronger the colour, the more likely the move. Hover or focus a cell for the exact value.";
    }
    heatEl.replaceChildren(heatmap({ rows, cols: S, values: vals, fmt, mode: md, title: "transition matrix",
      tipFmt: (v) => (mode === "diff" ? `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)} pts` : pct(v)) }));
  }
  paint();

  // absorption: probability of ever reaching each stage
  const absCard = card("Long-run outlook", "Before churning, how likely is a customer starting here to ever reach each stage? (absorption analysis, N = (I − Q)⁻¹)",
    { badge: h("span", { class: "row gap8" }, liveBadge(`Live v${m.version}`)) });
  const chips = h("div", { class: "chips" });
  const absEl = h("div");
  const facts = h("div", { class: "mini-stats" });
  absCard.body.append(chips, absEl, facts);
  const drawAbs = () => {
    chips.replaceChildren(...names.slice(0, 6).map((s) => h("button", { class: `chip ${s === start ? "on" : ""}`, onclick: () => { start = s; drawAbs(); } },
      h("i", { class: "sw", style: { background: stateColor(s) } }), s)));
    const a = m.absorption[start];
    const rows = names.slice(0, 6).filter((s) => s !== start).map((s) => ({ label: s, values: { live: a.prob_ever[s] } }));
    absEl.replaceChildren(hbars(rows, { series: [{ key: "live", name: "Probability of ever reaching", color: "var(--series-1)" }], fmt: pct, max: 1, labelWidth: 130 }));
    facts.replaceChildren(
      h("div", {}, h("span", { class: "tiny muted" }, "Expected steps before churn"), h("strong", {}, num(a.steps_to_exit, 2))),
      h("div", {}, h("span", { class: "tiny muted" }, "Expected orders"), h("strong", {}, num(a.expected_orders, 3))),
      h("div", {}, h("span", { class: "tiny muted" }, "Expected product views"), h("strong", {}, num(a.expected_visits["Product View"], 2))));
  };
  drawAbs();

  const readCard = card("How to read this", null);
  readCard.body.append(h("ul", { class: "read-list" },
    h("li", {}, h("strong", {}, "Visitor → View "), "is almost 100%: a session starts when someone lands on a product."),
    h("li", {}, h("strong", {}, "View → Visitor "), "means the session ended but the customer came back later (a new session)."),
    h("li", {}, h("strong", {}, "Purchase → Repeat Purchase "), "is a second order on a later visit. Browsing between orders is not re-entered into the funnel, so the chain keeps track of which order stage a customer is in."),
    h("li", {}, h("strong", {}, "Exit "), "is churn: no activity for 30 days. It is absorbing, so a stationary distribution would be 100% Exit; that's why the long-run view uses absorption probabilities instead."),
    m.unobserved.length ? h("li", {}, h("strong", {}, "Not observed this month: "), m.unobserved.join(", "), " — those rows are sent to Exit rather than guessed.") : null));

  root.append(matCard, h("div", { class: "grid-2" }, absCard, readCard));
}
