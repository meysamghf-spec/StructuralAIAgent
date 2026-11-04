"use client";

import { useState } from "react";
import type { Frame3dDriftRow } from "@/lib/chat-types";
import { type DriftMode, fmtTick, hasDisplacement, niceTicks, seriesFor } from "@/lib/drift-chart";

type T = (key: string) => string;
const COLORS: Record<string, string> = { X: "#5fa8ff", Y: "#ffd54f" };
const W = 280, H = 210, L = 40, R = 12, TOP = 22, B = 36;

/** Storey drift / displacement profile with axes, ticks, legend, limit line and per-storey tooltips. */
export default function DriftChart({ rows, limitPct, storeys, t }: { rows: Frame3dDriftRow[]; limitPct: number | null; storeys: number; t: T }) {
  const [mode, setMode] = useState<DriftMode>("drift");
  const [pick, setPick] = useState<{ dir: string; storey: number } | null>(null);
  const canDisp = hasDisplacement(rows);
  const dirs = (["X", "Y"] as const).filter((d) => rows.some((r) => r.direction === d));
  const series = dirs.map((d) => ({ dir: d, pts: seriesFor(rows, d, mode) }));
  const n = Math.max(1, storeys, ...rows.map((r) => r.storey));
  const showLimit = mode === "drift" && limitPct !== null && limitPct > 0;
  const vmax = Math.max(...series.flatMap((s) => s.pts.map((p) => p.v)), showLimit ? (limitPct as number) : 0, 1e-6);
  const xt = niceTicks(vmax);
  const xMax = xt[xt.length - 1];
  const px = (v: number) => L + ((W - L - R) * v) / xMax;
  const py = (k: number) => H - B - ((H - B - TOP) * k) / n;
  const yStep = Math.max(1, Math.ceil(n / 8));
  const yt = Array.from({ length: Math.floor(n / yStep) + 1 }, (_, i) => i * yStep);
  if (yt[yt.length - 1] !== n) {
    if (n - yt[yt.length - 1] < yStep / 2 && yt.length > 1) yt[yt.length - 1] = n;
    else yt.push(n);
  }
  const unit = mode === "drift" ? "%" : " mm";
  const picked = pick ? rows.find((r) => r.direction === pick.dir && r.storey === pick.storey) : null;
  const peak = series.map((s) => s.pts.reduce((a, p) => (p.v > a.v ? p : a), { storey: 0, v: -Infinity } as { storey: number; v: number }));

  return (
    <div className="v3d-drift-wrap" data-testid="drift-chart" dir="ltr">
      {canDisp ? (
        <div className="v3d-tabs" role="group" aria-label={t("Story drift")}>
          {(["drift", "disp"] as const).map((m) => (
            <button key={m} type="button" data-testid={`drift-mode-${m}`} aria-pressed={mode === m} className={mode === m ? "v3d-btn v3d-on" : "v3d-btn"} onClick={() => { setMode(m); setPick(null); }}>
              {t(m === "drift" ? "Drift" : "Displacement")}
            </button>
          ))}
        </div>
      ) : null}
      <svg viewBox={`0 0 ${W} ${H}`} className="v3d-drift" role="img" aria-label={t(mode === "drift" ? "Drift ratio (%)" : "Displacement (mm)")}>
        {xt.map((v) => (
          <g key={`x${v}`}>
            <line x1={px(v)} x2={px(v)} y1={TOP} y2={H - B} stroke="#2c3a4c" strokeWidth={0.6} />
            <text x={px(v)} y={H - B + 11} fill="#cfd8e3" fontSize={8} textAnchor="middle">{fmtTick(v)}</text>
          </g>
        ))}
        {yt.map((k) => (
          <g key={`y${k}`}>
            <line x1={L} x2={W - R} y1={py(k)} y2={py(k)} stroke="#2c3a4c" strokeWidth={0.6} />
            <text x={L - 4} y={py(k) + 3} fill="#cfd8e3" fontSize={8} textAnchor="end">{k}</text>
          </g>
        ))}
        <line x1={L} y1={H - B} x2={W - R} y2={H - B} stroke="#9aa4b1" />
        <line x1={L} y1={TOP} x2={L} y2={H - B} stroke="#9aa4b1" />
        <text x={(L + W - R) / 2} y={H - 6} fill="#e6edf5" fontSize={9} textAnchor="middle" data-testid="drift-x-title">
          {t(mode === "drift" ? "Drift ratio (%)" : "Displacement (mm)")}
        </text>
        <text x={10} y={(TOP + H - B) / 2} fill="#e6edf5" fontSize={9} textAnchor="middle" transform={`rotate(-90 10 ${(TOP + H - B) / 2})`}>{t("Storey")}</text>
        {showLimit ? (
          <g data-testid="drift-limit">
            <line x1={px(limitPct as number)} x2={px(limitPct as number)} y1={TOP} y2={H - B} stroke="#e53935" strokeDasharray="4 3" />
            <text x={px(limitPct as number) + 3} y={TOP + 8} fill="#ff8a80" fontSize={8}>{`${t("Limit")} ${fmtTick(limitPct as number)}%`}</text>
          </g>
        ) : null}
        {series.map((s) => (
          <g key={s.dir}>
            <polyline points={s.pts.map((p) => `${px(p.v)},${py(p.storey)}`).join(" ")} fill="none" stroke={COLORS[s.dir]} strokeWidth={1.8} strokeDasharray={s.dir === "Y" ? "5 3" : undefined} />
            {s.pts.map((p) => (
              <circle key={p.storey} cx={px(p.v)} cy={py(p.storey)} r={pick?.dir === s.dir && pick.storey === p.storey ? 4 : 2.4} fill={COLORS[s.dir]} style={{ cursor: "pointer" }} onClick={() => setPick({ dir: s.dir, storey: p.storey })} data-testid={`drift-pt-${s.dir}-${p.storey}`}>
                <title>{`${s.dir} · ${t("Storey")} ${p.storey}: ${fmtTick(p.v)}${unit}`}</title>
              </circle>
            ))}
          </g>
        ))}
        {series.map((s, i) => (
          <g key={`lg${s.dir}`} transform={`translate(${W - R - 44 * (series.length - i)},${TOP - 12})`}>
            <line x1={0} x2={12} y1={0} y2={0} stroke={COLORS[s.dir]} strokeWidth={2} strokeDasharray={s.dir === "Y" ? "4 2" : undefined} />
            <circle cx={6} cy={0} r={2.2} fill={COLORS[s.dir]} />
            <text x={15} y={3} fill={COLORS[s.dir]} fontSize={8}>{s.dir}</text>
          </g>
        ))}
      </svg>
      <p className="v3d-muted" data-testid="drift-readout">
        {picked
          ? `${picked.direction} · ${t("Storey")} ${picked.storey}: ${t("Drift")} ${fmtTick(picked.ratioAmplifiedPct ?? 0)}% · Δ ${fmtTick(picked.driftElasticMm ?? 0)} mm${picked.uMaxMm != null ? ` · u ${fmtTick(picked.uMaxMm)} mm` : ""}`
          : peak.filter((p) => p.storey > 0).map((p, i) => `${series[i].dir}: max ${fmtTick(p.v)}${unit} @ ${t("Storey")} ${p.storey}`).join(" · ")}
      </p>
      {series.length === 2 && series[0].pts.length > 0 && series[0].pts.every((p, i) => Math.abs(p.v - (series[1].pts[i]?.v ?? NaN)) < 1e-9) ? (
        <p className="v3d-muted" data-testid="drift-xy-same">{t("X and Y are identical (symmetric model); Y is drawn dashed over X.")}</p>
      ) : null}
      <p className="v3d-muted">{t(mode === "drift" ? "Inter-storey drift ratio (amplified, as checked in design); tap a point for values." : "Elastic total displacement of each storey (max at roof).")}</p>
    </div>
  );
}
