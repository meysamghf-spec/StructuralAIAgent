import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  chipOf,
  dcChip,
  designReadiness,
  designRunInputs,
  foundationMaxDc,
  governingMember,
  inputLabel,
  sectionText,
} from "@/lib/design-run";
import { makeUiT } from "@/lib/ui-i18n";

const read = (rel: string) => readFileSync(join(__dirname, "..", rel), "utf8");

const INPUTS = { storeys: 3, bays_x: 2, bays_y: 2, beam_b_m: 0.3, beam_h_m: 0.45, column_b_m: 0.4, column_h_m: 0.4 };
const COMPLETED = { status: "completed" };

describe("designReadiness", () => {
  it("is ready with complete inputs and a completed analysis", () => {
    expect(designReadiness(INPUTS, COMPLETED)).toEqual({ ready: true, missing: [] });
  });

  it("lists a missing model and missing analysis with human labels and the page to fix them", () => {
    const r = designReadiness(null, null);
    expect(r.ready).toBe(false);
    expect(r.missing.map((m) => m.id)).toEqual(["model", "analysis"]);
    expect(r.missing.find((m) => m.id === "model")!.href).toBe("/workspace/model");
    expect(r.missing.find((m) => m.id === "analysis")!.href).toBe("/workspace/analysis");
  });

  it("never exposes raw keys: bays_x/bays_y become 'Bays in X/Y'", () => {
    const r = designReadiness({ ...INPUTS, bays_x: null, bays_y: "" }, { status: "MISSING_REQUIRED_INPUT", missing_inputs: ["bays_x", "bays_y"] });
    expect(r.ready).toBe(false);
    const labels = r.missing.map((m) => m.label);
    expect(labels).toContain("Bays in X");
    expect(labels).toContain("Bays in Y");
    expect(labels.some((l) => l.includes("_"))).toBe(false);
    expect(r.missing.filter((m) => m.id === "bays_x")).toHaveLength(1);
    expect(inputLabel("storeys")).toBe("Stories");
  });

  it("takes missing inputs reported by the engine payload even if the saved inputs look complete", () => {
    const r = designReadiness(INPUTS, { status: "MISSING_REQUIRED_INPUT", missing_inputs: ["storeys", "frame_model"] });
    expect(r.missing.map((m) => m.id)).toEqual(["storeys", "analysis"]);
  });
});

describe("status chips", () => {
  it("maps engine codes to Pass / Needs review / Fail, unknown is never a pass", () => {
    expect(chipOf("PASS")).toBe("pass");
    expect(chipOf("FAIL")).toBe("fail");
    expect(chipOf("OVERLAP")).toBe("fail");
    expect(chipOf("CHECK")).toBe("review");
    expect(chipOf("")).toBe("review");
    expect(chipOf(undefined)).toBe("review");
    expect(dcChip(0.99)).toBe("pass");
    expect(dcChip(1)).toBe("pass");
    expect(dcChip(1.01)).toBe("fail");
    expect(dcChip(null)).toBeNull();
  });
});

describe("governing member and sections", () => {
  const design = {
    beams: [
      { group: "B-X-S1-edge", storey: 1, DC_flexure: 0.9, DC_shear: 0.4 },
      { group: "B-Y-S2-mid", storey: 2, DC_flexure: 0.5, DC_shear: 0.95 },
    ],
    columns: [{ group: "C-S1-corner", storey: 1, DC: 0.8 }, { group: "C-S2-mid", storey: 2, DC: null }],
  };

  it("picks the group and check with the largest D/C", () => {
    expect(governingMember(design)).toEqual({ group: "B-Y-S2-mid", dc: 0.95, check: "shear" });
    expect(governingMember({ beams: [], columns: [] })).toBeNull();
    expect(governingMember({ beams: [], columns: [{ group: "C1", DC: "1.2" }] })).toEqual({ group: "C1", dc: 1.2, check: "axial-flexure" });
  });

  it("shows b×h in mm from the engine inputs, with per-storey overrides first", () => {
    expect(sectionText("beam", { storey: 1 }, INPUTS)).toBe("300×450");
    expect(sectionText("column", { storey: 2 }, INPUTS)).toBe("400×400");
    expect(sectionText("column", { storey: 2 }, { ...INPUTS, group_sections: { C2: [0.5, 0.6] } })).toBe("500×600");
    expect(sectionText("beam", { storey: 1 }, null)).toBe("—");
    expect(sectionText("beam", { storey: 1 }, {})).toBe("—");
  });

  it("foundation max D/C ignores missing values", () => {
    expect(foundationMaxDc({ rows: [{ bearing_dc: 0.5, DC_oneway: 0.6, DC_punching: 0.95, DC_flexure: null }] })).toBeCloseTo(0.95);
    expect(foundationMaxDc({ rows: [] })).toBeNull();
  });
});

describe("designRunInputs", () => {
  it("keeps the saved model, requests foundation design and the UI language", () => {
    const { inputs, codeSwitchedOn } = designRunInputs({ ...INPUTS, design_code: "MABHAS9" }, "fa");
    expect(codeSwitchedOn).toBe(false);
    expect(inputs).toMatchObject({ storeys: 3, bays_x: 2, design_code: "MABHAS9", foundation: true, lang: "fa" });
  });

  it("switches the Mabhas 9 member design on only when no design code was selected", () => {
    expect(designRunInputs({ ...INPUTS, design_code: "NONE" }, "en")).toMatchObject({ codeSwitchedOn: true, inputs: { design_code: "MABHAS9" } });
    expect(designRunInputs(INPUTS, "en").inputs.design_code).toBe("MABHAS9");
  });
});

describe("Design page component", () => {
  const src = read("components/design/DesignRunPage.tsx");

  it("has exactly one button, wired to the frame3d run (analysis + Mabhas 9 design + footings)", () => {
    expect(src.match(/<button\b/g)).toHaveLength(1);
    expect(src).toContain("runFrame3d(");
    expect(src).toContain("saveFrame3dPayload(");
    expect(src).toContain('data-testid="design-button"');
    expect(src).toContain("disabled={disabled}");
  });

  it("has loading, success, error, empty and missing-input states", () => {
    for (const id of ["design-loading", "design-success", "design-error", "design-empty", "design-missing"]) {
      expect(src, id).toContain(id);
    }
    expect(read("lib/design-run.ts")).toContain('href: "/workspace/analysis"');
  });

  it("shows only design content: no analysis, downloads, drawings, optimization or model inputs", () => {
    for (const bad of ["DownloadsPanel", "Frame3dViewer", "DetailingStep", "Frame3dResultCard", "FRAME_FORM_FIELDS", "optimiz", "storeyLateral", "modal"]) {
      expect(src.includes(bad), bad).toBe(false);
    }
    for (const id of ["design-status-banner", "design-kpis", "design-beams-table", "design-columns-table", "design-foundation-table", "design-notes", "kpi-max-dc", "kpi-governing"]) {
      expect(src, id).toContain(id);
    }
  });

  it("does not touch the analysis workspace files", () => {
    expect(read("app/workspace/design/page.tsx")).not.toContain("workspace/analysis/");
  });

  it("every translated string used by the page has a Persian translation", () => {
    const fa = makeUiT("fa");
    const keys = Array.from(src.matchAll(/\bt\("([^"]+)"\)/g)).map((m) => m[1]);
    keys.push("Pass", "Needs review", "Fail", "3D frame model", "Analysis results", "Bays in X", "Bays in Y", "Stories", "flexure", "shear", "axial + bending", "Go to Model");
    for (const key of new Set(keys)) {
      if (["D/C"].includes(key)) continue;
      expect(fa(key), key).not.toBe(key);
    }
    expect(fa("Design")).toBe("طراحی");
    expect(makeUiT("en")("Design")).toBe("Design");
  });
});
