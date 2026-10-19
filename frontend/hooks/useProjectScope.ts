"use client";

import { apiFetch, type ProjectListResponse, type ProjectSummary } from "@/lib/api";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getCurrentProjectId, PROJECT_EVENT, setCurrentProjectId } from "@/lib/current-project";

export function useProjectScope(initialProjectId?: string | null) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectIdState] = useState("");
  const setSelectedProjectId = useCallback((id: string) => {
    setSelectedProjectIdState(id);
    if (id) setCurrentProjectId(id);
  }, []);
  useEffect(() => {
    const onChange = (e: Event) => {
      const id = (e as CustomEvent<string | null>).detail;
      if (id) setSelectedProjectIdState(id);
    };
    window.addEventListener(PROJECT_EVENT, onChange);
    return () => window.removeEventListener(PROJECT_EVENT, onChange);
  }, []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshProjects = useCallback(async () => {
    const response = await apiFetch<ProjectListResponse>("/api/v1/projects");
    setProjects(response.projects);
    return response.projects;
  }, []);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const loadedProjects = await refreshProjects();
        const wanted = initialProjectId || getCurrentProjectId();
        const preferred =
          wanted && loadedProjects.some((project) => project.id === wanted)
            ? wanted
            : loadedProjects[0]?.id ?? "";
        setSelectedProjectIdState(preferred);
        if (preferred) setCurrentProjectId(preferred);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load projects");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, [initialProjectId, refreshProjects]);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  return {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    selectedProject,
    loading,
    error,
    setError,
    refreshProjects,
  };
}
