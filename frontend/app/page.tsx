"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch, type HealthResponse, type ProjectListResponse } from "@/lib/api";

export default function DashboardPage() {
  const { isAuthenticated, loading: authLoading, user } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [projectCount, setProjectCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadPublicHealth() {
      try {
        const healthResponse = await apiFetch<HealthResponse>("/health");
        if (active) {
          setHealth(healthResponse);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to reach backend");
        }
      }
    }
    void loadPublicHealth();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setProjectCount(null);
      return;
    }
    let active = true;
    async function loadProjects() {
      try {
        const projects = await apiFetch<ProjectListResponse>("/api/v1/projects");
        if (active) {
          setProjectCount(projects.projects.length);
          setError(null);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load projects");
        }
      }
    }
    void loadProjects();
    return () => {
      active = false;
    };
  }, [isAuthenticated]);

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
      ) : null}

      <div className="grid cards-3">
        <article className="card">
          <h3>Platform Status</h3>
          <p className="metric">{health?.status === "ok" ? "Online" : "Unknown"}</p>
          <p className="muted">FastAPI health endpoint</p>
        </article>
        <article className="card">
          <h3>Projects</h3>
          {authLoading ? <p className="muted">Checking session…</p> : null}
          {!authLoading && !isAuthenticated ? (
            <>
              <p className="metric">—</p>
              <p className="muted">
                <Link href="/login">Sign in</Link> to view your projects.
              </p>
            </>
          ) : null}
          {!authLoading && isAuthenticated ? (
            <>
              <p className="metric">{projectCount ?? "…"}</p>
              <p className="muted">
                <Link href="/projects">Open project list</Link>
              </p>
            </>
          ) : null}
        </article>
        <article className="card">
          <h3>Account</h3>
          {!authLoading && isAuthenticated && user ? (
            <>
              <p className="metric">{user.display_name ?? user.email}</p>
              <p className="muted">{user.email}</p>
            </>
          ) : (
            <>
              <p className="metric">Guest</p>
              <p className="muted">
                <Link href="/login">Sign in</Link> or <Link href="/register">register</Link>
              </p>
            </>
          )}
        </article>
      </div>

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
