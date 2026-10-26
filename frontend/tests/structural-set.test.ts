import { describe, expect, it } from "vitest";
import { mapStructuralSet } from "@/lib/structural-set";

describe("mapStructuralSet", () => {
  it("maps chat metadata", () => {
    const s = mapStructuralSet({
      id: "a".repeat(32),
      sheets: [{ sheet_no: "S-101", title: "Column layout", title_fa: "پلان", scale: "1:100", job_id: "j", filename: "S-101.dxf", file_id: null }],
      notes: ["x"],
      pdf: true,
      pdf_file_id: "f",
    });
    expect(s?.sheets[0].sheet_no).toBe("S-101");
    expect(s?.pdf).toBe(true);
    expect(s?.notes).toEqual(["x"]);
  });
  it("rejects junk", () => {
    expect(mapStructuralSet(null)).toBeNull();
    expect(mapStructuralSet({ id: 3 })).toBeNull();
  });
});
