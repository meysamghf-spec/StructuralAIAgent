import { apiFetch } from "./api";

export async function runFrame3d(inputs: Record<string, unknown>, assumeDefaults = false): Promise<unknown> {
  const res = await apiFetch<{ frame3d_analysis: unknown }>("/api/v1/frame3d/run", {
    method: "POST",
    body: JSON.stringify({ inputs, assume_defaults: assumeDefaults }),
  });
  return res.frame3d_analysis;
}
