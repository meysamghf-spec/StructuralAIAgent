"use client";

import { CostBreakdownTable } from "./CostBreakdownTable";
import { getCurrentProjectId } from "@/lib/current-project";
import {
  barsLabel, cancelJob, candLabel, fmtNum, getJob, isActive, OptApiError, parseSections, savingsPct, costChangeText, startJob,
  type OptJob, type SectionLists,
} from "@/lib/optimization-full";
import { useEffect, useRef, useState } from "react";

const PLACEHOLDER = "مثال: ستون‌ها 40x40، 40x60، 50x50؛ تیرها 30x40، 35x50\nمیلگرد 16 و 18 و 20 AIII، بتن C30\nستون‌های گوشه طبقات 1 تا 3: 50x50، 50x60\nتیرها IPE200 تا IPE360 (فولادی)";

/** Extra section on the Optimization page: full optimizer (rectangular / steel sections, member types, Mabhas 9 rebar, async job). */
export function FullOptimizationSection() {
  const [source, setSource] = useState<"frame" | "model">("frame");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [lists, setLists] = useState<SectionLists | null>(null);
  const [budget, setBudget] = useState("120");
  const [band, setBand] = useState("2");
  const [job, setJob] = useState<OptJob | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const fail = (e: unknown) => setError(e instanceof OptApiError ? e.fa : e instanceof Error ? e.message : "خطا");

  function poll(id: string) {
    timer.current = setTimeout(async () => {
      try {
        const j = await getJob(id);
        setJob(j);
        if (isActive(j)) poll(id);
      } catch (e) { fail(e); }
    }, 1500);
  }

  async function preview() {
    setError(""); setBusy(true);
    try { setLists(await parseSections(text, file)); } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function run() {
    setError(""); setBusy(true); setJob(null);
    try {
      const l = file ? await parseSections(text, file) : null;
      if (l) setLists(l);
      const j = await startJob({ source, project_id: getCurrentProjectId(), section_text: l ? "" : text, lists: l,
        options: { time_budget_s: Number(budget) || 120, storey_band: Number(band) || 2 } });
      setJob(j); poll(j.id);
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  const r = job?.result;
  const pct = Math.round((job?.progress?.fraction ?? 0) * 100);
  const save = r ? savingsPct(r) : null;

  return (
    <section className="card" dir="rtl" lang="fa" aria-labelledby="full-opt-title" style={{ textAlign: "right" }}>
      <h3 id="full-opt-title">بهینه‌سازی کامل مقاطع (نسخه جدید)</h3>
      <p className="subtitle">
        ستون مستطیلی، گروه‌بندی عضو به عضو و تیپ‌های تعریف‌شده، طراحی واقعی میلگرد مبحث ۹، مقاطع فولادی از کاتالوگ؛ اجرا در پس‌زمینه با نمایش پیشرفت.
        هر مقداری که ندهید فرض می‌شود و در نتیجه اعلام می‌شود.
      </p>

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

      {r ? (
        <div style={{ marginTop: 12 }}>
          <p>
            <strong>{r.feasible ? "طرح قابل‌قبول (همه کنترل‌ها برقرار)" : "هنوز طرحی که همه کنترل‌ها را برقرار کند یافت نشد؛ فهرست بزرگ‌تر یا زمان بیشتر بدهید."}</strong>
            {" "}هزینه: {fmtNum(r.cost)} {r.currency}{save != null ? ` (${costChangeText(r)})` : ""} — دریفت/مجاز: {fmtNum(r.drift_ratio, 2)}
          </p>
          <p style={{ fontSize: 13 }}>
            بتن {fmtNum(r.quantities.concrete_m3, 1)} m³ — میلگرد {fmtNum(r.quantities.rebar_kg)} kg — قالب {fmtNum(r.quantities.formwork_m2)} m²
            {r.quantities.steel_kg ? ` — فولاد ${fmtNum(r.quantities.steel_kg)} kg` : ""} — {fmtNum(r.evaluations)} تحلیل در {fmtNum(r.elapsed_s, 1)} ثانیه
          </p>
          <CostBreakdownTable r={r} />
          <div style={{ overflowX: "auto" }}>
            <table className="data-table" style={{ minWidth: 560, width: "100%" }}>
              <thead><tr><th>گروه</th><th>اعضا</th><th>مقطع</th><th>میلگرد</th><th>خاموت / تنگ</th><th>D/C</th></tr></thead>
              <tbody>
                {r.groups.map((g) => (
                  <tr key={g.group}>
                    <td>{g.label}</td><td>{fmtNum(g.members)}</td><td dir="ltr">{g.section}</td>
                    <td dir="ltr">{barsLabel(g)}</td><td dir="ltr" style={{ fontSize: 12 }}>{g.stirrups ?? g.ties ?? "—"}</td>
                    <td style={{ color: g.DC > 1 ? "#b91c1c" : undefined }}>{fmtNum(g.DC, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details style={{ marginTop: 8 }}>
            <summary>فرض‌ها</summary>
            <ul>{[...r.assumptions, ...(r.assumed_inputs ?? [])].map((a) => <li key={a}>{a}</li>)}</ul>
          </details>
        </div>
      ) : null}
    </section>
  );
}
