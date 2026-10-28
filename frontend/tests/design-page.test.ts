import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { summarizeDesign } from "@/lib/frame3d-design-summary";
import { makeUiT, UI_FA } from "@/lib/ui-i18n";
import { DESIGN_OPTIONS } from "@/app/workspace/design/DesignWorkspaceClient";

const read = (rel: string) => readFileSync(join(__dirname, "..", rel), "utf8");

describe("design summary (Mabhas 9 rows of the latest frame run)", () => {
  it("computes max D/C, overstressed groups and the SCWB minimum", () => {
    const s = summarizeDesign({
      beams: [
        { group: "B1", DC_flexure: 0.82, DC_shear: "0.4" },
        { group: "B2", DC_flexure: 1.08, DC_shear: 0.6 },
      ],
      columns: [{ group: "C1", DC: 0.91 }, { group: "C2", DC: null }],
      scwb: [{ level: 1, min_ratio: 1.4 }, { level: 2, min_ratio: "1.25" }],
    });
    expect(s.beamGroups).toBe(2);
    expect(s.columnGroups).toBe(2);
    expect(s.maxBeamFlexureDc).toBeCloseTo(1.08);
    expect(s.maxBeamShearDc).toBeCloseTo(0.6);
    expect(s.maxColumnDc).toBeCloseTo(0.91);
    expect(s.maxDc).toBeCloseTo(1.08);
    expect(s.overstressedGroups).toBe(1);
    expect(s.scwbMinRatio).toBeCloseTo(1.25);
  });

  it("returns nulls when there are no rows", () => {
    const s = summarizeDesign({ beams: [], columns: [], scwb: [] });
    expect(s.maxDc).toBeNull();
    expect(s.scwbMinRatio).toBeNull();
    expect(s.overstressedGroups).toBe(0);
  });
});

describe("design page is design-specific", () => {
  it("page shows the design panel and the PEM design checks without a collapsed wrapper", () => {
    const page = read("app/workspace/design/page.tsx");
    expect(page).toContain('mode="design"');
    expect(page).toContain("<DesignWorkspaceClient />");
    expect(page).not.toContain("LegacySection");
  });

  it("design mode no longer repeats the analysis viewer, foundation view or full analysis card", () => {
    const panel = read("components/frame3d/Frame3dWorkspacePanel.tsx");
    expect(panel).toContain('mode === "design" ? (\n        <Frame3dDesignCard');
    expect(panel).toContain('mode !== "foundation" && mode !== "design"');
    expect(panel).toContain('(mode === "results" || mode === "foundation") ? (\n        <SectionErrorBoundary label="Foundation">');
    expect(panel).toContain('["design", "drawings"]');
  });

  it("keeps the PEM design endpoints and links back to analysis", () => {
    const client = read("app/workspace/design/DesignWorkspaceClient.tsx");
    expect(client).toContain("runDesign(");
    expect(client).toContain("listAvailableAnalysisRuns(");
    expect(client).toContain('href="/workspace/analysis"');
    expect(DESIGN_OPTIONS.map((o) => o.value)).toEqual(["CONCRETE_BEAM", "STEEL_BEAM", "CONCRETE_COLUMN", "STEEL_COLUMN"]);
  });

  it("has fa translations for the new design strings", () => {
    const fa = makeUiT("fa");
    for (const key of [
      "Project design checks",
      "Design readiness",
      "Run design check",
      "Latest design result",
      "Design run history",
      "Member design",
      "Design summary",
      "Max column D/C",
      "Concrete beam design",
      "Analysis results required",
    ]) {
      expect(fa(key), key).not.toBe(key);
    }
    expect(UI_FA["Run design check"]).toBeTruthy();
    expect(makeUiT("en")("Run design check")).toBe("Run design check");
  });
});
