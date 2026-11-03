import { describe, expect, it } from "vitest";

import { approvalStatus, filterRows, memberDesignRows, memberForceRows } from "@/lib/chat-full-results";
import { mapOptimizationFull } from "@/lib/chat-mappers";
import type { Frame3dResults } from "@/lib/chat-types";
import type { ViewerData } from "@/lib/frame3d-viewer";

const viewer = {
  nodes: [], supports: [], footings: [], levels: [], xs: [], ys: [], zs: [], modes: [], displacements: {}, reactions: {},
  members: [
    { id: "B1", type: "beam", storey: 1, section: "30x50", dc: 0.8, rebar: "3Φ18", designStatus: "PASS", group: "B-S1" },
    { id: "C1", type: "column", storey: 1, section: "40x40", dc: 1.2, rebar: "8Φ20", designStatus: null, group: null },
    { id: "C2", type: "column", storey: 2, section: "40x40", dc: null, rebar: null, designStatus: null, group: null },
  ],
  cases: ["DEAD", "LIVE"],
  combos: { "1.2D+1.6L": { DEAD: 1.2, LIVE: 1.6 } },
  forces: { DEAD: { B1: [1, 10, 20, -20, 0], C1: [-100, 2, 3, 4, 0] }, LIVE: { B1: [0, 5, 10, -10, 0] } },
} as unknown as ViewerData;

describe("chat full results helpers", () => {
  it("lists every member's forces for a combo", () => {
    const rows = memberForceRows(viewer, "1.2D+1.6L");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toMatchObject({ id: "B1", Vi: 20, Mi: 40 });
    expect(rows[1]).toMatchObject({ id: "C1", N: -120 });
    expect(rows[2].N).toBeNull();
  });

  it("builds per-member design rows with pass/fail", () => {
    const rows = memberDesignRows(viewer);
    expect(rows.map((r) => r.id)).toEqual(["B1", "C1"]);
    expect(rows[1].status).toBe("FAIL");
    expect(filterRows(rows, "column").map((r) => r.id)).toEqual(["C1"]);
    expect(filterRows(rows, "1")).toHaveLength(2);
  });

  it("derives approval status", () => {
    const base = { drift: [], driftReferenceLimitPct: 0.5, design: { status: "PASS", beams: [{ DC: 0.7 }], columns: [] }, baseShearStatus: null, driftCheck: null } as unknown as Frame3dResults;
    expect(approvalStatus(base).state).toBe("pass");
    expect(approvalStatus({ ...base, design: { ...base.design!, columns: [{ DC_shear: 1.3 }] } } as unknown as Frame3dResults).state).toBe("fail");
    expect(approvalStatus({ ...base, design: null } as unknown as Frame3dResults).state).toBe("review");
    expect(approvalStatus({ ...base, drift: [{ ratioAmplifiedPct: 0.9 }] } as unknown as Frame3dResults).state).toBe("fail");
  });

  it("maps optimization_full chat payloads", () => {
    const result = { feasible: true, groups: [], cost: 1 };
    expect(mapOptimizationFull({ optimization_full: { status: "done", result, source_fa: "قاب پیش‌فرض" } })).toMatchObject({ status: "done", sourceFa: "قاب پیش‌فرض" });
    expect(mapOptimizationFull({ kind: "optimization_full", status: "error", error: "x", result: null })).toMatchObject({ status: "error", error: "x" });
    expect(mapOptimizationFull({ kind: "frame3d" })).toBeNull();
    expect(mapOptimizationFull(null)).toBeNull();
  });
});
