"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { IncompleteInputsNote, missingInputs } from "@/components/frame3d/DownloadsPanel";
import { useLatestFrame3d } from "@/components/frame3d/Frame3dWorkspacePanel";
import { useProjectScope } from "@/hooks/useProjectScope";
import { useUiLang } from "@/hooks/useUiLang";
import {
  createReport,
  generateReportVersion,
  getReportVersion,
  listReports,
  type ReportVersionDetail,
} from "@/lib/api";
import { download } from "@/lib/frame3d-downloads";
import { buildReportHtml } from "@/lib/frame3d-report";
import {
  buildReportRows,
  REPORT_GENERATE_TYPES,
  reportJsonFilename,
  reportStatusKey,
  reportTypeKey,
  versionMissingData,
  versionSections,
  type ReportRow,
} from "@/lib/reports-workspace";

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatDate(value: string | null, lang: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(lang === "fa" ? "fa-IR" : undefined, { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** The Reports page body: only reports (stored reports + the calculation report of the latest 3D frame run). */
export function ReportsList() {
  const { t, lang } = useUiLang();
  const { projects, selectedProjectId, setSelectedProjectId, loading, error, setError } = useProjectScope();
  const frame = useLatestFrame3d();
  const frameHtml = useMemo(
    () => (frame.results ? buildReportHtml(frame.results, null, new Date().toLocaleString()) : null),
    [frame.results],
  );
  const [stored, setStored] = useState<unknown>([]);
  const [listLoading, setListLoading] = useState(false);
  const [type, setType] = useState<string>("PROJECT_SUMMARY");
  const [generating, setGenerating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [version, setVersion] = useState<{ id: string; data?: ReportVersionDetail; error?: string; busy?: boolean } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = useCallback(async (projectId: string) => {
    if (!projectId) {
      setStored([]);
      return;
    }
    setListLoading(true);
    try {
      const res = await listReports(projectId);
      setStored(Array.isArray(res?.reports) ? res.reports : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStored([]);
    } finally {
      setListLoading(false);
    }
  }, [setError]);

  useEffect(() => {
    setOpenId(null);
    setVersion(null);
    void refresh(selectedProjectId);
  }, [selectedProjectId, refresh]);

  const incomplete = missingInputs(frame.inputs);
  const rows = useMemo(() => buildReportRows(stored, Boolean(frameHtml) && frame.projectId === selectedProjectId), [stored, frameHtml, frame.projectId, selectedProjectId]);

  async function generate() {
    if (!selectedProjectId) return;
    setGenerating(true);
    setError(null);
    try {
      const report = await createReport(selectedProjectId, type, t(reportTypeKey(type)));
      await generateReportVersion(selectedProjectId, report.id, type);
      await refresh(selectedProjectId);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function loadVersion(row: ReportRow): Promise<ReportVersionDetail | null> {
    if (!row.version) return null;
    setVersion({ id: row.id, busy: true });
    try {
      const data = await getReportVersion(selectedProjectId, row.id, row.version);
      setVersion({ id: row.id, data });
      return data;
    } catch (e) {
      setVersion({ id: row.id, error: e instanceof Error ? e.message : String(e) });
      return null;
    }
  }

  async function toggleOpen(row: ReportRow) {
    if (openId === row.id) {
      setOpenId(null);
      return;
    }
    setOpenId(row.id);
    if (row.source === "stored") await loadVersion(row);
  }

  async function downloadStored(row: ReportRow) {
    setActionError(null);
    setBusy(`${row.id}:json`);
    try {
      const data = version?.id === row.id && version.data ? version.data : await loadVersion(row);
      if (!data) throw new Error(t("This report has no generated version yet."));
      saveBlob(new Blob([JSON.stringify(data.content, null, 2)], { type: "application/json" }), reportJsonFilename(row.title, row.type, row.version));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function downloadFrame(name: "report_pdf" | "report_md", format: "pdf" | "md") {
    setActionError(null);
    setBusy(name);
    try {
      await download({ kind: "report", name }, format, { inputs: frame.inputs, projectId: frame.projectId, saveToFiles: false });
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  function downloadFrameHtml() {
    if (frameHtml) saveBlob(new Blob([frameHtml], { type: "text/html" }), "frame3d-report.html");
  }

  const dir = lang === "fa" ? "rtl" : "ltr";
  return (
    <section className="panel reports-page" dir={dir} data-testid="reports-page">
      <header className="page-header">
        <h2>{t("Reports")}</h2>
        <p className="subtitle">{t("Project reports and calculation reports.")}</p>
      </header>

      <div className="reports-toolbar">
        <label className="reports-field">
          <span className="muted">{t("Project")}</span>
          <select
            className="input project-select"
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            disabled={loading || projects.length === 0}
            aria-label={t("Project")}
          >
            {projects.length === 0 ? <option value="">—</option> : null}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label className="reports-field">
          <span className="muted">{t("Report type")}</span>
          <select className="input" value={type} onChange={(e) => setType(e.target.value)} aria-label={t("Report type")}>
            {REPORT_GENERATE_TYPES.map((x) => (
              <option key={x} value={x}>{t(reportTypeKey(x))}</option>
            ))}
          </select>
        </label>
        <button className="button" type="button" disabled={!selectedProjectId || generating} onClick={() => void generate()} data-testid="generate-report">
          {generating ? t("Generating…") : t("Generate report")}
        </button>
      </div>

      {error ? <p className="alert error" role="alert">{error}</p> : null}
      {actionError ? <p className="alert error" role="alert">{actionError}</p> : null}
      {incomplete.length && frame.projectId === selectedProjectId ? <IncompleteInputsNote missing={incomplete} lang={lang} /> : null}

      {!loading && projects.length === 0 ? (
        <div className="empty-state" data-testid="reports-no-project">
          <p>{t("No projects yet. Create one to start working here.")}</p>
          <Link className="cta-button" href="/projects/new">{t("Create project")}</Link>
        </div>
      ) : listLoading && rows.length === 0 ? (
        <p className="muted">{t("Loading…")}</p>
      ) : rows.length === 0 ? (
        <div className="empty-state" data-testid="reports-empty">
          <strong>{t("No reports yet")}</strong>
          <p>{t("Generate a report above, or analyse a 3D frame in the chat to get a calculation report.")}</p>
        </div>
      ) : (
        <ul className="workspace-list reports-list" data-testid="reports-list">
          {rows.map((row) => {
            const date = formatDate(row.date, lang);
            const isOpen = openId === row.id;
            const frameRow = row.source === "frame3d";
            return (
              <li key={row.id} className="report-row workspace-list-item compact" data-testid="report-row">
                <div className="report-row-head">
                  <div className="report-row-main">
                    <strong>{frameRow ? t("Calculation report") : row.title || t(reportTypeKey(row.type))}</strong>
                    <p className="muted">
                      {t(reportTypeKey(row.type))}
                      {frameRow ? ` · ${t("Latest 3D frame run")}` : ""}
                      {row.version ? ` · ${t("Version")} ${row.version}` : ""}
                      {` · ${date ?? t("Not dated")}`}
                    </p>
                  </div>
                  {row.status ? <span className="status-pill">{t(reportStatusKey(row.status))}</span> : null}
                </div>
                <div className="frame3d-actions report-row-actions">
                  <button
                    type="button"
                    className="button secondary"
                    aria-expanded={isOpen}
                    disabled={!frameRow && !row.version}
                    onClick={() => void toggleOpen(row)}
                  >
                    {isOpen ? t("Close") : t("Open")}
                  </button>
                  {frameRow ? (
                    <>
                      <button type="button" className="button" onClick={downloadFrameHtml}>{t("Download")} HTML</button>
                      <button type="button" className="button" disabled={Boolean(incomplete.length) || busy === "report_pdf"} onClick={() => void downloadFrame("report_pdf", "pdf")}>
                        {busy === "report_pdf" ? t("Preparing…") : `${t("Download")} PDF`}
                      </button>
                      <button type="button" className="button" disabled={Boolean(incomplete.length) || busy === "report_md"} onClick={() => void downloadFrame("report_md", "md")}>
                        {busy === "report_md" ? t("Preparing…") : `${t("Download")} Markdown`}
                      </button>
                    </>
                  ) : (
                    <button type="button" className="button" disabled={!row.version || busy === `${row.id}:json`} onClick={() => void downloadStored(row)}>
                      {busy === `${row.id}:json` ? t("Preparing…") : `${t("Download")} JSON`}
                    </button>
                  )}
                </div>
                {isOpen && frameRow && frameHtml ? <iframe className="report-frame" title={t("Calculation report")} srcDoc={frameHtml} /> : null}
                {isOpen && !frameRow ? <StoredVersionView state={version?.id === row.id ? version : null} t={t} /> : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function StoredVersionView({ state, t }: { state: { data?: ReportVersionDetail; error?: string; busy?: boolean } | null; t: (k: string) => string }) {
  if (!state || state.busy) return <p className="muted">{t("Loading…")}</p>;
  if (state.error) return <p className="alert error" role="alert">{state.error}</p>;
  const sections = versionSections(state.data?.content);
  const missing = versionMissingData(state.data?.traceability_metadata);
  return (
    <div className="report-version" data-testid="report-version">
      {sections.length === 0 ? <p className="muted">{t("No sections in this version.")}</p> : null}
      {sections.map((s) => (
        <details key={s.key} className="report-section">
          <summary>{s.title}</summary>
          {s.text ? <pre dir="ltr">{s.text}</pre> : null}
        </details>
      ))}
      {missing.length ? (
        <div className="report-missing">
          <strong>{t("Missing data")}</strong>
          <ul>{missing.map((m) => <li key={m}>{m}</li>)}</ul>
        </div>
      ) : null}
    </div>
  );
}
