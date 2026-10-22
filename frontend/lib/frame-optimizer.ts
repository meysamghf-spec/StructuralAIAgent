import { apiFetch } from "./api";

export type FrameOptGroup = {
  group: string;
  type: "column" | "beam";
  storeys: number[];
  section_cm: string;
  initial_section_cm: string;
  governing_constraint: string;
  utilization: number;
};

export type FrameOptSummary = {
  objective: number;
  cost_toman: number;
  weight_kg: number;
  concrete_m3: number;
  rebar_kg: number;
  formwork_m2: number;
  feasible: boolean;
  max_drift_ratio: number;
};

export type FrameOptimizationResult = {
  kind: "frame_optimization";
  status: string;
  method: Record<string, unknown> & { objective?: string; seed?: number };
  initial: FrameOptSummary;
  fsd: FrameOptSummary;
  optimal: FrameOptSummary;
  savings_pct: number;
  savings_reference?: string;
  drift_limit: number;
  groups: FrameOptGroup[];
  convergence: {
    fsd: { iteration: number; objective: number; feasible: boolean }[];
    ga: { generation: number; best_objective: number; feasible: boolean; evaluations: number }[];
  };
  evaluations: number;
  elapsed_s: number;
  limits: string[];
  objective_unit?: string;
  report_markdown?: string;
};

export type FrameOptimizeInputs = {
  storeys: number;
  bays_x: number;
  bays_y: number;
  bay_x_m: number;
  bay_y_m: number;
  storey_height_m: number;
  zone: string;
  soil: string;
  lang?: string;
};

export type FrameOptimizeOptions = {
  objective: "cost" | "weight";
  prices?: { concrete_m3: number; rebar_kg: number; formwork_m2: number };
  seed?: number;
  time_budget_s?: number;
  max_evaluations?: number;
};

export async function runFrameOptimization(
  inputs: FrameOptimizeInputs,
  options: FrameOptimizeOptions,
): Promise<FrameOptimizationResult> {
  const body = await apiFetch<{ frame_optimization: FrameOptimizationResult }>("/api/v1/frame3d/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs, options }),
  });
  return body.frame_optimization;
}

/** Points for the convergence chart: FSD iterations then GA generations, best-so-far objective. */
export function convergenceSeries(res: FrameOptimizationResult): { x: number; y: number; stage: "fsd" | "ga" }[] {
  const pts: { x: number; y: number; stage: "fsd" | "ga" }[] = [];
  res.convergence.fsd.forEach((p) => pts.push({ x: pts.length, y: p.objective, stage: "fsd" }));
  res.convergence.ga.forEach((p) => pts.push({ x: pts.length, y: p.best_objective, stage: "ga" }));
  return pts;
}

export function formatObjective(value: number, objective: string | undefined): string {
  return objective === "weight"
    ? `${Math.round(value).toLocaleString("en-US")} kg`
    : `${Math.round(value).toLocaleString("en-US")} toman`;
}
