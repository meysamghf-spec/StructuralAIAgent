import { describe, expect, it } from "vitest";
import {
  formatDesignInventory,
  getDesignCapabilityLabel,
  getDesignStatusLabel,
} from "../lib/design-workspace";

describe("design workspace display helpers", () => {
  it("maps design statuses to engineer-friendly labels", () => {
    expect(getDesignStatusLabel("REQUIRES_ANALYSIS")).toBe("Analysis results required");
    expect(getDesignStatusLabel("MODEL_NOT_READY")).toBe("Model not ready");
  });

  it("provides plain-language capability guidance", () => {
    expect(getDesignCapabilityLabel("REQUIRES_SOLVER")).toContain("design engine");
    expect(getDesignCapabilityLabel("REQUIRES_SOLVER", "fa")).toContain("موتور");
  });

  it("formats design inventory for cards", () => {
    const items = formatDesignInventory({
      member_count: 3,
      material_count: 2,
      section_count: 4,
      load_combination_count: 1,
    });
    expect(items).toHaveLength(4);
  });
});
