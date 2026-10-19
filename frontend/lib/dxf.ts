// Minimal ASCII DXF reader for the built-in viewer (LINE, POLYLINE/VERTEX incl. 3D, LWPOLYLINE, CIRCLE, ARC, TEXT/MTEXT).

export type DxfEntity =
  | { type: "LINE"; layer: string; pts: number[][] }
  | { type: "POLY"; layer: string; pts: number[][]; closed: boolean }
  | { type: "CIRCLE"; layer: string; c: number[]; r: number }
  | { type: "TEXT"; layer: string; p: number[]; h: number; text: string; center: boolean };

export type DxfSheet = { name: string; x0: number; x1: number };
export type DxfDoc = { entities: DxfEntity[]; layers: string[]; sheets: DxfSheet[]; is3d: boolean };

function pairs(text: string): Array<[number, string]> {
  const lines = text.split(/\r?\n/);
  const out: Array<[number, string]> = [];
  for (let i = 0; i + 1 < lines.length; i += 2) out.push([Number(lines[i].trim()), lines[i + 1].trim()]);
  return out;
}

export function parseDxf(text: string): DxfDoc {
  const ps = pairs(text);
  let i = 0;
  while (i < ps.length && !(ps[i][0] === 2 && ps[i][1] === "ENTITIES")) i++;
  const entities: DxfEntity[] = [];
  let is3d = false;
  let poly: { layer: string; pts: number[][]; closed: boolean } | null = null;
  while (i < ps.length) {
    if (ps[i][0] !== 0) { i++; continue; }
    const type = ps[i][1];
    if (type === "ENDSEC" || type === "EOF") break;
    const g: Record<number, string[]> = {};
    i++;
    while (i < ps.length && ps[i][0] !== 0) {
      (g[ps[i][0]] ??= []).push(ps[i][1]);
      i++;
    }
    const n = (code: number, k = 0) => Number(g[code]?.[k] ?? 0);
    const layer = g[8]?.[0] ?? "0";
    if (n(30) || n(31)) is3d = true;
    if (type === "LINE") entities.push({ type: "LINE", layer, pts: [[n(10), n(20), n(30)], [n(11), n(21), n(31)]] });
    else if (type === "POLYLINE") poly = { layer, pts: [], closed: (n(70) & 1) === 1 };
    else if (type === "VERTEX" && poly) poly.pts.push([n(10), n(20), n(30)]);
    else if (type === "SEQEND" && poly) { entities.push({ type: "POLY", ...poly }); poly = null; }
    else if (type === "LWPOLYLINE") {
      const xs = g[10] ?? [], ys = g[20] ?? [];
      entities.push({ type: "POLY", layer, pts: xs.map((x, k) => [Number(x), Number(ys[k] ?? 0), 0]), closed: (n(70) & 1) === 1 });
    } else if (type === "CIRCLE" || type === "ARC") entities.push({ type: "CIRCLE", layer, c: [n(10), n(20), n(30)], r: n(40) });
    else if (type === "TEXT" || type === "MTEXT") {
      const center = Boolean(g[72]?.[0] && g[72][0] !== "0");
      const p = center && g[11] ? [n(11), n(21), n(31)] : [n(10), n(20), n(30)];
      entities.push({ type: "TEXT", layer, p, h: n(40) || 0.3, text: (g[1]?.[0] ?? "").replace(/\\P/g, " "), center });
    }
  }
  const layers = Array.from(new Set(entities.map((e) => e.layer))).sort();
  return { entities, layers, sheets: findSheets(entities), is3d };
}

/** Sheets = side-by-side plans titled by TEXT on layer TITLE (our plans.dxf places story k at x offset (k-1)*pitch). */
export function findSheets(entities: DxfEntity[]): DxfSheet[] {
  const titles = entities
    .filter((e): e is Extract<DxfEntity, { type: "TEXT" }> => e.type === "TEXT" && e.layer === "TITLE")
    .sort((a, b) => a.p[0] - b.p[0]);
  if (titles.length < 2) return [];
  return titles.map((t, k) => {
    const prev = titles[k - 1]?.p[0], next = titles[k + 1]?.p[0];
    const pitch = (next ?? t.p[0] + (t.p[0] - prev!)) - t.p[0];
    return { name: t.text.split("  ")[0], x0: t.p[0] - pitch * 0.25, x1: t.p[0] + pitch * 0.75 };
  });
}

export type Projection = "top" | "iso";

export function project(p: number[], proj: Projection): [number, number] {
  if (proj === "top") return [p[0], p[1]];
  const c = Math.cos(Math.PI / 6);
  return [(p[0] - p[1]) * c, (p[0] + p[1]) * 0.5 + p[2]];
}

function entityXs(e: DxfEntity): number[] {
  if (e.type === "LINE" || e.type === "POLY") return e.pts.map((p) => p[0]);
  if (e.type === "CIRCLE") return [e.c[0]];
  return [e.p[0]];
}

export function filterEntities(doc: DxfDoc, visibleLayers: Set<string>, sheet: DxfSheet | null): DxfEntity[] {
  return doc.entities.filter((e) => {
    if (!visibleLayers.has(e.layer)) return false;
    if (!sheet) return true;
    const xs = entityXs(e);
    const mid = (Math.min(...xs) + Math.max(...xs)) / 2;
    return mid >= sheet.x0 && mid < sheet.x1;
  });
}

export function bounds(entities: DxfEntity[], proj: Projection): [number, number, number, number] {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const add = (p: number[], r = 0) => {
    const [x, y] = project(p, proj);
    x0 = Math.min(x0, x - r); y0 = Math.min(y0, y - r); x1 = Math.max(x1, x + r); y1 = Math.max(y1, y + r);
  };
  for (const e of entities) {
    if (e.type === "LINE" || e.type === "POLY") e.pts.forEach((p) => add(p));
    else if (e.type === "CIRCLE") add(e.c, e.r);
    else add(e.p, e.h);
  }
  if (!Number.isFinite(x0)) return [0, 0, 10, 10];
  return [x0, y0, x1 - x0 || 1, y1 - y0 || 1];
}

const LAYER_COLORS: Record<string, string> = {
  GRID: "#64748b", GRID_TEXT: "#cbd5e1", COLUMNS: "#f8fafc", BEAMS: "#38bdf8", TITLE: "#fde68a",
  SECTION_TEXT: "#a5f3fc", DESIGN_TEXT: "#86efac", FOUNDATION: "#d6a35c", FOUNDATION_TEXT: "#fcd34d",
  FRAME_COLUMNS: "#f8fafc", FRAME_BEAMS: "#38bdf8", FRAME_LABELS: "#fde68a",
};

export function layerColor(layer: string): string {
  if (LAYER_COLORS[layer]) return LAYER_COLORS[layer];
  let h = 0;
  for (const ch of layer) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${h} 70% 70%)`;
}
