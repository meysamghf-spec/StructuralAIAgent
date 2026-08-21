"use client";

import { ProjectScopePanel } from "@/components/workspace/ProjectScopePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { runProjectValidation, type ValidationReportResponse } from "@/lib/api";
import { getValidationStatusLabel } from "@/lib/workspace";
import { useState } from "react";

export default function ValidationWorkspaceClient() {
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } =
    useProjectScope();
  const [report, setReport] = useState<ValidationReportResponse | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleValidate() {
    if (!selectedProjectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setReport(await runProjectValidation(selectedProjectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Quality</p>
        <h2>Validation</h2>
        <p className="subtitle">
          Check the project configuration, assumptions, and code setup before analysis and design work.
        </p>
      </header>

      <ProjectScopePanel
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={setSelectedProjectId}
        loading={loading}
      />

      <section className="card">
        <h3>Run validation</h3>
        <button className="button" type="button" disabled={!selectedProjectId || busy} onClick={() => void handleValidate()}>
          {busy ? "Validating…" : "Validate project"}
        </button>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {report ? (
        <section className="card">
          <h3>Validation result</h3>
          <p className="metric">{getValidationStatusLabel(report.overall_status)}</p>
          <p className="muted">{report.summary}</p>
          <ul className="feature-list">
            {report.findings.map((finding) => (
              <li key={`${finding.code}-${finding.message}`}>
                [{getValidationStatusLabel(finding.status)}] {finding.message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}
