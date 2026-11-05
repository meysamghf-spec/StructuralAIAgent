"use client";

import { CostBreakdownTable } from "./CostBreakdownTable";
import { barsLabel, barsLines, costChangeText, fmtNum, savingsPct, type OptResult } from "@/lib/optimization-full";

/** Result of a full section optimization (Optimization page and chat card). */
export function OptResultView({ r, assumptionsOpen = false }: { r: OptResult; assumptionsOpen?: boolean }) {
  const save = savingsPct(r);
  return (
    <div style={{ marginTop: 12 }} data-testid="opt-result-view">
      <p>
        <strong>{r.feasible ? "طرح قابل‌قبول (همه کنترل‌ها برقرار)" : "هنوز طرحی که همه کنترل‌ها را برقرار کند یافت نشد؛ فهرست بزرگ‌تر یا زمان بیشتر بدهید."}</strong>
        {" "}هزینه: {fmtNum(r.cost)} {r.currency}{save != null ? ` (${costChangeText(r)})` : ""} — دریفت/مجاز: {fmtNum(r.drift_ratio, 2)}
      </p>
      <p style={{ fontSize: 13 }}>
        بتن {fmtNum(r.quantities.concrete_m3, 1)} m³ — میلگرد {fmtNum(r.quantities.rebar_kg)} kg — قالب {fmtNum(r.quantities.formwork_m2)} m²
        {r.quantities.steel_kg ? ` — فولاد ${fmtNum(r.quantities.steel_kg)} kg` : ""} — {fmtNum(r.evaluations)} تحلیل در {fmtNum(r.elapsed_s, 1)} ثانیه
      </p>
      <CostBreakdownTable r={r} />
      <div className="opt-table-scroll" data-testid="opt-groups-table">
        <table className="data-table" style={{ minWidth: 560, width: "100%" }}>
          <thead><tr><th>گروه</th><th>اعضا (تعداد)</th><th>مقطع (mm)</th><th>میلگرد طولی (Φ mm)</th><th>خاموت / تنگ (Φ mm @ mm)</th><th>D/C (–)</th></tr></thead>
          <tbody>
            {r.groups.map((g) => (
              <tr key={g.group}>
                <td>{g.label}</td><td className="num">{fmtNum(g.members)}</td><td className="num"><bdi dir="ltr" className="ltr-iso">{g.section}</bdi></td>
                <td className="num">{(() => {
                  const lines = barsLines(g);
                  if (!lines) return <bdi dir="ltr" className="ltr-iso">{barsLabel(g)}</bdi>;
                  return lines.map((l) => (
                    <div key={l.label} className="rebar-line"><span>{l.label}:</span> <bdi dir="ltr" className="ltr-iso">{l.value}</bdi></div>
                  ));
                })()}</td>
                <td className="num" style={{ fontSize: 12 }}><bdi dir="ltr" className="ltr-iso">{g.stirrups ?? g.ties ?? "—"}</bdi></td>
                <td className="num" style={{ color: g.DC > 1 ? "#b91c1c" : undefined }}>{fmtNum(g.DC, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details style={{ marginTop: 8 }} open={assumptionsOpen}>
        <summary>فرض‌ها</summary>
        <ul>{[...(r.assumed_inputs ?? []), ...r.assumptions].map((a) => <li key={a}>{a}</li>)}</ul>
      </details>
    </div>
  );
}
