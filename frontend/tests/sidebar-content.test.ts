import { describe, expect, it } from "vitest";
import { bounds, filterEntities, parseDxf, project } from "@/lib/dxf";
import { previewKind } from "@/lib/file-preview";
import { buildReportHtml } from "@/lib/frame3d-report";
import { mapFrame3dResults } from "@/lib/chat-mappers";

function dxf(entities: string[]): string {
  return ["0", "SECTION", "2", "ENTITIES", ...entities, "0", "ENDSEC", "0", "EOF"].join("\r\n");
}
const ent = (type: string, layer: string, codes: Array<[number, string | number]>) => ["0", type, "8", layer, ...codes.flatMap(([c, v]) => [String(c), String(v)])];

const SAMPLE = dxf([
  ...ent("TEXT", "TITLE", [[10, 0], [20, -3], [40, 0.5], [1, "STORY 1 PLAN  x"]]),
  ...ent("TEXT", "TITLE", [[10, 20], [20, -3], [40, 0.5], [1, "FOUNDATION PLAN  qa=150"]]),
  ...ent("LINE", "GRID", [[10, 0], [20, 0], [11, 10], [21, 0]]),
  ...ent("LINE", "BEAMS", [[10, 20], [20, 0], [11, 30], [21, 0]]),
  ...ent("POLYLINE", "FOUNDATION", [[66, 1], [70, 1]]),
  ...ent("VERTEX", "FOUNDATION", [[10, 20], [20, 0]]),
  ...ent("VERTEX", "FOUNDATION", [[10, 22], [20, 0]]),
  ...ent("VERTEX", "FOUNDATION", [[10, 22], [20, 2]]),
  ...["0", "SEQEND"],
  ...ent("CIRCLE", "GRID_TEXT", [[10, 0], [20, 12], [40, 0.5]]),
]);

describe("built-in DXF viewer data", () => {
  const doc = parseDxf(SAMPLE);
  it("parses entities, layers and sheets", () => {
    expect(doc.entities.map((e) => e.type)).toEqual(["TEXT", "TEXT", "LINE", "LINE", "POLY", "CIRCLE"]);
    expect(doc.layers).toEqual(["BEAMS", "FOUNDATION", "GRID", "GRID_TEXT", "TITLE"]);
    expect(doc.sheets.map((s) => s.name)).toEqual(["STORY 1 PLAN", "FOUNDATION PLAN"]);
    expect(doc.is3d).toBe(false);
    const poly = doc.entities[4];
    expect(poly.type === "POLY" && poly.closed && poly.pts.length).toBe(3);
  });
  it("filters by layer and sheet and computes bounds", () => {
    const all = new Set(doc.layers);
    const fnd = filterEntities(doc, all, doc.sheets[1]);
    expect(fnd.map((e) => e.layer).sort()).toEqual(["BEAMS", "FOUNDATION", "TITLE"]);
    const noGrid = filterEntities(doc, new Set(["BEAMS"]), null);
    expect(noGrid).toHaveLength(1);
    expect(bounds(noGrid, "top")).toEqual([20, 0, 10, 1]);
    expect(project([1, 1, 2], "iso")[1]).toBeCloseTo(3);
  });
});

describe("file preview kinds", () => {
  it("detects types", () => {
    expect(previewKind("plans.DXF", null)).toBe("dxf");
    expect(previewKind("a.pdf", null)).toBe("pdf");
    expect(previewKind("x.bin", "image/png")).toBe("image");
    expect(previewKind("model.e2k", null)).toBe("text");
    expect(previewKind("x.zip", "application/zip")).toBe("none");
  });
});

describe("HTML report", () => {
  it("renders tables and escapes text, RTL for Persian", () => {
    const r = mapFrame3dResults({
      kind: "frame3d_analysis",
      status: "completed",
      lang: "fa",
      fields: [{ label: "<b>x</b>", value: "1", unit: "kN" }],
      drift: [{ direction: "X", storey: 1, drift_elastic_mm: 1, ratio_elastic_pct: 0.1, ratio_amplified_pct: 0.5 }],
      beam_forces_by_storey: [{ storey: 1, M_neg_kn_m: 10, M_pos_kn_m: 5, V_kn: 7 }],
      column_forces_by_storey: [{ storey: 1, P_kn: 100 }],
      foundation: { status: "PASS", qa_kpa: 150, qa_assumed: true, rows: [{ group: "F-corner", B_m: 1.9, h_m: 0.3, status: "PASS" }] },
    })!;
    const html = buildReportHtml(r, "Arak", "2026-10-19");
    expect(html).toContain('dir="rtl"');
    expect(html).toContain("&lt;b&gt;x&lt;/b&gt;");
    expect(html).toContain("F-corner");
    expect(html).toContain("Arak");
    expect(html).toContain("قبول");
  });
});
