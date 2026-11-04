/**
 * 3D-frame model size limits — mirror of backend/app/application/frame3d_limits.py (the single source of truth,
 * also served by GET /api/v1/frame3d/limits). tests/frame3d-limits.test.ts fails if the two drift apart.
 */
export const FRAME_LIMITS = {
  storeys: 100,
  bays: 30, // per direction
  nodes: 8000, // (bays X+1)·(bays Y+1)·(storeys+1)
  optNodes: 1500, // member-size optimisation (many re-analyses)
  backgroundNodes: 1500, // above this the run shows a "large model" progress notice
  minSpanM: 1.5,
  maxSpanM: 15,
} as const;

export const frameNodeCount = (storeys: number, baysX: number, baysY: number): number =>
  (baysX + 1) * (baysY + 1) * (storeys + 1);

/** Big models: the viewer and tables switch to their lighter modes above this many nodes / rows. */
export const LARGE_MODEL_NODES = 1500;

/** Viewer: above this many visible members the 3D view draws merged line layers (one draw call each). */
export const LARGE_VIEW_MEMBERS = 3000;

/** "Large model" notice (form + chat) when a run is above backgroundNodes; null for normal models. */
export function largeModelNotice(storeys: number, baysX: number, baysY: number, lang: "en" | "fa"): string | null {
  if (![storeys, baysX, baysY].every((v) => Number.isFinite(v) && v > 0)) return null;
  const n = frameNodeCount(storeys, baysX, baysY);
  if (n <= FRAME_LIMITS.backgroundNodes || n > FRAME_LIMITS.nodes) return null;
  return lang === "fa"
    ? `مدل بزرگ (${n.toLocaleString("fa-IR")} گره) — تحلیل و طراحی ممکن است حدود ۳۰ ثانیه یا بیشتر طول بکشد.`
    : `Large model (${n} nodes) — analysis + design may take ~30 s or more.`;
}
