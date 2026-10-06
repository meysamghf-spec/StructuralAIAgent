import { describe, expect, it } from "vitest";
import { polygonPoints, spaceFill } from "../lib/building";

describe("building plan helpers", () => {
  it("serializes polygon points for SVG", () => {
    expect(polygonPoints([{ x: 0, y: 0 }, { x: 12, y: 0 }, { x: 12, y: 22 }])).toBe(
      "0,0 12,0 12,22",
    );
  });

  it("uses distinct fills for bedrooms and stairs", () => {
    expect(spaceFill("BEDROOM")).not.toBe(spaceFill("STAIR"));
  });
});
