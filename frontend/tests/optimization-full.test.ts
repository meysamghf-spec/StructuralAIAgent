import { describe, expect, it } from "vitest";
import { barsLabel, candLabel, isActive, savingsPct, type OptGroup, type OptJob } from "@/lib/optimization-full";

describe("full optimization helpers", () => {
  it("labels rectangular and steel candidates", () => {
    expect(candLabel([0.4, 0.6])).toBe("40×60");
    expect(candLabel("IPE300")).toBe("IPE300");
  });
  it("shows column bars or beam top/bottom bars", () => {
    expect(barsLabel({ bars: "12Φ20" } as OptGroup)).toBe("12Φ20");
    expect(barsLabel({ top_bars: "4Φ18", bottom_bars: "3Φ16" } as OptGroup)).toContain("4Φ18");
    expect(barsLabel({} as OptGroup)).toBe("—");
  });
  it("computes savings and job activity", () => {
    expect(savingsPct({ cost: 90, initial_cost: 100 })).toBe(10);
    expect(savingsPct({ cost: 90, initial_cost: null })).toBeNull();
    expect(isActive({ status: "running" } as OptJob)).toBe(true);
    expect(isActive({ status: "done" } as OptJob)).toBe(false);
    expect(isActive(null)).toBe(false);
  });
});

import { costChangeText } from "@/lib/optimization-full";
describe("costChangeText", () => {
  it("never shows a negative reduction", () => {
    expect(costChangeText({ cost: 90, initial_cost: 100 })).toContain("کاهش");
    const t = costChangeText({ cost: 162, initial_cost: 100, initial_feasible: false });
    expect(t).toContain("افزایش هزینه");
    expect(t).toContain("پاس نمی‌کرد");
    expect(t).not.toContain("−");
  });
});
