import { describe, expect, it } from "vitest";
import { mapViewerData } from "@/lib/frame3d-viewer";
import { endForces, envelope, governing, inspectorRows, sectionProps, stresses } from "@/lib/member-inspector";

const raw = {
  nodes: [{ id: "a", x: 0, y: 0, z: 0 }, { id: "b", x: 0, y: 0, z: 3 }],
  members: [{ id: "C1", i: "a", j: "b", type: "column", storey: 1, b: 0.4, h: 0.4, section: "C40x40" }],
  cases: ["D", "L"],
  combos: { "1.4D": { D: 1.4 }, "1.2D+1.6L": { D: 1.2, L: 1.6 } },
  forces: { D: { C1: [100, 5, 10, -8, 0] }, L: { C1: [50, 2, 4, -3, 0] } },
  forces6: { D: { C1: [100, 5, 1, 0.5, 2, 10, 100, 5, 1, 0.5, 1, -8] }, L: { C1: [50, 2, 0, 0, 0, 4, 50, 2, 0, 0, 0, -3] } },
  material: { type: "concrete", fc_mpa: 25 },
};

describe("member inspector", () => {
  const v = mapViewerData(raw)!;
  const m = v.members[0];
  it("combines full end forces per combo", () => {
    const e = endForces(v, "1.2D+1.6L", "C1")!;
    expect(e.full).toBe(true);
    expect(e.i.N).toBeCloseTo(200);
    expect(e.i.M3).toBeCloseTo(18.4);
    expect(e.i.T).toBeCloseTo(0.6);
  });
  it("envelope and governing use combos", () => {
    const { rows } = inspectorRows(v, "C1");
    expect(rows.length).toBe(4);
    const env = envelope(rows)!;
    expect(env.N.max).toBeCloseTo(200);
    expect(env.N.maxAt).toBe("1.2D+1.6L");
    expect(governing(rows, sectionProps(v, m))).toBe("1.2D+1.6L");
  });
  it("elastic stresses and strain", () => {
    const s = sectionProps(v, m);
    expect(s.E_mpa).toBeCloseTo(23500);
    const st = stresses({ N: 160, V2: 0, V3: 0, T: 0, M2: 0, M3: 10.6667 }, s);
    expect(st.axial).toBeCloseTo(-1.0);
    expect(st.bend3).toBeCloseTo(1.0, 2);
    expect(st.epsMin).toBeCloseTo(-2 / 23500, 6);
  });
  it("falls back to the compact row", () => {
    const v2 = mapViewerData({ ...raw, forces6: undefined })!;
    const e = endForces(v2, "D", "C1")!;
    expect(e.full).toBe(false);
    expect(e.j.M3).toBe(-8);
  });
});
