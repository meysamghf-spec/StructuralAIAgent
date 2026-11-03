import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { importViewerData } from "../lib/import-viewer";
import type { ImportState } from "../lib/model-import";

const src = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");

describe("3D force visuals are shown by default", () => {
  it("analysis mode auto-runs the saved frame model and opens on bending moment + deformed shape", () => {
    const panel = src("components/frame3d/Frame3dWorkspacePanel.tsx");
    expect(panel).toContain('mode === "analysis" || mode === "results" || mode === "design" || mode === "foundation") && !payload');
    expect(panel).toContain('initialDisplay={mode === "analysis" || mode === "results" ? "M3" : undefined}');
    expect(panel).toContain("latestImport(pid)");
    const viewer = src("components/chat/Frame3dViewer.tsx");
    expect(viewer).toContain("initialDeformed");
  });

  it("viewer sits right under the analysis KPIs, above the long tables", () => {
    const c = src("app/workspace/analysis/AnalysisWorkspaceClient.tsx");
    expect(c.indexOf("<AnalysisKpis")).toBeLessThan(c.indexOf("{viewer}"));
    expect(c.indexOf("{viewer}")).toBeLessThan(c.indexOf("<AnalysisSections"));
  });

  it("maps an imported model's analysis viewer block, or falls back to its geometry", () => {
    const model = {
      nodes: { a: { x: 0, y: 0, z: 0 }, b: { x: 0, y: 0, z: 3 }, c: { x: 5, y: 0, z: 3 } },
      members: [{ id: "C1", i: "a", j: "b", type: "column", section: "S" }, { id: "B1", i: "b", j: "c", type: "beam", section: "S" }],
      supports: { a: [true, true, true, true, true, true] },
      sections: { S: { b: 0.3, h: 0.5 } },
    };
    const geo = importViewerData({ model, analysis: null } as unknown as ImportState);
    expect(geo?.members.map((m) => m.id)).toEqual(["C1", "B1"]);
    expect(geo?.supports).toEqual(["a"]);
    const withForces = importViewerData({
      model,
      analysis: {
        viewer: {
          nodes: [{ id: "a", x: 0, y: 0, z: 0 }, { id: "b", x: 0, y: 0, z: 3 }],
          supports: ["a"],
          members: [{ id: "C1", i: "a", j: "b", type: "column", storey: 1, section: "S", b: 0.3, h: 0.5 }],
          cases: ["Dead"], combos: {}, forces: { Dead: { C1: [-10, 1, 2, -1, 0] } }, displacements_mm: {}, reactions: {},
        },
      },
    } as unknown as ImportState);
    expect(withForces?.cases).toEqual(["Dead"]);
    expect(withForces?.members).toHaveLength(1);
    expect(importViewerData(null)).toBeNull();
  });
});
