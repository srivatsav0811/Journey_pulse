// Your data — upload a business's own customer activity (CSV), check how it was read, and build the same
// live model every other page uses. Guided and in plain language; no statistics vocabulary needed.
import { api, state, uploadCsv } from "../api.js";
import { h, card, toast } from "../ui.js";
import { int, date, money } from "../format.js";

const ROLE_LABEL = {
  view: "Looked at a product", cart: "Added to cart", remove_from_cart: "Removed from cart",
  purchase: "Bought something", ignore: "Ignore this action",
};
const FIELDS = [
  { key: "user", label: "Customer", hint: "Who did it: an id, email or account number", required: true },
  { key: "time", label: "Date and time", hint: "When it happened", required: true },
  { key: "event", label: "Action", hint: "What they did: viewed, added to cart, bought…", required: true },
  { key: "session", label: "Visit / session (optional)", hint: "If you have one. If not, we group activity into visits ourselves" },
  { key: "price", label: "Order value (optional)", hint: "The amount spent, used for revenue figures" },
];
const PRIVACY_STATIC = "Your file is read inside this browser tab and is never uploaded anywhere. Close the tab and it is gone.";
const PRIVACY_LOCAL = "Your file goes only to the JourneyPulse program running on your own computer. It is processed in memory and not saved.";

// kept at module level so the form survives the app re-rendering this page
const S = { file: null, ins: null, map: {}, roles: {}, dayfirst: false, churn: 30, loyal: 3, aov: "", busy: false, error: "", done: null };

export async function render(root) {
  const host = h("div", { class: "view-inner" });
  root.append(host);
  const draw = () => host.replaceChildren(...build(draw));
  draw();
}

function build(draw) {
  const parts = [];
  const loaded = state.meta.datasets.find((d) => d.name === "custom");

  // ---------------------------------------------------------------- intro
  const intro = card("Use your own data", "Upload a record of what your customers did and get the same analysis, live model and recommendations.");
  intro.body.append(
    h("p", { class: "callout-inline" }, window.JP_STATIC ? PRIVACY_STATIC : PRIVACY_LOCAL),
    h("div", { class: "grid-2" },
      h("div", {},
        h("h3", {}, "What your file needs"),
        h("ul", { class: "read-list" },
          h("li", {}, h("strong", {}, "One row per customer action"), " in a CSV file (export from Excel, Shopify, a CRM or your database)."),
          h("li", {}, "Three columns: ", h("strong", {}, "who"), " (customer id), ", h("strong", {}, "when"), " (date and time) and ", h("strong", {}, "what"), " they did (viewed a product, added to cart, bought)."),
          h("li", {}, "Optional: a session id and the order value."),
          h("li", {}, h("strong", {}, "At least about three months"), " of history (about seven weeks is the bare minimum with the default 30-day window) and a few thousand rows or more. The model compares periods, so it needs time."),
          h("li", {}, window.JP_STATIC ? "Up to about 400,000 rows in this web version; the downloadable version handles millions." : "Up to 3 million rows."))),
      h("div", {},
        h("h3", {}, "What it looks like"),
        miniTable(["When", "Customer", "Action", "Order value"], [
          ["2026-01-05 13:26", "C1236", "Viewed product", ""], ["2026-01-06 05:32", "C1113", "Added to basket", ""],
          ["2026-01-06 05:37", "C1113", "Placed order", "10.51"]]),
        h("div", { class: "row gap8 wrap", style: { marginTop: "12px" } },
          h("button", { class: "btn btn-primary", type: "button", onclick: () => useSample(draw) }, "Try the sample file"),
          h("a", { class: "btn", href: "sample/business_sample.csv", download: "business_sample.csv" }, "Download the sample")))));
  parts.push(intro);

  // ---------------------------------------------------------------- already loaded
  if (loaded) {
    const c = card("Your data is loaded", loaded.label, { badge: h("span", { class: "status ok" }, "In use") });
    c.body.append(h("div", { class: "row gap8 wrap" },
      h("button", { class: "btn btn-primary", type: "button", onclick: () => window.jpUseDataset("custom", "overview") }, "Open the overview"),
      h("button", { class: "btn", type: "button", onclick: async () => { await uploadCsv(null, "remove"); S.done = null; await window.jpRefreshDatasets(); draw(); toast("Removed", "Your data was removed from this session."); } }, "Remove my data")));
    if (S.done) c.body.append(summary(S.done));
    parts.push(c);
  }

  // ---------------------------------------------------------------- 1. choose a file
  const pick = card("1. Choose your file", S.file ? `${S.file.name} · ${(S.file.size / 1e6).toFixed(1)} MB` : "A CSV file from your computer");
  const input = h("input", { type: "file", accept: ".csv,text/csv", id: "jp-file", class: "sr-only" });
  input.addEventListener("change", () => input.files[0] && chooseFile(input.files[0], draw));
  const drop = h("label", { class: "drop", for: "jp-file" },
    h("strong", {}, S.file ? "Choose a different file" : "Choose a CSV file"), h("span", { class: "muted" }, "or drag it here"));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer.files[0]) chooseFile(e.dataTransfer.files[0], draw); });
  pick.body.append(input, drop);
  if (S.busy && !S.ins) pick.body.append(h("p", { class: "muted" }, "Reading your file…"));
  if (S.error) pick.body.append(h("p", { class: "callout-inline err" }, S.error));
  parts.push(pick);

  // ---------------------------------------------------------------- 2. check the reading
  if (S.ins) parts.push(checkCard(draw));
  return parts;
}

function miniTable(cols, rows) {
  return h("div", { class: "table-wrap" }, h("table", { class: "mini" },
    h("thead", {}, h("tr", {}, ...cols.map((c) => h("th", {}, c)))),
    h("tbody", {}, ...rows.map((r) => h("tr", {}, ...r.map((c) => h("td", { style: { whiteSpace: "nowrap" } }, c)))))));
}

function summary(d) {
  const s = d.summary || d;
  return h("div", { class: "stack", style: { gap: "10px" } },
    h("div", { class: "mini-stats" },
      stat("Customers", int(s.customers)), stat("Buyers", int(s.buyers)), stat("Orders", int(s.orders)),
      stat("Period", `${date(s.start)} – ${date(s.end)}`), stat("Average order", money(s.aov)),
      stat("Compared by", `${(d.batches || []).length} ${s.batch_unit || "month"}s`)),
    ...(d.warnings || []).map((w) => h("p", { class: "callout-inline" }, w)));
}
const stat = (k, v) => h("div", {}, h("span", { class: "tiny muted" }, k), h("strong", {}, v));

// ---------------------------------------------------------------- file handling
async function chooseFile(file, draw) {
  S.file = file; S.ins = null; S.error = ""; S.done = null; S.busy = true; S.map = {}; S.roles = {};
  draw();
  if (window.JP_STATIC && file.size > 80e6) {
    S.busy = false; S.error = "This file is large for a browser tab (over 80 MB). Use a shorter date range or a sample of customers, or run JourneyPulse on your computer for big files.";
    return draw();
  }
  try {
    S.ins = await uploadCsv(file, "inspect");
    S.map = { ...S.ins.guess };
    S.roles = Object.fromEntries(S.ins.event_values.map((e) => [e.value, e.role]));
    S.dayfirst = !!(S.ins.time_check && S.ins.time_check.dayfirst_suggested);
  } catch (err) { S.error = err.message; }
  S.busy = false;
  draw();
}

async function useSample(draw) {
  try {
    const res = await fetch("sample/business_sample.csv");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    await chooseFile(new File([blob], "business_sample.csv", { type: "text/csv" }), draw);
  } catch (err) { S.error = `Could not load the sample (${err.message}).`; draw(); }
}

async function refreshActions(draw) {
  S.busy = true; draw();
  try {
    const ins = await uploadCsv(S.file, "inspect", { mapping: { event: S.map.event } });
    S.ins.event_values = ins.event_values;
    S.roles = Object.fromEntries(ins.event_values.map((e) => [e.value, e.role]));
    S.error = "";
  } catch (err) { S.error = err.message; S.ins.event_values = []; S.roles = {}; }
  S.busy = false; draw();
}

// ---------------------------------------------------------------- step 2
function checkCard(draw) {
  const ins = S.ins;
  const c = card("2. Check how we read your file", `${int(ins.n_rows)} rows · ${ins.columns.length} columns`);

  c.body.append(h("div", {}, h("div", { class: "eyebrow" }, "The first rows of your file"), previewTable(ins.preview)));

  // columns
  const grid = h("div", { class: "form-grid" });
  for (const f of FIELDS) {
    const sel = h("select", { "aria-label": f.label },
      h("option", { value: "" }, f.required ? "Choose a column…" : "None"),
      ...ins.columns.map((col) => h("option", { value: col }, col)));
    sel.value = S.map[f.key] || "";
    sel.addEventListener("change", () => {
      S.map[f.key] = sel.value || null;
      if (f.key === "event" && S.map.event) refreshActions(draw); else draw();
    });
    grid.append(h("label", { class: "field" }, h("span", {}, f.label), sel, h("small", { class: "muted" }, f.hint)));
  }
  c.body.append(h("div", {}, h("div", { class: "eyebrow" }, "Which column is which"), grid));

  // date reading
  const tc = ins.time_check;
  if (S.map.time && tc) {
    const cb = h("input", { type: "checkbox", id: "jp-dayfirst" });
    cb.checked = S.dayfirst;
    cb.addEventListener("change", () => { S.dayfirst = cb.checked; });
    c.body.append(h("div", { class: "field" },
      h("label", { class: "row gap8" }, cb, h("span", {}, "Dates are written day first (31/01/2026)")),
      h("small", { class: tc.parsed_share < 0.8 ? "err" : "muted" },
        tc.parsed_share < 0.8
          ? `We could not read most dates in "${S.map.time}" (example: ${tc.example}). Pick the right column.`
          : `We read "${tc.example}" as ${tc.read_as}. If that looks wrong, tick the box above and re-check.`)));
  }

  // action meanings
  const acts = h("div", { class: "table-wrap" });
  if (ins.event_values.length) {
    acts.append(h("table", { class: "mini" },
      h("thead", {}, h("tr", {}, h("th", {}, "Action in your file"), h("th", { class: "n" }, "Rows"), h("th", {}, "What it means for the journey"))),
      h("tbody", {}, ...ins.event_values.map((e) => {
        const sel = h("select", { "aria-label": `Meaning of ${e.value}` }, ...Object.entries(ROLE_LABEL).map(([k, v]) => h("option", { value: k }, v)));
        sel.value = S.roles[e.value] || "ignore";
        sel.addEventListener("change", () => { S.roles[e.value] = sel.value; draw(); });
        return h("tr", {}, h("td", { style: { whiteSpace: "normal" } }, e.value), h("td", { class: "n" }, int(e.count)), h("td", {}, sel));
      }))));
  }
  const hasBuy = Object.values(S.roles).includes("purchase");
  c.body.append(h("div", {}, h("div", { class: "eyebrow" }, "What each action means"),
    ins.event_values.length ? acts : h("p", { class: "muted" }, "Choose the action column above."),
    ins.event_values.length && !hasBuy ? h("p", { class: "callout-inline err" }, "Mark at least one action as “Bought something”, otherwise there is nothing to measure.") : null));

  // settings
  const num = (key, label, hint, min, max) => {
    const inp = h("input", { type: "number", min, max, value: S[key] });
    inp.addEventListener("input", () => { S[key] = inp.value; });
    return h("label", { class: "field" }, h("span", {}, label), inp, h("small", { class: "muted" }, hint));
  };
  const settings = h("div", { class: "form-grid" },
    num("churn", "A customer is “lost” after … days of no activity", "30 suits most online shops; use 90 or more for things people buy rarely", 1, 365),
    num("loyal", "A customer is “loyal” from their … order", "Usually 3", 2, 20));
  if (!S.map.price) settings.append(num("aov", "Average order value", "No order value column, so this number is used for revenue figures", 0, 1e9));
  c.body.append(h("div", {}, h("div", { class: "eyebrow" }, "Two business settings"), settings));

  // build
  if (S.error) c.body.append(h("p", { class: "callout-inline err" }, S.error));
  const ok = S.map.user && S.map.time && S.map.event && hasBuy && !S.busy;
  const btn = h("button", { class: "btn btn-primary", type: "button", disabled: ok ? null : true, onclick: () => analyse(draw) },
    S.busy ? "Working…" : "Analyse my data");
  c.body.append(h("div", { class: "row gap12 wrap" }, btn, h("span", { class: "tiny muted" }, window.JP_STATIC ? PRIVACY_STATIC : PRIVACY_LOCAL)));
  if (S.busy) c.body.append(h("p", { class: "muted" }, window.JP_STATIC ? "Building your model in the browser. A large file can take a minute…" : "Building your model…"));
  return c;
}

function previewTable(p) {
  return h("div", { class: "table-wrap" }, h("table", { class: "mini" },
    h("thead", {}, h("tr", {}, ...p.columns.map((c) => h("th", {}, c)))),
    h("tbody", {}, ...p.rows.map((r) => h("tr", {}, ...r.map((c) => h("td", { style: { whiteSpace: "nowrap" } }, c)))))));
}

async function analyse(draw) {
  S.busy = true; S.error = ""; draw();
  try {
    const mapping = { time: S.map.time, user: S.map.user, event: S.map.event, session: S.map.session || null, price: S.map.price || null,
      event_map: S.roles, dayfirst: S.dayfirst, churn_days: S.churn, loyal_at: S.loyal, aov: S.aov === "" ? 0 : Number(S.aov) };
    const res = await uploadCsv(S.file, "build", { mapping, name: S.file.name });
    S.done = res;
    S.busy = false;
    toast("Your data is ready", `${int(res.summary.customers)} customers analysed.`);
    await window.jpUseDataset("custom", "overview");
  } catch (err) {
    S.busy = false; S.error = err.message; draw();
  }
}
