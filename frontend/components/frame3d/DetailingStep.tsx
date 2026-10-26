"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { projectChatHref } from "@/lib/current-project";
import {
  DETAILING_COMMAND,
  DETAILING_EVENT,
  detailingDoneAt,
  detailingStatus,
  detailingFromGlance,
  detailingStatusLabel,
  type DetailingStatus,
} from "@/lib/detailing-step";
import { loadDetailingPlan, type DetailingPlan } from "@/lib/detailing-plan";
import { download } from "@/lib/frame3d-downloads";
import { isRtl, type Frame3dLang } from "@/lib/frame3d-i18n";
import { useUiLang } from "@/hooks/useUiLang";

type Props = {
  /** Inputs of the frame run (the backend rebuilds design + rebar from these). */
  inputs: Record<string, unknown> | null;
  projectId: string | null;
  /** A Mabhas 9 design exists for this run. */
  hasDesign: boolean;
  /** Language of the surrounding card (chat result cards follow the prompt language); defaults to the UI language. */
  lang?: Frame3dLang;
};

const TXT: Record<string, { en: string; fa: string }> = {
  title: { en: "Detailing", fa: "جزئیات‌سازی (دیتیلینگ)" },
  desc: {
    en: "Rebar detailing sheets (beams, columns, bar schedule) and the structural drawing set, built from the Mabhas 9 design above.",
    fa: "نقشه‌های جزئیات آرماتوربندی (تیر، ستون، جدول میلگرد) و مجموعهٔ نقشه‌های اجرایی سازه، بر پایهٔ طراحی مبحث نهم بالا.",
  },
  needDesign: { en: "Run the Mabhas 9 design first; there is nothing to detail yet.", fa: "ابتدا طراحی مبحث نهم را اجرا کنید؛ هنوز چیزی برای جزئیات‌سازی نیست." },
  locked: { en: "Rebar sheets are not included in your plan.", fa: "نقشه‌های آرماتوربندی در پلن شما نیست." },
  upgrade: { en: "See plans", fa: "مشاهده پلن‌ها" },
  rebar: { en: "Rebar details (DXF)", fa: "جزئیات آرماتوربندی (DXF)" },
  set: { en: "Structural drawing set (PDF)", fa: "نقشه‌های اجرایی سازه (PDF)" },
  cad: { en: "Open CAD page", fa: "باز کردن صفحهٔ CAD" },
  chat: { en: "Or type in chat:", fa: "یا در گفتگو بنویسید:" },
  openChat: { en: "Open chat", fa: "باز کردن گفتگو" },
  busy: { en: "Generating…", fa: "در حال ساخت…" },
  doneAt: { en: "Last generated", fa: "آخرین ساخت" },
};

export function DetailingStep({ inputs, projectId, hasDesign, lang }: Props) {
  const ui = useUiLang();
  const l: Frame3dLang = lang ?? ui.lang;
  const tx = (k: string) => TXT[k][l];
  const rtl = isRtl(l);
  const [plan, setPlan] = useState<DetailingPlan | null>(null);
  const [doneAt, setDoneAt] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void loadDetailingPlan().then((p) => live && setPlan(p));
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    const sync = () => setDoneAt(detailingDoneAt(projectId));
    sync();
    window.addEventListener(DETAILING_EVENT, sync);
    return () => window.removeEventListener(DETAILING_EVENT, sync);
  }, [projectId]);

  const status: DetailingStatus = detailingStatus({
    hasDesign,
    designSheets: plan?.designSheets ?? null,
    enforcement: plan?.enforcement,
    doneAt,
  });
  const canRun = hasDesign && status !== "locked" && !!inputs;

  async function run(name: string, format: string) {
    setBusy(name);
    setErr(null);
    try {
      await download({ kind: "drawing", name }, format, { inputs, projectId, saveToFiles: Boolean(projectId) });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="engineering-result-block detailing-step" data-testid="detailing-step" data-status={status} dir={rtl ? "rtl" : "ltr"} lang={l}>
      <div className="detailing-step-head">
        <p className="engineering-result-label">{tx("title")}</p>
        <span className={`detailing-badge detailing-${status}`} data-testid="detailing-status">
          {detailingStatusLabel(status, l)}
        </span>
      </div>
      <p className="detailing-step-desc">{status === "not_run" ? tx("needDesign") : status === "locked" ? tx("locked") : tx("desc")}</p>
      {status === "done" && doneAt ? (
        <p className="muted detailing-step-meta">
          {tx("doneAt")}: <time dateTime={doneAt}>{new Date(doneAt).toLocaleString(l === "fa" ? "fa-IR" : "en-GB")}</time>
        </p>
      ) : null}
      {status === "locked" ? (
        <p>
          <Link className="button secondary" href="/workspace/upgrades">
            {tx("upgrade")}
          </Link>
        </p>
      ) : (
        <div className="button-row detailing-step-actions">
          <button type="button" className="button" disabled={!canRun || busy !== null} onClick={() => void run("dxf_rebar", "dxf")}>
            {busy === "dxf_rebar" ? tx("busy") : tx("rebar")}
          </button>
          <button type="button" className="button secondary" disabled={!canRun || busy !== null} onClick={() => void run("structural_set", "pdf")}>
            {busy === "structural_set" ? tx("busy") : tx("set")}
          </button>
          <Link className="button secondary" href="/workspace/cad">
            {tx("cad")}
          </Link>
        </div>
      )}
      {err ? (
        <p className="alert error" role="alert">
          {err}
        </p>
      ) : null}
      <p className="muted detailing-step-chat">
        {tx("chat")} <code dir={l === "fa" ? "rtl" : "ltr"}>{DETAILING_COMMAND[l]}</code>{" "}
        <Link className="link-button" href={projectId ? projectChatHref(projectId) : "/"}>
          {tx("openChat")}
        </Link>
      </p>
    </div>
  );
}

const GLANCE_TXT: Record<string, { en: string; fa: string }> = {
  label: { en: "Detailing", fa: "جزئیات‌سازی (دیتیلینگ)" },
  not_run: {
    en: "Not run yet: finish the design first, then ask for the rebar detailing.",
    fa: "هنوز اجرا نشده: ابتدا طراحی را کامل کنید، سپس جزئیات آرماتوربندی را بخواهید.",
  },
  ready: {
    en: "The design passed. Rebar detailing sheets are generated from the 3D frame design, not stored in this workflow package.",
    fa: "طراحی تأیید شد. نقشه‌های جزئیات آرماتوربندی از طراحی قاب سه‌بعدی ساخته می‌شوند و در این بستهٔ گردش‌کار ذخیره نشده‌اند.",
  },
  done: { en: "Reinforcement detail sheet (S-401) is part of this run.", fa: "برگهٔ جزئیات آرماتور (S-401) بخشی از این اجراست." },
  chat: { en: "Say in chat:", fa: "در گفتگو بگویید:" },
  cad: { en: "Open CAD page", fa: "باز کردن صفحهٔ CAD" },
  design: { en: "Open Design page", fa: "باز کردن صفحهٔ طراحی" },
};

/** One-line Detailing status for the Assistants page (stepper + dossier use the same glance value). */
export function DetailingGlanceNote({ value, projectId }: { value: string; projectId?: string | null }) {
  const { lang } = useUiLang();
  const g = (k: string) => GLANCE_TXT[k][lang];
  const status = detailingFromGlance(value);
  return (
    <div className="detailing-glance" data-testid="detailing-glance" data-status={status} dir={isRtl(lang) ? "rtl" : "ltr"} lang={lang}>
      <p className="muted">
        <strong>{g("label")}</strong>{" "}
        <span className={`detailing-badge detailing-${status}`}>{detailingStatusLabel(status, lang)}</span> {g(status)}
      </p>
      {status !== "not_run" ? (
        <p className="muted">
          {g("chat")} <code dir={lang === "fa" ? "rtl" : "ltr"}>{DETAILING_COMMAND[lang]}</code>{" "}
          <Link className="link-button" href={projectId ? projectChatHref(projectId) : "/"}>
            {lang === "fa" ? "گفتگو" : "Chat"}
          </Link>
          {" · "}
          <Link className="link-button" href="/workspace/design">
            {g("design")}
          </Link>
          {" · "}
          <Link className="link-button" href="/workspace/cad">
            {g("cad")}
          </Link>
        </p>
      ) : null}
    </div>
  );
}
