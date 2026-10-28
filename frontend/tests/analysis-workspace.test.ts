import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { makeUiT, UI_FA } from "../lib/ui-i18n";
import { ANALYSIS_OPTIONS } from "../app/workspace/analysis/AnalysisWorkspaceClient";
import {
  formatAnalysisInventory,
  getAnalysisCapabilityLabel,
  getAnalysisStatusLabel,
} from "../lib/analysis-workspace";

describe("analysis workspace display helpers", () => {
  it("maps analysis statuses to engineer-friendly labels", () => {
    expect(getAnalysisStatusLabel("REQUIRES_SOLVER")).toBe("Solver required");
    expect(getAnalysisStatusLabel("MODEL_NOT_READY")).toBe("Model not ready");
  });

  it("maps capability guidance for unavailable solver execution", () => {
    expect(getAnalysisCapabilityLabel("REQUIRES_SOLVER")).toContain("solver");
  });

  it("formats model inventory for cards", () => {
    const items = formatAnalysisInventory({
      member_count: 4,
      support_count: 2,
      load_case_count: 3,
      load_combination_count: 5,
      level_count: 2,
    });
    expect(items.some((item) => item.startsWith("Members:"))).toBe(true);
    expect(items).toHaveLength(5);
  });
});

describe("project analysis page (duplicate 3D-frame half removed)", () => {
  const root = resolve(__dirname, "..");
  const read = (rel: string) => readFileSync(resolve(root, rel), "utf8");

  it("renders only the PEM analysis workspace, not the duplicate 3D frame panel or the legacy wrapper", () => {
    const page = read("app/workspace/analysis/page.tsx");
    expect(page).toContain("AnalysisWorkspaceClient");
    expect(page).not.toContain("Frame3dWorkspacePanel");
    expect(page).not.toContain("LegacySection");
  });

  it("frame3d panel no longer has an analysis mode", () => {
    const panel = read("components/frame3d/Frame3dWorkspacePanel.tsx");
    expect(panel).not.toContain('mode === "analysis"');
    expect(panel).not.toMatch(/type Mode = [^;]*"analysis"/);
    expect(panel).not.toContain("Rerun with saved model");
  });

  it("keeps the PEM analysis features and links to the Model page", () => {
    const client = read("app/workspace/analysis/AnalysisWorkspaceClient.tsx");
    for (const needle of ["getAnalysisReadiness", "getLoadCombinationSummary", "listAnalysisRuns", "runAnalysis", "listPemVersions", "/workspace/model"]) {
      expect(client).toContain(needle);
    }
    expect(ANALYSIS_OPTIONS.map((o) => o.value)).toEqual(["STATIC", "MODAL", "DRIFT", "LATERAL_DRIFT"]);
  });

  it("is translated to Persian (title, options, statuses)", () => {
    const t = makeUiT("fa");
    expect(t("Project analysis")).toBe("آنالیز پروژه");
    expect(makeUiT("en")("Project analysis")).toBe("Project analysis");
    for (const o of ANALYSIS_OPTIONS) expect(UI_FA[o.label]).toBeTruthy();
    for (const s of ["CREATED", "RUNNING", "SUCCESS", "WARNING", "FAILED", "NOT_IMPLEMENTED", "REQUIRES_SOLVER", "MODEL_NOT_READY"]) {
      expect(UI_FA[getAnalysisStatusLabel(s)]).toBeTruthy();
    }
    expect(UI_FA["Rerun with saved model"]).toBeUndefined();
  });
});
