"use client";

// Model section: import an ETABS .e2k / SAP2000 .s2k / SAFE .f2k / AutoCAD .dxf, show the engineer review (everything not read / approximated),
// let the engineer edit or confirm, then analyse with SAIA's own frame3d engine.
import { useEffect, useMemo, useState } from "react";

import { useUiLang } from "@/hooks/useUiLang";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";
import {
  analyzeImport, ImportApiError, latestImport, parseImport, precheckFile, reviewImport, SOILS, SYSTEMS, ZONES,
  type ImportIssue, type ImportState, type ReviewEdits,
} from "@/lib/model-import";

import { ImportResults } from "./ImportResults";

type SecEdit = { mode: "rect" | "props" | "catalog"; catalog: string; b: string; h: string; A: string; I33: string; I22: string; J: string };
const emptySec = (): SecEdit => ({ mode: "rect", catalog: "", b: "", h: "", A: "", I33: "", I22: "", J: "" });
const SECTION_CODES = new Set(["section_shape", "section_missing"]);

const TXT = {
  en: {
    title: "Import model (ETABS .e2k · SAP2000 .s2k · SAFE .f2k · AutoCAD .dxf)", sub: "Slabs, diaphragms, releases, P-Delta, modal/response spectrum and 2800 seismic/wind are analysed by the SAIA engine. DWG: save as DXF.",
    catalog: "Steel catalog (e.g. IPE300, HE200B, BOX200x10)", settings: "Analysis settings", seismicGen: "2800 seismic (generated if the file has none)",
    zone: "Zone", soil: "Soil type", importance: "Importance I", system: "Lateral system", wind: "Wind (Mabhas 6)", windOn: "Generate wind loads", V: "Basic wind speed (km/h)",
    pdelta: "P-Delta", diaph: "Rigid floor diaphragms", floorLoad: "Floor (area) load on slabs (optional)", q: "q (kN/m², down)",
    dxfTitle: "DXF plan → frame", storeys: "Storeys", height: "Storey height (m)", colSec: "Column section", slabs: "slabs",
    choose: "Choose file", parsing: "Reading…", counts: "Read from file", review: "Engineer review",
    reviewHelp: "Items SAIA could not read or had to approximate. Fix blocking items and confirm the rest before analysis.",
    blocking: "Blocking", approximated: "Approximated", ignored: "Not read", assumptions: "Assumptions (SI units: kN, m)",
    confirm: "Confirm", confirmAll: "Confirm all non-blocking items", rect: "Rectangle b × h (mm)", props: "A (cm²), I33, I22, J (cm⁴)",
    extraLoad: "Add gravity line load on beams (optional)", pattern: "Load pattern", w: "w (kN/m, down)", story: "Story (blank = all)",
    apply: "Apply review", analyze: "Analyse with SAIA engine", analyzing: "Analysing…", results: "Analysis results",
    engine: "Engine", baseR: "Base reaction Fz (kN)", maxD: "Max displacement (mm)", node: "at node", governing: "Governing members (envelope)",
    member: "Member", noProject: "No project selected — results will not be saved to a project.", ready: "Ready for analysis", remaining: "unconfirmed",
    nodes: "nodes", members: "members", sections: "sections", supports: "supports", load_patterns: "load patterns", combos: "combinations",
  },
  fa: {
    title: "ورود مدل (ETABS ‎.e2k · SAP2000 ‎.s2k · SAFE ‎.f2k · AutoCAD ‎.dxf)", sub: "دال‌ها، دیافراگم، آزادسازی انتها، P-Delta، تحلیل مودال/طیفی و زلزله و باد ۲۸۰۰ با موتور SAIA تحلیل می‌شوند. DWG را به DXF ذخیره کنید.",
    catalog: "کاتالوگ فولادی (مثلاً IPE300، HE200B، BOX200x10)", settings: "تنظیمات تحلیل", seismicGen: "زلزله ۲۸۰۰ (اگر در فایل نباشد تولید می‌شود)",
    zone: "پهنه", soil: "نوع خاک", importance: "ضریب اهمیت I", system: "سیستم باربر جانبی", wind: "باد (مبحث ۶)", windOn: "تولید بار باد", V: "سرعت مبنای باد (km/h)",
    pdelta: "اثر P-Delta", diaph: "دیافراگم صلب طبقات", floorLoad: "بار سطحی روی دال‌ها (اختیاری)", q: "q (kN/m²، رو به پایین)",
    dxfTitle: "پلان DXF ← قاب", storeys: "تعداد طبقات", height: "ارتفاع طبقه (m)", colSec: "مقطع ستون", slabs: "دال",
    choose: "انتخاب فایل", parsing: "در حال خواندن…", counts: "خوانده‌شده از فایل", review: "بازبینی مهندس",
    reviewHelp: "مواردی که SAIA نتوانست بخواند یا تقریب زد. موارد مسدودکننده را اصلاح و بقیه را پیش از تحلیل تأیید کنید.",
    blocking: "مسدودکننده", approximated: "تقریبی", ignored: "خوانده نشد", assumptions: "فرض‌ها (واحد SI: کیلونیوتن، متر)",
    confirm: "تأیید", confirmAll: "تأیید همه‌ی موارد غیرمسدودکننده", rect: "مستطیل b × h (میلی‌متر)", props: "A (cm²)، I33، I22، J (cm⁴)",
    extraLoad: "افزودن بار خطی ثقلی روی تیرها (اختیاری)", pattern: "الگوی بار", w: "w (kN/m، رو به پایین)", story: "طبقه (خالی = همه)",
    apply: "اعمال بازبینی", analyze: "تحلیل با موتور SAIA", analyzing: "در حال تحلیل…", results: "نتایج تحلیل",
    engine: "موتور", baseR: "عکس‌العمل پایه Fz (kN)", maxD: "بیشینه تغییرمکان (mm)", node: "در گره", governing: "اعضای بحرانی (پوش)",
    member: "عضو", noProject: "پروژه‌ای انتخاب نشده — نتایج در پروژه ذخیره نمی‌شود.", ready: "آماده‌ی تحلیل", remaining: "تأییدنشده",
    nodes: "گره", members: "عضو", sections: "مقطع", supports: "تکیه‌گاه", load_patterns: "الگوی بار", combos: "ترکیب بار",
  },
} as const;

export function ModelImportPanel() {
  const { lang } = useUiLang();
  const fa = lang === "fa";
  const t = TXT[fa ? "fa" : "en"];
  const [projectId, setProjectId] = useState<string | null>(null);
  const [state, setState] = useState<ImportState | null>(null);
  const [busy, setBusy] = useState<"" | "parse" | "review" | "analyze">("");
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set());
  const [secEdits, setSecEdits] = useState<Record<string, SecEdit>>({});
  const [load, setLoad] = useState({ pattern: "", w: "", story: "" });
  const [area, setArea] = useState({ pattern: "", q: "", story: "" });
  const [opts, setOpts] = useState({ zone: "HIGH", soil: "II", importance: "1", system: "RC_IMF", wind: false, V: "100", pdelta: true, diaph: true });
  const [dxf, setDxf] = useState({ storeys: "3", height: "3.2", column: "" });

  useEffect(() => {
    const sync = () => setProjectId(getCurrentProjectId());
    sync();
    window.addEventListener(PROJECT_EVENT, sync);
    return () => window.removeEventListener(PROJECT_EVENT, sync);
  }, []);
  useEffect(() => {
    if (!projectId) return;
    latestImport(projectId).then((s) => s && adopt(s)).catch(() => undefined);
  }, [projectId]);

  function adopt(s: ImportState) {
    setState(s);
    setConfirmed(new Set(s.review.issues.filter((i) => i.confirmed).map((i) => i.id)));
    setError(null);
  }
  function fail(e: unknown) {
    setError(e instanceof ImportApiError ? (fa ? e.fa : e.en) : String((e as Error)?.message ?? e));
  }

  async function onFile(f: File | undefined) {
    if (!f) return;
    const pre = precheckFile(f.name);
    if (pre) { setError(fa ? pre.fa : pre.en); return; }
    setBusy("parse"); setError(null);
    try { adopt(await parseImport(f, projectId)); setSecEdits({}); } catch (e) { fail(e); } finally { setBusy(""); }
  }

  const issues = state?.review.issues ?? [];

  const nonBlocking = issues.filter((i) => i.severity !== "blocking");
  const unconfirmed = nonBlocking.filter((i) => !confirmed.has(i.id)).length;
  const isDxfPlan = !!(state?.model as Record<string, unknown> | undefined)?.dxf_plan;
  const patterns = useMemo(() => Object.keys(state?.model.load_patterns ?? {}), [state]);

  function buildEdits(): ReviewEdits {
    const sections: NonNullable<ReviewEdits["sections"]> = {};
    for (const [name, e] of Object.entries(secEdits)) {
      if (e.mode === "catalog") {
        if (e.catalog.trim()) sections[name] = { catalog: e.catalog.trim().toUpperCase() };
      } else if (e.mode === "rect") {
        const b = Number(e.b), h = Number(e.h);
        if (b > 0 && h > 0) sections[name] = { b: b / 1000, h: h / 1000 };
      } else {
        const A = Number(e.A), I33 = Number(e.I33), I22 = Number(e.I22), J = Number(e.J);
        if (A > 0 && I33 > 0 && I22 > 0 && J > 0) sections[name] = { A: A * 1e-4, I33: I33 * 1e-8, I22: I22 * 1e-8, J: J * 1e-8 };
      }
    }
    const edits: ReviewEdits = { sections, confirmed: [...confirmed] };
    const w = Number(load.w);
    if (load.pattern && w) edits.beam_line_loads = [{ pattern: load.pattern, w, ...(load.story ? { story: load.story } : {}) }];
    const q = Number(area.q);
    if (area.pattern && q) edits.area_loads = [{ pattern: area.pattern, q, ...(area.story ? { story: area.story } : {}) }];
    edits.seismic = { zone: opts.zone, soil: opts.soil, importance: Number(opts.importance) || 1, system: opts.system };
    edits.wind = { enabled: opts.wind, V_kmh: Number(opts.V) || 100 };
    edits.pdelta = opts.pdelta;
    edits.rigid_diaphragms = opts.diaph;
    if (isDxfPlan) edits.dxf = { storeys: Math.max(1, Math.round(Number(dxf.storeys) || 1)), height: Number(dxf.height) || 3.2, ...(dxf.column.trim() ? { column_section: dxf.column.trim().toUpperCase() } : {}) };
    return edits;
  }

  async function onApply(): Promise<ImportState | null> {
    if (!state) return null;
    setBusy("review");
    try { const s = await reviewImport(state.model, buildEdits(), projectId); adopt(s); setLoad({ pattern: "", w: "", story: "" }); setArea({ pattern: "", q: "", story: "" }); return s; }
    catch (e) { fail(e); return null; } finally { setBusy(""); }
  }
  async function onAnalyze() {
    const s = await onApply();
    if (!s || !s.review.can_analyze || s.review.requires_confirmation.length) return;
    setBusy("analyze");
    try { adopt(await analyzeImport(s.model, projectId)); } catch (e) { fail(e); } finally { setBusy(""); }
  }

  const sevLabel = (i: ImportIssue) => (i.severity === "blocking" ? t.blocking : i.severity === "approximated" ? t.approximated : t.ignored);
  const sevColor = (i: ImportIssue) => (i.severity === "blocking" ? "#f04438" : i.severity === "approximated" ? "#f79009" : "#98a2b3");
  const box: React.CSSProperties = { border: "1px solid var(--border, rgba(127,127,127,0.4))", borderRadius: 10, padding: 12, marginTop: 12, background: "rgba(127,127,127,0.06)" };
  const input: React.CSSProperties = { width: "100%", minWidth: 0, padding: "6px 8px", border: "1px solid rgba(127,127,127,0.5)", borderRadius: 6, fontSize: 14, background: "transparent", color: "inherit" };
  const btn: React.CSSProperties = { padding: "8px 14px", borderRadius: 8, border: "1px solid #1d4ed8", background: "#1d4ed8", color: "#fff", fontSize: 14, cursor: "pointer" };

  return (
    <section dir={fa ? "rtl" : "ltr"} data-testid="model-import-panel" style={{ ...box, marginTop: 0, marginBottom: 16, maxWidth: "100%", overflowX: "hidden" }}>
      <h2 style={{ margin: 0, fontSize: 18 }}>{t.title}</h2>
      <p style={{ margin: "4px 0 10px", color: "inherit", opacity: 0.8, fontSize: 13 }}>{t.sub}</p>
      {!projectId && <p style={{ fontSize: 12, color: "#f79009" }}>{t.noProject}</p>}
      <label style={{ ...btn, display: "inline-block" }}>
        {busy === "parse" ? t.parsing : t.choose}
        <input type="file" accept=".e2k,.s2k,.f2k,.dxf,.dwg" hidden data-testid="model-import-file" onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = ""; }} />
      </label>
      {error && <p role="alert" style={{ color: "#f04438", fontSize: 14 }}>{error}</p>}

      {state && (
        <>
          <div style={box}>
            <strong>{t.counts}: </strong><span dir="ltr">{state.model.filename}</span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8, fontSize: 13 }}>
              {(["nodes", "members", "slabs", "sections", "supports", "load_patterns", "combos"] as const).map((k) => (
                <span key={k} style={{ background: "rgba(127,127,127,0.18)", borderRadius: 6, padding: "2px 8px" }}><bdi dir="ltr">{state.review.counts[k] ?? 0}</bdi> {t[k]}</span>
              ))}
            </div>
          </div>

          <div style={box} data-testid="model-import-review">
            <h3 style={{ margin: "0 0 4px", fontSize: 16 }}>{t.review}</h3>
            <p style={{ margin: "0 0 8px", fontSize: 13, color: "inherit", opacity: 0.8 }}>{t.reviewHelp}</p>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {issues.map((i) => (
                <li key={i.id} style={{ borderTop: "1px solid rgba(127,127,127,0.25)", padding: "8px 0", display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
                  <span style={{ color: sevColor(i), fontWeight: 600, fontSize: 12, minWidth: 80 }}>{sevLabel(i)}</span>
                  <span style={{ flex: "1 1 220px", fontSize: 14, overflowWrap: "anywhere" }}>{fa ? i.fa : i.en}{i.count > 1 ? ` (×${i.count})` : ""}</span>
                  {i.severity !== "blocking" && (
                    <label style={{ fontSize: 13, whiteSpace: "nowrap" }}>
                      <input type="checkbox" checked={confirmed.has(i.id)} onChange={(e) => {
                        const n = new Set(confirmed); if (e.target.checked) n.add(i.id); else n.delete(i.id); setConfirmed(n);
                      }} /> {t.confirm}
                    </label>
                  )}
                  {i.severity === "blocking" && SECTION_CODES.has(i.code) && (
                    <SectionEditor t={t} value={secEdits[i.item] ?? emptySec()} input={input}
                      onChange={(v) => setSecEdits({ ...secEdits, [i.item]: v })} />
                  )}
                </li>
              ))}
            </ul>
            {nonBlocking.length > 0 && (
              <button type="button" style={{ ...btn, background: "transparent", color: "#3b82f6", marginTop: 8 }} onClick={() => setConfirmed(new Set(nonBlocking.map((i) => i.id)))}>{t.confirmAll}</button>
            )}
            {isDxfPlan && (
              <div style={{ ...box, background: "transparent" }} data-testid="model-import-dxf">
                <strong style={{ fontSize: 14 }}>{t.dxfTitle}</strong>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8, marginTop: 6 }}>
                  <label style={{ fontSize: 12 }}>{t.storeys}<input style={input} inputMode="numeric" dir="ltr" value={dxf.storeys} onChange={(e) => setDxf({ ...dxf, storeys: e.target.value })} /></label>
                  <label style={{ fontSize: 12 }}>{t.height}<input style={input} inputMode="decimal" dir="ltr" value={dxf.height} onChange={(e) => setDxf({ ...dxf, height: e.target.value })} /></label>
                  <label style={{ fontSize: 12 }}>{t.colSec}<input style={input} dir="ltr" placeholder="COLUMN / HE200B" value={dxf.column} onChange={(e) => setDxf({ ...dxf, column: e.target.value })} /></label>
                </div>
              </div>
            )}
            <details style={{ marginTop: 10 }} data-testid="model-import-settings">
              <summary style={{ fontSize: 14, cursor: "pointer" }}>{t.settings}</summary>
              <p style={{ fontSize: 12, margin: "8px 0 4px", opacity: 0.85 }}>{t.seismicGen}</p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8 }}>
                <label style={{ fontSize: 12 }}>{t.zone}<select style={input} value={opts.zone} onChange={(e) => setOpts({ ...opts, zone: e.target.value })}>{ZONES.map((z) => <option key={z}>{z}</option>)}</select></label>
                <label style={{ fontSize: 12 }}>{t.soil}<select style={input} value={opts.soil} onChange={(e) => setOpts({ ...opts, soil: e.target.value })}>{SOILS.map((z) => <option key={z}>{z}</option>)}</select></label>
                <label style={{ fontSize: 12 }}>{t.importance}<select style={input} value={opts.importance} onChange={(e) => setOpts({ ...opts, importance: e.target.value })}>{["0.8", "1", "1.2", "1.4"].map((z) => <option key={z}>{z}</option>)}</select></label>
                <label style={{ fontSize: 12 }}>{t.system}<select style={input} value={opts.system} onChange={(e) => setOpts({ ...opts, system: e.target.value })}>{SYSTEMS.map((z) => <option key={z}>{z}</option>)}</select></label>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 10, fontSize: 13, alignItems: "center" }}>
                <label><input type="checkbox" checked={opts.wind} onChange={(e) => setOpts({ ...opts, wind: e.target.checked })} /> {t.windOn}</label>
                {opts.wind && <label style={{ fontSize: 12 }}>{t.V} <input style={{ ...input, width: 80 }} inputMode="decimal" dir="ltr" value={opts.V} onChange={(e) => setOpts({ ...opts, V: e.target.value })} /></label>}
                <label><input type="checkbox" checked={opts.pdelta} onChange={(e) => setOpts({ ...opts, pdelta: e.target.checked })} /> {t.pdelta}</label>
                <label><input type="checkbox" checked={opts.diaph} onChange={(e) => setOpts({ ...opts, diaph: e.target.checked })} /> {t.diaph}</label>
              </div>
            </details>
            <details style={{ marginTop: 10 }}>
              <summary style={{ fontSize: 14, cursor: "pointer" }}>{t.floorLoad}</summary>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8, marginTop: 8 }}>
                <label style={{ fontSize: 12 }}>{t.pattern}
                  <select style={input} value={area.pattern} onChange={(e) => setArea({ ...area, pattern: e.target.value })}>
                    <option value="">—</option>{patterns.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select></label>
                <label style={{ fontSize: 12 }}>{t.q}<input style={input} inputMode="decimal" dir="ltr" value={area.q} onChange={(e) => setArea({ ...area, q: e.target.value })} /></label>
                <label style={{ fontSize: 12 }}>{t.story}<input style={input} dir="ltr" value={area.story} onChange={(e) => setArea({ ...area, story: e.target.value })} /></label>
              </div>
            </details>
            <details style={{ marginTop: 10 }}>
              <summary style={{ fontSize: 14, cursor: "pointer" }}>{t.extraLoad}</summary>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8, marginTop: 8 }}>
                <label style={{ fontSize: 12 }}>{t.pattern}
                  <select style={input} value={load.pattern} onChange={(e) => setLoad({ ...load, pattern: e.target.value })}>
                    <option value="">—</option>{patterns.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select></label>
                <label style={{ fontSize: 12 }}>{t.w}<input style={input} inputMode="decimal" dir="ltr" value={load.w} onChange={(e) => setLoad({ ...load, w: e.target.value })} /></label>
                <label style={{ fontSize: 12 }}>{t.story}<input style={input} dir="ltr" value={load.story} onChange={(e) => setLoad({ ...load, story: e.target.value })} /></label>
              </div>
            </details>
            <details style={{ marginTop: 10 }}>
              <summary style={{ fontSize: 14, cursor: "pointer" }}>{t.assumptions} ({state.review.assumptions.length})</summary>
              <ul style={{ fontSize: 13 }}>{state.review.assumptions.map((a) => <li key={a.en}>{fa ? a.fa : a.en}</li>)}</ul>
            </details>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12, alignItems: "center" }}>
              <button type="button" style={{ ...btn, background: "transparent", color: "#3b82f6" }} disabled={!!busy} onClick={() => void onApply()}>{t.apply}</button>
              <button type="button" style={{ ...btn, opacity: busy ? 0.6 : 1 }} disabled={!!busy} data-testid="model-import-analyze" onClick={() => void onAnalyze()}>{busy === "analyze" ? t.analyzing : t.analyze}</button>
              <span style={{ fontSize: 13, color: state.review.blocking || unconfirmed ? "#f79009" : "#12b76a" }}>
                {state.review.blocking || unconfirmed ? `${state.review.blocking} ${t.blocking} · ${unconfirmed} ${t.remaining}` : t.ready}
              </span>
            </div>
          </div>

          {state.analysis && <ImportResults a={state.analysis} fa={fa} />}
        </>
      )}
    </section>
  );
}

function SectionEditor({ t, value, onChange, input }: { t: (typeof TXT)["en"] | (typeof TXT)["fa"]; value: SecEdit; onChange: (v: SecEdit) => void; input: React.CSSProperties }) {
  const f = (k: keyof SecEdit, label: string) => (
    <label key={k} style={{ fontSize: 12 }}>{label}<input style={input} inputMode="decimal" dir="ltr" value={value[k]} onChange={(e) => onChange({ ...value, [k]: e.target.value })} /></label>
  );
  return (
    <div style={{ flexBasis: "100%" }}>
      <div style={{ display: "flex", gap: 12, fontSize: 13, flexWrap: "wrap" }}>
        <label><input type="radio" checked={value.mode === "rect"} onChange={() => onChange({ ...value, mode: "rect" })} /> {t.rect}</label>
        <label><input type="radio" checked={value.mode === "props"} onChange={() => onChange({ ...value, mode: "props" })} /> {t.props}</label>
        <label><input type="radio" checked={value.mode === "catalog"} onChange={() => onChange({ ...value, mode: "catalog" })} /> {t.catalog}</label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(90px, 1fr))", gap: 8, marginTop: 6 }}>
        {value.mode === "catalog" ? [f("catalog", "IPE / HEA / HEB / UNP / BOX / PIPE")] : value.mode === "rect" ? [f("b", "b"), f("h", "h")] : [f("A", "A"), f("I33", "I33"), f("I22", "I22"), f("J", "J")]}
      </div>
    </div>
  );
}
