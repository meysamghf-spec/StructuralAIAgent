"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { SectionErrorBoundary } from "@/components/common/SectionErrorBoundary";
import { isIncompleteFramePayload, incompleteInputs, useLatestFrame3d } from "@/components/frame3d/Frame3dWorkspacePanel";
import { MissingInputsForm } from "@/components/frame3d/MissingInputsForm";
import { useUiLang } from "@/hooks/useUiLang";
import { getAnalysisStatusLabel } from "@/lib/analysis-workspace";
import { listAnalysisRuns, type AnalysisRunSummary } from "@/lib/analysis";
import { computeKpis, driftSeries, fmtNum, modelChips, roofDisplacements, type DriftStatus } from "@/lib/analysis-results";
import type { Frame3dResults } from "@/lib/chat-types";
import { getCurrentProjectId, projectChatHref } from "@/lib/current-project";
import { missingGeometry } from "@/lib/input-labels";

type Lang = "en" | "fa";
type TabId = "drift" | "modal" | "shear" | "members" | "runs";

const FA_STATUS: Record<string, string> = {
  Queued: "در صف", Running: "در حال اجرا", Completed: "کامل", "Completed with warnings": "کامل با هشدار",
  Failed: "ناموفق", "Not available yet": "هنوز در دسترس نیست", "Solver required": "نیازمند حلگر", "Model not ready": "مدل آماده نیست",
};

/** Results-only Analysis page: status banner, KPI cards and result tabs — no model/input forms, design, downloads or drawings. */
export function AnalysisResultsOnly() {
  return (
    <SectionErrorBoundary label="Analysis results">
      <Inner />
    </SectionErrorBoundary>
  );
}

function Inner() {
  const { lang } = useUiLang();
  const { projectId, payload, inputs, results, error } = useLatestFrame3d();
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);
  const incomplete = isIncompleteFramePayload(payload) || (!payload && !!inputs && missingGeometry(inputs).length > 0);
  const completed = !!results && results.status === "completed";
  const savedInputs = incompleteInputs(payload) ?? inputs;

  return (
    <div className="ar-page" dir={lang === "fa" ? "rtl" : "ltr"} lang={lang} data-testid="analysis-results-page">
      {incomplete ? (
        <section className="ar-card ar-state" data-testid="analysis-incomplete">
          <h2>{tx("Analysis is waiting for inputs", "تحلیل منتظر ورودی است")}</h2>
          <p className="muted">
            {tx(
              "The last model is missing required values. Enter them here and the analysis re-runs — nothing is guessed.",
              "در آخرین مدل مقادیر لازم کم است. آن‌ها را اینجا وارد کنید تا تحلیل دوباره اجرا شود — چیزی حدس زده نمی‌شود.",
            )}
          </p>
          <MissingInputsForm inputs={savedInputs} projectId={projectId} keys={missingGeometry(savedInputs ?? {})} />
          <RunLinks projectId={projectId} lang={lang} />
        </section>
      ) : completed && results ? (
        <ResultsBody results={results} lang={lang} projectId={projectId} />
      ) : results ? (
        <section className="ar-card ar-state" data-testid="analysis-not-completed">
          <h2>{tx("The last analysis did not complete", "آخرین تحلیل کامل نشد")}</h2>
          <p className="muted">{results.message ?? results.status}</p>
          <RunLinks projectId={projectId} lang={lang} />
        </section>
      ) : (
        <section className="ar-card ar-state" data-testid="analysis-empty">
          <h2>{tx("No analysis results yet", "هنوز نتیجهٔ تحلیلی نیست")}</h2>
          <p className="muted">
            {tx(
              "Results of your analysis runs — displacements, storey drifts, periods, base shear and member forces — appear here. Run an analysis from the chat or build the model first.",
              "نتایج تحلیل — جابه‌جایی‌ها، رانش طبقات، دوره‌های تناوب، برش پایه و نیروهای اعضا — اینجا نمایش داده می‌شود. تحلیل را از چت اجرا کنید یا ابتدا مدل را بسازید.",
            )}
          </p>
          <RunLinks projectId={projectId} lang={lang} />
        </section>
      )}
      {error ? <p className="alert error">{error}</p> : null}
      {!results || !completed ? <RunsLog projectId={projectId} lang={lang} /> : null}
    </div>
  );
}

function RunLinks({ projectId, lang }: { projectId: string | null; lang: Lang }) {
  return (
    <div className="ar-actions">
      <Link className="button" href={projectId ? projectChatHref(projectId) : "/"}>
        {lang === "fa" ? "اجرای تحلیل در چت" : "Run the analysis in chat"}
      </Link>
      <Link className="button secondary" href="/workspace/model">
        {lang === "fa" ? "رفتن به مدل" : "Go to Model"}
      </Link>
    </div>
  );
}

function ResultsBody({ results, lang, projectId }: { results: Frame3dResults; lang: Lang; projectId: string | null }) {
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);
  const kpi = computeKpis(results);
  const chips = modelChips(results.inputs, lang);
  const [tab, setTab] = useState<TabId>("drift");
  const tabs: Array<{ id: TabId; en: string; fa: string; show: boolean }> = [
    { id: "drift", en: "Drift & displacement", fa: "رانش و جابه‌جایی", show: results.drift.length > 0 },
    { id: "modal", en: "Modal", fa: "مودال", show: !!results.modal },
    { id: "shear", en: "Base shear & storey forces", fa: "برش پایه و نیروی طبقات", show: results.storeyLateral.length > 0 || !!results.baseShearStatus },
    { id: "members", en: "Member forces", fa: "نیروی اعضا", show: results.storeyForces.length > 0 },
    { id: "runs", en: "Run status", fa: "وضعیت اجراها", show: true },
  ];
  const visible = tabs.filter((x) => x.show);
  const active = visible.some((x) => x.id === tab) ? tab : visible[0].id;

  return (
    <>
      <section className="ar-banner" data-testid="analysis-banner" aria-label={tx("Run summary", "خلاصهٔ اجرا")}>
        <div className="ar-banner-main">
          <span className="ar-chip ok">{tx("Completed", "کامل")}</span>
          {results.code ? <span className="ar-chip">{results.code}</span> : null}
          <span className="ar-chip">{tx("Units: kN · m · mm", "واحدها: kN · m · mm")}</span>
          {results.modelFromProjectMemory ? <span className="ar-chip">{tx("Model from project memory", "مدل از حافظهٔ پروژه")}</span> : null}
        </div>
        {chips.length ? (
          <ul className="ar-chips" aria-label={tx("Model summary", "خلاصهٔ مدل")}>
            {chips.map((c) => (
              <li key={c} className="ar-chip soft">{c}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="ar-kpis" data-testid="analysis-kpis" aria-label={tx("Key results", "نتایج کلیدی")}>
        <Kpi label={tx("Roof displacement (max)", "جابه‌جایی بام (بیشینه)")} value={fmtNum(kpi.maxDisplacementMm, 1)} unit="mm" hint={kpi.maxDisplacementDir ? `${tx("dir", "جهت")} ${kpi.maxDisplacementDir} · ${tx("elastic", "ارتجاعی")}` : undefined} />
        <Kpi
          label={tx("Max storey drift ratio", "بیشینه نسبت رانش طبقه")}
          value={fmtNum(kpi.maxDriftPct, 3)}
          unit="%"
          hint={kpi.driftLimitPct !== null ? `${tx("limit", "حد")} ${kpi.driftLimitPct}%` : undefined}
          chip={<DriftChip status={kpi.driftStatus} lang={lang} />}
        />
        <Kpi label={tx("Fundamental period", "دورهٔ تناوب اصلی")} value={fmtNum(kpi.fundamentalPeriodS, 3)} unit="s" />
        <Kpi label={tx("Base shear", "برش پایه")} value={fmtNum(kpi.baseShearKn, 1)} unit="kN" />
        <Kpi label={tx("Total mass", "جرم کل")} value={fmtNum(kpi.totalMassT, 1)} unit="t" hint={kpi.totalMassT === null ? tx("not reported by this run", "در این اجرا گزارش نشده") : undefined} />
      </section>

      <div className="ar-tabs" role="tablist" aria-label={tx("Result sections", "بخش‌های نتایج")}>
        {visible.map((x) => (
          <button
            key={x.id}
            id={`ar-tab-${x.id}`}
            role="tab"
            type="button"
            aria-selected={active === x.id}
            aria-controls={`ar-panel-${x.id}`}
            className={active === x.id ? "ar-tab active" : "ar-tab"}
            onClick={() => setTab(x.id)}
          >
            {lang === "fa" ? x.fa : x.en}
          </button>
        ))}
      </div>

      <section className="ar-card" role="tabpanel" id={`ar-panel-${active}`} aria-labelledby={`ar-tab-${active}`} data-testid={`analysis-panel-${active}`}>
        {active === "drift" ? <DriftPanel results={results} lang={lang} /> : null}
        {active === "modal" ? <ModalPanel results={results} lang={lang} /> : null}
        {active === "shear" ? <ShearPanel results={results} lang={lang} /> : null}
        {active === "members" ? <MembersPanel results={results} lang={lang} /> : null}
        {active === "runs" ? <RunsLog projectId={projectId} lang={lang} bare /> : null}
      </section>

      {results.warnings.length ? (
        <section className="ar-card ar-warn">
          <h3>{tx("Warnings", "هشدارها")}</h3>
          <ul>{results.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </section>
      ) : null}
      {results.disclaimer ? <p className="muted ar-disclaimer">{results.disclaimer}</p> : null}
    </>
  );
}

function Kpi({ label, value, unit, hint, chip }: { label: string; value: string; unit: string; hint?: string; chip?: React.ReactNode }) {
  return (
    <article className="ar-kpi">
      <p className="ar-kpi-label">{label}</p>
      <p className="ar-kpi-value" dir="ltr">
        {value} {value !== "—" ? <span className="ar-kpi-unit">{unit}</span> : null}
      </p>
      <p className="ar-kpi-foot">
        {chip}
        {hint ? <span className="muted">{hint}</span> : null}
      </p>
    </article>
  );
}

function DriftChip({ status, lang }: { status: DriftStatus; lang: Lang }) {
  const fa = lang === "fa";
  if (status === "pass") return <span className="ar-chip ok">{fa ? "قبول" : "Pass"}</span>;
  if (status === "review") return <span className="ar-chip warn">{fa ? "نیازمند بازبینی" : "Needs review"}</span>;
  if (status === "reference") return <span className="ar-chip soft">{fa ? "فقط مرجع" : "Reference only"}</span>;
  return null;
}

function Note({ children }: { children: React.ReactNode }) {
  return <p className="muted ar-note">{children}</p>;
}

function DriftPanel({ results, lang }: { results: Frame3dResults; lang: Lang }) {
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);
  const series = driftSeries(results.drift);
  const limit = results.driftReferenceLimitPct;
  const roofs = roofDisplacements(results.drift);
  return (
    <>
      <h3>{tx("Storey drift & lateral displacement", "رانش طبقات و جابه‌جایی جانبی")}</h3>
      <div className="ar-roofs">
        {roofs.map((r) => (
          <span key={r.direction} className="ar-chip soft" dir="ltr">
            {tx("Roof", "بام")} {r.direction}: {r.mm.toFixed(1)} mm
          </span>
        ))}
      </div>
      <DriftChart series={series} limit={limit} lang={lang} />
      <div className="ar-scroll">
        <table className="engineering-result-table" data-testid="drift-table">
          <thead>
            <tr>
              <th>{tx("Storey", "طبقه")}</th>
              <th>{tx("Dir", "جهت")}</th>
              <th>{tx("Δ elastic (mm)", "Δ ارتجاعی (mm)")}</th>
              <th>{tx("Δ/h elastic (%)", "Δ/h ارتجاعی (%)")}</th>
              <th>{tx("Design drift ratio (%)", "نسبت رانش طراحی (%)")}</th>
            </tr>
          </thead>
          <tbody>
            {results.drift.map((row) => (
              <tr key={`${row.direction}-${row.storey}`}>
                <td>{row.storey}</td>
                <td>{row.direction}</td>
                <td>{fmtNum(row.driftElasticMm, 2)}</td>
                <td>{fmtNum(row.ratioElasticPct, 3)}</td>
                <td>
                  {fmtNum(row.ratioAmplifiedPct, 3)}
                  {limit !== null && row.ratioAmplifiedPct !== null && row.ratioAmplifiedPct > limit ? " ⚠" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Note>
        {results.driftCheck && limit !== null
          ? `${tx("Standard 2800 drift limit", "حد رانش استاندارد ۲۸۰۰")} ${limit}%: ${results.driftCheck}`
          : limit !== null
            ? tx(`Reference ${limit}% shown for orientation only; not a Standard 2800 check.`, `مقدار مرجع ${limit}% فقط برای راهنمایی است؛ کنترل استاندارد ۲۸۰۰ نیست.`)
            : tx("Elastic results of the built-in 3D frame solver.", "نتایج ارتجاعی حلگر قاب سه‌بعدی داخلی.")}{" "}
        {tx("Roof displacement is the sum of elastic storey drifts.", "جابه‌جایی بام مجموع رانش‌های ارتجاعی طبقات است.")}
      </Note>
    </>
  );
}

/** Dependency-free SVG bars: design drift ratio per storey and direction, with the limit as a dashed line. */
function DriftChart({ series, limit, lang }: { series: Record<string, Array<{ storey: number; pct: number }>>; limit: number | null; lang: Lang }) {
  const dirs = Object.keys(series);
  if (!dirs.length) return null;
  const all = dirs.flatMap((d) => series[d].map((p) => p.pct));
  const max = Math.max(...all, limit ?? 0, 0.0001) * 1.1;
  const storeys = Array.from(new Set(dirs.flatMap((d) => series[d].map((p) => p.storey)))).sort((a, b) => b - a);
  const rowH = 14 * dirs.length + 10;
  const W = 100;
  const colors = ["#38bdf8", "#a78bfa", "#34d399"];
  return (
    <figure className="ar-chart" data-testid="drift-chart">
      <svg viewBox={`0 0 ${W + 12} ${storeys.length * rowH + 6}`} role="img" aria-label={lang === "fa" ? "نمودار رانش طبقات" : "Storey drift chart"} preserveAspectRatio="xMinYMin meet">
        {storeys.map((s, i) => (
          <g key={s} transform={`translate(0 ${i * rowH + 2})`}>
            <text x="0" y="9" fontSize="4" fill="#94a3b8">{s}</text>
            {dirs.map((d, j) => {
              const p = series[d].find((x) => x.storey === s);
              const w = p ? (p.pct / max) * W : 0;
              return (
                <g key={d}>
                  <rect x="8" y={j * 12} width={w} height="9" rx="1.5" fill={colors[j % colors.length]} opacity={limit !== null && p && p.pct > limit ? 1 : 0.85} />
                  {p ? <text x={8 + w + 1} y={j * 12 + 7} fontSize="3.4" fill="#cbd5e1">{p.pct.toFixed(2)}</text> : null}
                </g>
              );
            })}
          </g>
        ))}
        {limit !== null ? <line x1={8 + (limit / max) * W} x2={8 + (limit / max) * W} y1="0" y2={storeys.length * rowH + 4} stroke="#f87171" strokeDasharray="2 2" strokeWidth="0.6" /> : null}
      </svg>
      <figcaption className="muted ar-legend" dir="ltr">
        {dirs.map((d, j) => (
          <span key={d}><i style={{ background: colors[j % colors.length] }} /> {d}</span>
        ))}
        {limit !== null ? <span><i className="lim" /> {lang === "fa" ? "حد" : "limit"} {limit}%</span> : null}
        <span>{lang === "fa" ? "درصد" : "%"}</span>
      </figcaption>
    </figure>
  );
}

function ModalPanel({ results, lang }: { results: Frame3dResults; lang: Lang }) {
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);
  const m = results.modal!;
  const cum = m.modes.reduce<{ x: number; y: number }>((a, r) => ({ x: a.x + (r.massXPct ?? 0), y: a.y + (r.massYPct ?? 0) }), { x: 0, y: 0 });
  return (
    <>
      <h3>{tx("Modal periods & mass participation", "دوره‌های تناوب مودال و مشارکت جرم")}</h3>
      <div className="ar-roofs">
        <span className="ar-chip soft" dir="ltr">Σ Mx {cum.x.toFixed(1)}%</span>
        <span className="ar-chip soft" dir="ltr">Σ My {cum.y.toFixed(1)}%</span>
      </div>
      <div className="ar-scroll">
        <table className="engineering-result-table">
          <thead>
            <tr><th>{tx("Mode", "مود")}</th><th>T (s)</th><th>Mx (%)</th><th>My (%)</th><th>Rz (%)</th></tr>
          </thead>
          <tbody>
            {m.modes.map((r) => (
              <tr key={r.mode}>
                <td>{r.mode}</td><td>{fmtNum(r.periodS, 3)}</td><td>{fmtNum(r.massXPct, 1)}</td><td>{fmtNum(r.massYPct, 1)}</td><td>{fmtNum(r.massRzPct, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {m.spectrum.length ? (
        <ul className="ar-list">
          {m.spectrum.map((s) => (
            <li key={s.direction} dir="ltr">
              {s.direction}: V<sub>dyn</sub> {fmtNum(s.vDynamicKn, 1)} kN · V<sub>static</sub> {fmtNum(s.vStaticKn, 1)} kN · ×{fmtNum(s.scaleFactor, 3)} · {fmtNum(s.maxDriftPct, 2)}%
            </li>
          ))}
        </ul>
      ) : null}
      <Note>{m.scaleRule ?? tx("Modal analysis of the built-in solver; periods in seconds, mass participation in % of total mass.", "تحلیل مودال حلگر داخلی؛ دوره‌های تناوب به ثانیه و مشارکت جرم به درصد جرم کل.")}</Note>
    </>
  );
}

function ShearPanel({ results, lang }: { results: Frame3dResults; lang: Lang }) {
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);
  const rows = [...results.storeyLateral].sort((a, b) => b.storey - a.storey);
  const max = Math.max(...rows.map((r) => r.shearKn), 1);
  return (
    <>
      <h3>{tx("Base shear & lateral storey forces", "برش پایه و نیروهای جانبی طبقات")}</h3>
      {rows.length ? (
        <div className="ar-scroll">
          <table className="engineering-result-table" data-testid="shear-table">
            <thead>
              <tr><th>{tx("Storey", "طبقه")}</th><th>{tx("Force (kN)", "نیرو (kN)")}</th><th>{tx("Storey shear (kN)", "برش طبقه (kN)")}</th><th aria-hidden="true" /></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.storey}>
                  <td>{r.storey}</td><td>{fmtNum(r.forceKn, 1)}</td><td>{fmtNum(r.shearKn, 1)}</td>
                  <td className="ar-bar-cell"><span className="ar-bar" style={{ width: `${(r.shearKn / max) * 100}%` }} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {results.baseShearStatus ? (
        <p className="ar-check">
          <span className="ar-chip ok">{results.baseShearStatus}</span> {tx("Base shear check: sum of reactions vs C·W", "کنترل برش پایه: مجموع واکنش‌ها در برابر C·W")}
        </p>
      ) : null}
      <Note>{tx("Equivalent static lateral forces; shear accumulates from the roof down.", "نیروهای جانبی معادل استاتیکی؛ برش از بام به پایین انباشته می‌شود.")}</Note>
    </>
  );
}

function MembersPanel({ results, lang }: { results: Frame3dResults; lang: Lang }) {
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);
  const beams = results.storeyForces.filter((r) => r.beamMNegKnM !== null || r.beamMPosKnM !== null || r.beamVKn !== null);
  const cols = results.storeyForces.filter((r) => r.columnPKn !== null);
  return (
    <>
      <h3>{tx("Member force envelopes", "پوش نیروی اعضا")}</h3>
      <details open className="ar-details">
        <summary>{tx("Beams (per storey)", "تیرها (هر طبقه)")}</summary>
        <div className="ar-scroll">
          <table className="engineering-result-table">
            <thead><tr><th>{tx("Storey", "طبقه")}</th><th>M⁻ (kN·m)</th><th>M⁺ (kN·m)</th><th>V (kN)</th></tr></thead>
            <tbody>
              {beams.map((r) => (
                <tr key={r.storey}><td>{r.storey}</td><td>{fmtNum(r.beamMNegKnM, 1)}</td><td>{fmtNum(r.beamMPosKnM, 1)}</td><td>{fmtNum(r.beamVKn, 1)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <details className="ar-details">
        <summary>{tx("Columns (per storey)", "ستون‌ها (هر طبقه)")}</summary>
        <div className="ar-scroll">
          <table className="engineering-result-table">
            <thead><tr><th>{tx("Storey", "طبقه")}</th><th>P (kN)</th></tr></thead>
            <tbody>
              {cols.map((r) => (
                <tr key={r.storey}><td>{r.storey}</td><td>{fmtNum(r.columnPKn, 1)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <Note>{tx("Envelope over all load combinations — analysis forces only, not design capacities.", "پوش همهٔ ترکیب بارها — فقط نیروهای تحلیل، نه ظرفیت‌های طراحی.")}</Note>
    </>
  );
}

function RunsLog({ projectId, lang, bare }: { projectId: string | null; lang: Lang; bare?: boolean }) {
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);
  const [runs, setRuns] = useState<AnalysisRunSummary[] | null>(null);
  useEffect(() => {
    const pid = projectId ?? getCurrentProjectId();
    if (!pid) {
      setRuns([]);
      return;
    }
    let live = true;
    listAnalysisRuns(pid)
      .then((r) => live && setRuns(r.runs))
      .catch(() => live && setRuns([]));
    return () => {
      live = false;
    };
  }, [projectId]);
  if (!runs || (runs.length === 0 && !bare)) return null;
  const label = (s: string) => {
    const en = getAnalysisStatusLabel(s);
    return lang === "fa" ? FA_STATUS[en] ?? en : en;
  };
  const body = runs.length ? (
    <ul className="ar-runs" data-testid="analysis-runs">
      {runs.map((r) => (
        <li key={r.id}>
          <strong dir="ltr">{r.analysis_type}</strong> <span className="ar-chip soft">{label(r.status)}</span>
          <span className="muted" dir="ltr"> v{r.pem_version} · {r.created_at ? new Date(r.created_at).toLocaleString() : ""}</span>
        </li>
      ))}
    </ul>
  ) : (
    <p className="muted">{tx("No platform analysis runs recorded yet.", "هنوز اجرای تحلیلی ثبت نشده است.")}</p>
  );
  return bare ? (
    <>
      <h3>{tx("Analysis run status (STATIC / MODAL / DRIFT)", "وضعیت اجرای تحلیل (STATIC / MODAL / DRIFT)")}</h3>
      {body}
    </>
  ) : (
    <section className="ar-card">
      <h3>{tx("Analysis run status", "وضعیت اجرای تحلیل")}</h3>
      {body}
    </section>
  );
}
