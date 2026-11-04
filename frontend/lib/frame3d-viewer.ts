// Pure data helpers for the ETABS-style 3D viewer (no three.js here so they are unit-testable).

export type ViewerNode = { id: string; x: number; y: number; z: number };
export type ViewerMember = {
  id: string;
  i: string;
  j: string;
  type: "beam" | "column";
  storey: number;
  section: string;
  b: number;
  h: number;
  group: string | null;
  dc: number | null;
  designStatus: string | null;
  rebar: string | null;
};
export type ViewerFooting = { column: string; node: string; x: number; y: number; position: string; B: number; h: number; info?: Record<string, unknown> };
export type ViewerData = {
  nodes: ViewerNode[];
  supports: string[];
  members: ViewerMember[];
  cases: string[];
  combos: Record<string, Record<string, number>>;
  forces: Record<string, Record<string, number[]>>;
  displacements: Record<string, Record<string, number[]>>;
  reactions: Record<string, Record<string, number[]>>;
  footings: ViewerFooting[];
  levels: number[];
  xs: number[];
  ys: number[];
  zs: number[];
  /** Mode shapes (any model): nodal displacement vectors normalised to max |u| = 1. */
  modes: ViewerMode[];
  /** Member inspector: per case, [N, V2, V3, T, M2, M3] at i then j (optional; older payloads lack it). */
  forces6?: Record<string, Record<string, number[]>>;
  material?: { type: string; fc_mpa?: number; fy_mpa?: number };
};
export type ViewerMode = {
  mode: number;
  T: number;
  freq: number;
  mass: { ux: number; uy: number; rz: number };
  disp: Record<string, number[]>;
};

export function parseModes(raw: unknown): ViewerMode[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((m): m is Record<string, unknown> => !!m && typeof m === "object" && !!(m as Record<string, unknown>).disp)
    .map((m, i) => ({
      mode: num(m.mode, i + 1),
      T: num(m.T_s),
      freq: num(m.freq_hz) || (num(m.T_s) > 0 ? 1 / num(m.T_s) : 0),
      mass: { ux: num(m.mass_x_pct), uy: num(m.mass_y_pct), rz: num(m.mass_rz_pct) },
      disp: m.disp as Record<string, number[]>,
    }));
}

/** Animated mode displacement of one node: amplitude × φ × sin(2π·speed·t) (sinusoidal, any model). */
export function modeOffset(mode: ViewerMode, nodeId: string, amplitude: number, timeS: number, speed = 1): [number, number, number] {
  const u = mode.disp[nodeId] ?? [0, 0, 0];
  const f = amplitude * Math.sin(2 * Math.PI * speed * timeS);
  return [(u[0] ?? 0) * f, (u[1] ?? 0) * f, (u[2] ?? 0) * f];
}

/** "animate mode 2" / «مود ۲ را نشان بده» -> 2 */
export function requestedMode(text: string): number | null {
  const t = text.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d))).toLowerCase();
  const m = /(?:mode|مود)\s*(?:shape\s*)?(?:no\.?\s*)?(\d+)/.exec(t);
  return m ? Number(m[1]) : null;
}
export type DiagramKind = "M3" | "V2" | "P";

function num(v: unknown, d = 0): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : d;
}

function uniqSorted(values: number[]): number[] {
  return Array.from(new Set(values.map((v) => Math.round(v * 1000) / 1000))).sort((a, b) => a - b);
}

export function mapViewerData(raw: unknown): ViewerData | null {
  if (!raw || typeof raw !== "object") return null;
  const d = raw as Record<string, unknown>;
  if (!Array.isArray(d.nodes) || !Array.isArray(d.members)) return null;
  const nodes: ViewerNode[] = (d.nodes as Array<Record<string, unknown>>).map((n) => ({
    id: String(n.id),
    x: num(n.x),
    y: num(n.y),
    z: num(n.z),
  }));
  const members: ViewerMember[] = (d.members as Array<Record<string, unknown>>).map((m) => ({
    id: String(m.id),
    i: String(m.i),
    j: String(m.j),
    type: m.type === "column" ? "column" : "beam",
    storey: num(m.storey),
    section: String(m.section ?? ""),
    b: num(m.b, 0.3),
    h: num(m.h, 0.3),
    group: typeof m.group === "string" ? m.group : null,
    dc: typeof m.dc === "number" ? m.dc : null,
    designStatus: typeof m.design_status === "string" ? m.design_status : null,
    rebar: typeof m.rebar === "string" ? m.rebar : null,
  }));
  const footings: ViewerFooting[] = Array.isArray(d.footings)
    ? (d.footings as Array<Record<string, unknown>>).map((f) => ({
        column: String(f.column),
        node: String(f.node),
        x: num(f.x),
        y: num(f.y),
        position: String(f.position ?? ""),
        info: f,
        B: num(f.B_m),
        h: num(f.h_m),
      }))
    : [];
  const obj = <T,>(v: unknown) => (v && typeof v === "object" ? (v as T) : ({} as T));
  return {
    nodes,
    supports: Array.isArray(d.supports) ? (d.supports as unknown[]).map(String) : [],
    members,
    cases: Array.isArray(d.cases) ? (d.cases as unknown[]).map(String) : [],
    combos: obj<Record<string, Record<string, number>>>(d.combos),
    forces: obj<Record<string, Record<string, number[]>>>(d.forces),
    displacements: obj<Record<string, Record<string, number[]>>>(d.displacements_mm),
    reactions: obj<Record<string, Record<string, number[]>>>(d.reactions),
    footings,
    levels: Array.isArray(d.diaphragm_levels) ? (d.diaphragm_levels as unknown[]).map((x) => num(x)) : [],
    xs: uniqSorted(nodes.map((n) => n.x)),
    ys: uniqSorted(nodes.map((n) => n.y)),
    zs: uniqSorted(nodes.map((n) => n.z)),
    modes: parseModes(d.modes),
    forces6: obj<Record<string, Record<string, number[]>>>(d.forces6),
    material: d.material && typeof d.material === "object" ? (d.material as ViewerData["material"]) : undefined,
  };
}

/** Load-case/combination list (cases first, then combos) shown in the selector. */
export function loadOptions(v: ViewerData): string[] {
  return [...v.cases, ...Object.keys(v.combos)];
}

export function factorsFor(v: ViewerData, name: string): Record<string, number> {
  if (v.combos[name]) return v.combos[name];
  return v.cases.includes(name) ? { [name]: 1 } : {};
}

export function combine(table: Record<string, Record<string, number[]>>, factors: Record<string, number>, key: string): number[] | null {
  let out: number[] | null = null;
  for (const [c, f] of Object.entries(factors)) {
    const vec = table[c]?.[key];
    if (!vec) continue;
    out = out ? out.map((o, k) => o + f * (vec[k] ?? 0)) : vec.map((x) => f * x);
  }
  return out;
}

export function memberForces(v: ViewerData, load: string, memberId: string): number[] | null {
  return combine(v.forces, factorsFor(v, load), memberId);
}

export function nodeDisplacement(v: ViewerData, load: string, nodeId: string): number[] {
  return combine(v.displacements, factorsFor(v, load), nodeId) ?? [0, 0, 0];
}

export function baseReactions(v: ViewerData, load: string): Array<{ node: string; values: number[] }> {
  return v.supports.map((node) => ({ node, values: combine(v.reactions, factorsFor(v, load), node) ?? [0, 0, 0, 0, 0, 0] }));
}

export function memberLength(v: ViewerData, m: ViewerMember): number {
  const a = v.nodes.find((n) => n.id === m.i);
  const b = v.nodes.find((n) => n.id === m.j);
  if (!a || !b) return 0;
  return Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
}

/** Diagram ordinates at n+1 stations along the member. f = [N, Vi, Mi, Mj, w]. */
export function diagramValues(f: number[] | null, length: number, kind: DiagramKind, n = 10): number[] {
  if (!f || length <= 0) return Array(n + 1).fill(0);
  const [N, , Mi, Mj, w] = f;
  const out: number[] = [];
  for (let s = 0; s <= n; s++) {
    const x = (length * s) / n;
    if (kind === "P") out.push(N);
    else if (kind === "M3") out.push(Mi + ((Mj - Mi) * x) / length + (w * (x * x - x * length)) / 2);
    else out.push((Mj - Mi) / length - (w * length) / 2 + w * x);
  }
  return out;
}

export function maxAbs(values: number[]): number {
  return values.reduce((m, x) => Math.max(m, Math.abs(x)), 0);
}

/** ETABS-like D/C colour map: green < 0.7, yellow 0.7-0.9, orange 0.9-1.0, red > 1.0, grey = not designed. */
export function dcColor(dc: number | null): string {
  if (dc === null || dc === undefined) return "#9aa4b1";
  if (dc > 1.0 + 1e-9) return "#e53935";
  if (dc > 0.9) return "#fb8c00";
  if (dc > 0.7) return "#fdd835";
  return "#43a047";
}

export const DC_LEGEND: Array<[string, string]> = [
  ["#43a047", "0 – 0.70"],
  ["#fdd835", "0.70 – 0.90"],
  ["#fb8c00", "0.90 – 1.00"],
  ["#e53935", "> 1.00"],
  ["#9aa4b1", "—"],
];

export type TreeGroup = { key: string; label: string; items: string[] };

/** Model explorer: Stories -> Columns / Beams. */
export function explorerTree(v: ViewerData): TreeGroup[] {
  const out: TreeGroup[] = [];
  for (const k of [...v.levels].sort((a, b) => b - a)) {
    out.push({ key: `S${k}-C`, label: `Story ${k} · Columns`, items: v.members.filter((m) => m.storey === k && m.type === "column").map((m) => m.id) });
    out.push({ key: `S${k}-B`, label: `Story ${k} · Beams`, items: v.members.filter((m) => m.storey === k && m.type === "beam").map((m) => m.id) });
  }
  if (v.footings.length) out.push({ key: "F", label: "Footings", items: v.footings.map((f) => `F-${f.column}`) });
  return out;
}

/** Same convention as the DXF drawings: grid lines along X (x = const, ⟂ X) are numbered 1, 2, 3…;
 * grid lines along Y (y = const, ⟂ Y) are lettered A, B, C… */
export function gridLabelX(i: number): string {
  return String(i + 1);
}

export function gridLabelY(i: number): string {
  let s = "";
  let n = i;
  do {
    s = String.fromCharCode(65 + (n % 26)) + s;
    n = Math.floor(n / 26) - 1;
  } while (n >= 0);
  return s;
}

export const GRID_LEGEND = "Grids 1,2,3… ⟂ X ; Grids A,B,C… ⟂ Y";

/** Visible members for "plan at story k" (beams of level k + columns below it) or all when storey is null. */
export function visibleMembers(v: ViewerData, storey: number | null): ViewerMember[] {
  if (storey === null) return v.members;
  return v.members.filter((m) => m.storey === storey);
}

/** Auto deformation scale so that the largest displacement draws as ~4% of the model size. */
export function autoDeformScale(v: ViewerData, load: string): number {
  const size = Math.max(v.xs[v.xs.length - 1] - v.xs[0], v.ys[v.ys.length - 1] - v.ys[0], v.zs[v.zs.length - 1] - v.zs[0], 1);
  let umax = 0;
  for (const n of v.nodes) umax = Math.max(umax, maxAbs(nodeDisplacement(v, load, n.id)));
  return umax > 0 ? (0.04 * size * 1000) / umax : 1;
}

/** Storey lateral forces F_k (from the payload) -> storey shear V_k = sum of F above and at k. */
export function storeyShears(levelForces: Record<string, number> | null | undefined): Array<{ storey: number; forceKn: number; shearKn: number }> {
  const rows = Object.entries(levelForces ?? {})
    .map(([k, f]) => ({ storey: Number(k), forceKn: num(f) }))
    .filter((r) => Number.isFinite(r.storey) && r.storey > 0)
    .sort((a, b) => b.storey - a.storey);
  let acc = 0;
  return rows.map((r) => {
    acc += r.forceKn;
    return { ...r, shearKn: Math.round(acc * 10) / 10 };
  });
}

export type ViewKind = "3D" | "PLAN" | "ELEV_X" | "ELEV_Y";

/**
 * Members shown for a view. PLAN: the selected storey (top storey when All) — its beams and the columns below it.
 * ELEV_X: the frame on Y grid line `line` (XZ plane); ELEV_Y: the frame on X grid line `line` (YZ plane);
 * `line` null = all lines. 3D: storey filter only.
 */
export function viewMembers(v: ViewerData, view: ViewKind, storey: number | null, line: number | null): ViewerMember[] {
  const byId = new Map(v.nodes.map((n) => [n.id, n]));
  const on = (m: ViewerMember, axis: "x" | "y", c: number) => {
    const a = byId.get(m.i), b = byId.get(m.j);
    return !!a && !!b && Math.abs(a[axis] - c) < 1e-6 && Math.abs(b[axis] - c) < 1e-6;
  };
  if (view === "PLAN") {
    const k = planStorey(v, storey);
    return v.members.filter((m) => m.storey === k);
  }
  if (view === "ELEV_X") return line === null ? v.members : v.members.filter((m) => on(m, "y", v.ys[line]));
  if (view === "ELEV_Y") return line === null ? v.members : v.members.filter((m) => on(m, "x", v.xs[line]));
  return storey === null ? v.members : v.members.filter((m) => m.storey === storey);
}

/** Storey shown in plan: the selected one, else the top storey. */
export function planStorey(v: ViewerData, storey: number | null): number {
  return storey ?? (v.levels.length ? Math.max(...v.levels) : 0);
}

/** Orthographic camera for plan/elevations: position, up vector and half-extents (world units) of the frustum. */
export function orthoCamera(v: ViewerData, view: Exclude<ViewKind, "3D">, storey: number | null, line: number | null, aspect: number) {
  const x0 = v.xs[0], x1 = v.xs[v.xs.length - 1], y0 = v.ys[0], y1 = v.ys[v.ys.length - 1], z0 = Math.min(v.zs[0], -1), z1 = v.zs[v.zs.length - 1];
  const pad = 3;
  let w: number, h: number, pos: [number, number, number], target: [number, number, number], up: [number, number, number];
  if (view === "PLAN") {
    const z = v.zs[planStorey(v, storey)] ?? z1;
    w = x1 - x0 + 2 * pad; h = y1 - y0 + 2 * pad;
    target = [(x0 + x1) / 2, (y0 + y1) / 2, z]; pos = [target[0], target[1], z + 100]; up = [0, 1, 0];
  } else if (view === "ELEV_X") {
    const y = line === null ? (y0 + y1) / 2 : v.ys[line];
    w = x1 - x0 + 2 * pad; h = z1 - z0 + 2 * pad;
    target = [(x0 + x1) / 2, y, (z0 + z1) / 2]; pos = [target[0], y - 100, target[2]]; up = [0, 0, 1];
  } else {
    const x = line === null ? (x0 + x1) / 2 : v.xs[line];
    w = y1 - y0 + 2 * pad; h = z1 - z0 + 2 * pad;
    target = [x, (y0 + y1) / 2, (z0 + z1) / 2]; pos = [x + 100, target[1], target[2]]; up = [0, 0, 1];
  }
  const halfH = Math.max(h / 2, w / 2 / Math.max(aspect, 1e-3));
  return { pos, target, up, halfW: halfH * aspect, halfH };
}
