"use client";

// Model section: import an ETABS .e2k, show the engineer review (everything not read / approximated),
// let the engineer edit or confirm, then analyse with SAIA's own frame3d engine.
import { useEffect, useMemo, useState } from "react";

import { useUiLang } from "@/hooks/useUiLang";
import { getCurrentProjectId, PROJECT_EVENT } from "@/lib/current-project";
import {
  analyzeImport, fmt, ImportApiError, latestImport, parseImport, precheckFile, reviewImport,
  type ImportIssue, type ImportState, type ReviewEdits,
} from "@/lib/model-import";

type SecEdit = { mode: "rect" | "props"; b: string; h: string; A: string; I33: string; I22: string; J: string };
const emptySec = (): SecEdit => ({ mode: "rect", b: "", h: "", A: "", I33: "", I22: "", J: "" });
const SECTION_CODES = new Set(["section_shape", "section_missing"]);

const TXT = {
  en: {
    title: "Import model (ETABS .e2k)", sub: "SAFE .f2k, SAP2000 .s2k and AutoCAD .dxf come in the next phase. DWG: save as DXF.",
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
    title: "ورود مدل (ETABS ‎.e2k)", sub: "SAFE ‎.f2k، SAP2000 ‎.s2k و AutoCAD ‎.dxf در فاز بعد اضافه می‌شوند. DWG را به DXF ذخیره کنید.",
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
  const patterns = useMemo(() => Object.keys(state?.model.load_patterns ?? {}), [state]);

  function buildEdits(): ReviewEdits {
    const sections: NonNullable<ReviewEdits["sections"]> = {};
    for (const [name, e] of Object.entries(secEdits)) {
      if (e.mode === "rect") {
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
    return edits;
  }

  async function onApply(): Promise<ImportState | null> {
    if (!state) return null;
    setBusy("review");
    try { const s = await reviewImport(state.model, buildEdits(), projectId); adopt(s); setLoad({ pattern: "", w: "", story: "" }); return s; }
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
              {(["nodes", "members", "sections", "supports", "load_patterns", "combos"] as const).map((k) => (
                <span key={k} style={{ background: "rgba(127,127,127,0.18)", borderRadius: 6, padding: "2px 8px" }}>{state.review.counts[k] ?? 0} {t[k]}</span>
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

          {state.analysis && <Results t={t} a={state.analysis} />}
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
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(90px, 1fr))", gap: 8, marginTop: 6 }}>
        {value.mode === "rect" ? [f("b", "b"), f("h", "h")] : [f("A", "A"), f("I33", "I33"), f("I22", "I22"), f("J", "J")]}
      </div>
    </div>
  );
}

function Results({ t, a }: { t: (typeof TXT)["en"] | (typeof TXT)["fa"]; a: NonNullable<ImportState["analysis"]> }) {
  const cell: React.CSSProperties = { padding: "4px 8px", borderTop: "1px solid rgba(127,127,127,0.25)", textAlign: "start", whiteSpace: "nowrap" };
  return (
    <div style={{ border: "1px solid rgba(127,127,127,0.4)", borderRadius: 10, padding: 12, marginTop: 12 }} data-testid="model-import-results">
      <h3 style={{ margin: "0 0 4px", fontSize: 16 }}>{t.results}</h3>
      <p style={{ fontSize: 12, color: "inherit", opacity: 0.8, margin: 0 }}>{t.engine}: <span dir="ltr">{a.engine}</span></p>
      <div style={{ overflowX: "auto", marginTop: 8 }}>
        <table style={{ borderCollapse: "collapse", fontSize: 13, width: "100%" }}>
          <thead><tr><th style={cell}></th><th style={cell}>{t.baseR}</th><th style={cell}>{t.maxD}</th></tr></thead>
          <tbody>{Object.entries(a.cases).map(([k, c]) => (
            <tr key={k}><td style={cell} dir="ltr">{k.replace(/^(pattern|combo):/, "")}</td><td style={cell} dir="ltr">{fmt(c.base_reaction_kN[2])}</td>
              <td style={cell} dir="ltr">{fmt(c.max_displacement_m * 1000)} <span style={{ opacity: 0.7 }}>({c.max_displacement_node})</span></td></tr>
          ))}</tbody>
        </table>
      </div>
      <h4 style={{ margin: "12px 0 4px", fontSize: 14 }}>{t.governing}</h4>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 13, width: "100%" }}>
          <thead><tr><th style={cell}>{t.member}</th><th style={cell}>N (kN)</th><th style={cell}>V (kN)</th><th style={cell}>M (kN·m)</th><th style={cell}>T (kN·m)</th></tr></thead>
          <tbody>{a.governing_members.slice(0, 10).map((m) => (
            <tr key={m.member}><td style={cell} dir="ltr">{m.member}</td>{[m.N, m.V, m.M, m.T].map((v, i) => <td key={i} style={cell} dir="ltr">{fmt(v)}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
      <ul style={{ fontSize: 12, color: "inherit", opacity: 0.8 }}>{a.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}
