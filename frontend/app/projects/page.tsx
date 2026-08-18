"use client";

import { apiFetch, type CreateProjectResponse, type ProjectListResponse } from "@/lib/api";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectListResponse["projects"]>([]);
  const [name, setName] = useState("");
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

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      return;
    }
    setError(null);
    try {
      await apiFetch<CreateProjectResponse>("/api/v1/projects", {
        method: "POST",
        body: JSON.stringify({ name: name.trim() }),
      });
      setName("");
      await refreshProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Projects</p>
        <h2>Project Management</h2>
        <p className="subtitle">Create and open structural engineering projects.</p>
      </header>

      <form className="card form-row" onSubmit={handleCreate}>
        <input
          className="input"
          placeholder="New project name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <button className="button" type="submit">
          Create Project
        </button>
      </form>

      {error ? <div className="alert error">{error}</div> : null}

      <section className="card">
        <h3>Project List</h3>
        {loading ? <p className="muted">Loading projects…</p> : null}
        {!loading && projects.length === 0 ? (
          <p className="muted">No projects yet. Create one to begin.</p>
        ) : null}
        <ul className="project-list">
          {projects.map((project) => (
            <li key={project.id}>
              <div>
                <strong>{project.name}</strong>
                <p className="muted">{project.description ?? "No description"}</p>
              </div>
              <Link className="button secondary" href={`/projects/${project.id}`}>
                Open
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
