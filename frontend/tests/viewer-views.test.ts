import { describe, expect, it } from "vitest";

import { orthoCamera, planStorey, viewMembers, type ViewerData } from "@/lib/frame3d-viewer";

// 2x1 bays, 2 storeys; generic data (no RC-specific fields used)
const xs = [0, 5, 10], ys = [0, 4], zs = [0, 3, 6];
const nodes = xs.flatMap((x, i) => ys.flatMap((y, j) => zs.map((z, k) => ({ id: `N${i}${j}${k}`, x, y, z }))));
const members = [
  ...xs.flatMap((_, i) => ys.flatMap((_, j) => [1, 2].map((k) => ({ id: `C${i}${j}${k}`, i: `N${i}${j}${k - 1}`, j: `N${i}${j}${k}`, type: "column", storey: k })))),
  ...[1, 2].flatMap((k) => ys.flatMap((_, j) => [0, 1].map((i) => ({ id: `BX${i}${j}${k}`, i: `N${i}${j}${k}`, j: `N${i + 1}${j}${k}`, type: "beam", storey: k })))),
  ...[1, 2].flatMap((k) => xs.map((_, i) => ({ id: `BY${i}${k}`, i: `N${i}0${k}`, j: `N${i}1${k}`, type: "beam", storey: k }))),
];
const v = { xs, ys, zs, nodes, members, levels: [1, 2] } as unknown as ViewerData;

describe("viewer plan / elevation views", () => {
  it("plan shows the selected storey, or the top storey when All", () => {
    expect(planStorey(v, null)).toBe(2);
    expect(viewMembers(v, "PLAN", null, null).every((m) => m.storey === 2)).toBe(true);
    expect(viewMembers(v, "PLAN", 1, null).every((m) => m.storey === 1)).toBe(true);
  });
  it("elevations keep only the frame on the chosen grid line", () => {
    const ex = viewMembers(v, "ELEV_X", null, 1).map((m) => m.id);
    expect(ex).toContain("BX011");
    expect(ex.some((id) => id.startsWith("BY"))).toBe(false); // Y beams cross the line, not on it
    const ey = viewMembers(v, "ELEV_Y", null, 2).map((m) => m.id);
    expect(ey).toEqual(expect.arrayContaining(["BY21", "C201", "C212"]));
    expect(ey.some((id) => id.startsWith("BX"))).toBe(false);
    expect(viewMembers(v, "ELEV_X", null, null)).toHaveLength(members.length);
  });
  it("orthographic cameras look straight down / along the axes", () => {
    const p = orthoCamera(v, "PLAN", null, null, 1.5);
    expect(p.pos.slice(0, 2)).toEqual(p.target.slice(0, 2));
    expect(p.target[2]).toBe(6);
    const e = orthoCamera(v, "ELEV_X", null, 1, 1.5);
    expect(e.target[1]).toBe(4);
    expect(e.pos[1]).toBeLessThan(4);
    expect(e.up).toEqual([0, 0, 1]);
    expect(e.halfW / e.halfH).toBeCloseTo(1.5);
  });
});
