import type { Frame3dDriftRow } from "@/lib/chat-types";

export type DriftMode = "drift" | "disp";

/** "Nice" axis ticks from 0 to >= max (1/2/2.5/5 × 10^k steps). */
export function niceTicks(max: number, target = 5): number[] {
  const m = max > 0 && Number.isFinite(max) ? max : 1;
  const raw = m / target;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((f) => f * p).find((s) => s >= raw) ?? 10 * p;
  const n = Math.ceil(m / step - 1e-9);
  return Array.from({ length: n + 1 }, (_, i) => +(i * step).toPrecision(12));
}

export function fmtTick(v: number): string {
  if (v === 0) return "0";
  const a = Math.abs(v);
  return a >= 100 ? v.toFixed(0) : a >= 10 ? String(+v.toFixed(1)) : String(+v.toFixed(2));
}

/** Value plotted per storey: amplified inter-storey drift ratio (%) or elastic total displacement (mm). */
export function driftValue(r: Frame3dDriftRow, mode: DriftMode): number | null {
  return mode === "drift" ? r.ratioAmplifiedPct : (r.uMaxMm ?? null);
}

export function seriesFor(rows: Frame3dDriftRow[], dir: string, mode: DriftMode): Array<{ storey: number; v: number; row: Frame3dDriftRow }> {
  return rows
    .filter((r) => r.direction === dir)
    .sort((a, b) => a.storey - b.storey)
    .map((r) => ({ storey: r.storey, v: driftValue(r, mode), row: r }))
    .filter((p): p is { storey: number; v: number; row: Frame3dDriftRow } => p.v !== null && Number.isFinite(p.v));
}

export function hasDisplacement(rows: Frame3dDriftRow[]): boolean {
  return rows.some((r) => r.uMaxMm !== null && r.uMaxMm !== undefined);
}
