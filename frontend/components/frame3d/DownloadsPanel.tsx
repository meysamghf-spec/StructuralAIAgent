"use client";

import { useState } from "react";

import { SectionErrorBoundary } from "@/components/common/SectionErrorBoundary";
import { useUiLang } from "@/hooks/useUiLang";
import { DOWNLOADS, download, downloadAll, fetchDownload, type DownloadGroup, type ZipProgress, type DownloadItem } from "@/lib/frame3d-downloads";

type Props = {
  inputs: Record<string, unknown> | null | undefined;
  projectId?: string | null;
  optimization?: unknown;
  groups?: DownloadGroup[];
  title?: string;
  /** Start collapsed (an expandable panel) — default open. */
  collapsed?: boolean;
};

const FA: Record<string, string> = {
  "Downloads": "دانلودها",
  "Download all (ZIP)": "دانلود همه (ZIP)",
  "Also save to project Files": "ذخیره در فایل‌های پروژه",
  "Preparing ZIP…": "در حال آماده‌سازی ZIP…",
  "files in the ZIP": "فایل در ZIP",
  "Building all files on the server": "ساخت همهٔ فایل‌ها روی سرور",
  "usually 30–90 s": "معمولاً ۳۰ تا ۹۰ ثانیه",
  "Downloading ZIP…": "در حال دانلود ZIP…",
  "Try again": "تلاش دوباره",
  "saved to Files": "در فایل‌ها ذخیره شد",
  "Run an analysis first to enable downloads.": "برای دانلود، ابتدا تحلیل را اجرا کنید.",
  "Tables": "جداول", "Design": "طراحی", "Foundation": "فونداسیون", "Optimization": "بهینه‌سازی", "Figures": "شکل‌ها",
  "Drawings": "نقشه‌ها", "Model exports": "خروجی مدل", "Reports": "گزارش‌ها", "Show": "نمایش", "Hide": "بستن",
};
const GROUP_LABEL: Record<DownloadGroup, string> = {
  analysis: "Tables", design: "Design", foundation: "Foundation", optimization: "Optimization", figures: "Figures",
  drawings: "Drawings", models: "Model exports", reports: "Reports",
};

const REQUIRED = ["storeys", "bays_x", "bays_y"] as const;

/** Required geometry keys that are present but empty (a run that stopped at "missing required input"). */
export function missingInputs(inputs: Record<string, unknown> | null | undefined): string[] {
  if (!inputs || typeof inputs !== "object") return [];
  return REQUIRED.filter((k) => k in inputs && (inputs[k] === null || inputs[k] === "" || inputs[k] === undefined));
}

export function IncompleteInputsNote({ missing, lang }: { missing: string[]; lang?: string }) {
  const fa = lang === "fa";
  return (
    <p className="alert" role="note" data-testid="incomplete-inputs-note" dir={fa ? "rtl" : "ltr"}>
      {fa
        ? `ورودی‌های این اجرا کامل نیست${missing.length ? ` (${missing.join("، ")})` : ""}. لطفاً ورودی‌ها را در چت کامل کنید تا دانلودها فعال شوند.`
        : `This run's inputs are incomplete${missing.length ? ` (${missing.join(", ")})` : ""}. Complete the inputs in chat to enable downloads.`}
    </p>
  );
}

export function DownloadsPanel(props: Props) {
  const { lang } = useUiLang();
  const missing = missingInputs(props.inputs);
  if (missing.length) return <IncompleteInputsNote missing={missing} lang={lang} />;
  return (
    <SectionErrorBoundary label="Downloads">
      <DownloadsPanelInner {...props} />
    </SectionErrorBoundary>
  );
}

function DownloadsPanelInner({ inputs, projectId, optimization, groups, title, collapsed }: Props) {
  const { lang } = useUiLang();
  const tr = (s: string) => (lang === "fa" ? FA[s] ?? s : s);
  const [open, setOpen] = useState(!collapsed);
  const [busy, setBusy] = useState<string | null>(null);
  const [zip, setZip] = useState<ZipProgress | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toFiles, setToFiles] = useState(true);
  const [preview, setPreview] = useState<{ key: string; url: string } | null>(null);
  const shown = (groups ?? (Object.keys(DOWNLOADS) as DownloadGroup[])).filter((g) => g !== "optimization" || optimization);
  const ctx = { inputs, projectId, optimization, saveToFiles: toFiles };

  async function one(it: DownloadItem, f: string) {
    const key = `${it.kind}:${it.name}:${f}`;
    setBusy(key);
    setErr(null);
    try {
      await download(it, f, ctx);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }
  async function show(it: DownloadItem) {
    const key = `${it.kind}:${it.name}`;
    if (preview?.key === key) {
      URL.revokeObjectURL(preview.url);
      setPreview(null);
      return;
    }
    setBusy(key);
    setErr(null);
    try {
      const { blob } = await fetchDownload(it, "png", { ...ctx, saveToFiles: false });
      if (preview) URL.revokeObjectURL(preview.url);
      setPreview({ key, url: URL.createObjectURL(blob) });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }
  async function all() {
    if (zip) return;
    setZip({ state: "starting", elapsedS: 0 });
    setErr(null);
    setMsg(null);
    try {
      const r = await downloadAll(ctx, setZip);
      setMsg(`${r.files} ${tr("files in the ZIP")}${r.saved ? ` · ${tr("saved to Files")}` : ""}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setZip(null);
    }
  }
  const zipLabel = !zip
    ? err ? tr("Try again") + " — " + tr("Download all (ZIP)") : tr("Download all (ZIP)")
    : zip.state === "downloading" ? tr("Downloading ZIP…") : `${tr("Preparing ZIP…")} ${zip.elapsedS}s`;

  return (
    <section className="downloads-panel" data-testid="downloads-panel" dir={lang === "fa" ? "rtl" : "ltr"}>
      <div className="downloads-head">
        <h3>{title ?? tr("Downloads")}</h3>
        <div className="downloads-actions">
          <button className="button" type="button" disabled={!inputs || zip !== null} onClick={() => void all()} data-testid="zip-btn">
            {zipLabel}
          </button>
          {collapsed !== undefined ? (
            <button className="button secondary" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
              {open ? tr("Hide") : tr("Show")}
            </button>
          ) : null}
        </div>
      </div>
      {projectId ? (
        <label className="downloads-save">
          <input type="checkbox" checked={toFiles} onChange={(e) => setToFiles(e.target.checked)} /> {tr("Also save to project Files")}
        </label>
      ) : null}
      {!inputs ? <p className="muted">{tr("Run an analysis first to enable downloads.")}</p> : null}
      {zip && zip.state !== "downloading" ? (
        <p className="muted" role="status">
          {tr("Building all files on the server")} ({tr("usually 30–90 s")}) — {zip.elapsedS}s
          <progress style={{ display: "block", width: "100%" }} max={90} value={Math.min(zip.elapsedS, 88)} />
        </p>
      ) : null}
      {msg ? <p className="muted" role="status">{msg}</p> : null}
      {err ? <p className="alert error">{err}</p> : null}
      {open && inputs
        ? shown.map((g) => (
            <div className="downloads-group" key={g}>
              <h4>{tr(GROUP_LABEL[g])}</h4>
              <ul>
                {DOWNLOADS[g].map((it) => (
                  <li key={it.kind + it.name}>
                    <span className="downloads-label">{lang === "fa" ? it.labelFa : it.label}</span>
                    <span className="downloads-btns">
                      {it.kind === "figure" ? (
                        <button className="button secondary small" type="button" disabled={busy !== null} onClick={() => void show(it)}>
                          {preview?.key === `figure:${it.name}` ? tr("Hide") : tr("Show")}
                        </button>
                      ) : null}
                      {it.formats.map((f) => (
                        <button
                          key={f}
                          className="button secondary small"
                          type="button"
                          disabled={busy !== null}
                          onClick={() => void one(it, f)}
                        >
                          {busy === `${it.kind}:${it.name}:${f}` ? "…" : f.toUpperCase()}
                        </button>
                      ))}
                    </span>
                    {preview?.key === `${it.kind}:${it.name}` ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img className="downloads-preview" src={preview.url} alt={it.label} />
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))
        : null}
    </section>
  );
}
