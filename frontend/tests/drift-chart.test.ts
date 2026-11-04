import { describe, expect, it } from "vitest";
import { fmtTick, hasDisplacement, niceTicks, seriesFor } from "@/lib/drift-chart";
import type { Frame3dDriftRow } from "@/lib/chat-types";

const rows: Frame3dDriftRow[] = [
  { direction: "X", storey: 2, driftElasticMm: 12, ratioElasticPct: 0.4, ratioAmplifiedPct: 1.8, uMaxMm: 22 },
  { direction: "X", storey: 1, driftElasticMm: 10, ratioElasticPct: 0.3, ratioAmplifiedPct: 1.4, uMaxMm: 10 },
  { direction: "Y", storey: 1, driftElasticMm: 9, ratioElasticPct: 0.3, ratioAmplifiedPct: null },
];

describe("drift chart helpers", () => {
  it("nice ticks cover the max", () => {
    expect(niceTicks(94.18)).toEqual([0, 20, 40, 60, 80, 100]);
    expect(niceTicks(2)).toEqual([0, 0.5, 1, 1.5, 2]);
    expect(niceTicks(0)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1]);
  });
  it("formats ticks", () => {
    expect(fmtTick(0)).toBe("0");
    expect(fmtTick(2.5)).toBe("2.5");
    expect(fmtTick(1081.04)).toBe("1081");
  });
  it("series are sorted by storey, start at storey 1 (no fake base point) and skip nulls", () => {
    expect(seriesFor(rows, "X", "drift").map((p) => [p.storey, p.v])).toEqual([[1, 1.4], [2, 1.8]]);
    expect(seriesFor(rows, "X", "disp").map((p) => p.v)).toEqual([10, 22]);
    expect(seriesFor(rows, "Y", "drift")).toEqual([]);
    expect(hasDisplacement(rows)).toBe(true);
    expect(hasDisplacement([rows[2]])).toBe(false);
  });
});
