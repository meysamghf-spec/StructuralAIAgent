import { describe, expect, it } from "vitest";
import {
  formatModelCounts,
  getAnalysisStatusLabel,
  getModelSectionLabel,
  getRevisionChangeLabel,
} from "../lib/model-workspace";

describe("model workspace display helpers", () => {
  it("maps analysis status to engineer-friendly labels", () => {
    expect(getAnalysisStatusLabel("NOT_CONFIGURED")).toBe("Not configured");
    expect(getAnalysisStatusLabel("READY_FOR_ANALYSIS_ENGINE")).toBe(
      "Ready for analysis engine",
    );
  });

  it("maps revision change types to readable labels", () => {
    expect(getRevisionChangeLabel("GEOMETRY_UPDATE")).toBe("Geometry updated");
    expect(getRevisionChangeLabel("LOADS_UPDATE")).toBe("Loads updated");
  });

  it("maps model section keys to readable labels", () => {
    expect(getModelSectionLabel("load_combinations")).toBe("Load combinations");
    expect(getModelSectionLabel("analysis_model")).toBe("Analysis model");
  });

  it("formats model inventory counts for cards", () => {
    const counts = formatModelCounts({
      grid_count: 2,
      level_count: 3,
      material_count: 1,
      section_count: 4,
      member_count: 10,
      support_count: 2,
      load_case_count: 5,
      load_combination_count: 6,
    });
    expect(counts).toHaveLength(8);
    expect(counts.find((item) => item.label === "Members")?.value).toBe(10);
  });
});
