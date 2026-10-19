import { describe, expect, it } from "vitest";
import {
  autoDeformScale,
  baseReactions,
  dcColor,
  diagramValues,
  explorerTree,
  factorsFor,
  loadOptions,
  mapViewerData,
  memberForces,
  memberLength,
  nodeDisplacement,
  storeyShears,
} from "@/lib/frame3d-viewer";

const raw = {
  nodes: [
    { id: "N0", x: 0, y: 0, z: 0 },
    { id: "N1", x: 0, y: 0, z: 3 },
    { id: "N2", x: 5, y: 0, z: 3 },
  ],
  supports: ["N0"],
  members: [
    { id: "C0", i: "N0", j: "N1", type: "column", storey: 1, section: "C40x40", b: 0.4, h: 0.4, group: "C-S1", dc: 0.5, design_status: "PASS", rebar: "8Φ16" },
    { id: "B0", i: "N1", j: "N2", type: "beam", storey: 1, section: "B30x45", b: 0.3, h: 0.45, group: null, dc: null },
  ],
  cases: ["D", "L"],
  combos: { "1.2D+1.6L": { D: 1.2, L: 1.6 } },
  forces: { D: { B0: [0, 30, -20, -20, -12], C0: [100, 2, 5, -1, 0] }, L: { B0: [0, 10, -5, -5, -4], C0: [20, 1, 1, 0, 0] } },
  displacements_mm: { D: { N1: [0, 0, -1], N2: [0, 0, -2] }, L: { N1: [0, 0, -0.5], N2: [0, 0, -1] } },
  reactions: { D: { N0: [1, 2, 100, 0, 0, 0] }, L: { N0: [0, 0, 20, 0, 0, 0] } },
  footings: [{ column: "C0_0", node: "N0", x: 0, y: 0, position: "corner", B_m: 1.8, h_m: 0.4 }],
  diaphragm_levels: [1],
};

describe("frame3d viewer helpers", () => {
  const v = mapViewerData(raw)!;
  it("maps the payload", () => {
    expect(v.members[0].type).toBe("column");
    expect(v.members[1].dc).toBeNull();
    expect(v.footings[0].B).toBe(1.8);
    expect(v.xs).toEqual([0, 5]);
    expect(v.zs).toEqual([0, 3]);
    expect(mapViewerData(null)).toBeNull();
  });
  it("combines cases into combos linearly", () => {
    expect(loadOptions(v)).toEqual(["D", "L", "1.2D+1.6L"]);
    expect(factorsFor(v, "D")).toEqual({ D: 1 });
    expect(memberForces(v, "1.2D+1.6L", "C0")![0]).toBeCloseTo(152);
    expect(nodeDisplacement(v, "1.2D+1.6L", "N2")[2]).toBeCloseTo(-4);
    expect(nodeDisplacement(v, "D", "N0")).toEqual([0, 0, 0]);
    const r = baseReactions(v, "1.2D+1.6L");
    expect(r[0].values[2]).toBeCloseTo(152);
  });
  it("builds a parabolic M3 diagram with the analytical midspan value", () => {
    const L = memberLength(v, v.members[1]);
    expect(L).toBe(5);
    const m = diagramValues([0, 0, -20, -20, -12], L, "M3", 10);
    // M_mid = Mi - wL^2/8 = -20 + 12*25/8 = 17.5
    expect(m[5]).toBeCloseTo(17.5);
    expect(m[0]).toBeCloseTo(-20);
    const vv = diagramValues([0, 0, -20, -20, -12], L, "V2", 2);
    expect(vv[0]).toBeCloseTo(30);
    expect(vv[2]).toBeCloseTo(-30);
    expect(diagramValues([7, 0, 0, 0, 0], L, "P", 2)).toEqual([7, 7, 7]);
  });
  it("colours D/C ratios and builds the explorer tree", () => {
    expect(dcColor(0.5)).toBe("#43a047");
    expect(dcColor(0.8)).toBe("#fdd835");
    expect(dcColor(0.95)).toBe("#fb8c00");
    expect(dcColor(1.2)).toBe("#e53935");
    expect(dcColor(null)).toBe("#9aa4b1");
    const tree = explorerTree(v);
    expect(tree.map((g) => g.items.length)).toEqual([1, 1, 1]);
    expect(autoDeformScale(v, "D")).toBeGreaterThan(0);
  });
  it("accumulates storey shears from the top", () => {
    expect(storeyShears({ "1": 100, "2": 200, "3": 300 })).toEqual([
      { storey: 3, forceKn: 300, shearKn: 300 },
      { storey: 2, forceKn: 200, shearKn: 500 },
      { storey: 1, forceKn: 100, shearKn: 600 },
    ]);
  });
});
