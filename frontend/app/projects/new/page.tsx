"use client";

import { apiFetch, type CreateProjectResponse } from "@/lib/api";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { setCurrentProjectId } from "@/lib/current-project";
import { FormEvent, useState } from "react";

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await apiFetch<CreateProjectResponse>("/api/v1/projects", {
        method: "POST",
        body: JSON.stringify({ name: name.trim() }),
      });
      setCurrentProjectId(created.project.id);
      router.push(`/projects/${created.project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
      setBusy(false);
    }
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Projects</p>
        <h2 className="page-dup-title">New Project</h2>
        <p className="subtitle">Name your structural engineering project to create it.</p>
      </header>
      <form className="card form-row" onSubmit={handleCreate}>
        <input
          className="input"
          placeholder="Project name"
          aria-label="Project name"
          autoFocus
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <button className="button" type="submit" disabled={busy || !name.trim()}>
          {busy ? "Creating…" : "Create Project"}
        </button>
      </form>
      {error ? <div className="alert error">{error}</div> : null}
      <p className="muted"><Link href="/projects">Back to all projects</Link></p>
    </section>
  );
}
