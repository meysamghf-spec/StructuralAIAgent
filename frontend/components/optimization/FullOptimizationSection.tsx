"use client";

import { OptResultView } from "./OptResultView";
import Link from "next/link";

import { useActiveProjectId } from "@/hooks/useActiveProjectId";
import { applyOptimizedFrame } from "@/lib/optimized-frame";
import {
  cancelJob, candLabel, fmtNum, getJob, isActive, OptApiError, parseSections, startJob,
  getProjectFrame, type OptJob, type ProjectFrame, type SectionLists,
} from "@/lib/optimization-full";
import { useEffect, useRef, useState } from "react";

const PLACEHOLDER = "مثال: ستون‌ها 40x40، 40x60، 50x50؛ تیرها 30x40، 35x50\nمیلگرد 16 و 18 و 20 AIII، بتن C30\nستون‌های گوشه طبقات 1 تا 3: 50x50، 50x60\nتیرها IPE200 تا IPE360 (فولادی)";

/** Extra section on the Optimization page: full optimizer (rectangular / steel sections, member types, Mabhas 9 rebar, async job). */
export function FullOptimizationSection({ projectId: projectIdProp }: { projectId?: string | null } = {}) {
  const activeId = useActiveProjectId();
  const projectId = projectIdProp !== undefined ? projectIdProp : activeId;
  const jobProject = useRef<string | null>(null);
  const [frame, setFrame] = useState<ProjectFrame | null>(null);
  const [source, setSource] = useState<"frame" | "model">("frame");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [lists, setLists] = useState<SectionLists | null>(null);
  const [budget, setBudget] = useState("120");
  const [band, setBand] = useState("2");
  const [job, setJob] = useState<OptJob | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [appliedFrame, setAppliedFrame] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  // Project switched: stop following the previous project's job and show this project's frame inputs.
  useEffect(() => {
    let live = true;
    if (timer.current) clearTimeout(timer.current);
    setJob(null); setAppliedFrame(false); setError(""); setFrame(null);
    if (projectId) getProjectFrame(projectId).then((f) => { if (live) setFrame(f); }).catch(() => undefined);
    return () => { live = false; };
  }, [projectId]);

  const fail = (e: unknown) => setError(e instanceof OptApiError ? e.fa : e instanceof Error ? e.message : "خطا");

  function poll(id: string) {
    timer.current = setTimeout(async () => {
      try {
        const j = await getJob(id);
        setJob(j);
        if (isActive(j)) poll(id);
        else applyJobFrame(j);
      } catch (e) { fail(e); }
    }, 1500);
  }

  // Finished frame optimization → the re-analysed optimized frame becomes the project's model (toggle on the Model page).
  function applyJobFrame(j: OptJob) {
    const res = j.result as (OptJob["result"] & { optimized_frame3d?: { inputs?: Record<string, unknown> }; original_inputs?: unknown }) | null;
    const opt = res?.optimized_frame3d;
    if (j.status !== "done" || !opt?.inputs) return;
    applyOptimizedFrame(jobProject.current, { inputs: opt.inputs, payload: opt, original: res?.original_inputs, marker: `job|${j.id}` });
    setAppliedFrame(true);
  }

  async function preview() {
    setError(""); setBusy(true);
    try { setLists(await parseSections(text, file)); } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function run() {
    setError(""); setBusy(true); setJob(null); setAppliedFrame(false);
    try {
      const l = file ? await parseSections(text, file) : null;
      if (l) setLists(l);
      jobProject.current = projectId;
      const j = await startJob({ source, project_id: projectId, section_text: l ? "" : text, lists: l,
        options: { time_budget_s: Number(budget) || 120, storey_band: Number(band) || 2 } });
      setJob(j); poll(j.id);
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  const r = job?.result;
  const pct = Math.round((job?.progress?.fraction ?? 0) * 100);

  return (
    <section className="card" dir="rtl" lang="fa" aria-labelledby="full-opt-title" style={{ textAlign: "right" }}>
      <h3 id="full-opt-title">بهینه‌سازی کامل مقاطع (نسخه جدید)</h3>
      <p className="subtitle">
        ستون مستطیلی، گروه‌بندی عضو به عضو و تیپ‌های تعریف‌شده، طراحی واقعی میلگرد مبحث ۹، مقاطع فولادی از کاتالوگ؛ اجرا در پس‌زمینه با نمایش پیشرفت.
        هر مقداری که ندهید فرض می‌شود و در نتیجه اعلام می‌شود.
      </p>
      {projectId ? (
        <p className="muted" data-testid="full-opt-project-frame" role="status">
          {frame
            ? `ورودی پروژه فعال (${frame.chat_title ? `گفتگوی «${frame.chat_title}»` : frame.label?.fa ?? frame.source}): ${frame.inputs.storeys ?? "?"} طبقه، ${frame.inputs.bays_x ?? "?"}×${frame.inputs.bays_y ?? "?"} دهانه، ${frame.inputs.bay_x_m ?? "?"}×${frame.inputs.bay_y_m ?? "?"} متر`
            : "در حال خواندن قاب پروژه فعال…"}
        </p>
      ) : null}
      {projectId && frame?.limit_warning ? (
        <p className="field-hint" data-testid="full-opt-limit-warning" role="alert">{frame.limit_warning.fa}</p>
      ) : null}
      {projectId ? null : (
        <p className="field-hint">پروژه‌ای انتخاب نشده است.</p>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "end" }}>
        <label>منبع مدل{" "}
          <select value={source} onChange={(e) => setSource(e.target.value as "frame" | "model")}>
            <option value="frame">قاب صفحه مدل / گفتگو</option>
            <option value="model">مدل واردشده (ETABS/SAP/DXF)</option>
          </select>
        </label>
        <label>زمان مجاز (ثانیه){" "}
          <input type="number" min={10} max={900} value={budget} onChange={(e) => setBudget(e.target.value)} style={{ width: 90 }} />
        </label>
        <label>طبقات هر گروه{" "}
          <input type="number" min={1} max={20} value={band} onChange={(e) => setBand(e.target.value)} style={{ width: 70 }} />
        </label>
      </div>

      <label style={{ display: "block", marginTop: 12 }}>فهرست مقاطع، میلگردها، مصالح و تیپ اعضا (اختیاری)
        <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={PLACEHOLDER} rows={4}
          style={{ width: "100%", boxSizing: "border-box", direction: "rtl" }} />
      </label>
      <label style={{ display: "block", marginTop: 8 }}>یا فایل PDF / Excel / CSV{" "}
        <input type="file" accept=".pdf,.xlsx,.xlsm,.csv,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
        <button type="button" className="button secondary" onClick={preview} disabled={busy || (!text.trim() && !file)}>بررسی فهرست</button>
        <button type="button" className="button" onClick={run} disabled={busy || isActive(job)}>شروع بهینه‌سازی</button>
        {isActive(job) ? (
          <button type="button" className="button secondary" onClick={() => job && cancelJob(job.id).catch(fail)}>توقف</button>
        ) : null}
      </div>

      {error ? <p role="alert" style={{ color: "#b91c1c" }}>{error}</p> : null}

      {lists ? (
        <div style={{ marginTop: 12, fontSize: 14 }}>
          <strong>برداشت از فهرست:</strong>
          <ul>
            <li>ستون‌ها: {lists.columns.map(candLabel).join("، ") || "پیش‌فرض"}</li>
            <li>تیرها: {lists.beams.map(candLabel).join("، ") || "پیش‌فرض"}</li>
            {lists.braces.length ? <li>مهاربندها: {lists.braces.map(candLabel).join("، ")}</li> : null}
            <li>میلگردها: {lists.rebar_mm.length ? lists.rebar_mm.map((d) => `Φ${d}`).join("، ") : "پیش‌فرض Φ12–Φ32"}</li>
            {lists.member_types.map((t) => <li key={t.name}>تیپ «{t.name}»: {t.candidates.map(candLabel).join("، ")}</li>)}
          </ul>
        </div>
      ) : null}

      {job ? (
        <div style={{ marginTop: 12 }} aria-live="polite">
          <progress value={pct} max={100} style={{ width: "100%" }} />
          <p style={{ fontSize: 14 }}>
            وضعیت: {({ queued: "در صف", running: "در حال اجرا", done: "پایان یافت", cancelled: "متوقف شد", error: "خطا" } as const)[job.status]}
            {" — "}{pct}٪ — ارزیابی‌ها: {fmtNum(job.progress?.evals)}
            {job.progress?.best_cost ? <> — بهترین هزینه: {fmtNum(job.progress.best_cost)} تومان</> : null}
          </p>
          {job.error ? <p role="alert" style={{ color: "#b91c1c" }}>{job.error}</p> : null}
        </div>
      ) : null}

      {r ? <OptResultView r={r} /> : null}
      {appliedFrame ? (
        <p className="muted" data-testid="opt-frame-applied">
          مقاطع بهینه در مدل پروژه اعمال و تحلیل مجدد شد. <Link href="/workspace/model">مشاهده در صفحه مدل</Link>
        </p>
      ) : null}
    </section>
  );
}
