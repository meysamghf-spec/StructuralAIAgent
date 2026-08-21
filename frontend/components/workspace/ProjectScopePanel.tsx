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
      <p className="muted">
        {description ?? "This workspace is scoped to the selected project."}
      </p>
      <select
        className="input project-select"
        value={selectedProjectId}
        onChange={(event) => onProjectChange(event.target.value)}
        disabled={loading || projects.length === 0}
      >
        {projects.length === 0 ? <option value="">No projects available</option> : null}
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            {project.name}
          </option>
        ))}
      </select>
      {selected ? <p className="muted">Working in {selected.name}</p> : null}
    </section>
  );
}
