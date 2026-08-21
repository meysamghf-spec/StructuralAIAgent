"use client";

import { apiFetch, type ProjectListResponse, type ProjectSummary } from "@/lib/api";
import { useCallback, useEffect, useMemo, useState } from "react";

export function useProjectScope(initialProjectId?: string | null) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
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
        const preferred =
          initialProjectId &&
          loadedProjects.some((project) => project.id === initialProjectId)
            ? initialProjectId
            : loadedProjects[0]?.id ?? "";
        setSelectedProjectId(preferred);
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
