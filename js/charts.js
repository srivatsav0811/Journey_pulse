// charts.js — dependency-free charts (SVG + HTML), so the dashboard works offline.
// Conventions: thin marks, 4px rounded data-ends, 2px lines, >=8px end dots with a
// surface ring, hairline solid grid, legend for >=2 series, text never in series colour,
// hover tooltip on every mark.
import { h, showTip, hideTip, cssVar } from "./ui.js";

const SVGNS = "http://www.w3.org/2000/svg";
function s(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v);
  kids.flat(Infinity).forEach((k) => k != null && el.append(k instanceof Node ? k : document.createTextNode(String(k))));
  return el;
}

function niceTicks(lo, hi, count = 4) {
  if (hi === lo) hi = lo + 1;
  const span = hi - lo;
  const step0 = span / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((m) => span / m <= count) || 10 * mag;
  const start = Math.floor(lo / step) * step;
  const ticks = [];
  for (let v = start; v <= hi + step * 0.5; v += step) ticks.push(+v.toFixed(10));
  return ticks;
}

/** Re-render a chart whenever its container is resized. */
export function responsive(container, draw) {
  const run = () => { const w = container.clientWidth; if (w > 0 && w !== container._w) { container._w = w; draw(w); } };
  if (container._ro) container._ro.disconnect();
  container._ro = new ResizeObserver(run);
  container._ro.observe(container);
  container._w = 0;
  requestAnimationFrame(run);
}

export function legend(items) {
  return h("div", { class: "legend" }, items.map((it) =>
    h("span", {}, h("i", { class: it.type === "line" ? "ln" : "bx", style: { background: it.color } }), it.name)));
}

// ---------------------------------------------------------------- horizontal bars (HTML)
/**
 * rows: [{label, values: {key: number}, sub?}], series: [{key, name, color}]
 * First series is labelled at its tip; the others are in the tooltip and legend.
 */
export function hbars(rows, { series, fmt, max, labelWidth = 150 } = {}) {
  const top = max ?? Math.max(1e-12, ...rows.flatMap((r) => series.map((sr) => Math.abs(r.values[sr.key] ?? 0))));
  const wrap = h("div", { class: "hbars" });
  if (series.length > 1) wrap.append(legend(series.map((sr) => ({ name: sr.name, color: sr.color }))));
  for (const r of rows) {
    const bars = h("div", { class: "hb-bars" });
    series.forEach((sr, i) => {
      const v = r.values[sr.key] ?? 0;
      const w = Math.max(0, (Math.abs(v) / top) * 100);
      bars.append(h("div", { class: "hb-track" },
        h("div", { class: "hb-bar", style: { width: `${w}%`, background: sr.color, transitionDelay: `${i * 60}ms` } }),
        i === 0 ? h("span", { class: "hb-val" }, fmt(v)) : null));
    });
    const row = h("div", { class: "hb-row", tabindex: "0", style: { gridTemplateColumns: `${labelWidth}px 1fr` } },
      h("div", { class: "hb-label" }, h("span", {}, r.label), r.sub ? h("small", { class: "muted" }, r.sub) : null), bars);
    const tipFn = (e) => showTip(e, r.label, series.map((sr) => ({ color: sr.color, value: fmt(r.values[sr.key] ?? 0), label: sr.name })));
    row.addEventListener("pointermove", tipFn);
    row.addEventListener("pointerleave", hideTip);
    row.addEventListener("focus", (e) => { const b = row.getBoundingClientRect(); tipFn({ clientX: b.right - 40, clientY: b.top }); });
    row.addEventListener("blur", hideTip);
    wrap.append(row);
  }
  requestAnimationFrame(() => wrap.classList.add("in"));
  return wrap;
}

// ---------------------------------------------------------------- line chart (SVG)
/**
 * opts: {x: [labels], series: [{name, color, values}], yFmt, height, yMin, yMax, markers}
 */
export function lineChart(container, opts) {
  const { x, series, yFmt = (v) => v, height = 240 } = opts;
  container.classList.add("chart");
  const draw = (W) => {
    const longest = Math.max(...series.map((sr) => `${sr.name} ${yFmt(sr.values[sr.values.length - 1] ?? 0)}`.length));
    const M = { t: 16, r: series.length <= 4 ? Math.min(190, 16 + longest * 6.6) : 16, b: 30, l: 56 };
    const iw = Math.max(80, W - M.l - M.r), ih = height - M.t - M.b;
    const all = series.flatMap((sr) => sr.values).filter((v) => v != null);
    let lo = opts.yMin ?? Math.min(...all), hi = opts.yMax ?? Math.max(...all);
    const pad = (hi - lo) * 0.15 || Math.abs(hi) * 0.1 || 0.01;
    lo = opts.yMin ?? lo - pad; hi = opts.yMax ?? hi + pad;
    const ticks = niceTicks(lo, hi, 4);
    lo = Math.min(lo, ticks[0]); hi = Math.max(hi, ticks[ticks.length - 1]);
    const X = (i) => M.l + (x.length === 1 ? iw / 2 : (i / (x.length - 1)) * iw);
    const Y = (v) => M.t + ih - ((v - lo) / (hi - lo)) * ih;
    const svg = s("svg", { width: W, height, viewBox: `0 0 ${W} ${height}`, role: "img",
      "aria-label": opts.label || series.map((sr) => sr.name).join(", ") });
    const grid = s("g", { class: "grid" });
    ticks.forEach((t) => {
      grid.append(s("line", { x1: M.l, x2: M.l + iw, y1: Y(t), y2: Y(t) }));
      grid.append(s("text", { x: M.l - 10, y: Y(t) + 4, "text-anchor": "end", class: "tick" }, yFmt(t)));
    });
    x.forEach((lab, i) => grid.append(s("text", { x: X(i), y: height - 8, "text-anchor": "middle", class: "tick" }, lab)));
    svg.append(grid);
    const endLabels = [];
    [...series].reverse().forEach((sr) => {            // first series is drawn last, so it sits on top
      const pts = sr.values.map((v, i) => (v == null ? null : [X(i), Y(v)])).filter(Boolean);
      if (!pts.length) return;
      svg.append(s("path", { d: pts.map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(""), fill: "none",
        style: `stroke:${sr.color}`, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", class: "draw" }));
      pts.forEach((p, i) => svg.append(s("circle", { cx: p[0], cy: p[1], r: i === pts.length - 1 ? 4.5 : 3,
        style: `fill:${sr.color}; stroke: var(--surface)`, "stroke-width": 2 })));
      const last = sr.values.length - 1;
      if (sr.values[last] != null) endLabels.push({ y: Y(sr.values[last]), x: X(last), text: `${sr.name} ${yFmt(sr.values[last])}` });
    });
    // direct end labels only when they don't collide; otherwise the legend carries identity
    endLabels.sort((a, b) => a.y - b.y);
    const collide = endLabels.some((l, i) => i && l.y - endLabels[i - 1].y < 14);
    if (!collide && series.length <= 4) endLabels.forEach((l) => svg.append(s("text", { x: l.x + 10, y: l.y + 4, class: "end-label" }, l.text)));
    // crosshair + tooltip
    const cross = s("line", { class: "cross", y1: M.t, y2: M.t + ih, x1: M.l, x2: M.l, opacity: 0 });
    svg.append(cross);
    const hit = s("rect", { x: M.l - 20, y: M.t, width: iw + 40, height: ih, fill: "transparent" });
    hit.addEventListener("pointermove", (e) => {
      const rect = svg.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const i = Math.max(0, Math.min(x.length - 1, Math.round(((px - M.l) / iw) * (x.length - 1))));
      cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("opacity", 1);
      showTip(e, x[i], series.map((sr) => ({ color: sr.color, value: sr.values[i] == null ? "–" : yFmt(sr.values[i]), label: sr.name })));
    });
    hit.addEventListener("pointerleave", () => { cross.setAttribute("opacity", 0); hideTip(); });
    svg.append(hit);
    container.replaceChildren(series.length > 1 ? legend(series.map((sr) => ({ name: sr.name, color: sr.color, type: "line" }))) : "", svg);
  };
  responsive(container, draw);
}

// ---------------------------------------------------------------- heatmap (HTML grid)
function hexToRgb(hex) {
  const m = hex.replace("#", "").match(/.{2}/g);
  return m ? m.map((c) => parseInt(c, 16)) : [128, 128, 128];
}
function mix(a, b, t) { return a.map((v, i) => Math.round(v + (b[i] - v) * t)); }
function lum([r, g, b]) {
  const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

export function seqColor(t) {
  const steps = [0, 1, 2, 3, 4, 5, 6].map((i) => hexToRgb(cssVar(`--seq-${i}`)));
  const x = Math.max(0, Math.min(1, t)) * (steps.length - 1);
  const i = Math.min(steps.length - 2, Math.floor(x));
  return mix(steps[i], steps[i + 1], x - i);
}
export function divColor(t) {   // t in [-1, 1]
  const neg = hexToRgb(cssVar("--div-neg")), mid = hexToRgb(cssVar("--div-mid")), pos = hexToRgb(cssVar("--div-pos"));
  return t < 0 ? mix(mid, neg, Math.min(1, -t)) : mix(mid, pos, Math.min(1, t));
}

/**
 * rows/cols: labels; values[i][j]; mode "seq" (0..1 via sqrt scale) or "div" (signed, scaled by maxAbs)
 */
export function heatmap({ rows, cols, values, fmt, mode = "seq", tipFmt, title }) {
  const grid = h("div", { class: "heat", style: { gridTemplateColumns: `minmax(92px, 1.2fr) repeat(${cols.length}, minmax(44px, 1fr))` }, role: "table", "aria-label": title || "matrix" });
  grid.append(h("div", { class: "heat-corner muted tiny" }, "from ↓  to →"));
  cols.forEach((c) => grid.append(h("div", { class: "heat-col" }, c)));
  const maxAbs = Math.max(1e-9, ...values.flat().map(Math.abs));
  rows.forEach((r, i) => {
    grid.append(h("div", { class: "heat-row" }, r));
    cols.forEach((c, j) => {
      const v = values[i][j];
      const rgb = mode === "seq" ? seqColor(Math.sqrt(Math.max(0, v))) : divColor(v / maxAbs);
      const ink = lum(rgb) > 0.36 ? "#0b1020" : "#f4f7ff";
      const show = mode === "seq" ? v >= 0.005 : Math.abs(v) >= 0.0005;
      const cell = h("div", { class: "heat-cell", tabindex: "0", style: { background: `rgb(${rgb.join(",")})`, color: ink } },
        show ? fmt(v) : "");
      const tipFn = (e) => showTip(e, `${r} → ${c}`, [{ value: (tipFmt || fmt)(v) }]);
      cell.addEventListener("pointermove", tipFn);
      cell.addEventListener("pointerleave", hideTip);
      cell.addEventListener("focus", (e) => { const b = cell.getBoundingClientRect(); tipFn({ clientX: b.right, clientY: b.bottom }); });
      cell.addEventListener("blur", hideTip);
      grid.append(cell);
    });
  });
  return grid;
}

// ---------------------------------------------------------------- stacked columns (SVG)
export function stackedColumns(container, { x, series, yFmt = (v) => v, height = 260, label }) {
  container.classList.add("chart");
  const draw = (W) => {
    const M = { t: 12, r: 12, b: 30, l: 48 };
    const iw = W - M.l - M.r, ih = height - M.t - M.b;
    const band = iw / x.length, bw = Math.min(28, band * 0.55);
    const Y = (v) => M.t + ih - v * ih;
    const svg = s("svg", { width: W, height, viewBox: `0 0 ${W} ${height}`, role: "img", "aria-label": label || "stacked columns" });
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
      svg.append(s("line", { class: "gridline", x1: M.l, x2: M.l + iw, y1: Y(t), y2: Y(t) }));
      svg.append(s("text", { x: M.l - 8, y: Y(t) + 4, "text-anchor": "end", class: "tick" }, yFmt(t)));
    });
    x.forEach((lab, i) => {
      const cx = M.l + band * i + band / 2;
      let acc = 0;
      const g = s("g", { class: "col", tabindex: "0" });
      series.forEach((sr, k) => {
        const v = sr.values[i] || 0;
        if (v <= 0) return;
        const y0 = Y(acc), y1 = Y(acc + v);
        const hgt = Math.max(0, y0 - y1 - (acc > 0 ? 2 : 0));       // 2px surface gap between segments
        const top = acc + v >= 0.9999;
        g.append(s("rect", { x: cx - bw / 2, y: y1, width: bw, height: hgt, rx: top ? 4 : 0, style: `fill:${sr.color}` }));
        acc += v;
      });
      g.append(s("text", { x: cx, y: height - 8, "text-anchor": "middle", class: "tick" }, lab));
      const hit = s("rect", { x: cx - band / 2, y: M.t, width: band, height: ih, fill: "transparent" });
      const tipFn = (e) => showTip(e, `Step ${lab}`, series.filter((sr) => (sr.values[i] || 0) > 0.0005)
        .map((sr) => ({ color: sr.color, value: yFmt(sr.values[i]), label: sr.name })).reverse());
      hit.addEventListener("pointermove", tipFn);
      hit.addEventListener("pointerleave", hideTip);
      g.append(hit);
      svg.append(g);
    });
    container.replaceChildren(legend(series.map((sr) => ({ name: sr.name, color: sr.color }))), svg);
  };
  responsive(container, draw);
}
