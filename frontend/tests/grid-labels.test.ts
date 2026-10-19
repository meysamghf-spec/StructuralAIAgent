import { describe, expect, it } from "vitest";
import { GRID_LEGEND, gridLabelX, gridLabelY } from "@/lib/frame3d-viewer";

describe("grid naming matches the DXF drawings", () => {
  it("numbers lines along X and letters lines along Y", () => {
    expect([0, 1, 2].map(gridLabelX)).toEqual(["1", "2", "3"]);
    expect([0, 1, 25, 26].map(gridLabelY)).toEqual(["A", "B", "Z", "AA"]);
    expect(GRID_LEGEND).toContain("⟂ X");
  });
});
