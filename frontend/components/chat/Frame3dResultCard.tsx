"use client";

import type { Frame3dResults } from "@/lib/chat-types";

type Frame3dResultCardProps = {
  results: Frame3dResults;
};

export function Frame3dResultCard({ results }: Frame3dResultCardProps) {
  const completed = results.status === "completed";
  const limit = results.driftReferenceLimitPct;

  return (
    <section className="engineering-result-card" aria-label="3D frame analysis">
      <header className="engineering-result-header">
        <div>
          <p className="eyebrow">Structural analysis</p>
          <h3>3D frame analysis</h3>
        </div>
        <div className="engineering-result-badges">
          <span className={`chat-progress-badge ${completed ? "" : "warning"}`}>
            {completed ? "Completed" : results.status.replace(/_/g, " ")}
          </span>
        </div>
      </header>

      {results.code ? <p className="muted engineering-result-code">Code: {results.code}</p> : null}
      {!completed && results.message ? <p>{results.message}</p> : null}

      {completed && results.fields.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Model and results</p>
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
          <p className="engineering-result-label">Plan (beams and columns)</p>
          <PlanView xs={results.gridX} ys={results.gridY} />
        </div>
      ) : null}

      {results.drift.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Storey drift</p>
          <table className="engineering-result-table">
            <thead>
              <tr>
                <th>Storey</th>
                <th>Dir</th>
                <th>Δ elastic (mm)</th>
                <th>Δ/h elastic (%)</th>
                <th>0.7R·Δ/h (%)</th>
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
                ? `Standard 2800 drift limit ${limit}%: ${results.driftCheck}`
                : `Reference value ${limit}% shown for orientation only; not a Standard 2800 check.`}
            </p>
          ) : null}
        </div>
      ) : null}

      {results.modal ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Modal and response-spectrum analysis</p>
          <table className="engineering-result-table">
            <thead>
              <tr>
                <th>Mode</th>
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
                {s.direction}: V dynamic {fmt(s.vDynamicKn, 1)} kN vs static {fmt(s.vStaticKn, 1)} kN, scale ×
                {fmt(s.scaleFactor, 3)}, max scaled drift {fmt(s.maxDriftPct, 2)}%
              </li>
            ))}
          </ul>
          {results.modal.scaleRule ? <p className="muted">{results.modal.scaleRule}</p> : null}
        </div>
      ) : null}

      {results.design ? <DesignSection design={results.design} /> : null}

      {results.storeyForces.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Max member forces per storey (envelope)</p>
          <table className="engineering-result-table">
            <thead>
              <tr>
                <th>Storey</th>
                <th>Beam M⁻ (kN·m)</th>
                <th>Beam M⁺ (kN·m)</th>
                <th>Beam V (kN)</th>
                <th>Column P (kN)</th>
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
          <p className="engineering-result-label">Validation</p>
          <ul>
            <li>Base shear: sum of reactions vs C·W — {results.baseShearStatus}</li>
          </ul>
        </div>
      ) : null}

      <TextList title="Assumptions" items={results.assumptions} />
      <TextList title="Warnings" items={results.warnings} />

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

function DesignTable({ rows, columns }: { rows: Array<Record<string, string | number | null>>; columns: Array<[string, string]> }) {
  return (
    <table className="engineering-result-table">
      <thead>
        <tr>
          {columns.map(([key, label]) => (
            <th key={key}>{label}</th>
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

function DesignSection({ design }: { design: NonNullable<Frame3dResults["design"]> }) {
  return (
    <div className="engineering-result-block">
      <p className="engineering-result-label">
        Mabhas 9 RC design{design.ductility ? ` (${design.ductility} ductility)` : ""} — {design.status}
      </p>
      {design.message ? <p>{design.message}</p> : null}
      {design.beams.length > 0 ? <DesignTable rows={design.beams} columns={BEAM_COLUMNS} /> : null}
      {design.columns.length > 0 ? <DesignTable rows={design.columns} columns={COLUMN_COLUMNS} /> : null}
      {design.scwb.length > 0 ? (
        <ul>
          {design.scwb.map((j) => (
            <li key={String(j.level)}>
              Level {j.level}: ΣMnc/ΣMnb min {j.min_ratio} at {j.joint} ({j.direction}) — {j.status}
            </li>
          ))}
          {design.scwbNote ? <li className="muted">{design.scwbNote}</li> : null}
        </ul>
      ) : null}
      {design.beams.length > 0 ? (
        <p>
          <button type="button" className="link-button" onClick={() => downloadCsv("mabhas9-beams.csv", design.beams)}>
            Download beams CSV
          </button>{" "}
          <button type="button" className="link-button" onClick={() => downloadCsv("mabhas9-columns.csv", design.columns)}>
            Download columns CSV
          </button>
        </p>
      ) : null}
      <TextList title="Implemented clauses" items={design.clausesImplemented} />
      <TextList title="Simplified / not checked" items={design.clausesSimplified} />
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

function PlanView({ xs, ys }: { xs: number[]; ys: number[] }) {
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
      aria-label="Frame plan"
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
