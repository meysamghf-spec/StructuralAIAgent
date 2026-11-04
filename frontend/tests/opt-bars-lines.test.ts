import { describe, expect, it } from "vitest";
import { barsLines } from "@/lib/optimization-full";

describe("barsLines", () => {
  it("splits top/bottom into stacked Persian-labelled lines", () => {
    expect(barsLines({ top_bars: "3Φ25", bottom_bars: "3Φ22" } as never)).toEqual([
      { label: "بالا", value: "3Φ25" },
      { label: "پایین", value: "3Φ22" },
    ]);
  });
  it("returns null for single bars string (columns)", () => {
    expect(barsLines({ bars: "8Φ20" } as never)).toBeNull();
  });
});
