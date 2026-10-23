import { describe, expect, it } from "vitest";
import { DOWNLOADS, filenameFrom, requestBody } from "@/lib/frame3d-downloads";

describe("frame3d downloads", () => {
  it("covers every required output group with formats and labels", () => {
    const groups = Object.keys(DOWNLOADS);
    for (const g of ["analysis", "design", "foundation", "optimization", "figures", "drawings", "models", "reports"]) {
      expect(groups).toContain(g);
    }
    for (const items of Object.values(DOWNLOADS)) {
      for (const it of items) {
        expect(it.formats.length).toBeGreaterThan(0);
        expect(it.label && it.labelFa).toBeTruthy();
      }
    }
    const tables = DOWNLOADS.analysis.filter((i) => i.kind === "table");
    expect(tables.every((t) => t.formats.includes("xlsx") && t.formats.includes("csv"))).toBe(true);
    expect(DOWNLOADS.figures.every((f) => f.formats.includes("png"))).toBe(true);
    expect(DOWNLOADS.drawings.some((d) => d.formats.includes("dxf") && d.formats.includes("pdf"))).toBe(true);
    const models = DOWNLOADS.models.flatMap((m) => m.formats.concat(m.name));
    expect(models.join(" ")).toMatch(/e2k/);
    expect(models.join(" ")).toMatch(/s2k/);
    expect(models.join(" ")).toMatch(/f2k/);
  });

  it("only saves to Files when a project is known", () => {
    expect(JSON.parse(requestBody({ saveToFiles: true })).save_to_files).toBe(false);
    const b = JSON.parse(requestBody({ saveToFiles: true, projectId: "p1" }, { kind: "table" }));
    expect(b).toMatchObject({ save_to_files: true, project_id: "p1", kind: "table", inputs: null });
  });

  it("reads the filename from content-disposition", () => {
    const r = new Response("x", { headers: { "content-disposition": 'attachment; filename="frame-results.xlsx"' } });
    expect(filenameFrom(r, "f")).toBe("frame-results.xlsx");
    expect(filenameFrom(new Response("x"), "fallback.zip")).toBe("fallback.zip");
  });
});
