import { describe, expect, it } from "vitest";
import {
  formatAnalysisInventory,
  getAnalysisCapabilityLabel,
  getAnalysisStatusLabel,
} from "../lib/analysis-workspace";

describe("analysis workspace display helpers", () => {
  it("maps analysis statuses to engineer-friendly labels", () => {
    expect(getAnalysisStatusLabel("REQUIRES_SOLVER")).toBe("Solver required");
    expect(getAnalysisStatusLabel("MODEL_NOT_READY")).toBe("Model not ready");
  });

  it("maps capability guidance for unavailable solver execution", () => {
    expect(getAnalysisCapabilityLabel("REQUIRES_SOLVER")).toContain("solver");
  });

  it("formats model inventory for cards", () => {
    const items = formatAnalysisInventory({
      member_count: 4,
      support_count: 2,
      load_case_count: 3,
      load_combination_count: 5,
      level_count: 2,
    });
    expect(items.some((item) => item.startsWith("Members:"))).toBe(true);
    expect(items).toHaveLength(5);
  });
});
