// AI advisor — full-page chat. Same conversation as the floating drawer.
import { state } from "../api.js";
import { h, liveBadge, card } from "../ui.js";
import { mountChat } from "../chat.js";

export async function render(root) {
  const mode = state.health?.advisor_mode === "claude";
  const chatCard = h("section", { class: "glass card chat-card" });
  const side = card("What the advisor can do", "It answers from the same engine as the rest of the dashboard.", { badge: liveBadge() });
  side.body.append(
    h("ul", { class: "read-list" },
      h("li", {}, h("strong", {}, "Diagnose: "), "where customers leave, what changed month to month, how good the model is."),
      h("li", {}, h("strong", {}, "Test: "), "“what if checkout completion goes up 3 points?” — runs the simulator on the live matrix and on the frozen snapshot."),
      h("li", {}, h("strong", {}, "Decide: "), "“how should we spend a 5-point budget?” — runs the optimiser."),
      h("li", {}, h("strong", {}, "Act: "), "“what should we do for customers who carted but didn't buy?” — ranks levers and suggests tactics.")),
    h("div", { class: `mode-box ${mode ? "on" : ""}` },
      h("strong", {}, mode ? `Connected to Claude (${state.health.model})` : "Running as the offline analyst"),
      h("p", { class: "tiny soft" }, mode
        ? "Claude calls tools that compute on the live matrix; it never invents a number it didn't get from a tool."
        : "No ANTHROPIC_API_KEY is set, so a built-in analyst answers common questions from the same computations. Set the key and restart the server to switch to Claude.")),
    h("p", { class: "tiny muted" }, "Rankings and numbers are computed by the model. Suggested tactics come from a rule-based playbook; treat them as starting points."));
  root.append(h("div", { class: "grid-2 advisor-grid" }, chatCard, side));
  mountChat(chatCard, { large: true });
}
