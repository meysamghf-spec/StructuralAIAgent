"use client";

import { apiFetch, type ProjectListResponse } from "@/lib/api";
import Link from "next/link";
import { projectChatHref, setCurrentProjectId } from "@/lib/current-project";
import { useEffect, useState } from "react";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectListResponse["projects"]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refreshProjects() {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch<ProjectListResponse>("/api/v1/projects");
      setProjects(response.projects);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshProjects();
  }, []);

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Projects</p>
        <h2>Projects</h2>
        <p className="subtitle">Open a project or start a new one.</p>
        <Link className="button" href="/projects/new" data-testid="new-project-button">New project</Link>
      </header>


      {error ? <div className="alert error">{error}</div> : null}

      <section className="card">
        <h3>Project List</h3>
        {loading ? <p className="muted">Loading projects…</p> : null}
        {!loading && projects.length === 0 ? (
          <div className="first-project-cta" data-testid="projects-empty">
            <p>No projects yet. Create one to start chatting and analyzing.</p>
            <Link className="cta-button" href="/projects/new">Create project</Link>
          </div>
        ) : null}
        <ul className="project-list">
          {projects.map((project) => (
            <li key={project.id}>
              <div>
                <strong>{project.name}</strong>
                <p className="muted">{project.description ?? "No description"}</p>
              </div>
              <span className="project-actions">
                <Link className="button" href={projectChatHref(project.id)} onClick={() => setCurrentProjectId(project.id)}>
                  Open
                </Link>
                <Link className="button secondary" href={`/projects/${project.id}`}>
                  Details
                </Link>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
