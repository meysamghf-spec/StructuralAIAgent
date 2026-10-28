import type { Frame3dDesign } from "./chat-types";

export type DesignSummary = {
  beamGroups: number;
  columnGroups: number;
  maxBeamFlexureDc: number | null;
  maxBeamShearDc: number | null;
  maxColumnDc: number | null;
  /** Largest demand/capacity ratio over every beam and column group. */
  maxDc: number | null;
  /** Groups whose D/C is above 1.0 (over-stressed). */
  overstressedGroups: number;
  /** Smallest ΣMnc/ΣMnb over all levels (strong column / weak beam). */
  scwbMinRatio: number | null;
};

function num(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function maxOf(rows: Array<Record<string, string | number | null>>, key: string): number | null {
  const values = rows.map((row) => num(row[key])).filter((v): v is number => v !== null);
  return values.length ? Math.max(...values) : null;
}

function minOf(rows: Array<Record<string, string | number | null>>, key: string): number | null {
  const values = rows.map((row) => num(row[key])).filter((v): v is number => v !== null);
  return values.length ? Math.min(...values) : null;
}

/** KPI numbers for the Design page, derived only from the Mabhas 9 design rows of the latest frame run. */
export function summarizeDesign(design: Pick<Frame3dDesign, "beams" | "columns" | "scwb">): DesignSummary {
  const maxBeamFlexureDc = maxOf(design.beams, "DC_flexure");
  const maxBeamShearDc = maxOf(design.beams, "DC_shear");
  const maxColumnDc = maxOf(design.columns, "DC");
  const all = [maxBeamFlexureDc, maxBeamShearDc, maxColumnDc].filter((v): v is number => v !== null);
  const overstressed =
    design.beams.filter((row) => (num(row.DC_flexure) ?? 0) > 1 || (num(row.DC_shear) ?? 0) > 1).length +
    design.columns.filter((row) => (num(row.DC) ?? 0) > 1).length;
  return {
    beamGroups: design.beams.length,
    columnGroups: design.columns.length,
    maxBeamFlexureDc,
    maxBeamShearDc,
    maxColumnDc,
    maxDc: all.length ? Math.max(...all) : null,
    overstressedGroups: overstressed,
    scwbMinRatio: minOf(design.scwb, "min_ratio"),
  };
}
