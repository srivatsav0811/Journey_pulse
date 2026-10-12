// format.js — number formatting used everywhere, so the same value always reads the same way.

export function pct(x, digits) {
  if (x == null || Number.isNaN(x)) return "–";
  const v = x * 100;
  const d = digits ?? (Math.abs(v) < 1 && v !== 0 ? 2 : 1);
  return `${v.toFixed(d)}%`;
}

export function pts(x, digits = 1) {
  if (x == null) return "–";
  const v = x * 100;
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)} pts`;
}

export function signedPct(x, digits = 1) {
  if (x == null || !Number.isFinite(x)) return "–";
  return `${x >= 0 ? "+" : ""}${(x * 100).toFixed(digits)}%`;
}

export function money(x, { compact = false } = {}) {
  if (x == null || !Number.isFinite(x)) return "–";
  if (compact && Math.abs(x) >= 1000) {
    return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(x);
  }
  return new Intl.NumberFormat("en", { maximumFractionDigits: 0 }).format(x);
}

export function num(x, digits = 2) {
  if (x == null || !Number.isFinite(x)) return "–";
  return new Intl.NumberFormat("en", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(x);
}

export function int(x) {
  if (x == null) return "–";
  return new Intl.NumberFormat("en").format(Math.round(x));
}

export function signedMoney(x) {
  if (x == null || !Number.isFinite(x)) return "–";
  return `${x >= 0 ? "+" : "−"}${money(Math.abs(x))}`;
}

export function date(s) {
  if (!s) return "–";
  const d = new Date(s.replace(" ", "T"));
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
