"use client";

import { listProjectFiles, type ProjectFileSummary } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

export function useProjectFiles(projectId: string | null, refreshToken = 0) {
  const [files, setFiles] = useState<ProjectFileSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    if (!projectId) {
      setFiles([]);
      setError(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setFiles([]);
    setLoading(true);
    setError(null);
    listProjectFiles(projectId)
      .then((response) => {
        if (!cancelled) {
          setFiles(Array.isArray(response?.files) ? response.files : []);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setFiles([]);
          setError(err instanceof Error ? err.message : "Unable to load project files.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    const cancel = reload();
    return cancel;
  }, [reload, refreshToken]);

  return {
    files,
    loading,
    error,
    retry: () => {
      reload();
    },
  };
}
