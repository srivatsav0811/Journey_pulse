// ui.js — small DOM helpers. All data goes in through textContent; only the
// constant icon strings below are ever set as markup.
import { state } from "./api.js";

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;            // only used with ICONS constants
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export const ICONS = {
  overview: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/></svg>',
  journey: '<svg viewBox="0 0 24 24"><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M7 6h10M6 8l5 8M18 8l-5 8"/></svg>',
  adaptive: '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 21v-5h5"/></svg>',
  whatif: '<svg viewBox="0 0 24 24"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/></svg>',
  optimize: '<svg viewBox="0 0 24 24"><path d="M12 2l3 7h7l-5.5 4.5L18.5 21 12 16.5 5.5 21l2-7.5L2 9h7z"/></svg>',
  actions: '<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/><circle cx="5" cy="12" r="2"/></svg>',
  predict: '<svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/></svg>',
  validation: '<svg viewBox="0 0 24 24"><path d="M9 12l2 2 4-4"/><path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/></svg>',
  advisor: '<svg viewBox="0 0 24 24"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z"/><path d="M8.5 11h.01M12 11h.01M15.5 11h.01"/></svg>',
  method: '<svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/></svg>',
  warn: '<svg viewBox="0 0 24 24"><path d="M12 3l10 18H2z"/><path d="M12 10v4M12 17.5v.01"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg>',
  snow: '<svg viewBox="0 0 24 24"><path d="M12 2v20M4 7l16 10M20 7L4 17"/></svg>',
  tool: '<svg viewBox="0 0 24 24"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.8-.7-.7-2.8z"/></svg>',
  send: '<svg viewBox="0 0 24 24"><path d="M4 12l16-8-6 16-2.5-6.5z"/></svg>',
  spark: '<svg viewBox="0 0 24 24"><path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/></svg>',
};

export function icon(name, cls = "") {
  return h("span", { class: `ic ${cls}`, html: ICONS[name] || "", "aria-hidden": "true" });
}

export function liveBadge(text) {
  const v = state.live;
  return h("span", { class: "live-badge", title: "Computed on the live, self-updating matrix" },
    text || `Live matrix v${v ? v.version : "–"}${v ? " · " + v.label : ""}`);
}

export function frozenBadge(short = false) {
  const v = state.live;
  return h("span", { class: "frozen-badge", title: "What a model fitted once and never updated would say" },
    icon("snow"), short ? `Frozen · ${v ? v.frozen_label : ""}` : `Frozen snapshot · ${v ? v.frozen_label : ""}`);
}

export function status(kind, text) {
  return h("span", { class: `status ${kind}` }, icon(kind === "warn" ? "warn" : "check"), text);
}

export function card(title, sub, { cls = "", badge, right } = {}) {
  const head = h("div", { class: "card-head" },
    h("div", {}, h("h3", {}, title), sub ? h("p", {}, sub) : null),
    h("div", { class: "row gap8" }, right || null, badge || null));
  const body = h("div", { class: "card-body" });
  const el = h("section", { class: `glass card ${cls}` }, head, body);
  el.body = body;
  return el;
}

export function tile(label, value, delta, { cls = "" } = {}) {
  return h("div", { class: `glass tile ${cls}` },
    h("span", { class: "label" }, label),
    h("span", { class: "value" }, value),
    delta ? h("span", { class: "delta" }, delta) : null);
}

export function deltaSpan(x, fmt, { goodUp = true } = {}) {
  if (x == null || !Number.isFinite(x) || Math.abs(x) < 1e-12) return h("span", { class: "muted" }, "no change");
  const good = goodUp ? x > 0 : x < 0;
  return h("span", { class: good ? "up" : "down" }, `${x > 0 ? "▲" : "▼"} ${fmt(Math.abs(x))}`);
}

// ---------------------------------------------------------------- tooltip
const tip = () => document.getElementById("tooltip");

export function showTip(evt, title, rows) {
  const t = tip();
  t.replaceChildren(
    title ? h("div", { class: "tt-title" }, title) : "",
    ...rows.map((r) => h("div", { class: "tt-row" },
      r.color ? h("span", { class: "key", style: { background: r.color } }) : null,
      h("strong", {}, r.value), r.label ? h("span", { class: "muted" }, r.label) : null)));
  t.hidden = false;
  const pad = 14;
  const { innerWidth: W, innerHeight: H } = window;
  const r = t.getBoundingClientRect();
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + r.width > W - 8) x = evt.clientX - r.width - pad;
  if (y + r.height > H - 8) y = evt.clientY - r.height - pad;
  t.style.left = `${x}px`;
  t.style.top = `${y}px`;
}

export function hideTip() { tip().hidden = true; }

// ---------------------------------------------------------------- toast
export function toast(title, body, ms = 5200) {
  const el = h("div", { class: "glass toast" }, h("strong", {}, title), body ? h("span", { class: "soft" }, body) : null);
  document.getElementById("toasts").append(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 400); }, ms);
}

// ---------------------------------------------------------------- safe markdown (bold, italics, bullets)
export function markdown(text) {
  const root = h("div", { class: "md" });
  const blocks = String(text || "").split(/\n{2,}/);
  for (const block of blocks) {
    const lines = block.split("\n").filter((l) => l.trim() !== "");
    let list = null, para = null;
    for (const line of lines) {
      const bullet = line.match(/^\s*[-•*]\s+(.*)$/);
      if (bullet) {
        para = null;
        if (!list) { list = h("ul"); root.append(list); }
        list.append(inline(h("li"), bullet[1]));
      } else {
        list = null;
        if (!para) { para = h("p"); root.append(para); } else para.append(h("br"));
        inline(para, line);
      }
    }
  }
  return root;
}

function inline(el, text) {
  const parts = text.split(/(\*\*[^*]+\*\*|_[^_]+_)/g);
  for (const p of parts) {
    if (!p) continue;
    if (p.startsWith("**") && p.endsWith("**")) el.append(h("strong", {}, p.slice(2, -2)));
    else if (p.startsWith("_") && p.endsWith("_") && p.length > 2) el.append(h("em", {}, p.slice(1, -1)));
    else el.append(document.createTextNode(p));
  }
  return el;
}

export function stateColor(name) {
  const map = { "Visitor": "--state-visitor", "Product View": "--state-view", "Add to Cart": "--state-cart",
    "Purchase": "--state-purchase", "Repeat Purchase": "--state-repeat", "Loyal Customer": "--state-loyal", "Exit": "--state-exit" };
  return `var(${map[name] || "--ink-3"})`;
}

export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function setFill(input) {
  const min = +input.min, max = +input.max, v = +input.value;
  input.style.setProperty("--fill", `${((v - min) / (max - min)) * 100}%`);
}
