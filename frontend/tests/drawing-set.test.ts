import { describe, expect, it } from "vitest";
import { groupDrawingSet, pendingSheetsAreAbsent, sheetAvailabilityLabel } from "../lib/drawing-set";
import type { DrawingSetIndex } from "../lib/drawing-set";

describe("PEM drawing set index", () => {
  it("keeps unproduced section and detail sheets out of the set", () => {
    const sheets = [
      { sheet_number: "S-201" },
      { sheet_number: "S-202" },
      { sheet_number: "S-203" },
    ];
    const pending = [
      { sheet_number: "S-301", availability: "NOT_GENERATED" },
      { sheet_number: "S-401", availability: "NOT_GENERATED" },
    ];
    expect(pendingSheetsAreAbsent(sheets, pending)).toBe(true);
    expect(sheetAvailabilityLabel("NOT_AVAILABLE")).toBe("Not available in the current PEM");
    expect(sheetAvailabilityLabel("NOT_GENERATED")).toBe("Not generated");
  });

  it("separates schedules from plans and ungenerated sheets", () => {
    const index: DrawingSetIndex = {
      project_id: "project-1",
      pem_snapshot_id: "snapshot-1",
      pem_version: 2,
      drawing_set_id: "DS-1",
      generated_at: "2026-01-01T00:00:00Z",
      disclaimers: [],
      sheets: [
        sheet("S-001", "STRUCTURAL", null),
        sheet("S-201", "STRUCTURAL", "S-201"),
        sheet("S-201.2", "STRUCTURAL", "S-201"),
        sheet("A-001", "ARCHITECTURAL", null),
      ],
      pending_sheets: [{ sheet_number: "S-301", title: "Structural sections", availability: "NOT_GENERATED" }],
    };
    const groups = groupDrawingSet(index);
    expect(groups.schedules.map((item) => item.sheet_number)).toEqual(["S-201", "S-201.2"]);
    expect(groups.structural.map((item) => item.sheet_number)).toEqual(["S-001"]);
    expect(groups.architectural.map((item) => item.sheet_number)).toEqual(["A-001"]);
    expect(groups.pending.map((item) => item.sheet_number)).toEqual(["S-301"]);
  });
});

function sheet(
  sheetNumber: string,
  discipline: string,
  scheduleFamily: string | null,
): DrawingSetIndex["sheets"][number] {
  return {
    sheet_number: sheetNumber,
    title: sheetNumber,
    discipline,
    availability: scheduleFamily ? "NOT_AVAILABLE" : "AVAILABLE",
    schedule_family: scheduleFamily,
    missing_data: [],
    content_signature: sheetNumber,
  };
}
