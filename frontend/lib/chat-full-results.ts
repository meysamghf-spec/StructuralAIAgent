// Pure helpers for the inline "all results in chat" sections (unit-testable, no React).
import type { Frame3dResults } from "./chat-types";
import { memberForces, type ViewerData } from "./frame3d-viewer";

export type MemberForceRow = { id: string; type: string; storey: number; section: string; N: number | null; Vi: number | null; Mi: number | null; Mj: number | null };
export type MemberDesignRow = { id: string; type: string; storey: number; section: string; group: string; rebar: string; dc: number | null; status: string };
export type ApprovalState = "pass" | "fail" | "review";

const r1 = (x: number | undefined) => (typeof x === "number" && Number.isFinite(x) ? Math.round(x * 10) / 10 : null);

/** All members' end forces for one load case / combination. f = [N, Vi, Mi, Mj, w]. */
export function memberForceRows(v: ViewerData, load: string): MemberForceRow[] {
  return v.members.map((m) => {
    const f = memberForces(v, load, m.id);
    return { id: m.id, type: m.type, storey: m.storey, section: m.section, N: r1(f?.[0]), Vi: r1(f?.[1]), Mi: r1(f?.[2]), Mj: r1(f?.[3]) };
  });
}

/** Per-member design: section, bars, D/C and pass/fail, from the viewer members (filled by the Mabhas 9 design). */
export function memberDesignRows(v: ViewerData): MemberDesignRow[] {
  return v.members
    .filter((m) => m.dc !== null || m.rebar || m.designStatus)
    .map((m) => ({
      id: m.id, type: m.type, storey: m.storey, section: m.section, group: m.group ?? "—", rebar: m.rebar ?? "—", dc: m.dc,
      status: m.designStatus ?? (m.dc === null ? "—" : m.dc <= 1 ? "PASS" : "FAIL"),
    }));
}

export function filterRows<T extends { id: string; type: string; storey: number }>(rows: T[], q: string): T[] {
  const s = q.trim().toLowerCase();
  if (!s) return rows;
  return rows.filter((r) => r.id.toLowerCase().includes(s) || r.type.includes(s) || String(r.storey) === s);
}

/**
 * Validation / approval status of a chat frame run (AI suggestion only; the engineer signs off):
 * fail when a member D/C > 1, the design failed or drift exceeds the limit; review when a check is missing or not
 * conclusive; pass otherwise.
 */
export function approvalStatus(r: Frame3dResults): { state: ApprovalState; reasons: string[] } {
  const reasons: string[] = [];
  let fail = false;
  let review = false;
  const lim = r.driftReferenceLimitPct;
  const over = lim === null ? [] : r.drift.filter((d) => d.ratioAmplifiedPct !== null && d.ratioAmplifiedPct > lim);
  if (over.length) { fail = true; reasons.push(`drift > ${lim}% (${over.length})`); }
  if (r.design) {
    const bad = [...r.design.beams, ...r.design.columns].filter((row) => {
      const dcs = [row.DC, row.DC_flexure, row.DC_shear].map((x) => Number(x)).filter((x) => Number.isFinite(x));
      return dcs.some((x) => x > 1);
    });
    if (bad.length) { fail = true; reasons.push(`D/C > 1 (${bad.length})`); }
    if (r.design.status !== "PASS" && !bad.length) { review = true; reasons.push(`design: ${r.design.status}`); }
  } else {
    review = true; reasons.push("no member design");
  }
  if (r.baseShearStatus && !/ok|pass|match/i.test(r.baseShearStatus)) { review = true; reasons.push(`base shear: ${r.baseShearStatus}`); }
  if (r.driftCheck && /fail|not/i.test(r.driftCheck) && !over.length) { review = true; reasons.push(`drift: ${r.driftCheck}`); }
  return { state: fail ? "fail" : review ? "review" : "pass", reasons };
}
