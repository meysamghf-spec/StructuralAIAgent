import { describe, expect, it } from "vitest";
import { DESIGN_LEGEND, dcDisplay, rebarBasisTag } from "@/lib/design-dc";

describe("design D/C display (pt616u)", () => {
  it("formats normal ratios with 3 digits", () => {
    expect(dcDisplay(0.8123).text).toBe("0.812");
    expect(dcDisplay(1.2).over).toBe(true);
    expect(dcDisplay(null).text).toBe("—");
  });
  it("replaces the 999 sentinel with NG and a tooltip", () => {
    const d = dcDisplay(999);
    expect(d.text).toBe("NG");
    expect(d.ng).toBe(true);
    expect(d.title).toMatch(/enlarge/);
    expect(dcDisplay("-999").text).toBe("NG");
  });
  it("caps very large ratios at >10 with the value in the tooltip", () => {
    const d = dcDisplay(11.71);
    expect(d.text).toBe(">10");
    expect(d.title).toContain("11.71");
    expect(dcDisplay(9.99).text).toBe("9.990");
  });
  it("tags NG reinforcement basis", () => {
    expect(rebarBasisTag("MAX_FEASIBLE")?.short).toBe("NG·max");
    expect(rebarBasisTag("MINIMUM")?.short).toBe("NG·min");
    expect(rebarBasisTag("DESIGN")).toBeNull();
  });
  it("has a bilingual legend with units", () => {
    expect(DESIGN_LEGEND.every((l) => l.en && l.fa)).toBe(true);
    expect(DESIGN_LEGEND.map((l) => l.en).join(" ")).toContain("kN·m");
  });
});
