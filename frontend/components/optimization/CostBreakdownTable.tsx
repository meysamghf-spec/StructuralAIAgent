"use client";

import { fmtNum, type CostBreakdown, type OptResult } from "@/lib/optimization-full";

const ROWS: { key: keyof CostBreakdown["components"]; label: string }[] = [
  { key: "concrete", label: "بتن" },
  { key: "rebar", label: "میلگرد" },
  { key: "formwork", label: "قالب‌بندی" },
  { key: "steel", label: "مقاطع فولادی" },
];

/** Initial vs final quantities and cost split, so weight vs cost differences are clear. */
export function CostBreakdownTable({ r }: { r: OptResult }) {
  const qi = r.initial_quantities ?? null;
  const qf = r.quantities;
  const bi = r.cost_breakdown?.initial ?? null;
  const bf = r.cost_breakdown?.final ?? null;
  if (!qf) return null;
  const sw = (q: OptResult["quantities"] | null) => (q ? (q.rebar_kg || 0) + (q.steel_kg || 0) : null);
  return (
    <div style={{ overflowX: "auto", marginTop: 8 }} data-testid="cost-breakdown">
      <table className="data-table" style={{ minWidth: 520, width: "100%" }}>
        <thead><tr><th>مقدار</th><th>طرح اولیه</th><th>طرح نهایی</th></tr></thead>
        <tbody>
          <tr><td>وزن فولاد (میلگرد + مقاطع فولادی) kg</td><td>{fmtNum(sw(qi))}</td><td>{fmtNum(sw(qf))}</td></tr>
          <tr><td>حجم بتن m³</td><td>{fmtNum(qi?.concrete_m3, 1)}</td><td>{fmtNum(qf.concrete_m3, 1)}</td></tr>
          <tr><td>قالب‌بندی m²</td><td>{fmtNum(qi?.formwork_m2)}</td><td>{fmtNum(qf.formwork_m2)}</td></tr>
          <tr><td><strong>هزینه کل ({r.currency})</strong></td><td>{fmtNum(r.initial_cost)}</td><td>{fmtNum(r.cost)}</td></tr>
        </tbody>
      </table>
      {bf ? (
        <table className="data-table" style={{ minWidth: 520, width: "100%", marginTop: 6 }}>
          <thead><tr><th>سهم از هزینه</th><th>طرح اولیه</th><th>طرح نهایی</th></tr></thead>
          <tbody>
            {ROWS.filter((x) => (bi?.components[x.key] ?? 0) > 0 || bf.components[x.key] > 0).map((x) => (
              <tr key={x.key}>
                <td>{x.label}</td>
                <td>{bi ? `${fmtNum(bi.components[x.key])} (${fmtNum(bi.share_pct[x.key], 1)}٪)` : "—"}</td>
                <td>{`${fmtNum(bf.components[x.key])} (${fmtNum(bf.share_pct[x.key], 1)}٪)`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      <p style={{ fontSize: 12, opacity: 0.8 }}>
        وزن فولاد فقط میلگرد و مقاطع فولادی است؛ هزینه کل شامل بتن و قالب هم می‌شود، پس کاهش زیاد وزن فولاد ممکن است هزینه کل را کم تغییر دهد.
      </p>
    </div>
  );
}
