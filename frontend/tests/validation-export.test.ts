import { describe, expect, it } from "vitest";
import { validationReportToCsv, validationReportToMarkdown } from "../lib/validation-export";

const report = {
  project_id: "p",
  overall_status: "WARNING",
  summary: "Validation completed with warnings",
  findings: [{ status: "WARNING", code: "X", message: 'has, comma and "quote"', category: "CODE" }],
} as never;

describe("validation export", () => {
  it("builds CSV with escaping and markdown", () => {
    const csv = validationReportToCsv(report);
    expect(csv.split("\n")[0]).toBe("status,category,code,message");
    expect(csv).toContain('"has, comma and ""quote"""');
    expect(validationReportToMarkdown(report)).toContain("`X`");
  });
});
