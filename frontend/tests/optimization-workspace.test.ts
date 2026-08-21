import { describe, expect, it } from "vitest";
import {
  formatMemberOptimizationResults,
  formatOptimizationInventory,
  formatOptimizationMode,
  getOptimizationCapabilityLabel,
  getOptimizationStatusLabel,
} from "../lib/optimization-workspace";

describe("optimization workspace display helpers", () => {
  it("maps optimization statuses to engineer-friendly labels", () => {
    expect(getOptimizationStatusLabel("REQUIRES_ANALYSIS")).toBe("Analysis results required");
    expect(getOptimizationStatusLabel("REQUIRES_SOLVER")).toBe("Optimization engine required");
  });

  it("provides plain-language capability guidance", () => {
    expect(getOptimizationCapabilityLabel("REQUIRES_SOLVER")).toContain("optimization engine");
    expect(getOptimizationCapabilityLabel("REQUIRES_SOLVER", "fa")).toContain("موتور");
  });

  it("formats optimization inventory for cards", () => {
    const items = formatOptimizationInventory({
      member_count: 3,
      material_count: 2,
      section_count: 4,
      load_combination_count: 1,
    });
    expect(items).toHaveLength(4);
  });

  it("formats multi-member optimization results", () => {
    const lines = formatMemberOptimizationResults({
      optimization_mode: "INDEPENDENT",
      member_results: [
        {
          member_name: "B1",
          selected_section_name: "W18x35",
          governing_utilization: 0.82,
        },
      ],
    });
    expect(lines[0]).toContain("B1");
    expect(lines[0]).toContain("W18x35");
  });
});
