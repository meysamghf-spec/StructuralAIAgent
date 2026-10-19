// SAFE-like foundation results, generic for any footing layout (pure functions; the component only draws).
// Method (stated in the UI): rigid footing, linear soil pressure q(x,y) = P/A + Mx·y/Iy + My·x/Ix (no tension cut-off
// shown as 0); cantilever bending per metre width from the column face: m(u) = q̄·(u)²/2 where u is the distance from
// the footing edge; settlement by Winkler springs s = q / ks with ks = 120·qa (Bowles, ks ≈ 40·FS·qa, FS = 3).
import type { ViewerFooting } from "@/lib/frame3d-viewer";

export type FoundationField = "pressure" | "mx" | "my" | "settlement" | "punching";
export const FIELD_UNITS: Record<FoundationField, string> = { pressure: "kPa", mx: "kN·m/m", my: "kN·m/m", settlement: "mm", punching: "D/C" };

const n = (v: unknown, d = 0) => (typeof v === "number" && Number.isFinite(v) ? v : d);

export function footingLoads(f: ViewerFooting) {
  const i = f.info ?? {};
  return { P: n(i.P_kn), Mx: n(i.Mx_kn_m), My: n(i.My_kn_m), c1: n(i.c1_m, 0.4), c2: n(i.c2_m, 0.4) };
}

/** Soil pressure (kPa) at local point (u, v) measured from the footing centre (m). */
export function pressureAt(f: ViewerFooting, u: number, v: number): number {
  const { P, Mx, My } = footingLoads(f);
  const A = f.B * f.B, I = f.B ** 4 / 12;
  return Math.max(0, P / A + (My * u) / I + (Mx * v) / I);
}

/** Cantilever bending moment per metre (kN·m/m) about the column face, in direction x (mx) or y (my). */
export function momentAt(f: ViewerFooting, u: number, v: number, dir: "x" | "y"): number {
  const { c1, c2 } = footingLoads(f);
  const s = dir === "x" ? u : v;
  const face = (dir === "x" ? c1 : c2) / 2;
  const edge = f.B / 2;
  const a = Math.abs(s);
  if (a > edge) return 0;
  const lever = edge - Math.max(a, face); // overhang beyond the section
  const q = pressureAt(f, dir === "x" ? Math.sign(s || 1) * (edge + Math.max(a, face)) / 2 : u, dir === "y" ? Math.sign(s || 1) * (edge + Math.max(a, face)) / 2 : v);
  return (q * lever * lever) / 2;
}

export function settlementAt(f: ViewerFooting, u: number, v: number, qa: number): number {
  const ks = 120 * Math.max(qa, 1); // kN/m³
  return (pressureAt(f, u, v) / ks) * 1000;
}

export function fieldAt(f: ViewerFooting, field: FoundationField, u: number, v: number, qa: number): number {
  if (field === "pressure") return pressureAt(f, u, v);
  if (field === "mx") return momentAt(f, u, v, "x");
  if (field === "my") return momentAt(f, u, v, "y");
  if (field === "settlement") return settlementAt(f, u, v, qa);
  return n(f.info?.DC_punching);
}

/** Sampled field for the whole layout: cells per footing plus the global range. */
export function sampleField(footings: ViewerFooting[], field: FoundationField, qa: number, cells = 12) {
  let lo = Infinity, hi = -Infinity;
  const out = footings.map((f) => {
    const vals: number[][] = [];
    for (let i = 0; i < cells; i++) {
      const row: number[] = [];
      for (let j = 0; j < cells; j++) {
        const u = -f.B / 2 + (f.B * (j + 0.5)) / cells, v = -f.B / 2 + (f.B * (i + 0.5)) / cells;
        const val = fieldAt(f, field, u, v, qa);
        lo = Math.min(lo, val); hi = Math.max(hi, val);
        row.push(val);
      }
      vals.push(row);
    }
    return vals;
  });
  if (field === "punching") { lo = 0; hi = Math.max(1.2, hi); }
  if (!Number.isFinite(lo)) { lo = 0; hi = 1; }
  return { grid: out, lo, hi: hi > lo ? hi : lo + 1 };
}

/** Blue → green → yellow → red contour colour for t in [0, 1]. */
export function contourColor(t: number): string {
  const c = Math.min(1, Math.max(0, t));
  const stops = [[37, 99, 235], [34, 197, 94], [250, 204, 21], [239, 68, 68]];
  const k = Math.min(stops.length - 2, Math.floor(c * (stops.length - 1)));
  const f = c * (stops.length - 1) - k;
  const m = stops[k].map((a, i) => Math.round(a + (stops[k + 1][i] - a) * f));
  return `rgb(${m[0]}, ${m[1]}, ${m[2]})`;
}

export function dcColor(dc: number): string {
  return dc > 1 ? "#ef4444" : dc > 0.9 ? "#f97316" : dc > 0.7 ? "#facc15" : "#22c55e";
}

/** Values along a strip (section cut) at global y = yCut through every footing it crosses. */
export function stripProfile(footings: ViewerFooting[], field: FoundationField, qa: number, yCut: number, samples = 24) {
  const pts: Array<{ x: number; v: number }> = [];
  for (const f of [...footings].sort((a, b) => a.x - b.x)) {
    const v = yCut - f.y;
    if (Math.abs(v) > f.B / 2) continue;
    for (let k = 0; k <= samples; k++) {
      const u = -f.B / 2 + (f.B * k) / samples;
      pts.push({ x: f.x + u, v: fieldAt(f, field, u, v, qa) });
    }
  }
  return pts;
}
