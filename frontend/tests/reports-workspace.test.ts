import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import {
  buildReportRows,
  FRAME_REPORT_ID,
  reportJsonFilename,
  reportStatusKey,
  reportTypeKey,
  versionMissingData,
  versionSections,
} from "../lib/reports-workspace";
import { UI_FA } from "../lib/ui-i18n";

const rep = (id: string, updated: string, extra: Record<string, unknown> = {}) => ({
  id,
  project_id: "p1",
  report_type: "ANALYSIS",
  title: `Report ${id}`,
  status: "COMPLETED",
  current_version: 2,
  created_at: updated,
  updated_at: updated,
  ...extra,
});

describe("reports page rows", () => {
  it("lists stored reports newest first with title, type, status, version and date", () => {
    const rows = buildReportRows([rep("a", "2026-10-01T10:00:00Z"), rep("b", "2026-10-20T10:00:00Z")], false);
    expect(rows.map((r) => r.id)).toEqual(["b", "a"]);
    expect(rows[0]).toMatchObject({ source: "stored", type: "ANALYSIS", status: "COMPLETED", version: 2, title: "Report b" });
    expect(rows[0].date).toBe("2026-10-20T10:00:00Z");
  });

  it("puts the latest-frame calculation report first, without inventing a date or status", () => {
    const rows = buildReportRows([rep("a", "2026-10-01T10:00:00Z")], true);
    expect(rows[0]).toMatchObject({ id: FRAME_REPORT_ID, source: "frame3d", type: "CALCULATION", date: null, status: null });
    expect(rows).toHaveLength(2);
  });

  it("is empty when there is nothing, and survives malformed API bodies", () => {
    expect(buildReportRows([], false)).toEqual([]);
    expect(buildReportRows(undefined, false)).toEqual([]);
    expect(buildReportRows({ reports: [] }, false)).toEqual([]);
    expect(buildReportRows([null, {}, rep("ok", "2026-10-01T10:00:00Z")], false).map((r) => r.id)).toEqual(["ok"]);
  });

  it("maps types and statuses to translatable labels that exist in Persian", () => {
    expect(reportTypeKey("CALCULATION")).toBe("Calculation report");
    expect(reportTypeKey("???")).toBe("Engineering report");
    expect(reportStatusKey("COMPLETED")).toBe("Ready");
    expect(reportStatusKey("WEIRD")).toBe("WEIRD");
    for (const k of ["Ready", "Draft", "Generating", "Failed", "Calculation report", "Analysis report", "Project summary", "Open", "Reports", "Generate report", "No reports yet"]) {
      expect(UI_FA[k], k).toBeTruthy();
    }
  });
});

describe("report version viewer", () => {
  it("extracts sections and missing data from a stored version", () => {
    const content = {
      sections: [
        { key: "summary", title: "Summary", content: { a: 1 } },
        { key: "analysis", title: "Analysis", content: { data_availability: { status: "not_run", message: "No analysis" } } },
        { key: "empty", title: "", content: {} },
      ],
    };
    const s = versionSections(content);
    expect(s.map((x) => x.title)).toEqual(["Summary", "Analysis", "empty"]);
    expect(s[0].text).toContain('"a": 1');
    expect(s[1].missing).toBe(true);
    expect(s[2].text).toBe("");
    expect(versionSections(null)).toEqual([]);
    expect(versionMissingData({ missing_data: ["No analysis", 3] })).toEqual(["No analysis"]);
    expect(versionMissingData(undefined)).toEqual([]);
  });

  it("names downloads safely", () => {
    expect(reportJsonFilename("Analysis report", "ANALYSIS", 2)).toBe("analysis-report-v2.json");
    expect(reportJsonFilename("گزارش", "ANALYSIS", null)).toBe("analysis.json");
  });
});

describe("Reports page (full content restored)", () => {
  const root = resolve(__dirname, "..");
  const page = readFileSync(resolve(root, "app/workspace/reports/page.tsx"), "utf8");
  const list = readFileSync(resolve(root, "components/reports/ReportsList.tsx"), "utf8");

  it("renders the reports list plus the calculation report, downloads and report tools", () => {
    for (const part of ["<ReportsList />", "<ReportPanel />", "<FrameDownloads />", "<ReportsWorkspaceClient />"]) {
      expect(page).toContain(part);
    }
  });

  it("has no analysis/design/model/drawing/optimization panels", () => {
    for (const banned of ["SolverInlinePanel", "DetailingStep", "FoundationView", "DxfViewer", "optimization", "downloadAll", "Rebar"]) {
      expect(list).not.toContain(banned);
    }
  });

  it("keeps Reports in the navigation", () => {
    expect(readFileSync(resolve(root, "lib/nav.ts"), "utf8")).toContain('href: "/workspace/reports"');
  });
});
