import { describe, expect, it } from "vitest";
import { convergenceSeries, formatObjective, type FrameOptimizationResult } from "@/lib/frame-optimizer";

describe("frame optimizer helpers", () => {
  it("builds a combined FSD + GA convergence series", () => {
    const res = {
      convergence: {
        fsd: [{ iteration: 1, objective: 10, feasible: true }, { iteration: 2, objective: 8, feasible: true }],
        ga: [{ generation: 0, best_objective: 7, feasible: true, evaluations: 5 }],
      },
    } as unknown as FrameOptimizationResult;
    const s = convergenceSeries(res);
    expect(s.map((p) => p.y)).toEqual([10, 8, 7]);
    expect(s.map((p) => p.stage)).toEqual(["fsd", "fsd", "ga"]);
  });
  it("formats objective units", () => {
    expect(formatObjective(1234.4, "cost")).toBe("1,234 toman");
    expect(formatObjective(99.6, "weight")).toBe("100 kg");
  });
});
