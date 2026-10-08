// app.js — shell: routing, navigation, dataset switch, streaming months into the
// live model, theme, and the advisor drawer.
import { api, state, onLiveChange } from "./api.js";
import { h, ICONS, toast, hideTip } from "./ui.js";
import { mountChat, rerenderChats } from "./chat.js";

const VIEWS = [
  { id: "overview", title: "Overview", sub: "The customer journey at a glance", icon: "overview", group: "Insight" },
  { id: "journey", title: "Journey map", sub: "Transition probabilities between every stage", icon: "journey", group: "Insight" },
  { id: "adaptive", title: "Adaptive engine", sub: "Drift tests and per-stage update weights, month by month", icon: "adaptive", group: "Insight" },
  { id: "whatif", title: "What-if simulator", sub: "Test a change on the live model, next to the frozen snapshot", icon: "whatif", group: "Decide" },
  { id: "optimize", title: "Budget optimiser", sub: "Where a limited improvement budget earns the most", icon: "optimize", group: "Decide" },
  { id: "actions", title: "Next best actions", sub: "What moves customers at each stage forward", icon: "actions", group: "Decide" },
  { id: "predict", title: "Prediction", sub: "Where a customer is likely to be in k steps", icon: "predict", group: "Decide" },
  { id: "advisor", title: "AI advisor", sub: "Ask business questions in plain words", icon: "advisor", group: "Decide" },
  { id: "validation", title: "Model quality", sub: "Held-out accuracy, calibration, and adaptive vs static", icon: "validation", group: "Trust" },
  { id: "method", title: "Data & method", sub: "Dataset, state mapping, formulas and limitations", icon: "method", group: "Trust" },
];

const loaders = {
  overview: () => import("./views/overview.js"), journey: () => import("./views/journey.js"),
  adaptive: () => import("./views/adaptive.js"), whatif: () => import("./views/whatif.js"),
  optimize: () => import("./views/optimize.js"), actions: () => import("./views/actions.js"),
  predict: () => import("./views/predict.js"), advisor: () => import("./views/advisor.js"),
  validation: () => import("./views/validation.js"), method: () => import("./views/method.js"),
};

let current = null, cleanup = null, renderToken = 0;
const viewEl = document.getElementById("view");

// ---------------------------------------------------------------- theme
function initTheme() {
  let t = "light";
  try { t = localStorage.getItem("jp-theme") || t; } catch { /* storage blocked */ }
  document.documentElement.dataset.theme = t;
  document.getElementById("theme-btn").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("jp-theme", next); } catch { /* ignore */ }
    if (current) renderView(current, { keepScroll: true });
  });
}

// ---------------------------------------------------------------- nav
function buildNav() {
  const nav = document.getElementById("nav");
  let group = null;
  for (const v of VIEWS) {
    if (v.group !== group) { group = v.group; nav.append(h("div", { class: "nav-group" }, group)); }
    nav.append(h("a", { href: `#/${v.id}`, "data-view": v.id },
      h("span", { html: ICONS[v.icon], "aria-hidden": "true", style: { display: "contents" } }), v.title,
      v.tag ? h("span", { class: "tag" }, v.tag) : null));
  }
  document.getElementById("menu-btn").addEventListener("click", () => document.querySelector(".sidebar").classList.toggle("open"));
  nav.addEventListener("click", () => document.querySelector(".sidebar").classList.remove("open"));
}

function markActive(id) {
  document.querySelectorAll(".nav a").forEach((x) => x.classList.toggle("active", x.dataset.view === id));
}

// ---------------------------------------------------------------- routing
function route() {
  const id = (location.hash.replace("#/", "") || "overview").split("?")[0];
  const v = VIEWS.find((x) => x.id === id) ? id : "overview";
  renderView(v);
}

async function renderView(id, { keepScroll = false } = {}) {
  const token = ++renderToken;
  const v = VIEWS.find((x) => x.id === id);
  document.getElementById("page-title").textContent = v.title;
  document.getElementById("page-sub").textContent = v.sub;
  document.title = `${v.title} · JourneyPulse`;
  markActive(id);
  const y = window.scrollY;
  const changed = current !== id;
  current = id;
  hideTip();
  if (cleanup) { try { cleanup(); } catch { /* ignore */ } cleanup = null; }
  viewEl.classList.add("refreshing");
  try {
    const mod = await loaders[id]();
    if (token !== renderToken) return;
    const fresh = h("div", { class: "view-inner" });
    const maybe = await mod.render(fresh);
    if (token !== renderToken) { if (typeof maybe === "function") maybe(); return; }
    cleanup = typeof maybe === "function" ? maybe : null;
    viewEl.replaceChildren(fresh);
    if (changed) viewEl.focus({ preventScroll: true });
    window.scrollTo(0, keepScroll || !changed ? y : 0);
  } catch (err) {
    console.error(err);
    viewEl.replaceChildren(h("section", { class: "glass card" }, h("h3", {}, "Something went wrong"),
      h("p", { class: "muted" }, err.message), h("p", { class: "tiny muted" }, "Is the Python server running? Start it with: python -m backend.server")));
  } finally {
    viewEl.classList.remove("refreshing");
  }
}

// ---------------------------------------------------------------- live matrix pill + streaming
function paintLive(live) {
  document.getElementById("live-version").textContent = `v${live.version}`;
  document.getElementById("live-label").textContent = live.label;
  const pill = document.getElementById("live-pill");
  document.querySelectorAll("[data-stream]").forEach((b) => {
    const a = b.dataset.stream;
    b.disabled = (a === "next" || a === "latest") ? live.version >= live.latest : live.version <= 0;
  });
  const nt = document.querySelector(".next-text");
  if (nt) nt.textContent = live.version >= live.latest ? "Up to date" : "Next month";
}

function initStream() {
  document.querySelectorAll("[data-stream]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try {
      const r = await api("/api/stream", { method: "POST", body: { action: b.dataset.stream } });
      const drift = r.summary.drift_states;
      if (b.dataset.stream === "next") {
        toast(`Streamed ${r.live.label} into the model → live v${r.live.version}`,
          drift.length ? `Drift detected in ${drift.join(", ")} — those rows were re-weighted more strongly.` : "No meaningful drift: every row updated gently.");
      }
    } catch (err) { toast("Could not update the model", err.message); }
    finally { paintLive(state.live); }
  }));
  onLiveChange((live, prev) => {
    paintLive(live);
    if (prev) { renderView(current, { keepScroll: true }); rerenderChats(); }
  });
}

// ---------------------------------------------------------------- datasets
async function initDatasets() {
  state.meta = await api("/api/datasets");
  const sel = document.getElementById("dataset-select");
  let saved = null;
  try { saved = localStorage.getItem("jp-dataset"); } catch { /* ignore */ }
  const avail = state.meta.datasets.filter((d) => d.available);
  state.dataset = avail.some((d) => d.name === saved) ? saved : state.meta.default;
  sel.replaceChildren(...state.meta.datasets.map((d) => h("option", { value: d.name, disabled: !d.available || null,
    selected: d.name === state.dataset || null }, d.available ? d.label : `${d.label} (not downloaded)`)));
  sel.addEventListener("change", async () => {
    state.dataset = sel.value;
    try { localStorage.setItem("jp-dataset", sel.value); } catch { /* ignore */ }
    viewEl.classList.add("refreshing");
    toast("Switching dataset", "The first load of a real dataset builds a cache (about 15 seconds).", 3500);
    await api("/api/timeline");        // the live-change listener re-renders the view and chats
  });
  await api("/api/timeline");          // sets state.live before the first render
}

async function initAdvisorMode() {
  try {
    state.health = await api("/api/health");
    const el = document.getElementById("advisor-mode");
    el.classList.add(state.health.advisor_mode);
    const name = { claude: "Claude", groq: "Groq" }[state.health.advisor_mode];
    el.lastChild.textContent = name ? `Advisor: ${name} (${state.health.model})` : "Advisor: offline analyst";
    document.getElementById("drawer-mode").textContent = name
      ? `${name}, with tools that compute on the live matrix`
      : window.JP_STATIC ? "Offline analyst · the browser demo has no API key" : "Offline analyst · set GROQ_API_KEY or ANTHROPIC_API_KEY";
  } catch { /* shown by the view error instead */ }
}

function initDrawer() {
  const fab = document.getElementById("advisor-fab"), drawer = document.getElementById("drawer");
  let mounted = false;
  const open = (v) => {
    drawer.hidden = !v; fab.setAttribute("aria-expanded", String(v));
    if (v && !mounted) { mountChat(document.getElementById("drawer-chat")); mounted = true; }
    if (v) drawer.querySelector("textarea")?.focus();
  };
  fab.addEventListener("click", () => open(true));
  document.getElementById("drawer-close").addEventListener("click", () => open(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !drawer.hidden) open(false); });
  window.addEventListener("hashchange", () => { if (location.hash === "#/advisor") open(false); });
}

async function main() {
  initTheme();
  buildNav();
  initStream();
  initDrawer();
  try {
    await initDatasets();
    await initAdvisorMode();
  } catch (err) {
    viewEl.replaceChildren(h("section", { class: "glass card" }, h("h3", {}, window.JP_STATIC ? "The in-browser engine could not start" : "Can't reach the JourneyPulse server"),
      h("p", { class: "muted" }, window.JP_STATIC
        ? `${err.message}. The browser demo needs a modern browser and internet access to download the Python runtime; try reloading.`
        : `${err.message}. Start it from the project folder with:  python -m backend.server`)));
    return;
  }
  window.addEventListener("hashchange", route);
  window.addEventListener("scroll", hideTip, { passive: true });
  route();
}

main();
