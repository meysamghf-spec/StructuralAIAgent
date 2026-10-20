import { describe, expect, it } from "vitest";

import { mapViewerData } from "@/lib/frame3d-viewer";
import { modeOffset, parseModes, requestedMode } from "@/lib/frame3d-viewer";

const raw = [
  { mode: 1, T_s: 0.5, freq_hz: 2, mass_x_pct: 80, mass_y_pct: 0, mass_rz_pct: 1, disp: { A: [1, 0, 0], B: [0.5, 0, 0] } },
  { mode: 2, T_s: 0.25, mass_x_pct: 0, mass_y_pct: 79, mass_rz_pct: 0, disp: { A: [0, 1, 0] } },
];

describe("mode shape animation (generic)", () => {
  it("parses modes with T, f and mass participation", () => {
    const m = parseModes(raw);
    expect(m.map((x) => [x.mode, x.T, x.freq])).toEqual([[1, 0.5, 2], [2, 0.25, 4]]);
    expect(m[1].mass).toEqual({ ux: 0, uy: 79, rz: 0 });
    expect(parseModes(null)).toEqual([]);
  });

  it("animates node displacement sinusoidally and leaves unknown nodes still", () => {
    const [m] = parseModes(raw);
    expect(modeOffset(m, "A", 2, 0.25, 1)[0]).toBeCloseTo(2); // sin(π/2)
    expect(modeOffset(m, "B", 2, 0.25, 1)[0]).toBeCloseTo(1);
    expect(modeOffset(m, "A", 2, 0.5, 1)[0]).toBeCloseTo(0);
    expect(modeOffset(m, "Z", 2, 0.25, 1)).toEqual([0, 0, 0]);
  });

  it("reads the chat command and maps viewer data for any model", () => {
    expect(requestedMode("مود ۲ را نشان بده")).toBe(2);
    expect(requestedMode("animate mode 3")).toBe(3);
    const v = mapViewerData({ nodes: [{ id: "A", x: 0, y: 0, z: 0 }, { id: "B", x: 0, y: 0, z: 3 }], members: [{ id: "M", i: "A", j: "B", type: "column" }], modes: raw });
    expect(v?.modes.length).toBe(2);
  });
});
