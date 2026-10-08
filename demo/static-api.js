// static-api.js — the browser-demo replacement for fetch("/api/..."): sends each call to the
// Pyodide worker (worker.js), which runs the real Python backend in this tab.
const view = () => document.getElementById("view");
let worker = null, readyResolve, readyReject, nextId = 1;
const pending = new Map();
const ready = new Promise((res, rej) => { readyResolve = res; readyReject = rej; });

function start() {
  if (worker) return;
  const show = (text) => { const v = view(); if (v) v.textContent = text; };
  show("Starting Python in your browser…");
  worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
  worker.onmessage = (e) => {
    const m = e.data;
    if (m.type === "status") show(m.text);
    else if (m.type === "ready") readyResolve();
    else if (m.type === "fatal") { show(`Could not start the in-browser engine: ${m.error}`); readyReject(new Error(m.error)); }
    else if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
  };
}

/** One API call. Resolves to {status, data}. */
export async function call(method, path, { query, body } = {}) {
  start();
  await ready;
  return new Promise((resolve) => {
    const id = nextId++;
    pending.set(id, resolve);
    worker.postMessage({ id, method, path, query, body });
  });
}
