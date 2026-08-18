import { apiFetch, type HealthResponse, type ProjectListResponse } from "@/lib/api";
import Link from "next/link";

async function loadDashboard() {
  try {
    const [health, projects] = await Promise.all([
      apiFetch<HealthResponse>("/health"),
      apiFetch<ProjectListResponse>("/api/v1/projects"),
    ]);
    return { health, projects, error: null as string | null };
  } catch (error) {
    return {
      health: null,
      projects: { projects: [] },
      error: error instanceof Error ? error.message : "Unable to reach backend",
    };
  }
}

export default async function DashboardPage() {
  const { health, projects, error } = await loadDashboard();

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Dashboard</p>
        <h2>Structural Engineering Workspace</h2>
        <p className="subtitle">
          Project management, document processing, code configuration, analysis, design,
          validation, and AI-assisted engineering workflows.
        </p>
      </header>

      {error ? (
        <div className="alert error">
          <strong>Backend unavailable.</strong> {error}
        </div>
      ) : (
        <div className="grid cards-3">
          <article className="card">
            <h3>Platform Status</h3>
            <p className="metric">{health?.status === "ok" ? "Online" : "Unknown"}</p>
            <p className="muted">FastAPI health endpoint</p>
          </article>
          <article className="card">
            <h3>Projects</h3>
            <p className="metric">{projects.projects.length}</p>
            <p className="muted">
              <Link href="/projects">Open project list</Link>
            </p>
          </article>
          <article className="card">
            <h3>Default Codes</h3>
            <p className="metric">US Profile</p>
            <p className="muted">IBC 2024 · ASCE 7-22 · ACI 318-25 · AISC 360-22</p>
          </article>
        </div>
      )}

      <section className="card">
        <h3>Workspace Areas</h3>
        <ul className="feature-list">
          <li>Projects and PEM configuration</li>
          <li>File upload, extraction, and document indexing</li>
          <li>Project memory and scoped context assembly</li>
          <li>CodeEngine, ValidationEngine, and unit conversion</li>
          <li>Analysis and design engine boundaries</li>
          <li>ETABS, SAP2000, SAFE, and AutoCAD adapter stubs</li>
          <li>AI Gateway and hybrid orchestration</li>
        </ul>
      </section>
    </section>
  );
}
