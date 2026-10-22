import Link from "next/link";
import type { ProjectSummary } from "@/lib/api";

export function ProjectScopePanel({
  projects,
  selectedProjectId,
  onProjectChange,
  loading,
  description,
}: {
  projects: ProjectSummary[];
  selectedProjectId: string;
  onProjectChange: (projectId: string) => void;
  loading?: boolean;
  description?: string;
}) {
  const selected = projects.find((project) => project.id === selectedProjectId);

  return (
    <section className="card">
      <h3>Active project</h3>
      <p className="muted">{description ?? "Pick the project this page works on."}</p>
      {!loading && projects.length === 0 ? (
        <div className="first-project-cta" data-testid="scope-empty">
          <p>No projects yet. Create one to start working here.</p>
          <Link className="cta-button" href="/projects/new">Create project</Link>
        </div>
      ) : null}
      <select
        className="input project-select"
        value={selectedProjectId}
        onChange={(event) => onProjectChange(event.target.value)}
        disabled={loading || projects.length === 0}
      >
        {projects.length === 0 ? <option value="">No projects yet</option> : null}
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            {project.name}
          </option>
        ))}
      </select>
      {selected ? (
        <p className="muted">Working in {selected.name}</p>
      ) : projects.length > 0 ? (
        <p className="field-hint" data-testid="scope-hint">Select a project to enable actions on this page.</p>
      ) : null}
    </section>
  );
}
