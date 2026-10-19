import { describe, expect, it } from "vitest";

import { contourColor, fieldAt, pressureAt, sampleField, settlementAt, stripProfile } from "@/lib/foundation-view";
import type { ViewerFooting } from "@/lib/frame3d-viewer";

const f = (x: number, y: number, P: number, My = 0): ViewerFooting => ({
  column: `C${x}`, node: "N", x, y, position: "edge", B: 2, h: 0.4, info: { P_kn: P, Mx_kn_m: 0, My_kn_m: My, c1_m: 0.4, c2_m: 0.4, DC_punching: 0.8 },
});

describe("SAFE-like foundation fields (rigid footing + Winkler)", () => {
  it("pressure is P/A when concentric and linear with moment", () => {
    expect(pressureAt(f(0, 0, 400), 0.3, -0.2)).toBeCloseTo(100);
    const e = f(0, 0, 400, 40);
    expect(pressureAt(e, 1, 0)).toBeCloseTo(100 + (40 * 1) / (16 / 12));
    expect(pressureAt(e, 1, 0)).toBeGreaterThan(pressureAt(e, -1, 0));
  });
  it("moment is zero at the edge, largest at the column face; settlement = q/ks", () => {
    const g = f(0, 0, 400);
    expect(fieldAt(g, "mx", 0.999, 0, 150)).toBeLessThan(fieldAt(g, "mx", 0.2, 0, 150));
    expect(fieldAt(g, "mx", 0.2, 0, 150)).toBeCloseTo((100 * 0.8 * 0.8) / 2);
    expect(settlementAt(g, 0, 0, 150)).toBeCloseTo((100 / 18000) * 1000);
  });
  it("works for any layout and cuts strips through crossed footings only", () => {
    const fs = [f(0, 0, 400), f(5, 0, 800), f(0, 7, 300)];
    const s = sampleField(fs, "pressure", 150, 6);
    expect(s.grid).toHaveLength(3);
    expect(s.hi).toBeCloseTo(200);
    const strip = stripProfile(fs, "pressure", 150, 0.5);
    expect(new Set(strip.map((p) => Math.round(p.x / 5)))).toEqual(new Set([0, 1]));
    expect(contourColor(0)).toBe("rgb(37, 99, 235)");
    expect(contourColor(1)).toBe("rgb(239, 68, 68)");
  });
});
