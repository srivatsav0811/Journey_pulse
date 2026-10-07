// effects.js — the only motion left: a short count-up for the headline figure.
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Animates a number in an element (headline figures). */
export function countTo(el, to, fmt, ms = 500) {
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
