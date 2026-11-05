"use client";

// Member inspector (additive panel): forces per case/combo, envelope, governing combo, elastic stresses and strains.
import { useMemo, useState } from "react";
import type { ViewerData, ViewerMember } from "@/lib/frame3d-viewer";
import { FORCE_KEYS, envelope, governing, inspectorRows, sectionProps, stresses } from "@/lib/member-inspector";

const f1 = (x: number) => (Number.isFinite(x) ? x.toFixed(1) : "—");
const f2 = (x: number) => (Number.isFinite(x) ? x.toFixed(2) : "—");
const fe = (x: number) => (Number.isFinite(x) ? (x * 1e6).toFixed(0) : "—");
const scroll = { overflowX: "auto" as const, maxWidth: "100%" };
const cell = { whiteSpace: "nowrap" as const, padding: "2px 6px", textAlign: "right" as const };

export default function MemberInspector({ data, member, load, fa }: { data: ViewerData; member: ViewerMember; load: string; fa: boolean }) {
  const { rows, full } = useMemo(() => inspectorRows(data, member.id), [data, member.id]);
  const sec = useMemo(() => sectionProps(data, member), [data, member]);
  const env = useMemo(() => envelope(rows), [rows]);
  const gov = useMemo(() => governing(rows, sec), [rows, sec]);
  const [chosen, setChosen] = useState<string | null>(null);
  const cur = chosen ?? gov ?? load;
  const row = rows.find((r) => r.load === cur) ?? rows[0];
  const L = (fa_: string, en: string) => (fa ? `${fa_} (${en})` : en);
  if (!rows.length) return null;
  const ends = row ? ([["i", stresses(row.i, sec)], ["j", stresses(row.j, sec)]] as const) : [];
  return (
    <section className="v3d-inspector" data-testid="member-inspector" dir={fa ? "rtl" : "ltr"} style={{ marginTop: 8, borderTop: "1px solid #3a4a5e", paddingTop: 6 }}>
      <p className="v3d-h">{L("بازرس عضو", "Member inspector")} · <span dir="ltr">{member.id}</span></p>
      <p style={{ fontSize: 12, margin: "2px 0" }} dir="ltr">
        {member.section} · b×h = {(sec.b * 1000).toFixed(0)}×{(sec.h * 1000).toFixed(0)} mm · A = {(sec.A * 1e4).toFixed(0)} cm² · S3 = {(sec.S3 * 1e6).toFixed(0)} cm³ · S2 = {(sec.S2 * 1e6).toFixed(0)} cm³ · E = {(sec.E_mpa / 1000).toFixed(1)} GPa ({sec.material})
      </p>
      {gov ? (
        <p style={{ fontSize: 12, margin: "2px 0" }}>
          {L("ترکیب بار حاکم", "Governing combo")}: <strong dir="ltr" style={{ background: "#7a5b00", padding: "0 4px", borderRadius: 3 }} data-testid="inspector-governing">{gov}</strong>
        </p>
      ) : null}

      <p className="v3d-h" style={{ marginTop: 6 }}>
        {L("تنش و کرنش", "Stress & strain")}{" "}
        <select value={cur} onChange={(e) => setChosen(e.target.value)} aria-label="Stress combo" data-testid="inspector-combo">
          {rows.map((r) => <option key={r.load} value={r.load}>{r.load}{r.load === gov ? " ★" : ""}</option>)}
        </select>
      </p>
      <div style={scroll} dir="ltr">
        <table className="v3d-table" dir="ltr" data-testid="inspector-stress">
          <thead>
            <tr><th style={cell}>End</th><th style={cell}>N/A</th><th style={cell}>M3/S3</th><th style={cell}>M2/S2</th><th style={cell}>σmax</th><th style={cell}>σmin</th><th style={cell}>τ2≈V2/Av</th><th style={cell}>τ3≈V3/Av</th><th style={cell}>εmax (µε)</th><th style={cell}>εmin (µε)</th></tr>
          </thead>
          <tbody>
            {ends.map(([e, s]) => (
              <tr key={e}><td style={cell}>{e}</td><td style={cell}>{f2(s.axial)}</td><td style={cell}>±{f2(s.bend3)}</td><td style={cell}>±{f2(s.bend2)}</td><td style={cell}>{f2(s.sMax)}</td><td style={cell}>{f2(s.sMin)}</td><td style={cell}>{f2(s.tau2)}</td><td style={cell}>{f2(s.tau3)}</td><td style={cell}>{fe(s.epsMax)}</td><td style={cell}>{fe(s.epsMin)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {env ? (
        <>
          <p className="v3d-h" style={{ marginTop: 6 }}>{L("پوش (بیشینه/کمینه)", "Envelope max/min")}</p>
          <div style={scroll} dir="ltr">
            <table className="v3d-table" dir="ltr" data-testid="inspector-envelope">
              <thead><tr><th style={cell} />{FORCE_KEYS.map((k) => <th key={k} style={cell}>{k}</th>)}</tr></thead>
              <tbody>
                <tr><td style={cell}>max</td>{FORCE_KEYS.map((k) => <td key={k} style={cell} title={env[k].maxAt}>{f1(env[k].max)}</td>)}</tr>
                <tr><td style={cell}>combo</td>{FORCE_KEYS.map((k) => <td key={k} style={{ ...cell, fontSize: 10 }}>{env[k].maxAt}</td>)}</tr>
                <tr><td style={cell}>min</td>{FORCE_KEYS.map((k) => <td key={k} style={cell} title={env[k].minAt}>{f1(env[k].min)}</td>)}</tr>
                <tr><td style={cell}>combo</td>{FORCE_KEYS.map((k) => <td key={k} style={{ ...cell, fontSize: 10 }}>{env[k].minAt}</td>)}</tr>
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      <p className="v3d-h" style={{ marginTop: 6 }}>{L("نیروهای انتهایی برای همه حالت‌ها و ترکیب‌ها", "End forces, all cases & combos")} <span dir="ltr">(kN, kN·m)</span></p>
      <div style={{ ...scroll, maxHeight: 320, overflowY: "auto" }} dir="ltr">
        <table className="v3d-table" dir="ltr" data-testid="inspector-forces">
          <thead>
            <tr><th style={cell}>Case/Combo</th><th style={cell}>End</th>{FORCE_KEYS.map((k) => <th key={k} style={cell}>{k}</th>)}</tr>
          </thead>
          <tbody>
            {rows.flatMap((r) => (["i", "j"] as const).map((e) => (
              <tr key={r.load + e} onClick={() => setChosen(r.load)} style={{ cursor: "pointer", background: r.load === gov ? "rgba(255,193,7,0.22)" : r.load === cur ? "rgba(79,195,247,0.15)" : undefined }}>
                <td style={{ ...cell, textAlign: "left" }}>{e === "i" ? r.load : ""}</td><td style={cell}>{e}</td>
                {FORCE_KEYS.map((k) => <td key={k} style={cell}>{f1(r[e][k])}</td>)}
              </tr>
            )))}
          </tbody>
        </table>
      </div>
      {!full ? <p className="v3d-muted" style={{ fontSize: 11 }}>{fa ? "این مدل فقط N، V2 و M3 را دارد. برای V3، M2 و T تحلیل را دوباره اجرا کنید." : "Only N, V2, M3 are in this payload; re-run the analysis for V3, M2, T."}</p> : null}

      <p className="v3d-muted" style={{ fontSize: 11 }}>
        {fa
          ? "تنش‌ها بر حسب MPa (کشش +)، ε = σ/E. این مقادیر ارتجاعی و بر اساس مقطع ناخالص (بدون ترک‌خوردگی و آرماتور) هستند و فقط برای بررسی‌اند، نه طراحی. Av = 5/6·A. N فشاری مثبت است."
          : "Stresses in MPa (tension +), ε = σ/E. Elastic, gross-section values (uncracked, no rebar) for checking only, not design. Av = 5/6·A. N is compression +."}
      </p>
    </section>
  );
}
