// Imported model (ETABS / SAP2000 / SAFE / DXF import) -> data for the shared 3D frame viewer.
// Uses the per-case viewer block returned by the backend analysis; older saved imports without it
// fall back to the geometry from the imported model (no force diagrams).
import type { Frame3dResults } from "./chat-types";
import { mapViewerData, type ViewerData } from "./frame3d-viewer";
import type { ImportState } from "./model-import";

type RawModel = {
  nodes?: Record<string, { x: number; y: number; z: number }>;
  members?: Array<{ id: string; i: string; j: string; type?: string; section?: string }>;
  supports?: Record<string, unknown[]>;
  sections?: Record<string, { b?: number; h?: number }>;
};

export function importViewerData(state: ImportState | null): ViewerData | null {
  if (!state) return null;
  const fromAnalysis = (state.analysis as unknown as { viewer?: unknown } | null)?.viewer;
  if (fromAnalysis) {
    const v = mapViewerData(fromAnalysis);
    if (v && v.members.length) return v;
  }
  const m = state.model as unknown as RawModel;
  if (!m?.nodes || !Array.isArray(m.members) || m.members.length === 0) return null;
  const zs = [...new Set(Object.values(m.nodes).map((n) => Number(n.z.toFixed(3))))].sort((a, b) => a - b);
  const storeyOf = (nid: string) => Math.max(0, zs.indexOf(Number((m.nodes?.[nid]?.z ?? 0).toFixed(3))));
  return mapViewerData({
    nodes: Object.entries(m.nodes).map(([id, n]) => ({ id, ...n })),
    supports: Object.entries(m.supports ?? {}).filter(([, f]) => Array.isArray(f) && f.some(Boolean)).map(([id]) => id),
    members: m.members.map((mem) => {
      const sec = m.sections?.[mem.section ?? ""] ?? {};
      return { id: mem.id, i: mem.i, j: mem.j, type: mem.type === "column" ? "column" : "beam", storey: Math.max(storeyOf(mem.i), storeyOf(mem.j)), section: mem.section ?? "", b: sec.b ?? 0.3, h: sec.h ?? 0.3 };
    }),
    cases: [],
    combos: {},
    forces: {},
    displacements_mm: {},
    reactions: {},
    diaphragm_levels: zs.slice(1).map((_, i) => i + 1),
  });
}

/** Minimal results object for the viewer's side panels (imports have no 2800 drift table). */
export function importViewerResults(lang: string): Frame3dResults {
  return { lang, drift: [], driftReferenceLimitPct: null, storeyLateral: [] } as unknown as Frame3dResults;
}
