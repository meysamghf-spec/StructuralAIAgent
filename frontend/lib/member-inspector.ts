// Member inspector: end forces per case/combo, envelope, governing combo, elastic gross-section stresses/strains.
import { combine, factorsFor, loadOptions, memberForces, type ViewerData, type ViewerMember } from "@/lib/frame3d-viewer";

export const FORCE_KEYS = ["N", "V2", "V3", "T", "M2", "M3"] as const;
export type ForceKey = (typeof FORCE_KEYS)[number];
export type EndForces = Record<ForceKey, number>;
export type InspectorRow = { load: string; isCombo: boolean; i: EndForces; j: EndForces };

const zero = (): EndForces => ({ N: 0, V2: 0, V3: 0, T: 0, M2: 0, M3: 0 });

/** End forces of one member for one case/combo. Uses forces6 when present, else the 5-value row (N, V, Mi, Mj). */
export function endForces(v: ViewerData, load: string, memberId: string): { i: EndForces; j: EndForces; full: boolean } | null {
  const f6 = v.forces6 && Object.keys(v.forces6).length ? combine(v.forces6, factorsFor(v, load), memberId) : null;
  if (f6 && f6.length >= 12) {
    const pick = (o: number): EndForces => ({ N: f6[o], V2: f6[o + 1], V3: f6[o + 2], T: f6[o + 3], M2: f6[o + 4], M3: f6[o + 5] });
    return { i: pick(0), j: pick(6), full: true };
  }
  const f = memberForces(v, load, memberId);
  if (!f) return null;
  const i = zero(), j = zero();
  i.N = j.N = f[0];
  i.V2 = f[1];
  j.V2 = f[1]; // compact row has only the i-end shear
  i.M3 = f[2];
  j.M3 = f[3];
  return { i, j, full: false };
}

export function inspectorRows(v: ViewerData, memberId: string): { rows: InspectorRow[]; full: boolean } {
  let full = false;
  const rows: InspectorRow[] = [];
  for (const load of loadOptions(v)) {
    const e = endForces(v, load, memberId);
    if (!e) continue;
    full = full || e.full;
    rows.push({ load, isCombo: !!v.combos[load], i: e.i, j: e.j });
  }
  return { rows, full };
}

export type Envelope = Record<ForceKey, { max: number; maxAt: string; min: number; minAt: string }>;

/** Envelope over the combos only (falls back to cases when there are no combos). */
export function envelope(rows: InspectorRow[]): Envelope | null {
  const src = rows.some((r) => r.isCombo) ? rows.filter((r) => r.isCombo) : rows;
  if (!src.length) return null;
  const out = {} as Envelope;
  for (const k of FORCE_KEYS) {
    let max = -Infinity, min = Infinity, maxAt = "", minAt = "";
    for (const r of src) for (const end of [r.i, r.j]) {
      if (end[k] > max) { max = end[k]; maxAt = r.load; }
      if (end[k] < min) { min = end[k]; minAt = r.load; }
    }
    out[k] = { max, maxAt, min, minAt };
  }
  return out;
}

export type SectionProps = { b: number; h: number; A: number; S2: number; S3: number; Av: number; E_mpa: number; material: string };

/** Rectangular gross section b×h (m); M3 bends about the local 3 axis (depth h), M2 about local 2 (width b). */
export function sectionProps(v: ViewerData, m: ViewerMember): SectionProps {
  const b = m.b > 0 ? m.b : 0.3, h = m.h > 0 ? m.h : 0.3;
  const steel = (v.material?.type ?? "concrete") === "steel";
  const fc = v.material?.fc_mpa && v.material.fc_mpa > 0 ? v.material.fc_mpa : 30;
  return { b, h, A: b * h, S3: (b * h * h) / 6, S2: (h * b * b) / 6, Av: (5 / 6) * b * h, E_mpa: steel ? 200000 : 4700 * Math.sqrt(fc), material: steel ? "steel" : `concrete f'c=${fc} MPa` };
}

export type Stress = { axial: number; bend3: number; bend2: number; sMax: number; sMin: number; tau2: number; tau3: number; epsMax: number; epsMin: number };

/** Elastic gross-section stresses (MPa, tension +) and strains at one end. Forces in kN / kN·m, N compression +. */
export function stresses(f: EndForces, s: SectionProps): Stress {
  const k = 1 / 1000; // kN/m² -> MPa
  const axial = (-f.N / s.A) * k;
  const bend3 = (Math.abs(f.M3) / s.S3) * k;
  const bend2 = (Math.abs(f.M2) / s.S2) * k;
  const sMax = axial + bend3 + bend2, sMin = axial - bend3 - bend2;
  return { axial, bend3, bend2, sMax, sMin, tau2: (Math.abs(f.V2) / s.Av) * k, tau3: (Math.abs(f.V3) / s.Av) * k, epsMax: sMax / s.E_mpa, epsMin: sMin / s.E_mpa };
}

/** Governing combo: the one with the largest |σ| at either end. */
export function governing(rows: InspectorRow[], s: SectionProps): string | null {
  const src = rows.some((r) => r.isCombo) ? rows.filter((r) => r.isCombo) : rows;
  let best: string | null = null, val = -1;
  for (const r of src) {
    const x = Math.max(...[r.i, r.j].map((e) => { const st = stresses(e, s); return Math.max(Math.abs(st.sMax), Math.abs(st.sMin)); }));
    if (x > val) { val = x; best = r.load; }
  }
  return best;
}
