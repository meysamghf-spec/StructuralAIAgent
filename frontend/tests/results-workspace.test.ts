import { describe, expect, it } from "vitest";

import { getValidationStatusLabel, getResultsAvailabilityMessage } from "../lib/engineering-results-workspace";
import {
  formatValidationFindings,
  getResultReadinessMessage,
  getResultTypeLabels,
  summarizeResultLineage,
} from "../lib/results-workspace";

describe("results workspace helpers", () => {
  it("describes readiness from validation and availability", () => {
    expect(getResultReadinessMessage("VALIDATED", true)).toContain("available");
    expect(getResultReadinessMessage("INCOMPLETE", false)).toContain("not available");
  });

  it("formats result types for cards", () => {
    expect(getResultTypeLabels(["frame_forces", "joint_displacements"])).toEqual([
      "frame forces",
      "joint displacements",
    ]);
  });

  it("reuses engineering result labels", () => {
    expect(getValidationStatusLabel("PARTIALLY_VALIDATED")).toContain("review");
    expect(getResultsAvailabilityMessage(false)).toContain("not available");
  });

  it("summarizes traceability lineage in plain language", () => {
    const summary = summarizeResultLineage([
      {
        id: "1",
        source_type: "analysis_result",
        target_type: "engineering_result",
        relationship_type: "ANALYSIS_TO_RESULT",
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    expect(summary[0]).toContain("Analysis result");
    expect(summary[0]).toContain("Validated solver result");
  });

  it("extracts validation findings from summary payload", () => {
    expect(
      formatValidationFindings({
        findings: [{ message: "Missing modal periods" }],
      }),
    ).toEqual(["Missing modal periods"]);
  });
});
