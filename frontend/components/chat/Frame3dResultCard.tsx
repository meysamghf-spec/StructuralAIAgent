"use client";

import { useEffect, useState } from "react";
import { getCurrentProjectId } from "@/lib/current-project";
import { saveFrame3dInputs } from "@/lib/frame3d-store";

import { downloadFrame3dExport } from "@/lib/api";
import type { Frame3dExport, Frame3dResults } from "@/lib/chat-types";
import dynamic from "next/dynamic";
import { isRtl, makeT } from "@/lib/frame3d-i18n";

const Frame3dViewer = dynamic(() => import("./Frame3dViewer"), { ssr: false });
const FoundationView = dynamic(() => import("@/components/frame3d/FoundationView"), { ssr: false });

type T = (key: string) => string;

type Frame3dResultCardProps = {
  results: Frame3dResults;
};

export function Frame3dResultCard({ results }: Frame3dResultCardProps) {
  const completed = results.status === "completed";
  const limit = results.driftReferenceLimitPct;
  const t = makeT(results.lang);
  const rtl = isRtl(results.lang);
  const is2800 = results.seismicCode === "IRAN_2800";
  const [viewerOpen, setViewerOpen] = useState(results.animateMode != null);
  useEffect(() => {
    if (results.status === "completed" && results.inputs) saveFrame3dInputs(getCurrentProjectId(), results.inputs);
  }, [results.status, results.inputs]);

  return (
    <section className="engineering-result-card" aria-label={t("3D frame analysis")} dir={rtl ? "rtl" : "ltr"} lang={results.lang}>
      <header className="engineering-result-header">
        <div>
          <p className="eyebrow">{t("Structural analysis")}</p>
          <h3>{t("3D frame analysis")}</h3>
        </div>
        <div className="engineering-result-badges">
          <span className={`chat-progress-badge ${completed ? "" : "warning"}`}>
            {completed ? t("Completed") : (t(results.status) !== results.status ? t(results.status) : results.status.replace(/_/g, " "))}
          </span>
        </div>
      </header>

      {results.code ? <p className="muted engineering-result-code">{t("Code")}: {results.code}</p> : null}
      {!completed && results.message ? <p>{results.message}</p> : null}

      {completed && results.fields.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{t("Model and results")}</p>
          <dl className="engineering-result-grid">
            {results.fields.map((field) => (
              <div key={field.label} className="engineering-result-field">
                <dt>{field.label}</dt>
                <dd>
                  {field.value}
                  {field.unit ? <span className="engineering-result-unit"> {field.unit}</span> : null}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}

      {completed && results.gridX.length > 1 && results.gridY.length > 1 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{t("Plan (beams and columns)")}</p>
          {results.viewer ? (
            <p>
              <button type="button" className="button" onClick={() => setViewerOpen(true)}>
                {t("Open 3D view")}
              </button>
            </p>
          ) : null}
          {results.showFoundation && results.viewer?.footings.length ? (
            <FoundationView data={results.viewer} qa={results.foundation?.qaKpa ?? 150} t={t} />
          ) : null}
          {viewerOpen && results.viewer ? (
            <Frame3dViewer data={results.viewer} results={results} t={t} onClose={() => setViewerOpen(false)} initialMode={results.animateMode ?? null} />
          ) : null}
          <PlanView xs={results.gridX} ys={results.gridY} label={t("Frame plan")} />
        </div>
      ) : null}

      {results.drift.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{t("Storey drift")}</p>
          <table className="engineering-result-table">
            <thead>
              <tr>
                <th>{t("Storey")}</th>
                <th>{t("Dir")}</th>
                <th>{t("Δ elastic (mm)")}</th>
                <th>{t("Δ/h elastic (%)")}</th>
                <th>{t(is2800 ? "Cd·Δ/(I·h) (%)" : "0.7R·Δ/h (%)")}</th>
              </tr>
            </thead>
            <tbody>
              {results.drift.map((row) => (
                <tr key={`${row.direction}-${row.storey}`}>
                  <td>{row.storey}</td>
                  <td>{row.direction}</td>
                  <td>{fmt(row.driftElasticMm, 2)}</td>
                  <td>{fmt(row.ratioElasticPct, 3)}</td>
                  <td>
                    {fmt(row.ratioAmplifiedPct, 3)}
                    {limit !== null && row.ratioAmplifiedPct !== null && row.ratioAmplifiedPct > limit ? " ⚠" : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {limit !== null ? (
            <p className="muted">
              {results.driftCheck
                ? `${t("Standard 2800 drift limit")} ${limit}%: ${t(results.driftCheck)}`
                : `${t("Reference value")} ${limit}% ${t("shown for orientation only; not a Standard 2800 check.")}`}
            </p>
          ) : null}
        </div>
      ) : null}

      {results.modal ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{t("Modal and response-spectrum analysis")}</p>
          <table className="engineering-result-table">
            <thead>
              <tr>
                <th>{t("Mode")}</th>
                <th>T (s)</th>
                <th>Mx (%)</th>
                <th>My (%)</th>
                <th>Rz (%)</th>
              </tr>
            </thead>
            <tbody>
              {results.modal.modes.slice(0, 6).map((m) => (
                <tr key={m.mode}>
                  <td>{m.mode}</td>
                  <td>{fmt(m.periodS, 3)}</td>
                  <td>{fmt(m.massXPct, 1)}</td>
                  <td>{fmt(m.massYPct, 1)}</td>
                  <td>{fmt(m.massRzPct, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul>
            {results.modal.spectrum.map((s) => (
              <li key={s.direction}>
                {s.direction}: {t("V dynamic")} {fmt(s.vDynamicKn, 1)} kN {t("vs static")} {fmt(s.vStaticKn, 1)} kN, {t("scale")} ×
                {fmt(s.scaleFactor, 3)}, {t("max scaled drift")} {fmt(s.maxDriftPct, 2)}%
              </li>
            ))}
          </ul>
          {results.modal.scaleRule ? <p className="muted">{results.modal.scaleRule}</p> : null}
        </div>
      ) : null}

      {results.design ? <DesignSection design={results.design} t={t} /> : null}

      {results.foundation ? <FoundationSection foundation={results.foundation} t={t} /> : null}

      {results.exports.length > 0 && results.inputs ? (
        <ExportSection
          exports={results.exports}
          inputs={results.inputs}
          requested={results.exportRequested}
          fromMemory={results.modelFromProjectMemory}
          t={t}
        />
      ) : null}

      {results.storeyForces.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{t("Max member forces per storey (envelope)")}</p>
          <table className="engineering-result-table">
            <thead>
              <tr>
                <th>{t("Storey")}</th>
                <th>{t("Beam M⁻ (kN·m)")}</th>
                <th>{t("Beam M⁺ (kN·m)")}</th>
                <th>{t("Beam V (kN)")}</th>
                <th>{t("Column P (kN)")}</th>
              </tr>
            </thead>
            <tbody>
              {results.storeyForces.map((row) => (
                <tr key={row.storey}>
                  <td>{row.storey}</td>
                  <td>{fmt(row.beamMNegKnM, 1)}</td>
                  <td>{fmt(row.beamMPosKnM, 1)}</td>
                  <td>{fmt(row.beamVKn, 1)}</td>
                  <td>{fmt(row.columnPKn, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {results.baseShearStatus ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{t("Validation")}</p>
          <ul>
            <li>{t("Base shear: sum of reactions vs C·W")} — {t(results.baseShearStatus)}</li>
          </ul>
        </div>
      ) : null}

      <TextList title={t("Assumptions")} items={results.assumptions} />
      <TextList title={t("Warnings")} items={results.warnings} />

      {results.disclaimer ? <p className="muted chat-disclaimer">{results.disclaimer}</p> : null}
    </section>
  );
}

const BEAM_COLUMNS: Array<[string, string]> = [
  ["group", "Group"],
  ["Mu_neg_kn_m", "Mu⁻"],
  ["Mu_pos_kn_m", "Mu⁺"],
  ["Vu_kn", "Vu"],
  ["top_bars", "Top"],
  ["bottom_bars", "Bottom"],
  ["stirrups", "Stirrups"],
  ["DC_flexure", "D/C M"],
  ["DC_shear", "D/C V"],
];
const COLUMN_COLUMNS: Array<[string, string]> = [
  ["group", "Group"],
  ["Pu_kn", "Pu"],
  ["Mu_y_kn_m", "Mu,y"],
  ["Mu_z_kn_m", "Mu,z"],
  ["bars", "Bars"],
  ["rho_pct", "ρ %"],
  ["ties", "Ties"],
  ["DC", "D/C"],
];

export function designCsv(rows: Array<Record<string, string | number | null>>): string {
  if (rows.length === 0) {
    return "";
  }
  const keys = Object.keys(rows[0]);
  const esc = (v: string | number | null | undefined) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [keys.join(","), ...rows.map((r) => keys.map((k) => esc(r[k])).join(","))].join("\n");
}

function downloadCsv(name: string, rows: Array<Record<string, string | number | null>>) {
  const blob = new Blob(["\ufeff" + designCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function DesignTable({ rows, columns, t }: { rows: Array<Record<string, string | number | null>>; columns: Array<[string, string]>; t: T }) {
  return (
    <table className="engineering-result-table">
      <thead>
        <tr>
          {columns.map(([key, label]) => (
            <th key={key}>{t(label)}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={String(row.group)}>
            {columns.map(([key]) => (
              <td key={key}>{row[key] ?? "—"}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DesignSection({ design, t }: { design: NonNullable<Frame3dResults["design"]>; t: T }) {
  return (
    <div className="engineering-result-block">
      <p className="engineering-result-label">
        {t("Mabhas 9 RC design")}
        {design.ductility ? ` (${t(design.ductility)} ${t("ductility")})` : ""} — {t(design.status)}
      </p>
      {design.message ? <p>{design.message}</p> : null}
      {design.beams.length > 0 ? <DesignTable rows={design.beams} columns={BEAM_COLUMNS} t={t} /> : null}
      {design.columns.length > 0 ? <DesignTable rows={design.columns} columns={COLUMN_COLUMNS} t={t} /> : null}
      {design.scwb.length > 0 ? (
        <ul>
          {design.scwb.map((j) => (
            <li key={String(j.level)}>
              {t("Level")} {j.level}: {t("ΣMnc/ΣMnb min")} {j.min_ratio} {t("at")} {j.joint} ({j.direction}) — {t(String(j.status))}
            </li>
          ))}
          {design.scwbNote ? <li className="muted">{design.scwbNote}</li> : null}
        </ul>
      ) : null}
      {design.beams.length > 0 ? (
        <p>
          <button type="button" className="link-button" onClick={() => downloadCsv("mabhas9-beams.csv", design.beams)}>
            {t("Download beams CSV")}
          </button>{" "}
          <button type="button" className="link-button" onClick={() => downloadCsv("mabhas9-columns.csv", design.columns)}>
            {t("Download columns CSV")}
          </button>
        </p>
      ) : null}
      <TextList title={t("Implemented clauses")} items={design.clausesImplemented} />
      <TextList title={t("Simplified / not checked")} items={design.clausesSimplified} />
    </div>
  );
}

export function orderExports(exports: Frame3dExport[]): Frame3dExport[] {
  return [...exports.filter((e) => e.requested), ...exports.filter((e) => !e.requested)];
}

function ExportSection({
  exports,
  inputs,
  requested,
  fromMemory,
  t,
}: {
  exports: Frame3dExport[];
  inputs: Record<string, unknown>;
  requested: string[];
  fromMemory: boolean;
  t: T;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const notes = exports.filter((e) => (requested.length ? e.requested : true) && e.notes.length > 0);
  async function run(e: Frame3dExport) {
    setBusy(e.format);
    setError(null);
    try {
      await downloadFrame3dExport(e.format, inputs, e.filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Export failed"));
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="engineering-result-block">
      <p className="engineering-result-label">
        {t("Export model (ETABS / SAFE / AutoCAD)")}
        {fromMemory ? ` — ${t("re-analysed from the last frame in this project")}` : ""}
      </p>
      <p>
        {orderExports(exports).map((e) => (
          <button
            key={e.format}
            type="button"
            className="link-button"
            disabled={busy !== null}
            onClick={() => void run(e)}
          >
            {busy === e.format ? t("Preparing…") : `${e.requested ? "★ " : ""}${e.label}`}
          </button>
        ))}
      </p>
      {error ? <p className="muted">{error}</p> : null}
      {notes.length > 0 ? (
        <ul className="muted">
          {notes.flatMap((e) => e.notes.map((n, i) => <li key={`${e.format}-${i}`}>{`${e.filename}: ${n}`}</li>))}
        </ul>
      ) : null}
    </div>
  );
}

const FOUNDATION_COLUMNS: Array<[string, string]> = [
  ["group", "Group"],
  ["P_service_kn", "P service"],
  ["size", "B × B × h (m)"],
  ["q_max_kpa", "qu max (kPa)"],
  ["bearing_dc", "D/C bearing"],
  ["DC_oneway", "D/C 1-way"],
  ["DC_punching", "D/C punching"],
  ["bars", "Bars"],
  ["DC_flexure", "D/C flexure"],
];

export function foundationRows(rows: Array<Record<string, string | number | null>>): Array<Record<string, string | number | null>> {
  return rows.map((r) => ({ ...r, size: r.B_m === null || r.B_m === undefined ? "—" : `${r.B_m} × ${r.B_m} × ${r.h_m}` }));
}

function FoundationSection({ foundation, t }: { foundation: NonNullable<Frame3dResults["foundation"]>; t: T }) {
  const rows = foundationRows(foundation.rows);
  return (
    <div className="engineering-result-block">
      <p className="engineering-result-label">
        {t("Foundation design (isolated footings)")} — {t(foundation.status)}
      </p>
      <p className="muted">
        {t("Allowable bearing")} {foundation.qaKpa} kPa{foundation.qaAssumed ? ` (${t("assumed")})` : ""}, {t("net")} {foundation.qaNetKpa} kPa
        {foundation.minGapM !== null ? ` · ${t("Min clear gap")} ${foundation.minGapM} m` : ""}
        {foundation.coverage !== null ? ` · ${t("Plan coverage")} ${Math.round(foundation.coverage * 100)}%` : ""}
      </p>
      {rows.length > 0 ? <DesignTable rows={rows} columns={FOUNDATION_COLUMNS} t={t} /> : null}
      {foundation.recommendation ? <p>{foundation.recommendation}</p> : null}
      {foundation.rows.length > 0 ? (
        <p>
          <button type="button" className="link-button" onClick={() => downloadCsv("foundation-footings.csv", foundation.rows)}>
            {t("Download footings CSV")}
          </button>
        </p>
      ) : null}
      <TextList title={t("Implemented clauses")} items={foundation.clausesImplemented} />
      <TextList title={t("Simplified / not checked")} items={foundation.clausesSimplified} />
    </div>
  );
}

function TextList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="engineering-result-block">
      <p className="engineering-result-label">{title}</p>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function fmt(value: number | null, digits: number): string {
  return value === null ? "—" : value.toFixed(digits);
}

function PlanView({ xs, ys, label }: { xs: number[]; ys: number[]; label: string }) {
  const width = xs[xs.length - 1] || 1;
  const depth = ys[ys.length - 1] || 1;
  const size = Math.max(width, depth);
  const pad = 0.12 * size;
  const stroke = size / 120;
  const col = size / 40;
  return (
    <svg
      viewBox={`${-pad} ${-pad} ${width + 2 * pad} ${depth + 2 * pad}`}
      role="img"
      aria-label={label}
      style={{ width: "100%", maxWidth: 320, height: "auto" }}
    >
      <g transform={`translate(0 ${depth}) scale(1 -1)`}>
        {ys.map((y) => (
          <line key={`bx-${y}`} x1={0} y1={y} x2={width} y2={y} stroke="currentColor" strokeWidth={stroke} />
        ))}
        {xs.map((x) => (
          <line key={`by-${x}`} x1={x} y1={0} x2={x} y2={depth} stroke="currentColor" strokeWidth={stroke} />
        ))}
        {xs.flatMap((x) =>
          ys.map((y) => (
            <rect key={`c-${x}-${y}`} x={x - col / 2} y={y - col / 2} width={col} height={col} fill="#d97706" />
          )),
        )}
      </g>
    </svg>
  );
}
