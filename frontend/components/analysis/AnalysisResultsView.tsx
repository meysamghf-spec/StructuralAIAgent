"use client";

import { StoreyBarChart } from "@/components/analysis/StoreyBarChart";
import { formatNum, type AnalysisView } from "@/lib/analysis-results";
import { TablePager, usePaged } from "@/components/common/TablePager";
import "./analysis.css";

type T = (key: string) => string;

function Table({ head, rows, bad }: { head: string[]; rows: Array<Array<string | number>>; bad?: boolean[] }) {
  const pg = usePaged(rows);
  const off = pg.page * pg.size;
  return (
    <div className="an-scroll">
      <TablePager {...pg} />
      <table className="an-table">
        <thead>
          <tr>{head.map((h) => <th key={h}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {pg.rows.map((r, i) => (
            <tr key={off + i} className={bad?.[off + i] ? "bad" : undefined}>
              {r.map((c, j) => <td key={j}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function KpiChip({ view, t }: { view: AnalysisView; t: T }) {
  if (view.driftState === "pass") return <span className="an-chip pass">✓ {t("Pass")}</span>;
  if (view.driftState === "review") return <span className="an-chip review">! {t("Needs review")}</span>;
  if (view.driftState === "reference") return <span className="an-chip ref">{t("Reference only")}</span>;
  return null;
}

export function AnalysisKpis({ view, t }: { view: AnalysisView; t: T }) {
  const dirTxt = (dir: string, storey: number) => `${t("storey")} ${storey} · ${t("dir")} ${dir}`;
  return (
    <section className="an-kpis" aria-label="KPIs" data-testid="an-kpis">
      <div className="an-kpi">
        <h4>{t("Max displacement")}</h4>
        <div className="an-kpi-val" dir="ltr">
          {view.maxDisplacement ? formatNum(view.maxDisplacement.mm) : "—"}
          <small>mm</small>
        </div>
        <div className="an-kpi-sub">{view.maxDisplacement ? dirTxt(view.maxDisplacement.direction, view.maxDisplacement.storey) : t("Not computed for this model")}</div>
      </div>
      <div className={`an-kpi ${view.driftState === "review" ? "review" : view.driftState === "pass" ? "pass" : ""}`}>
        <h4>{t("Max story drift")}</h4>
        <div className="an-kpi-val" dir="ltr">
          {view.maxDrift ? formatNum(view.maxDrift.pct, 3) : "—"}
          <small>%</small>
        </div>
        <div className="an-kpi-sub">
          <KpiChip view={view} t={t} />{" "}
          {view.maxDrift ? dirTxt(view.maxDrift.direction, view.maxDrift.storey) : t("Not computed for this model")}
          {view.driftLimitPct !== null ? <> · {t("limit")} <span dir="ltr">{formatNum(view.driftLimitPct, 2)} %</span></> : null}
        </div>
      </div>
      <div className="an-kpi">
        <h4>{t("Fundamental period")}</h4>
        <div className="an-kpi-val" dir="ltr">
          {formatNum(view.fundamentalPeriodS, 3)}
          <small>s</small>
        </div>
        <div className="an-kpi-sub">T₁</div>
      </div>
      <div className="an-kpi">
        <h4>{t("Base shear")}</h4>
        <div className="an-kpi-val" dir="ltr">
          {formatNum(view.baseShear?.vKn ?? null, 1)}
          <small>kN</small>
        </div>
        <div className="an-kpi-sub">{view.baseShear?.c != null ? <>C = <span dir="ltr">{formatNum(view.baseShear.c, 4)}</span></> : t("Not computed for this model")}</div>
      </div>
    </section>
  );
}

export function AnalysisSections({ view, t }: { view: AnalysisView; t: T }) {
  const storeyNums = view.storeys.map((s) => s.storey);
  const limit = view.driftLimitPct;
  const dirs = view.directions;
  const driftSeries = dirs.map((d) => ({ key: d, label: d, values: view.storeys.map((s) => s.driftPct[d] ?? null) }));
  const dispSeries = dirs.map((d) => ({ key: d, label: d, values: view.storeys.map((s) => (s.displacementMm[d] === null || s.displacementMm[d] === undefined ? null : Math.abs(s.displacementMm[d] as number))) }));
  const driftRows = view.storeys.flatMap((s) => dirs.map((d) => ({ s, d })));
  const hasStoreyData = view.storeys.some((s) => dirs.some((d) => s.driftPct[d] != null || s.displacementMm[d] != null));
  const shearSeries = [{ key: "V", label: "V", values: view.storeys.map((s) => s.shearKn) }];
  const forceRows = view.storeys.filter((s) => s.forceKn !== null || s.shearKn !== null);
  const periodSeries = [{ key: "T", label: "T", values: view.modes.map((m) => m.periodS) }];

  return (
    <>
      {hasStoreyData ? (
        <section className="an-sec" data-testid="an-drift">
          <h3>{t("Drift and displacement per storey")}</h3>
          <div className="an-two">
            <StoreyBarChart title={t("Story drift ratio (%)")} unit="%" storeys={storeyNums} series={driftSeries} limit={limit} limitLabel={`${t("Drift limit")} ${formatNum(limit, 2)} %`} digits={3} storeyLabel={t("Storey")} />
            <StoreyBarChart title={t("Lateral displacement (mm)")} unit="mm" storeys={storeyNums} series={dispSeries} storeyLabel={t("Storey")} />
          </div>
          <Table
            head={[t("Storey"), t("Direction"), t("Displacement (mm)"), t("Drift Δ elastic (mm)"), t("Drift ratio (%)")]}
            rows={driftRows.map(({ s, d }) => [s.storey, d, formatNum(s.displacementMm[d]), formatNum(s.driftElasticMm[d]), formatNum(s.driftPct[d], 3)])}
            bad={driftRows.map(({ s, d }) => limit !== null && view.driftState !== "reference" && (s.driftPct[d] ?? 0) > limit)}
          />
          <p className="an-note">{t("Elastic lateral displacement of the highest level.")} {t("Amplified (inelastic) drift ratio from the design-force analysis.")}</p>
        </section>
      ) : null}

      <section className="an-sec" data-testid="an-modal">
        <h3>{t("Modal periods")}</h3>
        {view.modes.length ? (
          <>
            <div className="an-two">
              <div className="an-bars-periods">
                <StoreyBarChart title={t("Period T (s)")} unit="s" storeys={view.modes.map((m) => m.mode)} series={periodSeries} digits={3} storeyLabel={t("Mode")} topFirst={false} />
              </div>
              <Table
                head={[t("Mode"), t("Period T (s)"), t("Mass X (%)"), t("Mass Y (%)"), t("Mass Rz (%)"), t("Cumulative X (%)"), t("Cumulative Y (%)")]}
                rows={view.modes.map((m) => [m.mode, formatNum(m.periodS, 4), formatNum(m.massXPct, 1), formatNum(m.massYPct, 1), formatNum(m.massRzPct, 1), formatNum(m.cumXPct, 1), formatNum(m.cumYPct, 1)])}
              />
            </div>
            {view.modesFor90 ? (
              <p className="an-note">{t("Modes needed for 90% mass")}: {Object.entries(view.modesFor90).map(([k, v]) => `${k} = ${v}`).join(" · ")}</p>
            ) : null}
          </>
        ) : (
          <p className="an-note">{t("Modal analysis was not run for this model.")}</p>
        )}
      </section>

      <section className="an-sec" data-testid="an-shear">
        <h3>{t("Base shear and storey forces")}</h3>
        {view.baseShear ? (
          <div className="an-stats" dir="auto">
            <div><span>{t("Seismic weight W")}</span><b dir="ltr">{formatNum(view.baseShear.weightKn, 1)} kN</b></div>
            <div><span>{t("Seismic coefficient C")}</span><b dir="ltr">{formatNum(view.baseShear.c, 4)}</b></div>
            <div><span>{t("Base shear V")}</span><b dir="ltr">{formatNum(view.baseShear.vKn, 1)} kN</b></div>
            {view.baseShear.status ? <div><span>{t("Equilibrium check")}</span><b dir="ltr">{view.baseShear.status}</b></div> : null}
            {view.pDelta?.thetaMax ? <div><span>{t("Max stability index θ")}</span><b dir="ltr">{Object.entries(view.pDelta.thetaMax).map(([k, v]) => `${k} ${formatNum(v, 4)}`).join(" · ")}{view.pDelta.status ? ` (${view.pDelta.status})` : ""}</b></div> : null}
          </div>
        ) : null}
        {forceRows.length ? (
          <div className="an-two">
            <StoreyBarChart title={t("Storey shear V (kN)")} unit="kN" storeys={storeyNums} series={shearSeries} digits={1} storeyLabel={t("Storey")} />
            <Table head={[t("Storey"), t("Storey force F (kN)"), t("Storey shear V (kN)")]} rows={forceRows.map((s) => [s.storey, formatNum(s.forceKn, 1), formatNum(s.shearKn, 1)])} />
          </div>
        ) : null}
        {view.spectrum.length ? (
          <>
            <h4 className="an-note">{t("Dynamic vs static base shear")}</h4>
            <Table head={[t("Direction"), t("V dynamic (kN)"), t("V static (kN)"), t("Scale factor")]} rows={view.spectrum.map((s) => [s.direction, formatNum(s.vDynamicKn, 1), formatNum(s.vStaticKn, 1), formatNum(s.scaleFactor, 3)])} />
          </>
        ) : null}
      </section>

      {view.storeyMember.length || view.members.length ? (
        <section className="an-sec" data-testid="an-members">
          <h3>{t("Member forces")}</h3>
          {view.storeyMember.length ? (
            <details className="an-details" open>
              <summary>{t("Envelope per storey")}</summary>
              <Table
                head={[t("Storey"), t("Beam M⁻ (kN·m)"), t("Beam M⁺ (kN·m)"), t("Beam V (kN)"), t("Column P (kN)"), t("Column M (kN·m)")]}
                rows={view.storeyMember.map((s) => [s.storey, formatNum(s.beamMNegKnM, 1), formatNum(s.beamMPosKnM, 1), formatNum(s.beamVKn, 1), formatNum(s.columnPKn, 1), formatNum(s.columnMKnM, 1)])}
              />
            </details>
          ) : null}
          {view.members.length ? (
            <details className="an-details">
              <summary>{t("All members")} ({view.members.length})</summary>
              <Table
                head={[t("Member"), t("Type"), t("Storey"), t("Position"), "M⁻ / P", "M⁺ / M", "V (kN)"]}
                rows={view.members.map((m) => [m.id, m.kind === "beam" ? t("Beam") : t("Column"), formatNum(m.storey, 0), m.position ?? "—", formatNum(m.a, 1), formatNum(m.b, 1), formatNum(m.c, 1)])}
              />
              <p className="an-note">{t("Beam")}: M⁻, M⁺ (kN·m), V (kN) · {t("Column")}: P (kN), M (kN·m)</p>
            </details>
          ) : null}
        </section>
      ) : null}

      {view.assumptions.length || view.warnings.length || view.disclaimer ? (
        <section className="an-sec" data-testid="an-notes">
          <h3>{t("Assumptions and limitations")}</h3>
          {view.disclaimer ? <p className="an-note" dir="auto">{view.disclaimer}</p> : null}
          <p className="an-note">{t("Results are stored in this browser for the project. They are not yet a server-side approved run.")}</p>
          {view.warnings.length ? (
            <details className="an-details">
              <summary>{t("Warnings")} ({view.warnings.length})</summary>
              <ul dir="auto">{view.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
            </details>
          ) : null}
          {view.assumptions.length ? (
            <details className="an-details">
              <summary>{t("Assumptions")} ({view.assumptions.length})</summary>
              <ul dir="auto">{view.assumptions.map((w, i) => <li key={i}>{w}</li>)}</ul>
            </details>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
