// api.js — talks to the Python backend and holds the shared client state.
// The one piece of state every view depends on is `state.live`: which version
// of the adaptive matrix is live. When it changes, every view re-renders.

export const state = {
  dataset: null,      // current dataset name
  meta: null,         // /api/datasets response (states, levers, objectives...)
  live: null,         // live tag {version, label, latest, strategy, frozen_label}
  health: null,
  chats: {},          // chat history per dataset, shared by drawer and advisor page
};

const liveListeners = new Set();

export function onLiveChange(fn) {
  liveListeners.add(fn);
  return () => liveListeners.delete(fn);
}

export function setLive(live, info = {}) {
  const prev = state.live;
  state.live = live;
  const changed = !prev || prev.version !== live.version || prev.dataset !== live.dataset || prev.strategy !== live.strategy;
  if (changed) liveListeners.forEach((fn) => fn(live, prev, info));
}

export async function api(path, { method = "GET", body, params } = {}) {
  const q = { dataset: state.dataset, ...(params || {}) };
  let ok, status, data;
  if (window.JP_STATIC) {
    // GitHub Pages demo: no server, so the Python backend runs in a Web Worker (see demo/)
    const { call } = await import("./static-api.js");
    const query = method === "GET" ? Object.fromEntries(Object.entries(q).filter(([, v]) => v != null)) : {};
    const r = await call(method, path, { query, body: method === "POST" ? { dataset: state.dataset, ...(body || {}) } : {} });
    ({ status, data } = r); ok = status === 200;
  } else {
    const url = new URL(path, window.location.origin);
    if (method === "GET") Object.entries(q).forEach(([k, v]) => v != null && url.searchParams.set(k, v));
    const res = await fetch(url, {
      method,
      headers: method === "POST" ? { "Content-Type": "application/json" } : undefined,
      body: method === "POST" ? JSON.stringify({ dataset: state.dataset, ...(body || {}) }) : undefined,
    });
    try { data = await res.json(); } catch { data = { error: `HTTP ${res.status}` }; }
    ok = res.ok; status = res.status;
  }
  if (!ok) throw new Error((data && data.error) || `HTTP ${status}`);
  if (data && data.live_tag) setLive(data.live_tag);
  if (data && data.live && data.live.version !== undefined && data.live.dataset) setLive(data.live);
  return data;
}

export const lever = (id) => state.meta.levers.find((l) => l.id === id);
