import { describe, expect, it } from "vitest";

import {
  getResultsAvailabilityMessage,
  getResultTypeLabel,
  getValidationStatusLabel,
} from "../lib/engineering-results-workspace";
import {
  getCadNextStep,
  getCadStatusLabel,
  getCadValidationLabel,
  getDrawingTypeLabel,
} from "../lib/cad-workspace";

describe("engineering results workspace labels", () => {
  it("maps validation statuses to friendly labels", () => {
    expect(getValidationStatusLabel("PARTIALLY_VALIDATED")).toBe(
      "Some results need engineering review",
    );
    expect(getValidationStatusLabel("REQUIRES_LOCAL_SOFTWARE")).toBe(
      "Local solver software required",
    );
  });

  it("describes results availability", () => {
    expect(getResultsAvailabilityMessage(false)).toBe("Analysis results are not available yet.");
    expect(getResultsAvailabilityMessage(true)).toContain("available");
  });

  it("formats result types", () => {
    expect(getResultTypeLabel("joint_displacements")).toBe("joint displacements");
  });
});

describe("cad workspace labels", () => {
  it("maps cad statuses to friendly labels", () => {
    expect(getCadStatusLabel("REQUIRES_LOCAL_SOFTWARE")).toBe(
      "AutoCAD 2027 is not available on this computer.",
    );
  });

  it("suggests next steps", () => {
    expect(getCadNextStep("REQUIRES_LOCAL_SOFTWARE", "DWG")).toContain("AutoCAD 2027");
    expect(getCadNextStep("SUCCESS", "DXF")).toContain("generated drawing");
  });

  it("formats drawing types and validation labels", () => {
    expect(getDrawingTypeLabel("FRAMING_PLAN")).toBe("Framing plan");
    expect(getDrawingTypeLabel("COLUMN_PLAN")).toBe("Column plan");
    expect(getDrawingTypeLabel("BEAM_PLAN")).toBe("Beam plan");
    expect(getDrawingTypeLabel("SLAB_PLAN")).toBe("Slab plan");
    expect(getCadValidationLabel("VALIDATED")).toBe("Drawing validated");
  });
});
