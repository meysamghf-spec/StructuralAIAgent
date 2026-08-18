const DEFAULT_API_BASE = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_BASE;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      typeof body?.error?.message === "string"
        ? body.error.message
        : `Request failed (${response.status})`;
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export type ProjectSummary = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
};

export type ProjectListResponse = {
  projects: ProjectSummary[];
};

export type CreateProjectResponse = {
  project: ProjectSummary;
  pem_version: number;
};

export type HealthResponse = {
  status: string;
};
