import { describe, expect, it } from "vitest";
import { pendingSheetsAreAbsent, sheetAvailabilityLabel } from "../lib/drawing-set";

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
});
