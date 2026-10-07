// chat.js — the advisor conversation, shared by the floating drawer and the Advisor page.
// History lives in state.chats[dataset], so both views show the same conversation.
import { api, state } from "./api.js";
import { h, icon, markdown } from "./ui.js";

const STARTERS = [
  "How is my business doing?",
  "Where are we losing the most customers?",
  "What if we improve checkout completion by 3 points?",
  "How should we spend a 5-point improvement budget?",
  "What should we do for customers who added to cart but didn't buy?",
  "What changed in customer behaviour over the last months?",
];

const TOOL_NAMES = {
  get_business_snapshot: "read live KPIs", get_stage_outlook: "stage outlook", simulate_change: "what-if on live matrix",
  optimise_budget: "optimiser on live matrix", get_drift_report: "drift report", predict_journey: "k-step prediction",
  get_model_quality: "validation",
};

const mounted = new Set();

function history() {
  const k = state.dataset;
  if (!state.chats[k]) state.chats[k] = [];
  return state.chats[k];
}

export function mountChat(container, { large = false } = {}) {
  const log = h("div", { class: "chat-log" });
  const suggest = h("div", { class: "chat-suggest" });
  const input = h("textarea", { rows: 1, placeholder: "Ask about your customers, a what-if, or where to invest…", "aria-label": "Message the advisor" });
  const send = h("button", { class: "btn btn-primary", type: "submit", "aria-label": "Send", html: '<svg viewBox="0 0 24 24"><path d="M4 12l16-8-6 16-2.5-6.5z"/></svg>' });
  const form = h("form", { class: "chat-form" }, input, send);
  container.replaceChildren(h("div", { class: `chat ${large ? "chat-large" : ""}` }, log, suggest, form));
  container.firstChild.style.height = "100%";

  const self = { log, suggest, input, render };
  mounted.add(self);

  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = `${Math.min(140, input.scrollHeight)}px`; });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
  form.addEventListener("submit", (e) => { e.preventDefault(); ask(input.value); input.value = ""; input.style.height = "auto"; });

  function render() {
    const msgs = history();
    log.replaceChildren();
    if (!msgs.length) {
      log.append(h("div", { class: "msg bot" }, markdown(
        `Hi — I'm your journey advisor for **${state.meta?.datasets.find((d) => d.name === state.dataset)?.label || "this store"}**.\n\n` +
        "Every number I give you is computed on the **live** adaptive matrix, so it reflects the latest month you've streamed in. " +
        "Ask me a what-if, where to invest, or how to move a group of customers forward.")));
    }
    for (const m of msgs) log.append(bubble(m));
    const last = [...msgs].reverse().find((m) => m.role === "assistant");
    suggest.replaceChildren(...(last?.suggestions || STARTERS.slice(0, large ? 6 : 3)).map((q) =>
      h("button", { class: "chip", type: "button", onclick: () => ask(q) }, q)));
    if (self.pending) log.append(h("div", { class: "msg bot typing", "aria-label": "Advisor is thinking" }, h("i"), h("i"), h("i")));
    log.scrollTop = log.scrollHeight;
  }

  render();
  return self;
}

function bubble(m) {
  if (m.role === "user") return h("div", { class: "msg user" }, m.content);
  const meta = h("div", { class: "msg-meta" });
  meta.append(h("span", { class: "tool-chip", title: m.model || "" }, icon("spark"), m.source === "claude" ? `Claude · ${m.model}` : "Offline analyst"));
  if (m.live_tag) meta.append(h("span", { class: "tool-chip" }, `live v${m.live_tag.version} · ${m.live_tag.label}`));
  (m.tools || []).forEach((t) => meta.append(h("span", { class: "tool-chip" }, icon("tool"), TOOL_NAMES[t.name] || t.name)));
  return h("div", { class: "msg bot" }, markdown(m.content), m.notice ? h("p", { class: "tiny muted" }, m.notice) : null, meta);
}

let busy = false;
export async function ask(text) {
  const q = String(text || "").trim();
  if (!q || busy) return;
  busy = true;
  const msgs = history();
  msgs.push({ role: "user", content: q });
  mounted.forEach((c) => { c.pending = true; c.render(); });
  try {
    const r = await api("/api/advisor", { method: "POST", body: { messages: msgs.map(({ role, content }) => ({ role, content })) } });
    msgs.push({ role: "assistant", content: r.reply, source: r.source, model: r.model, tools: r.tools, live_tag: r.live_tag,
      suggestions: r.suggestions, notice: r.notice });
  } catch (err) {
    msgs.push({ role: "assistant", content: `Sorry — the advisor could not answer (${err.message}).`, source: "error" });
  } finally {
    busy = false;
    mounted.forEach((c) => { c.pending = false; if (c.log.isConnected) c.render(); else mounted.delete(c); });
  }
}

export function rerenderChats() {
  mounted.forEach((c) => (c.log.isConnected ? c.render() : mounted.delete(c)));
}
