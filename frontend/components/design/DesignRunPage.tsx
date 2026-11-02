"use client";

import { DetailingPanel } from "@/components/detailing/DetailingPanel";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { SectionErrorBoundary } from "@/components/common/SectionErrorBoundary";
import { runFrame3d } from "@/components/frame3d/Frame3dWorkspacePanel";
import { useUiLang } from "@/hooks/useUiLang";
import { mapFrame3dResults } from "@/lib/chat-mappers";
import { hydrateFrame3dFromServer } from "@/lib/chat-runs";
import type { Frame3dResults } from "@/lib/chat-types";
import { ensureCurrentProject } from "@/lib/ensure-project";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";
import {
  chipOf,
  dcChip,
  designReadiness,
  designRunInputs,
  foundationMaxDc,
  governingMember,
  inputLabel,
  loadDesignLastRun,
  rowMaxDc,
  saveDesignLastRun,
  sectionText,
  type DesignChip,
  type DesignLastRun,
  type Row,
} from "@/lib/design-run";
import { summarizeDesign } from "@/lib/frame3d-design-summary";
import { FRAME3D_EVENT, loadFrame3dInputs, loadFrame3dPayload, saveFrame3dInputs, saveFrame3dPayload } from "@/lib/frame3d-store";
import s from "./DesignRunPage.module.css";

type Phase = "idle" | "running" | "success" | "error";

const CHIP_LABEL: Record<DesignChip, string> = { pass: "Pass", review: "Needs review", fail: "Fail" };

function Chip({ chip, t }: { chip: DesignChip; t: (k: string) => string }) {
  return (
    <span className={`${s.chip} ${s[`chip_${chip}`]}`} data-chip={chip}>
      {t(CHIP_LABEL[chip])}
    </span>
  );
}

function dc(v: unknown): string {
  const n = typeof v === "number" ? v : typeof v === "string" ? Number.parseFloat(v) : NaN;
  return Number.isFinite(n) ? n.toFixed(3) : "—";
}

function DcCell({ value }: { value: unknown }) {
  const n = typeof value === "number" ? value : typeof value === "string" ? Number.parseFloat(value) : null;
  const chip = n !== null && Number.isFinite(n) ? dcChip(n) : null;
  return <td className={`${s.num} ${chip === "fail" ? s.dcFail : ""}`}>{dc(value)}</td>;
}

function cell(v: unknown): string {
  return v === null || v === undefined || v === "" ? "—" : String(v);
}

function Table({ head, children, testId }: { head: string[]; children: React.ReactNode; testId: string }) {
  return (
    <div className={s.tableWrap} tabIndex={0} data-testid={testId}>
      <table className={s.table}>
        <thead>
          <tr>{head.map((h) => <th key={h}>{h}</th>)}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function Kpi({ label, value, unit, chip, t, testId }: { label: string; value: React.ReactNode; unit?: string; chip?: DesignChip | null; t: (k: string) => string; testId?: string }) {
  return (
    <div className={s.kpi} data-testid={testId}>
      <span className={s.kpiLabel}>{label}</span>
      <strong className={s.kpiValue} dir="ltr">{value}{unit ? <small> {unit}</small> : null}</strong>
      {chip ? <Chip chip={chip} t={t} /> : null}
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className={s.noteBlock}>
      <h4>{title}</h4>
      <ul>{items.map((i) => <li key={i}>{i}</li>)}</ul>
    </div>
  );
}

function DesignResults({ results, t }: { results: Frame3dResults; t: (k: string) => string }) {
  const design = results.design!;
  const sum = summarizeDesign(design);
  const gov = governingMember(design);
  const inputs = results.inputs as Record<string, unknown> | null;
  const fnd = results.foundation;
  const overall = chipOf(design.status);
  const members = design.beams.length + design.columns.length;
  const checkLabel = gov ? t(gov.check === "flexure" ? "flexure" : gov.check === "shear" ? "shear" : "axial + bending") : "";
  const bannerText =
    overall === "pass" ? t("All designed member groups satisfy the checked criteria.")
      : overall === "fail" ? t("One or more checks fail. See the tables below.")
        : t("Some checks need engineering review before the design can be accepted.");
  return (
    <>
      <section className={`${s.banner} ${s[`banner_${overall}`]}`} data-testid="design-status-banner" aria-live="polite">
        <div>
          <p className={s.bannerLabel}>{t("Design status")}</p>
          <p className={s.bannerText}>{bannerText}</p>
          <p className={s.bannerMeta}>
            {t("Code")}: {results.designCode ?? design.code}
            {design.ductility ? ` · ${t(design.ductility)} ${t("ductility")}` : ""}
          </p>
        </div>
        <Chip chip={overall} t={t} />
      </section>

      <div className={s.kpis} data-testid="design-kpis">
        <Kpi t={t} testId="kpi-members" label={t("Designed member groups")} value={members} />
        <Kpi t={t} testId="kpi-max-dc" label={t("Max demand/capacity ratio")} value={sum.maxDc === null ? "—" : sum.maxDc.toFixed(3)} chip={dcChip(sum.maxDc)} />
        <Kpi t={t} testId="kpi-governing" label={t("Governing member")} value={gov ? gov.group : "—"} unit={gov ? `(${checkLabel})` : undefined} />
        <Kpi t={t} testId="kpi-failing" label={t("Groups with D/C > 1")} value={sum.overstressedGroups} chip={sum.overstressedGroups > 0 ? "fail" : "pass"} />
        {sum.scwbMinRatio !== null ? (
          <Kpi t={t} testId="kpi-scwb" label={t("Min ΣMnc/ΣMnb")} value={sum.scwbMinRatio.toFixed(3)} />
        ) : null}
      </div>

      {design.message ? <p className={s.message}>{design.message}</p> : null}

      {design.beams.length > 0 ? (
        <section className={s.section} data-testid="design-beams">
          <h3>{t("Beams")}</h3>
          <Table
            testId="design-beams-table"
            head={[t("Group"), `${t("Section b×h")} (mm)`, "Mu⁻ (kN·m)", "Mu⁺ (kN·m)", "Vu (kN)", t("Top bars"), t("Bottom bars"), t("Stirrups"), t("D/C flexure"), t("D/C shear"), t("Status")]}
          >
            {design.beams.map((r: Row) => (
              <tr key={String(r.group)}>
                <td className={s.name}>{cell(r.group)}</td>
                <td className={s.num} dir="ltr">{sectionText("beam", r, inputs)}</td>
                <td className={s.num}>{cell(r.Mu_neg_kn_m)}</td>
                <td className={s.num}>{cell(r.Mu_pos_kn_m)}</td>
                <td className={s.num}>{cell(r.Vu_kn)}</td>
                <td dir="ltr">{cell(r.top_bars)}</td>
                <td dir="ltr">{cell(r.bottom_bars)}</td>
                <td dir="ltr">{cell(r.stirrups)}</td>
                <DcCell value={r.DC_flexure} />
                <DcCell value={r.DC_shear} />
                <td><Chip chip={chipOf(String(r.status ?? ""))} t={t} /></td>
              </tr>
            ))}
          </Table>
        </section>
      ) : null}

      {design.columns.length > 0 ? (
        <section className={s.section} data-testid="design-columns">
          <h3>{t("Columns")}</h3>
          <Table
            testId="design-columns-table"
            head={[t("Group"), `${t("Section b×h")} (mm)`, "Pu (kN)", "Mu,y (kN·m)", "Mu,z (kN·m)", t("Bars"), "ρ (%)", t("Ties"), t("D/C"), t("Status")]}
          >
            {design.columns.map((r: Row) => (
              <tr key={String(r.group)}>
                <td className={s.name}>{cell(r.group)}</td>
                <td className={s.num} dir="ltr">{sectionText("column", r, inputs)}</td>
                <td className={s.num}>{cell(r.Pu_kn)}</td>
                <td className={s.num}>{cell(r.Mu_y_kn_m)}</td>
                <td className={s.num}>{cell(r.Mu_z_kn_m)}</td>
                <td dir="ltr">{cell(r.bars)}</td>
                <td className={s.num}>{cell(r.rho_pct)}</td>
                <td dir="ltr">{cell(r.ties)}</td>
                <DcCell value={r.DC} />
                <td><Chip chip={chipOf(String(r.status ?? ""))} t={t} /></td>
              </tr>
            ))}
          </Table>
        </section>
      ) : null}

      {design.scwb.length > 0 ? (
        <section className={s.section} data-testid="design-scwb">
          <h3>{t("Strong column / weak beam")}</h3>
          {design.scwbNote ? <p className="muted">{design.scwbNote}</p> : null}
          <Table testId="design-scwb-table" head={[t("Level"), t("Joint"), t("Direction"), t("Min ΣMnc/ΣMnb"), t("Status")]}>
            {design.scwb.map((r: Row) => (
              <tr key={String(r.level)}>
                <td className={s.num}>{cell(r.level)}</td>
                <td dir="ltr">{cell(r.joint)}</td>
                <td>{cell(r.direction)}</td>
                <DcCell value={r.min_ratio} />
                <td><Chip chip={chipOf(String(r.status ?? ""))} t={t} /></td>
              </tr>
            ))}
          </Table>
        </section>
      ) : null}

      {fnd && fnd.rows.length > 0 ? (
        <section className={s.section} data-testid="design-foundation">
          <h3>{t("Foundation (isolated footings)")}</h3>
          <p className="muted">
            {t("Allowable bearing")}: {fnd.qaKpa ?? "—"} kPa{fnd.qaAssumed ? ` (${t("assumed")})` : ""} · {t("Max D/C")}: {dc(foundationMaxDc(fnd))}
          </p>
          <Table
            testId="design-foundation-table"
            head={[t("Group"), "B (m)", "h (m)", "q max (kPa)", t("D/C bearing"), t("D/C one-way shear"), t("D/C punching"), t("D/C flexure"), t("Bars"), t("Status")]}
          >
            {fnd.rows.map((r: Row) => (
              <tr key={String(r.group)}>
                <td className={s.name}>{cell(r.group)}</td>
                <td className={s.num}>{cell(r.B_m)}</td>
                <td className={s.num}>{cell(r.h_m)}</td>
                <td className={s.num}>{cell(r.q_max_kpa)}</td>
                <DcCell value={r.bearing_dc} />
                <DcCell value={r.DC_oneway} />
                <DcCell value={r.DC_punching} />
                <DcCell value={r.DC_flexure} />
                <td dir="ltr">{cell(r.bars)}</td>
                <td><Chip chip={chipOf(String(r.status ?? ""))} t={t} /></td>
              </tr>
            ))}
          </Table>
          {fnd.recommendation ? <p className="muted">{fnd.recommendation}</p> : null}
        </section>
      ) : null}

      <section className={s.section} data-testid="design-notes">
        <h3>{t("Notes and assumptions")}</h3>
        <List title={t("Assumptions")} items={results.assumptions} />
        <List title={t("Warnings")} items={results.warnings} />
        <List title={t("Simplified or not implemented (limitations)")} items={[...design.clausesSimplified, ...(fnd?.clausesSimplified ?? [])]} />
        {results.disclaimer ? <p className="muted">{results.disclaimer}</p> : null}
        <p className="muted">{t("Results are engine output for review by the responsible engineer; they are not a final approval.")}</p>
      </section>
    </>
  );
}

function formatAt(iso: string, lang: "en" | "fa"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(lang === "fa" ? "fa-IR" : "en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export function DesignRunPage() {
  return (
    <SectionErrorBoundary label="Design">
      <DesignRunPageInner />
    </SectionErrorBoundary>
  );
}

function DesignRunPageInner() {
  const { lang, t } = useUiLang();
  const [projectId, setProjectId] = useState<string | null>(null);
  const [inputs, setInputs] = useState<Record<string, unknown> | null>(null);
  const [payload, setPayload] = useState<unknown>(null);
  const [lastRun, setLastRun] = useState<DesignLastRun | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => {
      const pid = getCurrentProjectId();
      if (!pid) void ensureCurrentProject();
      setProjectId(pid);
      const saved = loadFrame3dInputs(pid);
      if (!saved) void hydrateFrame3dFromServer(pid);
      setInputs(saved);
      setPayload(loadFrame3dPayload(pid));
      setLastRun(loadDesignLastRun(pid));
    };
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    window.addEventListener(FRAME3D_EVENT, sync);
    return () => {
      window.removeEventListener(PROJECT_EVENT, sync);
      window.removeEventListener(FRAME3D_EVENT, sync);
    };
  }, []);

  const results = useMemo(() => (payload ? mapFrame3dResults(payload) : null), [payload]);
  const readiness = useMemo(() => designReadiness(inputs, payload), [inputs, payload]);
  const hasDesign = !!results?.design && (results.design.beams.length + results.design.columns.length > 0);
  const running = phase === "running";

  const run = useCallback(async () => {
    if (!inputs || !readiness.ready || running) return;
    setPhase("running");
    setError(null);
    setNote(null);
    try {
      const { inputs: runInputs, codeSwitchedOn } = designRunInputs(inputs, lang);
      const fresh = await runFrame3d(runInputs);
      const mapped = mapFrame3dResults(fresh);
      if (!mapped) throw new Error(t("The engine returned no member design for this model."));
      if (mapped.status === "MISSING_REQUIRED_INPUT") {
        const names = mapped.missing.filter((k) => k !== "frame_model").map((k) => t(inputLabel(k)));
        throw new Error(`${t("The model is incomplete")}${names.length ? `: ${names.join(lang === "fa" ? "، " : ", ")}` : ""}`);
      }
      if (mapped.status !== "completed" || !mapped.design) {
        throw new Error(mapped.message || t("The engine returned no member design for this model."));
      }
      saveFrame3dInputs(projectId, runInputs);
      saveFrame3dPayload(projectId, fresh);
      const stamp = { at: new Date().toISOString(), ok: true };
      saveDesignLastRun(projectId, stamp);
      setLastRun(stamp);
      if (codeSwitchedOn) setNote(t("The project had no design code selected, so the Mabhas 9 member design was used."));
      setPhase("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase("error");
    }
  }, [inputs, readiness.ready, running, lang, projectId, t]);

  const label = running ? t("Designing…") : t("Design");
  const disabled = !readiness.ready || running;
  const empty = !hasDesign;

  return (
    <section className={s.page} dir={lang === "fa" ? "rtl" : "ltr"} lang={lang} data-testid="design-page">
      <header className={s.header}>
        <p className={s.eyebrow}>{t("Structural design")}</p>
        <h2 data-testid="design-title">{t("Design results")}</h2>
        <p className="subtitle">{t("Mabhas 9 member design of the analysed model: demand/capacity ratios, reinforcement and sections.")}</p>
      </header>

      <div className={`${s.action} ${empty ? s.actionEmpty : ""}`} data-testid={empty ? "design-empty" : "design-action"}>
        {empty ? (
          <div className={s.emptyText}>
            <h3>{t("No design results yet")}</h3>
            <p className="muted">
              {readiness.ready
                ? t("Press Design to run the member design on the analysed model. The results will appear here.")
                : t("The design needs the items listed below.")}
            </p>
          </div>
        ) : (
          <div className={s.lastRun}>
            {lastRun ? <span>{t("Last design run")}: {formatAt(lastRun.at, lang)}</span> : <span className="muted">{t("Showing the latest saved results of this project.")}</span>}
          </div>
        )}
        <button
          type="button"
          className={`button ${s.designButton} ${empty ? s.designButtonBig : ""}`}
          data-testid="design-button"
          disabled={disabled}
          aria-busy={running}
          aria-describedby={!readiness.ready ? "design-missing" : undefined}
          onClick={() => void run()}
        >
          {label}
        </button>
      </div>

      {!readiness.ready ? (
        <div className={s.missing} id="design-missing" role="note" data-testid="design-missing">
          <strong>{t("Design is disabled until these are available:")}</strong>
          <ul>
            {readiness.missing.map((m) => (
              <li key={m.id}>
                <span>{t(m.label)}</span> —{" "}
                <Link href={m.href}>{m.href === "/workspace/analysis" ? t("Go to Analysis") : t("Go to Model")}</Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {running ? <p className={s.status} role="status" data-testid="design-loading">{t("Running the design on the analysed model…")}</p> : null}
      {phase === "success" ? <p className={`${s.status} ${s.statusOk}`} role="status" data-testid="design-success">{t("Design finished. The results below are updated.")}</p> : null}
      {note ? <p className={s.status} data-testid="design-note">{note}</p> : null}
      {phase === "error" && error ? <p className={`${s.status} ${s.statusErr}`} role="alert" data-testid="design-error">{t("Design failed")}: {error}</p> : null}

      {results?.design && hasDesign ? <DesignResults results={results} t={t} /> : null}
      <DetailingPanel compact />
    </section>
  );
}
