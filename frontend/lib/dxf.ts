// Minimal ASCII DXF reader for the built-in viewer: LINE, POLYLINE/VERTEX incl. 3D, LWPOLYLINE, CIRCLE, ARC, TEXT/MTEXT,
// DIMENSION (drawn from its rendered *D block), HATCH (boundary drawn filled), LEADER. Paper-space entities are skipped
// (the viewer shows model space). Persian text written in visual order for AutoCAD is turned back to logical order.

export type DxfEntity =
  | { type: "LINE"; layer: string; pts: number[][] }
  | { type: "POLY"; layer: string; pts: number[][]; closed: boolean; fill?: boolean }
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

/** AutoCAD-ready Persian (shaped presentation forms, visual order) -> logical order for the browser's bidi. */
export function logicalText(t: string): string {
  if (!/[\uFB50-\uFDFF\uFE70-\uFEFF]/.test(t)) return t;
  const runs = t.match(/[A-Za-z0-9.,:+\-±×x@=/%°()Φ]+|[^A-Za-z0-9.,:+\-±×x@=/%°()Φ]+/g) ?? [t];
  const flip: Record<string, string> = { "(": ")", ")": "(" };
  return runs
    .reverse()
    .map((r) => (/^[A-Za-z0-9.,:+\-±×x@=/%°()Φ]+$/.test(r) ? r : Array.from(r).reverse().map((c) => flip[c] ?? c).join("")))
    .join("")
    .normalize("NFKC");
}

type Group = Record<number, string[]>;

function readEntities(ps: Array<[number, string]>, i: number, onEntity: (type: string, g: Group) => void, stop: (type: string, g: Group) => boolean): number {
  while (i < ps.length) {
    if (ps[i][0] !== 0) { i++; continue; }
    const type = ps[i][1];
    const g: Group = {};
    i++;
    while (i < ps.length && ps[i][0] !== 0) {
      (g[ps[i][0]] ??= []).push(ps[i][1]);
      i++;
    }
    if (stop(type, g)) break;
    onEntity(type, g);
  }
  return i;
}

export function parseDxf(text: string): DxfDoc {
  const ps = pairs(text);
  let is3d = false;
  const toEntities = (out: DxfEntity[]) => {
    let poly: { layer: string; pts: number[][]; closed: boolean } | null = null;
    return (type: string, g: Group) => {
      const n = (code: number, k = 0) => Number(g[code]?.[k] ?? 0);
      const layer = g[8]?.[0] ?? "0";
      if (g[67]?.[0] === "1") return; // paper space
      if (n(30) || n(31)) is3d = true;
      if (type === "LINE") out.push({ type: "LINE", layer, pts: [[n(10), n(20), n(30)], [n(11), n(21), n(31)]] });
      else if (type === "POLYLINE") poly = { layer, pts: [], closed: (n(70) & 1) === 1 };
      else if (type === "VERTEX" && poly) poly.pts.push([n(10), n(20), n(30)]);
      else if (type === "SEQEND" && poly) { out.push({ type: "POLY", ...poly }); poly = null; }
      else if (type === "LWPOLYLINE" || type === "LEADER" || type === "HATCH") {
        let xs = g[10] ?? [], ys = g[20] ?? [];
        if (type === "HATCH") { xs = xs.slice(1); ys = ys.slice(1); } // first 10/20 is the elevation point
        const pts = xs.map((x, k) => [Number(x), Number(ys[k] ?? 0), 0]);
        if (pts.length > 1) out.push({ type: "POLY", layer, pts, closed: type === "HATCH" || (type === "LWPOLYLINE" && (n(70) & 1) === 1), fill: type === "HATCH" });
      } else if (type === "CIRCLE" || type === "ARC") out.push({ type: "CIRCLE", layer, c: [n(10), n(20), n(30)], r: n(40) });
      else if (type === "SOLID") out.push({ type: "POLY", layer, pts: [[n(10), n(20), 0], [n(11), n(21), 0], [n(13), n(23), 0], [n(12), n(22), 0]], closed: true, fill: true });
      else if (type === "TEXT" || type === "MTEXT") {
        const center = Boolean((g[72]?.[0] && g[72][0] !== "0") || (g[73]?.[0] && g[73][0] !== "0"));
        const p = center && g[11] ? [n(11), n(21), n(31)] : [n(10), n(20), n(30)];
        out.push({ type: "TEXT", layer, p, h: n(40) || 0.3, text: logicalText((g[1]?.[0] ?? "").replace(/\\P/g, " ")), center });
      } else if (type === "DIMENSION") {
        for (const e of blocks.get(g[2]?.[0] ?? "") ?? []) out.push({ ...e, layer });
      }
    };
  };
  // anonymous dimension blocks (*D1, *D2 ...) hold the rendered dimension geometry
  const blocks = new Map<string, DxfEntity[]>();
  let i = 0;
  while (i < ps.length && !(ps[i][0] === 2 && ps[i][1] === "BLOCKS")) i++;
  if (i < ps.length) {
    let cur: DxfEntity[] | null = null;
    let handler: ((type: string, g: Group) => void) | null = null;
    i = readEntities(ps, i + 1, (type, g) => {
      if (type === "BLOCK") {
        const name = g[2]?.[0] ?? "";
        cur = name.startsWith("*D") ? [] : null;
        if (cur) { blocks.set(name, cur); handler = toEntities(cur); }
      } else if (type === "ENDBLK") { cur = null; handler = null; }
      else if (cur && handler) handler(type, { ...g, 67: [] });
    }, (type) => type === "ENDSEC");
  }
  i = 0;
  while (i < ps.length && !(ps[i][0] === 2 && ps[i][1] === "ENTITIES")) i++;
  const entities: DxfEntity[] = [];
  readEntities(ps, i + 1, toEntities(entities), (type) => type === "ENDSEC" || type === "EOF");
  const markers = entities.filter((e): e is Extract<DxfEntity, { type: "TEXT" }> => e.type === "TEXT" && e.layer === "S-SHEET");
  const drawn = entities.filter((e) => e.layer !== "S-SHEET");
  const layers = Array.from(new Set(drawn.map((e) => e.layer))).sort();
  const sheets = markers.length
    ? markers.map((m) => { const [name, x0, x1, title] = m.text.split("|"); return { name: title ? `${name} ${title}` : name, x0: Number(x0), x1: Number(x1) }; })
    : findSheets(drawn);
  return { entities: drawn, layers, sheets, is3d };
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
  "S-AXIS": "#ef4444", "S-AXIS-BUBBLE": "#e2e8f0", "S-CONC": "#f8fafc", "S-CONC-HIDDEN": "#94a3b8", "S-CONC-HATCH": "#475569",
  "S-FOOT": "#d6a35c", "S-FOOT-HATCH": "#7c5a2e", "S-REBAR-MAIN": "#f87171", "S-REBAR-STIR": "#4ade80", "S-TAG": "#fde047",
  "S-DIMS": "#e879f9", "S-LEVEL": "#60a5fa", "S-SECTION": "#f87171", "S-TABLE": "#e2e8f0", "S-NOTES": "#e2e8f0", "S-TITLE": "#fde68a",
  CONC_HATCH: "#475569", SECTION: "#f87171",
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
