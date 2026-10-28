import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { makeUiT } from "../lib/ui-i18n";
import {
  formatAnalysisInventory,
  getAnalysisCapabilityLabel,
  getAnalysisStatusLabel,
} from "../lib/analysis-workspace";
import { AN_FA, formatNum, makeAnalysisT, missingModelInputs, summarizeAnalysis } from "../lib/analysis-results";
import real from "./fixtures/frame3d-analysis-real.json";

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

describe("analysis results view-model (real engine payload)", () => {
  const view = summarizeAnalysis(real.payload)!;

  it("reads KPIs straight from the engine payload", () => {
    expect(view.completed).toBe(true);
    expect(view.maxDrift).toEqual({ pct: 2.907, direction: "Y", storey: 2 });
    expect(view.maxDisplacement).toEqual({ mm: 77.14, direction: "Y", storey: 5 });
    expect(view.fundamentalPeriodS).toBeCloseTo(1.0683, 4);
    expect(view.baseShear?.vKn).toBeCloseTo(1423.19, 2);
    expect(view.baseShear?.weightKn).toBeCloseTo(9487.96, 2);
  });

  it("flags a drift above the engine's Standard 2800 limit as 'review', never as pass", () => {
    expect(view.driftLimitPct).toBe(2);
    expect(view.driftState).toBe("review");
  });

  it("builds per-storey, modal, force and member tables", () => {
    expect(view.directions).toEqual(["X", "Y"]);
    expect(view.storeys.map((s) => s.storey)).toEqual([1, 2, 3, 4, 5]);
    expect(view.storeys[0].shearKn).not.toBeNull();
    expect(view.modes.length).toBeGreaterThan(0);
    expect(view.storeyMember).toHaveLength(5);
    expect(view.members.length).toBeGreaterThan(0);
    expect(view.spectrum.map((s) => s.direction)).toEqual(["X", "Y"]);
  });

  it("returns null for non-results and keeps missing values as null", () => {
    expect(summarizeAnalysis(null)).toBeNull();
    expect(formatNum(null)).toBe("—");
    expect(formatNum(1.23456, 2)).toBe("1.23");
  });

  it("shows pass for a PASS engine check and 'reference' (not pass) for other codes (synthetic payloads)", () => {
    const base = JSON.parse(JSON.stringify(real.payload));
    const pass = summarizeAnalysis({ ...base, drift_check: "PASS" })!;
    expect(pass.driftState).toBe("pass");
    // Non-2800: the engine gives no PASS/FAIL, only a reference limit -> never shown as pass.
    const other = summarizeAnalysis({ ...base, seismic_code: "OTHER", drift_check: undefined, drift_reference_limit_pct: 2.5 })!;
    expect(other.driftState).toBe("reference");
    expect(other.driftLimitPct).toBe(2.5);
    const none = summarizeAnalysis({ ...base, seismic_code: "OTHER", drift_check: undefined, drift_reference_limit_pct: undefined })!;
    expect(none.driftState).toBe("none");
  });

  it("does not treat an incomplete payload as results", () => {
    const v = summarizeAnalysis({ status: "MISSING_REQUIRED_INPUT", missing_inputs: ["storeys"], inputs: {} });
    expect(v?.completed ?? false).toBe(false);
  });
});

describe("analysis run prerequisites", () => {
  it("lists missing required inputs, or all of them when no model exists", () => {
    expect(missingModelInputs(null)).toEqual(["storeys", "bays_x", "bays_y"]);
    expect(missingModelInputs({ storeys: 4, bays_x: 3 })).toEqual(["bays_y"]);
    expect(missingModelInputs({ storeys: 4, bays_x: 3, bays_y: 2 })).toEqual([]);
  });
});

describe("project analysis page (results + one Analyze button)", () => {
  const root = resolve(__dirname, "..");
  const read = (rel: string) => readFileSync(resolve(root, rel), "utf8");
  const client = read("app/workspace/analysis/AnalysisWorkspaceClient.tsx");

  it("renders only the analysis workspace, not the duplicate 3D frame panel or the legacy wrapper", () => {
    const page = read("app/workspace/analysis/page.tsx");
    expect(page).toContain("AnalysisWorkspaceClient");
    expect(page).not.toContain("Frame3dWorkspacePanel");
    expect(page).not.toContain("LegacySection");
  });

  it("frame3d panel no longer has an analysis mode", () => {
    const panel = read("components/frame3d/Frame3dWorkspacePanel.tsx");
    expect(panel).not.toContain('mode === "analysis"');
    expect(panel).not.toMatch(/type Mode = [^;]*"analysis"/);
  });

  it("has exactly one Analyze button wired to the frame3d solver, with disabled/loading/error states", () => {
    expect((client.match(/data-testid="analyze-button"/g) ?? []).length).toBe(1);
    expect(client).toContain("runFrame3d(");
    expect(client).toContain("saveFrame3dPayload");
    for (const needle of ["analyze-disabled-reason", "analyze-error", "analyze-success", "aria-busy", "disabled={disabled}", "/workspace/model"]) {
      expect(client).toContain(needle);
    }
  });

  it("has no design, optimization, download or PEM-run panels", () => {
    for (const bad of ["runAnalysis", "<Frame3dWorkspacePanel", "optimiz", "Download", "design-workspace"]) {
      expect(client).not.toContain(bad);
    }
  });

  it("is translated to Persian (title, button, KPIs, sections, states)", () => {
    expect(makeUiT("fa")("Project analysis")).toBe("آنالیز پروژه");
    const t = makeAnalysisT("fa");
    expect(t("Analyze")).toBe("آنالیز");
    expect(makeAnalysisT("en")("Analyze")).toBe("Analyze");
    const used = new Set<string>();
    for (const f of ["app/workspace/analysis/AnalysisWorkspaceClient.tsx", "components/analysis/AnalysisResultsView.tsx"]) {
      for (const m of read(f).matchAll(/\bt\("([^"]+)"\)/g)) used.add(m[1]);
    }
    expect(used.size).toBeGreaterThan(40);
    const untranslated = [...used].filter((k) => !AN_FA[k] && makeUiT("fa")(k) === k);
    expect(untranslated).toEqual([]);
  });
});
