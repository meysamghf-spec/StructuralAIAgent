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
