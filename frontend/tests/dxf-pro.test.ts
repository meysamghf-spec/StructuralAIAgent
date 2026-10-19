import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { logicalText, parseDxf } from "@/lib/dxf";

describe("in-app DXF viewer reads the office-standard drawings", () => {
  it("draws dimensions from their blocks, hatches filled, skips paper space, fixes Persian order", () => {
    const doc = parseDxf(readFileSync(new URL("./fixtures/pro-plans.dxf", import.meta.url), "utf8"));
    expect(doc.layers).toEqual(expect.arrayContaining(["S-AXIS", "S-CONC", "S-DIMS", "S-CONC-HATCH", "S-TAG", "S-LEVEL"]));
    const dims = doc.entities.filter((e) => e.layer === "S-DIMS");
    expect(dims.some((e) => e.type === "TEXT" && e.text === "5000")).toBe(true);
    expect(doc.entities.some((e) => e.type === "POLY" && e.fill)).toBe(true);
    expect(doc.entities.some((e) => e.type === "TEXT" && e.text === "LOGO")).toBe(false); // title block is paper space
    expect(doc.entities.some((e) => e.type === "TEXT" && e.text.includes("پلان طبقه"))).toBe(true);
    expect(doc.sheets.map((s) => s.name.split(" ")[0])).toEqual(expect.arrayContaining(["S-01", "S-02", "S-10", "E-A"]));
  });
  it("leaves Latin untouched", () => {
    expect(logicalText("3Φ25 L=6200")).toBe("3Φ25 L=6200");
  });
});
