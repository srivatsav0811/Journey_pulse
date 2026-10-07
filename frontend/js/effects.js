// effects.js — the "liquid glass" layer: cursor ring + glow, cursor-tracked specular
// sheen on glass panels, magnetic buttons, parallax aurora, and drifting glass orbs
// that part around the cursor. Everything stops under prefers-reduced-motion.

const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = window.matchMedia("(pointer: fine)").matches;
export const pointer = { x: -9999, y: -9999, active: false };

export function initEffects() {
  const root = document.documentElement;
  const ring = document.querySelector(".cursor-ring");
  const blobs = [...document.querySelectorAll(".blob")];
  let rx = -9999, ry = -9999;

  window.addEventListener("pointermove", (e) => {
    pointer.x = e.clientX; pointer.y = e.clientY; pointer.active = true;
    root.style.setProperty("--cx", `${e.clientX}px`);
    root.style.setProperty("--cy", `${e.clientY}px`);
    // specular sheen: only the panel under the pointer is updated
    const g = e.target.closest && e.target.closest(".glass");
    if (g) {
      const r = g.getBoundingClientRect();
      g.style.setProperty("--mx", `${e.clientX - r.left}px`);
      g.style.setProperty("--my", `${e.clientY - r.top}px`);
    }
    const hot = e.target.closest && e.target.closest("a, button, input, select, textarea, [data-magnetic], .chip, .heat-cell, .hb-row");
    ring && ring.classList.toggle("hot", !!hot);
    if (!reduce) {
      const nx = e.clientX / window.innerWidth - 0.5, ny = e.clientY / window.innerHeight - 0.5;
      blobs.forEach((b, i) => {
        const k = (i + 1) * 18;
        b.style.setProperty("--px", `${nx * k}px`);
        b.style.setProperty("--py", `${ny * k}px`);
      });
    }
  }, { passive: true });
  document.addEventListener("pointerleave", () => { pointer.active = false; });

  // cursor ring follows with easing
  if (ring && finePointer && !reduce) {
    const tick = () => {
      rx += (pointer.x - rx) * 0.2; ry += (pointer.y - ry) * 0.2;
      root.style.setProperty("--rx", `${rx}px`);
      root.style.setProperty("--ry", `${ry}px`);
      requestAnimationFrame(tick);
    };
    tick();
  } else if (ring) ring.style.display = "none";

  initMagnetic();
  if (!reduce) initOrbs(document.getElementById("orbs"));
}

// buttons marked data-magnetic lean toward the cursor
function initMagnetic() {
  if (reduce || !finePointer) return;
  document.addEventListener("pointermove", (e) => {
    document.querySelectorAll("[data-magnetic]").forEach((el) => {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const dx = e.clientX - cx, dy = e.clientY - cy;
      const d = Math.hypot(dx, dy), R = Math.max(r.width, r.height) * 0.9 + 30;
      if (d < R) el.style.transform = `translate(${dx * 0.18}px, ${dy * 0.25}px)`;
      else if (el.style.transform) el.style.transform = "";
    });
  }, { passive: true });
}

// drifting glass orbs; the cursor pushes them away and they spring back
function initOrbs(canvas) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let W = 0, H = 0, dpr = 1;
  const orbs = [];
  const resize = () => {
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = window.innerWidth; H = window.innerHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  window.addEventListener("resize", resize);
  const hues = [[106, 168, 255], [39, 211, 180], [140, 120, 255], [106, 168, 255], [242, 166, 90]];
  for (let i = 0; i < 14; i++) {
    const r = 18 + Math.random() * 46;
    orbs.push({ x: Math.random() * W, y: Math.random() * H, hx: 0, hy: 0, vx: (Math.random() - 0.5) * 0.18, vy: (Math.random() - 0.5) * 0.18,
      r, ox: 0, oy: 0, c: hues[i % hues.length], ph: Math.random() * Math.PI * 2 });
  }
  let running = true;
  document.addEventListener("visibilitychange", () => { running = !document.hidden; if (running) requestAnimationFrame(frame); });
  const light = () => document.documentElement.dataset.theme === "light";
  function frame(t) {
    if (!running) return;
    ctx.clearRect(0, 0, W, H);
    for (const o of orbs) {
      o.x += o.vx; o.y += o.vy + Math.sin(t / 3000 + o.ph) * 0.05;
      if (o.x < -80) o.x = W + 80; if (o.x > W + 80) o.x = -80;
      if (o.y < -80) o.y = H + 80; if (o.y > H + 80) o.y = -80;
      // repulsion from the cursor, with a spring back to the drift path
      const dx = o.x + o.ox - pointer.x, dy = o.y + o.oy - pointer.y, d = Math.hypot(dx, dy);
      const R = 170 + o.r;
      if (pointer.active && d < R && d > 0.1) { const f = (1 - d / R) * 3.2; o.ox += (dx / d) * f; o.oy += (dy / d) * f; }
      o.ox *= 0.94; o.oy *= 0.94;
      const x = o.x + o.ox, y = o.y + o.oy;
      const [r, g, b] = o.c;
      const a = light() ? 0.22 : 0.16;
      const grd = ctx.createRadialGradient(x - o.r * 0.35, y - o.r * 0.4, o.r * 0.05, x, y, o.r);
      grd.addColorStop(0, `rgba(255,255,255,${a * 1.6})`);
      grd.addColorStop(0.35, `rgba(${r},${g},${b},${a})`);
      grd.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.fillStyle = grd;
      ctx.beginPath(); ctx.arc(x, y, o.r, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = `rgba(255,255,255,${light() ? 0.35 : 0.08})`;
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(x, y, o.r * 0.92, Math.PI * 1.1, Math.PI * 1.6); ctx.stroke();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

/** Smoothly animates a number in an element (hero figures). */
export function countTo(el, to, fmt, ms = 900) {
  if (reduce) { el.textContent = fmt(to); return; }
  const from = el._v ?? 0;
  const t0 = performance.now();
  const step = (now) => {
    const k = Math.min(1, (now - t0) / ms), e = 1 - (1 - k) ** 3;
    el._v = from + (to - from) * e;
    el.textContent = fmt(el._v);
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export const reducedMotion = reduce;
