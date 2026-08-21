"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import {
  createReport,
  generateReportVersion,
  listReports,
  type ReportSummary,
  type ReportVersionSummary,
} from "@/lib/api";
import {
  formatWorkspaceDate,
  getReportStatusLabel,
  getReportTypeLabel,
  truncateText,
} from "@/lib/workspace";
import { useCallback, useEffect, useState } from "react";

const REPORT_OPTIONS = [
  "PROJECT_SUMMARY",
  "STRUCTURAL_DESIGN",
  "ANALYSIS",
  "VALIDATION",
  "DECISION_HISTORY",
] as const;

export default function ReportsWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [selectedType, setSelectedType] = useState<string>("PROJECT_SUMMARY");
  const [latestVersion, setLatestVersion] = useState<ReportVersionSummary | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async (projectId: string) => {
    if (!projectId) {
      setReports([]);
      return;
    }
    const response = await listReports(projectId);
    setReports(response.reports);
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      void refresh(selectedProjectId);
    }
  }, [selectedProjectId, refresh]);

  async function handleCreateAndGenerate() {
    if (!selectedProjectId) {
      return;
    }
    setBusy(true);
    setError(null);
    setLatestVersion(null);
    try {
      const report = await createReport(
        selectedProjectId,
        selectedType,
        getReportTypeLabel(selectedType),
      );
      const version = await generateReportVersion(selectedProjectId, report.id, selectedType);
      setLatestVersion(version);
      await refresh(selectedProjectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Deliverables</p>
        <h2>Reports</h2>
        <p className="subtitle">
          Generate readable engineering reports from project context, decisions, and validation.
        </p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      <section className="card">
        <h3>Generate a report</h3>
        <div className="form-row">
          <select
            className="input"
            value={selectedType}
            onChange={(event) => setSelectedType(event.target.value)}
          >
            {REPORT_OPTIONS.map((type) => (
              <option key={type} value={type}>
                {getReportTypeLabel(type)}
              </option>
            ))}
          </select>
          <button className="button" type="button" disabled={!selectedProjectId || busy} onClick={() => void handleCreateAndGenerate()}>
            {busy ? "Generating…" : "Generate report"}
          </button>
        </div>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {latestVersion ? (
        <section className="card">
          <h3>Latest generated report</h3>
          <p className="muted">Version {latestVersion.version} · {getReportStatusLabel(latestVersion.status)}</p>
          <div className="execution-result">
            <p className="result-text">
              {typeof latestVersion.content.summary === "string"
                ? latestVersion.content.summary
                : "Report generated successfully. Open advanced details if you need the structured content."}
            </p>
          </div>
        </section>
      ) : null}

      <section className="card">
        <h3>Project reports</h3>
        {reports.length === 0 ? <p className="muted">No reports yet for this project.</p> : null}
        <ul className="workspace-list">
          {reports.map((report) => (
            <li key={report.id} className="workspace-list-item compact">
              <div>
                <strong>{report.title}</strong>
                <p className="muted">
                  {getReportTypeLabel(report.report_type)} · {getReportStatusLabel(report.status)} · v
                  {report.current_version}
                </p>
                <p className="muted">{formatWorkspaceDate(report.updated_at)}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
