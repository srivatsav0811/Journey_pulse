// Next best actions — for customers at a stage: where they are heading, which lever
// moves them forward most (computed on the live matrix), and what to do about it
// (a rule-based playbook, labelled as such).
import { api, state, lever } from "../api.js";
import { h, liveBadge, card, stateColor } from "../ui.js";
import { pct, money } from "../format.js";
import { hbars } from "../charts.js";
import { ask } from "../chat.js";

let stage = "Add to Cart";

export async function render(root) {
  const stages = state.meta.states.filter((s) => s !== "Exit");
  const chips = h("div", { class: "chips stage-chips" });
  const body = h("div", { class: "stack" });
  root.append(h("section", { class: "glass card" },
    h("div", { class: "card-head" }, h("div", {}, h("h3", {}, "Pick a group of customers"),
      h("p", {}, "Where they are in the journey right now. Everything below is recomputed for customers starting at that stage.")), liveBadge()),
    chips), body);

  async function load() {
    chips.replaceChildren(...stages.map((s) => h("button", { class: `chip ${s === stage ? "on" : ""}`, onclick: () => { stage = s; load(); } },
      h("i", { class: "sw", style: { background: stateColor(s) } }), s)));
    body.classList.add("refreshing");
    const o = await api("/api/outlook", { params: { stage } });
    body.classList.remove("refreshing");
    paint(o);
  }

  function paint(o) {
    const L = o.live, m = L.metrics;
    const nextRows = Object.entries(L.next).filter(([, p]) => p >= 0.0005).sort((a, b) => b[1] - a[1])
      .map(([s, p]) => ({ label: s === stage ? `${s} (stays)` : s, values: { p } }));
    const outlook = card(`Customers at ${stage}`, "Their next step, and where they end up over their whole journey.", { badge: liveBadge() });
    outlook.body.append(
      h("div", { class: "mini-stats" },
        h("div", {}, h("span", { class: "tiny muted" }, "Leave at the next step"), h("strong", {}, pct(L.p_exit_next))),
        h("div", {}, h("span", { class: "tiny muted" }, stage === "Loyal Customer" ? "Order again next" : "Move deeper next step"), h("strong", {}, pct(L.p_forward_next))),
        h("div", {}, h("span", { class: "tiny muted" }, stage === "Purchase" || stage === "Repeat Purchase" || stage === "Loyal Customer" ? "Ever become loyal" : "Ever place an order"),
          h("strong", {}, pct(["Purchase", "Repeat Purchase", "Loyal Customer"].includes(stage) ? m.p_loyal : m.p_first_order))),
        h("div", {}, h("span", { class: "tiny muted" }, "Worth per 1,000 of them"), h("strong", {}, money(m.revenue_per_1k)))),
      h("p", { class: "tiny muted" }, "Next step"),
      hbars(nextRows, { series: [{ key: "p", name: "Probability", color: "var(--series-1)" }], fmt: pct, max: 1, labelWidth: 150 }));

    const ranked = card("What moves them forward", `Levers ranked by extra revenue per 1,000 of these customers for each +1 point, on live v${o.live_tag.version}. Tactics are a suggested playbook, not model output.`);
    if (!L.ranked_levers.length) {
      ranked.body.append(h("p", { class: "muted" }, "No lever sits ahead of this stage — these customers are already at the end of the journey. Retention offers keep them ordering."));
    }
    L.ranked_levers.forEach((r, i) => {
      ranked.body.append(h("div", { class: `glass lever-card ${i === 0 ? "best" : ""}` },
        h("div", { class: "lever-card-head" },
          h("span", { class: "rank" }, `#${i + 1}`),
          h("div", {}, h("strong", {}, r.label), h("p", { class: "tiny muted" }, `${r.business} · now ${pct(r.current)} · up to +${(r.headroom * 100).toFixed(1)} pts possible`)),
          h("div", { class: "gain" }, h("strong", {}, `+${money(r.revenue_gain_per_1k_per_point)}`), h("span", { class: "tiny muted" }, "per +1 pt"))),
        i === 0 ? h("div", { class: "tactics" }, r.actions.map((a) =>
          h("div", { class: "tactic" }, h("span", { class: "eyebrow" }, a.channel), h("strong", {}, a.title), h("p", { class: "tiny soft" }, a.detail)))) :
          h("p", { class: "tiny muted" }, r.actions.map((a) => a.title).join(" · "))));
    });
    if (o.frozen_best && L.best && o.frozen_best !== L.best.lever) {
      ranked.body.append(h("p", { class: "callout-inline" }, `A frozen snapshot would have ranked “${lever(o.frozen_best).label}” first — the live model has moved on.`));
    }
    ranked.body.append(h("button", { class: "btn", onclick: () => { document.getElementById("advisor-fab").click(); ask(`What should we do for customers at the ${stage} stage?`); } },
      "Ask the advisor about this group"));
    body.replaceChildren(h("div", { class: "grid-2" }, outlook, ranked));
  }

  await load();
}
