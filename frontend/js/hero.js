// hero.js — the live journey field. Every particle is a simulated customer whose
// next move is sampled from the LIVE transition matrix, so when a new month is
// streamed in, the flows visibly re-weight. Nodes lean toward the cursor; a
// liquid-glass lens refracts the field under the pointer.
import { showTip, hideTip, cssVar } from "./ui.js";
import { reducedMotion } from "./effects.js";

const NAMES = ["Visitor", "Product View", "Add to Cart", "Purchase", "Repeat Purchase", "Loyal Customer", "Exit"];
const SHORT = ["Visitor", "View", "Cart", "1st order", "2nd order", "Loyal", "Churn"];
const VARS = ["--state-visitor", "--state-view", "--state-cart", "--state-purchase", "--state-repeat", "--state-loyal", "--state-exit"];
const EXIT = 6;

export class JourneyField {
  constructor(canvas, { onStats } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.onStats = onStats;
    this.P = null; this.Pdraw = null; this.Pfrom = null; this.morph = 1;
    this.particles = [];
    this.stats = { spawned: 0, finished: 0, finishedFirst: 0, loyal: 0 };
    this.glow = new Array(7).fill(0);
    this.mouse = { x: -999, y: -999, in: false };
    this.nodeOff = NAMES.map(() => ({ x: 0, y: 0 }));
    this.running = false;
    this.spawnAcc = 0;
    this.readColors();
    this._resize = () => this.resize();
    window.addEventListener("resize", this._resize);
    new MutationObserver(() => this.readColors()).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    canvas.addEventListener("pointermove", (e) => this.hover(e));
    canvas.addEventListener("pointerleave", () => { this.mouse.in = false; hideTip(); this.lens && (this.lens.style.opacity = 0); });
    this.lens = canvas.parentElement.querySelector(".lens");
    this.io = new IntersectionObserver(([en]) => { en.isIntersecting ? this.start() : this.stop(); });
    this.io.observe(canvas);
    this.resize();
  }

  readColors() {
    this.colors = VARS.map((v) => cssVar(v) || "#888");
    this.light = document.documentElement.dataset.theme === "light";
  }

  resize() {
    const r = this.canvas.parentElement.getBoundingClientRect();
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.W = Math.max(300, r.width); this.H = Math.max(260, r.height);
    this.canvas.width = this.W * this.dpr; this.canvas.height = this.H * this.dpr;
    this.canvas.style.width = `${this.W}px`; this.canvas.style.height = `${this.H}px`;
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    const W = this.W, H = this.H, narrow = W < 640;
    this.nodes = NAMES.map((_, i) => {
      if (i === EXIT) return { x: W * 0.5, y: H * (narrow ? 0.56 : 0.68) };
      const t = i / 5;
      return { x: W * (0.07 + t * 0.86), y: H * (narrow ? 0.34 : 0.32) - Math.sin(t * Math.PI) * H * 0.10 };
    });
    this.nodeR = narrow ? 12 : 16;
    if (!this.running) this.draw(0);
  }

  setMatrix(P) {
    if (!this.P) { this.P = P; this.Pdraw = P.map((r) => r.slice()); this.morph = 1; }
    else { this.Pfrom = this.Pdraw.map((r) => r.slice()); this.P = P; this.morph = 0; }
    if (reducedMotion || !this.running) { this.Pdraw = P.map((r) => r.slice()); this.morph = 1; this.draw(0); }
  }

  resetStats() { this.stats = { spawned: 0, finished: 0, finishedFirst: 0, loyal: 0 }; this.particles = []; }

  start() {
    if (this.running || reducedMotion) return;
    this.running = true;
    let last = performance.now(), statT = 0;
    const loop = (now) => {
      if (!this.running) return;
      const dt = Math.min(0.25, (now - last) / 1000); last = now;   // frame-rate independent, but no jump after a tab switch
      this.step(dt);
      this.draw(now);
      statT += dt;
      if (statT > 0.4 && this.onStats) { statT = 0; this.onStats({ ...this.stats }); }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  stop() { this.running = false; }

  sample(i) {
    const row = this.P[i];
    let u = Math.random(), acc = 0;
    for (let j = 0; j < row.length; j++) { acc += row[j]; if (u <= acc) return j; }
    return EXIT;
  }

  launch(p, from) {
    const to = this.sample(from);
    p.from = from; p.to = to; p.t = 0;
    if (to === from) { p.loop = true; p.dur = 0.55; }
    else {
      p.loop = false;
      const a = this.nodes[from], b = this.target(from, to);
      p.dur = 0.7 + Math.hypot(b.x - a.x, b.y - a.y) / 520 + Math.random() * 0.25;
      p.bend = (to === EXIT ? 0.18 : to < from ? -0.55 : 0.28) * (0.8 + Math.random() * 0.4);
    }
  }

  step(dt) {
    if (!this.P) return;
    if (this.morph < 1) {
      this.morph = Math.min(1, this.morph + dt / 0.8);
      const k = 1 - (1 - this.morph) ** 3;
      this.Pdraw = this.P.map((row, i) => row.map((v, j) => this.Pfrom[i][j] + (v - this.Pfrom[i][j]) * k));
    }
    // spawn new visitors
    this.spawnAcc += dt * (this.W < 640 ? 14 : 24);
    while (this.spawnAcc >= 1 && this.particles.length < 380) {
      this.spawnAcc -= 1;
      const p = { seen: new Set([0]), size: 1.6 + Math.random() * 1.6, jitter: Math.random() * Math.PI * 2, alpha: 1 };
      this.launch(p, 0);
      this.particles.push(p);
      this.stats.spawned++;
    }
    for (const p of this.particles) {
      p.t += dt / p.dur;
      if (p.t >= 1) {
        const j = p.to;
        this.glow[j] = Math.min(1, this.glow[j] + 0.12);
        if (j === EXIT) {            // journey complete: count it for the empirical conversion rate
          p.dead = true;
          this.stats.finished++;
          if (p.seen.has(3)) this.stats.finishedFirst++;
          continue;
        }
        if (!p.seen.has(j)) {
          p.seen.add(j);
          if (j === 5) this.stats.loyal++;
        }
        this.launch(p, j);
      }
    }
    this.particles = this.particles.filter((p) => !p.dead);
    this.glow = this.glow.map((g) => g * (1 - dt * 1.4));
    // nodes lean toward the cursor
    this.nodes.forEach((n, i) => {
      const o = this.nodeOff[i];
      let tx = 0, ty = 0;
      if (this.mouse.in) {
        const dx = this.mouse.x - n.x, dy = this.mouse.y - n.y, d = Math.hypot(dx, dy);
        if (d < 160) { tx = dx * 0.16 * (1 - d / 160); ty = dy * 0.16 * (1 - d / 160); }
      }
      o.x += (tx - o.x) * 0.12; o.y += (ty - o.y) * 0.12;
    });
  }

  pos(i) { const n = this.nodes[i], o = this.nodeOff[i]; return { x: n.x + o.x, y: n.y + o.y }; }

  // each stage drains into its own point along the churn sink, so the edges fan out
  target(from, to) {
    if (to !== EXIT) return this.pos(to);
    const e = this.pos(EXIT), span = Math.min(this.W * 0.30, 300);
    return { x: e.x + (from / 5 - 0.5) * span, y: e.y };
  }

  // quadratic control point: midpoint pushed along the edge's normal.
  // forward edges (bend > 0) and return edges (bend < 0) both arc upward; return arcs sit higher.
  curve(a, b, bend) {
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    const dx = b.x - a.x, dy = b.y - a.y;
    return { x: mx + bend * dy, y: my - bend * dx };
  }

  draw(now) {
    const { ctx, W, H } = this;
    ctx.clearRect(0, 0, W, H);
    if (!this.Pdraw) return;
    const P = this.Pdraw;
    // edges
    for (let i = 0; i < 6; i++) {
      for (let j = 0; j < 7; j++) {
        const p = P[i][j];
        if (i === j || p < 0.004) continue;
        const a = this.pos(i), b = this.target(i, j);
        const bend = j === EXIT ? 0.18 : j < i ? -0.55 : 0.28;
        const c = this.curve(a, b, bend);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(c.x, c.y, b.x, b.y);
        const w = 0.6 + Math.sqrt(p) * 7;
        const alpha = 0.10 + Math.sqrt(p) * 0.45;
        ctx.strokeStyle = j === EXIT ? `rgba(${this.light ? "120,130,150" : "150,160,185"},${alpha * 0.6})`
          : this.hexA(this.colors[j], alpha);
        ctx.lineWidth = w; ctx.lineCap = "round"; ctx.stroke();
      }
    }
    // churn sink
    const ex = this.pos(EXIT);
    const sinkW = Math.min(W * 0.34, 340);
    const g = ctx.createRadialGradient(ex.x, ex.y, 4, ex.x, ex.y, sinkW / 2);
    g.addColorStop(0, `rgba(${this.light ? "150,160,180" : "90,100,125"},${0.35 + this.glow[EXIT] * 0.3})`);
    g.addColorStop(1, "rgba(90,100,125,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(ex.x, ex.y, sinkW / 2, 22, 0, 0, Math.PI * 2); ctx.fill();
    // particles
    for (const p of this.particles) {
      let x, y;
      const a = this.pos(p.from);
      if (p.loop) {
        const ang = p.jitter + p.t * Math.PI * 2;
        x = a.x + Math.cos(ang) * (this.nodeR + 6); y = a.y + Math.sin(ang) * (this.nodeR + 6);
      } else {
        const b = this.target(p.from, p.to), c = this.curve(a, b, p.bend);
        const t = p.t, u = 1 - t;
        x = u * u * a.x + 2 * u * t * c.x + t * t * b.x;
        y = u * u * a.y + 2 * u * t * c.y + t * t * b.y;
      }
      if (this.mouse.in) {
        const dx = x - this.mouse.x, dy = y - this.mouse.y, d = Math.hypot(dx, dy);
        if (d < 70 && d > 0.1) { x += (dx / d) * (70 - d) * 0.35; y += (dy / d) * (70 - d) * 0.35; }
      }
      const fade = p.to === EXIT ? 1 - p.t * 0.85 : 1;
      ctx.fillStyle = p.to === EXIT ? `rgba(${this.light ? "110,120,140" : "170,178,200"},${0.55 * fade})` : this.hexA(this.colors[p.to], 0.95);
      ctx.beginPath(); ctx.arc(x, y, p.size, 0, Math.PI * 2); ctx.fill();
    }
    // nodes
    for (let i = 0; i < 6; i++) {
      const n = this.pos(i), r = this.nodeR, col = this.colors[i];
      const halo = ctx.createRadialGradient(n.x, n.y, r * 0.4, n.x, n.y, r * (2.6 + this.glow[i] * 1.6));
      halo.addColorStop(0, this.hexA(col, 0.45 + this.glow[i] * 0.3));
      halo.addColorStop(1, this.hexA(col, 0));
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(n.x, n.y, r * 4, 0, Math.PI * 2); ctx.fill();
      const body = ctx.createRadialGradient(n.x - r * 0.35, n.y - r * 0.4, r * 0.1, n.x, n.y, r);
      body.addColorStop(0, "rgba(255,255,255,0.95)");
      body.addColorStop(0.35, this.hexA(col, 0.95));
      body.addColorStop(1, this.hexA(col, 0.75));
      ctx.fillStyle = body; ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,0.55)"; ctx.lineWidth = 1.2; ctx.stroke();
      ctx.fillStyle = this.light ? "#0d1424" : "#f4f7ff";
      ctx.font = `600 ${this.W < 640 ? 10.5 : 12.5}px ${getComputedStyle(document.body).fontFamily}`;
      ctx.textAlign = "center";
      ctx.fillText(SHORT[i], n.x, n.y - r - 12);
    }
    ctx.fillStyle = this.light ? "#3f4a63" : "#c3cbe0";
    ctx.fillText("Churn (30 days inactive)", ex.x, ex.y + 36);
  }

  hexA(hex, a) {
    const m = hex.replace("#", "").match(/.{2}/g);
    if (!m) return hex;
    return `rgba(${parseInt(m[0], 16)},${parseInt(m[1], 16)},${parseInt(m[2], 16)},${a})`;
  }

  hover(e) {
    const r = this.canvas.getBoundingClientRect();
    this.mouse = { x: e.clientX - r.left, y: e.clientY - r.top, in: true };
    if (this.lens) {
      this.lens.style.opacity = 1;
      this.lens.style.transform = `translate(${this.mouse.x - 70}px, ${this.mouse.y - 70}px)`;
    }
    if (!this.P) return;
    const hit = this.nodes.findIndex((_, i) => i < 6 && Math.hypot(this.pos(i).x - this.mouse.x, this.pos(i).y - this.mouse.y) < this.nodeR + 10);
    if (hit < 0) return hideTip();
    const row = this.P[hit].map((p, j) => ({ j, p })).filter((d) => d.p >= 0.001).sort((a, b) => b.p - a.p).slice(0, 5);
    showTip(e, `From ${NAMES[hit]} (live matrix)`, row.map((d) => ({ color: this.colors[d.j], value: `${(d.p * 100).toFixed(d.p < 0.01 ? 2 : 1)}%`, label: `→ ${NAMES[d.j]}` })));
  }

  destroy() { this.stop(); this.io.disconnect(); window.removeEventListener("resize", this._resize); }
}
