"use client";

import { useMemo, useState } from "react";

import { FIELD_UNITS, contourColor, dcColor, sampleField, stripProfile, type FoundationField } from "@/lib/foundation-view";
import { gridLabelX, gridLabelY, type ViewerData, type ViewerFooting } from "@/lib/frame3d-viewer";

type T = (k: string) => string;
const FIELDS: Array<[FoundationField, string]> = [
  ["pressure", "Soil pressure"], ["mx", "Moment Mx"], ["my", "Moment My"], ["settlement", "Settlement"], ["punching", "Punching D/C"],
];

/** SAFE-like plan of the footings: contours, punching D/C, strip cut, extruded 3D and a properties panel. Generic layout. */
export default function FoundationView({ data, qa, t }: { data: ViewerData; qa: number; t: T }) {
  const fs = data.footings;
  const [field, setField] = useState<FoundationField>("pressure");
  const [is3d, setIs3d] = useState(false);
  const [cutLine, setCutLine] = useState(0);
  const [sel, setSel] = useState<ViewerFooting | null>(null);
  const S = useMemo(() => sampleField(fs, field, qa), [fs, field, qa]);
  if (!fs.length) return null;
  const pad = 3;
  const x0 = Math.min(...fs.map((f) => f.x - f.B / 2), ...data.xs) - pad, x1 = Math.max(...fs.map((f) => f.x + f.B / 2), ...data.xs) + pad;
  const y0 = Math.min(...fs.map((f) => f.y - f.B / 2), ...data.ys) - pad, y1 = Math.max(...fs.map((f) => f.y + f.B / 2), ...data.ys) + pad;
  const W = 640, k = W / (x1 - x0), H = (y1 - y0) * k;
  const iso = (x: number, y: number, z = 0): [number, number] =>
    is3d ? [(x - x0) * k * 0.8 + (y - y0) * k * 0.45, H * 0.9 - (y - y0) * k * 0.45 - z * k] : [(x - x0) * k, H - (y - y0) * k];
  const yCut = data.ys[Math.min(cutLine, data.ys.length - 1)] ?? 0;
  const prof = stripProfile(fs, field, qa, yCut);
  const pmax = Math.max(1e-9, ...prof.map((p) => p.v));
  const fmt = (v: number) => (field === "punching" ? v.toFixed(2) : v.toFixed(field === "settlement" ? 1 : 0));
  const cells = S.grid[0]?.length ?? 1;
  const info = (sel?.info ?? {}) as Record<string, unknown>;
  return (
    <section className="card foundation-view" aria-label={t("Foundation view")}>
      <div className="v3d-toolbar">
        <strong>{t("Foundation view")}</strong>
        <label>
          {t("Display")}{" "}
          <select aria-label={t("Display")} value={field} onChange={(e) => setField(e.target.value as FoundationField)}>
            {FIELDS.map(([f, l]) => <option key={f} value={f}>{t(l)}</option>)}
          </select>
        </label>
        <label><input type="checkbox" checked={is3d} onChange={(e) => setIs3d(e.target.checked)} /> {t("3D extruded")}</label>
        <label>
          {t("Strip cut on axis")}{" "}
          <select aria-label={t("Strip cut on axis")} value={cutLine} onChange={(e) => setCutLine(Number(e.target.value))}>
            {data.ys.map((_, j) => <option key={j} value={j}>{gridLabelY(j)}</option>)}
          </select>
        </label>
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <svg width={W * (is3d ? 1.25 : 1)} height={H + 10} style={{ background: "#1f2a38" }} role="img" aria-label="foundation plan">
          {!is3d && data.xs.map((x, i) => (
            <g key={`x${i}`}>
              <line x1={iso(x, y0 + 1)[0]} y1={iso(x, y0 + 1)[1]} x2={iso(x, y1 - 1)[0]} y2={iso(x, y1 - 1)[1]} stroke="#8fa3bf" strokeDasharray="6 4" />
              {[y0 + 0.6, y1 - 0.6].map((yy, q) => <g key={q}><circle cx={iso(x, yy)[0]} cy={iso(x, yy)[1]} r={9} fill="none" stroke="#e2e8f0" /><text x={iso(x, yy)[0]} y={iso(x, yy)[1] + 4} fontSize={10} fill="#e2e8f0" textAnchor="middle">{gridLabelX(i)}</text></g>)}
            </g>
          ))}
          {!is3d && data.ys.map((y, j) => (
            <g key={`y${j}`}>
              <line x1={iso(x0 + 1, y)[0]} y1={iso(x0 + 1, y)[1]} x2={iso(x1 - 1, y)[0]} y2={iso(x1 - 1, y)[1]} stroke={j === cutLine ? "#f472b6" : "#8fa3bf"} strokeDasharray={j === cutLine ? undefined : "6 4"} strokeWidth={j === cutLine ? 2 : 1} />
              {[x0 + 0.6, x1 - 0.6].map((xx, q) => <g key={q}><circle cx={iso(xx, y)[0]} cy={iso(xx, y)[1]} r={9} fill="none" stroke="#e2e8f0" /><text x={iso(xx, y)[0]} y={iso(xx, y)[1] + 4} fontSize={10} fill="#e2e8f0" textAnchor="middle">{gridLabelY(j)}</text></g>)}
            </g>
          ))}
          {fs.map((f, n) => {
            const h3 = is3d ? Math.max(f.h, 0.3) * 2 : 0;
            const dc = Number(f.info?.DC_punching ?? 0);
            return (
              <g key={f.column} data-footing={f.column} style={{ cursor: "pointer" }} onClick={() => setSel(f)}>
                {is3d ? (
                  <polygon points={[iso(f.x - f.B / 2, f.y - f.B / 2), iso(f.x + f.B / 2, f.y - f.B / 2), iso(f.x + f.B / 2, f.y - f.B / 2, h3), iso(f.x - f.B / 2, f.y - f.B / 2, h3)].map((p) => p.join(",")).join(" ")} fill="#475569" stroke="#0f172a" />
                ) : null}
                {S.grid[n].map((row, i) => row.map((v, j) => {
                  const cx = f.x - f.B / 2 + (f.B * j) / cells, cy = f.y - f.B / 2 + (f.B * i) / cells, d = f.B / cells;
                  const pts = [iso(cx, cy, h3), iso(cx + d, cy, h3), iso(cx + d, cy + d, h3), iso(cx, cy + d, h3)];
                  const col = field === "punching" ? dcColor(v) : contourColor((v - S.lo) / (S.hi - S.lo));
                  return <polygon key={`${i}-${j}`} points={pts.map((p) => p.join(",")).join(" ")} fill={col} stroke={col} />;
                }))}
                <polygon points={[iso(f.x - f.B / 2, f.y - f.B / 2, h3), iso(f.x + f.B / 2, f.y - f.B / 2, h3), iso(f.x + f.B / 2, f.y + f.B / 2, h3), iso(f.x - f.B / 2, f.y + f.B / 2, h3)].map((p) => p.join(",")).join(" ")}
                  fill="none" stroke={sel?.column === f.column ? "#ff00ff" : "#0f172a"} strokeWidth={sel?.column === f.column ? 3 : 1} />
                {(() => { const c1 = Number(f.info?.c1_m ?? 0.4) / 2, c2 = Number(f.info?.c2_m ?? 0.4) / 2; const z = h3;
                  return <polygon points={[iso(f.x - c1, f.y - c2, z), iso(f.x + c1, f.y - c2, z), iso(f.x + c1, f.y + c2, z), iso(f.x - c1, f.y + c2, z)].map((p) => p.join(",")).join(" ")} fill="#e2e8f0" stroke="#0f172a" />; })()}
                <text x={iso(f.x, f.y - f.B / 2, h3)[0]} y={iso(f.x, f.y - f.B / 2, h3)[1] + 12} fontSize={10} fill="#fff" textAnchor="middle">{`D/C ${dc.toFixed(2)}`}</text>
              </g>
            );
          })}
        </svg>
        <div style={{ minWidth: 220 }}>
          <strong>{t(FIELDS.find((x) => x[0] === field)![1])} ({FIELD_UNITS[field]})</strong>
          {field === "punching" ? (
            <ul className="legend-list">{[["≤ 0.70", "#22c55e"], ["0.70 – 0.90", "#facc15"], ["0.90 – 1.00", "#f97316"], ["> 1.00", "#ef4444"]].map(([l, c]) => <li key={l}><span style={{ background: c, display: "inline-block", width: 12, height: 12, marginInlineEnd: 6 }} />{l}</li>)}</ul>
          ) : (
            <div>
              <div style={{ height: 12, width: 200, background: `linear-gradient(90deg, ${[0, 0.33, 0.66, 1].map(contourColor).join(",")})` }} />
              <div style={{ display: "flex", justifyContent: "space-between", width: 200 }}><span>{fmt(S.lo)}</span><span>{fmt(S.hi)}</span></div>
            </div>
          )}
          <p className="muted" style={{ maxWidth: 260 }}>
            {t("Method: rigid footing, linear soil pressure q = P/A ± M·c/I under D+L; cantilever moments from the column face; settlement by Winkler springs ks = 120·qa.")}
          </p>
          {sel ? (
            <div className="footing-props" role="region" aria-label={t("Footing properties")}>
              <h4>{`${String(info.group ?? "F")} · ${sel.column}`}</h4>
              <table className="mini-table"><tbody>
                {([["B x B (m)", `${sel.B} x ${sel.B}`], ["h (m)", sel.h], ["P (D+L) kN", info.P_kn], ["Mx / My kN·m", `${info.Mx_kn_m} / ${info.My_kn_m}`],
                  ["Bottom mesh", info.bars], ["q max kPa", info.q_max_kpa], ["Bearing D/C", info.bearing_dc], ["One-way shear D/C", info.DC_oneway],
                  ["Punching D/C", info.DC_punching], ["Flexure D/C", info.DC_flexure], ["Status", info.status]] as Array<[string, unknown]>).map(([k2, v]) => (
                  <tr key={k2}><td>{t(k2)}</td><td>{String(v ?? "-")}</td></tr>
                ))}
              </tbody></table>
            </div>
          ) : <p className="muted">{t("Click a footing to see its properties, reinforcement and checks.")}</p>}
        </div>
      </div>
      <div>
        <strong>{t("Strip cut on axis")} {gridLabelY(cutLine)}</strong>
        <svg width={W} height={120} style={{ background: "#1f2a38" }} role="img" aria-label="strip profile">
          <line x1={0} y1={100} x2={W} y2={100} stroke="#8fa3bf" />
          <polyline fill="none" stroke="#f472b6" strokeWidth={2} points={prof.map((p) => `${(p.x - x0) * k},${100 - (p.v / pmax) * 85}`).join(" ")} />
          <text x={6} y={14} fontSize={11} fill="#e2e8f0">{`max ${fmt(pmax)} ${FIELD_UNITS[field]}`}</text>
        </svg>
      </div>
    </section>
  );
}
