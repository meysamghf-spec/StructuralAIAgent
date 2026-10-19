"use client";

import { apiFetch } from "@/lib/api";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { setCurrentProjectId } from "@/lib/current-project";

type ProjectContext = {
  project_id: string;
  project_name: string;
  pem_version: number | null;
  code_configuration: {
    jurisdiction: string;
    governing_building_code: string;
    loading_standard: string;
    concrete_standard: string;
    steel_standard: string;
  } | null;
  unit_configuration: {
    system: string;
    length_unit: string;
    force_unit: string;
    stress_unit: string;
  } | null;
  memory_total_count: number;
  files: Array<{ id: string; filename: string; extraction_status: string }>;
};

type ValidationReport = {
  overall_status: string;
  summary: string;
  findings: Array<{ code: string; message: string; status: string }>;
};

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [context, setContext] = useState<ProjectContext | null>(null);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (projectId) setCurrentProjectId(projectId);
    async function load() {
      setError(null);
      try {
        const contextResponse = await apiFetch<ProjectContext>(
          `/api/v1/projects/${projectId}/context`,
        );
        setContext(contextResponse);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load project");
      }
    }
    void load();
  }, [projectId]);

  async function runValidation() {
    setError(null);
    try {
      const report = await apiFetch<ValidationReport>(
        `/api/v1/projects/${projectId}/validate`,
        { method: "POST" },
      );
      setValidation(report);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Project</p>
        <h2>{context?.project_name ?? "Loading project…"}</h2>
        <p className="subtitle">
          <Link href="/projects">Back to projects</Link>
        </p>
      </header>

      {error ? <div className="alert error">{error}</div> : null}

      {context ? (
        <div className="grid cards-2">
          <article className="card">
            <h3>Configuration</h3>
            <p className="muted">PEM version {context.pem_version ?? "—"}</p>
            <ul className="feature-list">
              <li>Jurisdiction: {context.code_configuration?.jurisdiction ?? "—"}</li>
              <li>Building code: {context.code_configuration?.governing_building_code ?? "—"}</li>
              <li>Loading: {context.code_configuration?.loading_standard ?? "—"}</li>
              <li>Units: {context.unit_configuration?.length_unit ?? "—"} / {context.unit_configuration?.force_unit ?? "—"} / {context.unit_configuration?.stress_unit ?? "—"}</li>
            </ul>
          </article>
          <article className="card">
            <h3>Project Data</h3>
            <p className="metric">{context.memory_total_count}</p>
            <p className="muted">Indexed memory entries</p>
            <p className="muted">{context.files.length} uploaded files</p>
            <button className="button" type="button" onClick={() => void runValidation()}>
              Run Validation
            </button>
          </article>
        </div>
      ) : null}

      {validation ? (
        <section className="card">
          <h3>Validation — {validation.overall_status}</h3>
          <p className="muted">{validation.summary}</p>
          <ul className="feature-list">
            {validation.findings.map((finding) => (
              <li key={`${finding.code}-${finding.message}`}>
                [{finding.status}] {finding.code}: {finding.message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}
