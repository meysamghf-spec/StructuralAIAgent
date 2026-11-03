"use client";

// Inline "all results in chat" sections for a 3D frame run: every member's forces for every load case / combo,
// per-member design, validation / approval status and a detailing (R-01..R-03) preview. Collapsible so the chat
// stays readable; RTL-aware; scrollable tables for 412px phones.
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";

import { SectionErrorBoundary } from "@/components/common/SectionErrorBoundary";
import type { Frame3dResults } from "@/lib/chat-types";
import { approvalStatus, filterRows, memberDesignRows, memberForceRows } from "@/lib/chat-full-results";
import { download, fetchDownload } from "@/lib/frame3d-downloads";
import { loadOptions, type ViewerData } from "@/lib/frame3d-viewer";

const DxfViewer = dynamic(() => import("@/components/cad/DxfViewer").then((m) => m.DxfViewer), { ssr: false });

type L = "en" | "fa";
const TX: Record<string, { en: string; fa: string }> = {
  forces: { en: "Member forces — all members", fa: "نیروهای اعضا — همه اعضا" },
  load: { en: "Load case / combination", fa: "حالت بار / ترکیب بار" },
  filter: { en: "Filter (member id, beam, column or storey)", fa: "فیلتر (شناسه عضو، beam، column یا شماره طبقه)" },
  member: { en: "Member", fa: "عضو" }, type: { en: "Type", fa: "نوع" }, storey: { en: "Storey", fa: "طبقه" },
  section: { en: "Section", fa: "مقطع" }, group: { en: "Group", fa: "گروه" }, bars: { en: "Bars", fa: "آرماتور" },
  status: { en: "Status", fa: "وضعیت" },
  design: { en: "Design per member (Mabhas 9)", fa: "طراحی هر عضو (مبحث ۹)" },
  approval: { en: "Validation & approval status", fa: "وضعیت اعتبارسنجی و تأیید" },
  pass: { en: "Pass", fa: "قبول (Pass)" }, fail: { en: "Fail", fa: "رد (Fail)" }, review: { en: "Needs review", fa: "نیاز به بررسی (Needs Review)" },
  aiOnly: { en: "AI suggestion only — final sign-off is by the engineer.", fa: "این فقط پیشنهاد هوش مصنوعی است؛ تأیید نهایی با مهندس است." },
  detailing: { en: "Detailing preview (R-01 beams, R-02 columns, R-03 bar schedule)", fa: "پیش‌نمایش دیتیلینگ (R-01 تیرها، R-02 ستون‌ها، R-03 جدول میلگرد)" },
  show: { en: "Show detailing here", fa: "نمایش دیتیلینگ در همین‌جا" },
  loading: { en: "Building…", fa: "در حال ساخت…" },
  dxf: { en: "Rebar DXF", fa: "DXF آرماتوربندی" }, pdf: { en: "Rebar PDF", fa: "PDF آرماتوربندی" }, set: { en: "Drawing set PDF", fa: "PDF نقشه‌های اجرایی" },
  units: { en: "N, V (kN) · M (kN·m) at ends i / j", fa: "N و V (kN) · M (kN·m) در دو سر i / j" },
  noRows: { en: "No member matches the filter.", fa: "عضوی با این فیلتر پیدا نشد." },
};
const tt = (l: L, k: string) => TX[k]?.[l] ?? k;
const f1 = (v: number | null) => (v === null ? "—" : v.toFixed(1));
const scroll = { maxHeight: 360, overflow: "auto" } as const;

export function MemberForcesSection({ viewer, lang }: { viewer: ViewerData; lang: L }) {
  const opts = useMemo(() => loadOptions(viewer), [viewer]);
  const [load, setLoad] = useState(opts[opts.length - 1] ?? "");
  const [q, setQ] = useState("");
  const rows = useMemo(() => filterRows(memberForceRows(viewer, load), q), [viewer, load, q]);
  if (!viewer.members.length || !opts.length) return null;
  return (
    <details className="engineering-result-block chat-full-section" data-testid="chat-member-forces">
      <summary className="engineering-result-label">{tt(lang, "forces")} ({viewer.members.length} · {opts.length} {lang === "fa" ? "حالت/ترکیب" : "cases/combos"})</summary>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "8px 0" }}>
        <label style={{ fontSize: 13 }}>
          {tt(lang, "load")}{" "}
          <select value={load} onChange={(e) => setLoad(e.target.value)} data-testid="chat-forces-load">
            {opts.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={tt(lang, "filter")} aria-label={tt(lang, "filter")} style={{ minWidth: 0, flex: "1 1 160px" }} />
      </div>
      <div style={scroll}>
        <table className="engineering-result-table" dir="ltr">
          <thead><tr><th>{tt(lang, "member")}</th><th>{tt(lang, "type")}</th><th>{tt(lang, "storey")}</th><th>{tt(lang, "section")}</th><th>N</th><th>V</th><th>M i</th><th>M j</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}><td>{r.id}</td><td>{r.type}</td><td>{r.storey}</td><td>{r.section}</td><td>{f1(r.N)}</td><td>{f1(r.Vi)}</td><td>{f1(r.Mi)}</td><td>{f1(r.Mj)}</td></tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <p className="muted">{tt(lang, "noRows")}</p> : null}
      </div>
      <p className="muted">{tt(lang, "units")}</p>
    </details>
  );
}

export function MemberDesignSection({ viewer, lang }: { viewer: ViewerData; lang: L }) {
  const [q, setQ] = useState("");
  const all = useMemo(() => memberDesignRows(viewer), [viewer]);
  const rows = useMemo(() => filterRows(all, q), [all, q]);
  if (!all.length) return null;
  const failing = all.filter((r) => r.dc !== null && r.dc > 1).length;
  return (
    <details className="engineering-result-block chat-full-section" data-testid="chat-member-design">
      <summary className="engineering-result-label">{tt(lang, "design")} ({all.length}{failing ? ` · ⚠ ${failing} D/C>1` : ""})</summary>
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={tt(lang, "filter")} aria-label={tt(lang, "filter")} style={{ margin: "8px 0", width: "100%" }} />
      <div style={scroll}>
        <table className="engineering-result-table" dir="ltr">
          <thead><tr><th>{tt(lang, "member")}</th><th>{tt(lang, "type")}</th><th>{tt(lang, "storey")}</th><th>{tt(lang, "section")}</th><th>{tt(lang, "group")}</th><th>{tt(lang, "bars")}</th><th>D/C</th><th>{tt(lang, "status")}</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td><td>{r.type}</td><td>{r.storey}</td><td>{r.section}</td><td>{r.group}</td><td style={{ whiteSpace: "nowrap" }}>{r.rebar}</td>
                <td style={{ color: r.dc !== null && r.dc > 1 ? "#b91c1c" : undefined }}>{r.dc === null ? "—" : r.dc.toFixed(2)}</td><td>{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function ApprovalSection({ results, lang }: { results: Frame3dResults; lang: L }) {
  const { state, reasons } = approvalStatus(results);
  const color = state === "pass" ? "#15803d" : state === "fail" ? "#b91c1c" : "#b45309";
  return (
    <div className="engineering-result-block" data-testid="chat-approval" data-state={state}>
      <p className="engineering-result-label">{tt(lang, "approval")}</p>
      <p><span className="chat-progress-badge" style={{ color, borderColor: color }}>{tt(lang, state)}</span></p>
      {reasons.length ? <ul className="muted">{reasons.map((r) => <li key={r} dir="ltr">{r}</li>)}</ul> : null}
      <p className="muted">{tt(lang, "aiOnly")}</p>
    </div>
  );
}

export function ChatDetailingPreview({ inputs, projectId, lang }: { inputs: Record<string, unknown>; projectId: string | null; lang: L }) {
  const [dxf, setDxf] = useState<{ text: string; filename: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const ctx = { inputs, projectId, saveToFiles: false };
  async function show() {
    setBusy("show"); setErr(null);
    try {
      const { blob, filename } = await fetchDownload({ kind: "drawing", name: "dxf_rebar" }, "dxf", ctx);
      setDxf({ text: await blob.text(), filename });
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  async function get(name: string, format: string) {
    setBusy(name + format); setErr(null);
    try { await download({ kind: "drawing", name }, format, { ...ctx, saveToFiles: Boolean(projectId) }); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  return (
    <details className="engineering-result-block chat-full-section" data-testid="chat-detailing-preview">
      <summary className="engineering-result-label">{tt(lang, "detailing")}</summary>
      <div className="button-row" style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "8px 0" }}>
        <button type="button" className="button" disabled={busy !== null} onClick={() => void show()}>{busy === "show" ? tt(lang, "loading") : tt(lang, "show")}</button>
        <button type="button" className="button secondary" disabled={busy !== null} onClick={() => void get("dxf_rebar", "dxf")}>{tt(lang, "dxf")}</button>
        <button type="button" className="button secondary" disabled={busy !== null} onClick={() => void get("dxf_rebar", "pdf")}>{tt(lang, "pdf")}</button>
        <button type="button" className="button secondary" disabled={busy !== null} onClick={() => void get("structural_set", "pdf")}>{tt(lang, "set")}</button>
      </div>
      {err ? <p className="alert error" role="alert">{err}</p> : null}
      {dxf ? (
        <SectionErrorBoundary label="Detailing">
          <div style={{ maxWidth: "100%", overflow: "hidden" }}><DxfViewer text={dxf.text} filename={dxf.filename} height={380} /></div>
        </SectionErrorBoundary>
      ) : null}
    </details>
  );
}
