"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { DxfViewer } from "@/components/cad/DxfViewer";
import { SectionErrorBoundary } from "@/components/common/SectionErrorBoundary";
import { useUiLang } from "@/hooks/useUiLang";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";
import { loadDetailingPlan, type DetailingPlan } from "@/lib/detailing-plan";
import { DETAILING_COMMAND, DETAILING_FEATURE, markDetailingDone } from "@/lib/detailing-step";
import { download, fetchDownload } from "@/lib/frame3d-downloads";
import { loadFrame3dInputs } from "@/lib/frame3d-store";

const TXT: Record<string, { en: string; fa: string }> = {
  eyebrow: { en: "After design", fa: "پس از طراحی" },
  title: { en: "Detailing (rebar)", fa: "دیتیلینگ (جزئیات آرماتوربندی)" },
  desc: {
    en: "Rebar detailing of the project's latest frame design (Mabhas 9): beam and column reinforcement sheets and the bar bending schedule.",
    fa: "جزئیات آرماتوربندی آخرین طراحی قاب این پروژه (مبحث نهم): برگه‌های آرماتور تیر و ستون و جدول خم و برش میلگرد.",
  },
  show: { en: "Show rebar detailing", fa: "نمایش دیتیلینگ آرماتور" },
  refresh: { en: "Rebuild from the latest design", fa: "ساخت دوباره از آخرین طراحی" },
  loading: { en: "Building the rebar detailing…", fa: "در حال ساخت دیتیلینگ آرماتور…" },
  dxf: { en: "Download rebar DXF", fa: "دانلود DXF آرماتوربندی" },
  pdf: { en: "Rebar sheets (PDF)", fa: "برگه‌های آرماتوربندی (PDF)" },
  set: { en: "Structural drawing set (PDF)", fa: "نقشه‌های اجرایی سازه (PDF)" },
  sheets: {
    en: "Sheets: R-01 beam details, R-02 column details, R-03 bar bending schedule (pick the sheet in the viewer).",
    fa: "برگه‌ها: R-01 جزئیات تیر، R-02 جزئیات ستون، R-03 جدول میلگردها (برگه را در نمایشگر انتخاب کنید).",
  },
  noProject: { en: "Select or create a project first.", fa: "ابتدا یک پروژه انتخاب یا ایجاد کنید." },
  locked: {
    en: "Rebar detailing sheets are not included in your plan. The page stays visible; upgrade to generate them.",
    fa: "برگه‌های آرماتوربندی در پلن شما نیست. این صفحه نمایش داده می‌شود؛ برای ساخت آن‌ها پلن را ارتقا دهید.",
  },
  upgrade: { en: "See plans", fa: "مشاهده پلن‌ها" },
  noModel: {
    en: "No complete frame model in this project yet. Describe a frame in chat or complete it on the Model page, then come back.",
    fa: "هنوز مدل قاب کاملی در این پروژه نیست. قاب را در گفتگو توصیف کنید یا در صفحه مدل کامل کنید و برگردید.",
  },
  model: { en: "Model page", fa: "صفحه مدل" },
  design: { en: "Design page", fa: "صفحه طراحی" },
  open: { en: "Open the Detailing page", fa: "باز کردن صفحه دیتیلینگ" },
  chat: { en: "Or type in chat:", fa: "یا در گفتگو بنویسید:" },
  auto: {
    en: "If the run had no member design, the Mabhas 9 design is built automatically for the detailing.",
    fa: "اگر اجرای قاب طراحی اعضا نداشته باشد، طراحی مبحث نهم برای دیتیلینگ خودکار انجام می‌شود.",
  },
};

function isNoModel(msg: string): boolean {
  return /No complete 3D frame|incomplete|کامل نیست|مدل کامل|No usable|no frame/i.test(msg);
}

/** Detailing step: rebar drawings + bar schedule of the project's latest frame design, with DXF/PDF downloads. Never hidden. */
export function DetailingPanel({ compact = false }: { compact?: boolean }) {
  const { lang } = useUiLang();
  const tx = (k: string) => TXT[k][lang];
  const [projectId, setProjectId] = useState<string | null>(null);
  const [plan, setPlan] = useState<DetailingPlan | null>(null);
  const [dxf, setDxf] = useState<{ text: string; filename: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => {
      setProjectId(getCurrentProjectId());
      setDxf(null);
      setErr(null);
    };
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    void loadDetailingPlan().then(setPlan);
    return () => window.removeEventListener(PROJECT_EVENT, sync);
  }, []);

  const locked = Boolean(plan && plan.enforcement !== false && Array.isArray(plan.designSheets) && !plan.designSheets.includes(DETAILING_FEATURE));
  // null inputs -> the server uses the project's latest complete frame run (works on any device).
  const ctx = useCallback(() => ({ inputs: loadFrame3dInputs(projectId), projectId, saveToFiles: false }), [projectId]);

  const show = useCallback(async () => {
    if (!projectId) return;
    setBusy("show");
    setErr(null);
    try {
      const { blob, filename } = await fetchDownload({ kind: "drawing", name: "dxf_rebar" }, "dxf", ctx());
      setDxf({ text: await blob.text(), filename });
      markDetailingDone(projectId);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [projectId, ctx]);

  useEffect(() => {
    if (!compact && projectId && plan && !locked) void show();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compact, projectId, plan, locked]);

  async function get(name: string, format: string) {
    setBusy(name + format);
    setErr(null);
    try {
      await download({ kind: "drawing", name }, format, { ...ctx(), saveToFiles: Boolean(projectId) });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const disabled = !projectId || busy !== null || locked;
  return (
    <section className="card detailing-panel" data-testid="detailing-panel" dir={lang === "fa" ? "rtl" : "ltr"} lang={lang}>
      <p className="eyebrow">{tx("eyebrow")}</p>
      <h2>{tx("title")}</h2>
      <p className="subtitle">{tx("desc")}</p>
      {!projectId ? <p className="muted">{tx("noProject")} <Link href="/projects">{lang === "fa" ? "پروژه‌ها" : "Projects"}</Link></p> : null}
      {locked ? (
        <div className="alert" role="note" data-testid="detailing-locked">
          <p>{tx("locked")}</p>
          <Link className="button secondary" href="/workspace/upgrades">{tx("upgrade")}</Link>
        </div>
      ) : null}
      <div className="button-row detailing-step-actions">
        <button type="button" className="button" disabled={disabled} onClick={() => void show()} data-testid="detailing-show">
          {busy === "show" ? tx("loading") : dxf ? tx("refresh") : tx("show")}
        </button>
        <button type="button" className="button secondary" disabled={disabled} onClick={() => void get("dxf_rebar", "dxf")} data-testid="detailing-dxf">
          {busy === "dxf_rebardxf" ? tx("loading") : tx("dxf")}
        </button>
        <button type="button" className="button secondary" disabled={disabled} onClick={() => void get("dxf_rebar", "pdf")}>
          {busy === "dxf_rebarpdf" ? tx("loading") : tx("pdf")}
        </button>
        <button type="button" className="button secondary" disabled={disabled} onClick={() => void get("structural_set", "pdf")}>
          {busy === "structural_setpdf" ? tx("loading") : tx("set")}
        </button>
        {compact ? <Link className="button secondary" href="/workspace/detailing">{tx("open")}</Link> : null}
      </div>
      <p className="muted">{tx("auto")}</p>
      {busy === "show" ? <p role="status">{tx("loading")}</p> : null}
      {err ? (
        isNoModel(err) ? (
          <div className="empty-state" data-testid="detailing-no-model">
            <p>{tx("noModel")}</p>
            <p><Link href="/workspace/model">{tx("model")}</Link> · <Link href="/workspace/design">{tx("design")}</Link></p>
          </div>
        ) : (
          <p className="alert error" role="alert" data-testid="detailing-error">{err}</p>
        )
      ) : null}
      {dxf ? (
        <SectionErrorBoundary label="Detailing">
          <p className="muted">{tx("sheets")}</p>
          <div data-testid="detailing-viewer" style={{ maxWidth: "100%", overflow: "hidden" }}>
            <DxfViewer text={dxf.text} filename={dxf.filename} height={compact ? 420 : 560} />
          </div>
        </SectionErrorBoundary>
      ) : null}
      <p className="muted detailing-step-chat">
        {tx("chat")} <code>{DETAILING_COMMAND[lang]}</code>
      </p>
    </section>
  );
}
