import type { ValidationReportResponse } from "@/lib/api";

function csvCell(value: unknown): string {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function validationReportToCsv(report: ValidationReportResponse): string {
  const rows = [["status", "category", "code", "message"]];
  for (const finding of report.findings) {
    rows.push([finding.status, String((finding as { category?: string }).category ?? ""), finding.code, finding.message]);
  }
  if (report.findings.length === 0) {
    rows.push(["PASS", "", "ALL_CHECKS_PASSED", report.summary]);
  }
  return rows.map((row) => row.map(csvCell).join(",")).join("\n") + "\n";
}

export function validationReportToJson(report: ValidationReportResponse): string {
  return JSON.stringify(report, null, 2);
}

export function validationReportToMarkdown(report: ValidationReportResponse): string {
  const lines = [`# Validation report`, ``, `**Overall:** ${report.overall_status}`, ``, report.summary, ``];
  if (report.findings.length === 0) {
    lines.push("All validation checks passed.");
  } else {
    for (const f of report.findings) {
      lines.push(`- [${f.status}] \`${f.code}\` — ${f.message}`);
    }
  }
  return lines.join("\n") + "\n";
}

export function downloadTextFile(filename: string, content: string, mime: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: `${mime};charset=utf-8` }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
