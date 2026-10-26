// Self-contained HTML calculation report from a frame3d result (rendered in an iframe and downloadable).
import type { Frame3dResults } from "./chat-types";
import { makeT } from "./frame3d-i18n";

function esc(v: unknown): string {
  return String(v ?? "—").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

function table(headers: string[], rows: Array<Array<unknown>>): string {
  if (!rows.length) return "";
  return `<table><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`)
    .join("")}</tbody></table>`;
}

export function buildReportHtml(r: Frame3dResults, projectName: string | null, generatedAt: string): string {
  const t = makeT(r.lang);
  const fa = r.lang === "fa";
  const parts: string[] = [];
  parts.push(`<h1>${esc(t("3D frame analysis"))}${projectName ? ` — ${esc(projectName)}` : ""}</h1>`);
  parts.push(`<p class="meta">${esc(r.code ?? "")} · ${esc(generatedAt)}</p>`);
  if (r.disclaimer) parts.push(`<p class="note">${esc(r.disclaimer)}</p>`);
  parts.push(`<h2>${esc(t("Model and results"))}</h2>`);
  parts.push(table(["", "", ""], r.fields.map((f) => [f.label, f.value, f.unit ?? ""])).replace(/<thead>.*?<\/thead>/, ""));
  parts.push(`<h2>${esc(t("Storey drift"))}</h2>`);
  parts.push(table([t("Storey"), t("Dir"), t("Δ elastic (mm)"), t("Δ/h elastic (%)"), "Δ amplified (%)"],
    r.drift.map((d) => [d.storey, d.direction, d.driftElasticMm, d.ratioElasticPct, d.ratioAmplifiedPct])));
  parts.push(`<h2>${esc(t("Max member forces per storey (envelope)"))}</h2>`);
  parts.push(table([t("Storey"), t("Beam M⁻ (kN·m)"), t("Beam M⁺ (kN·m)"), t("Beam V (kN)"), t("Column P (kN)")],
    r.storeyForces.map((s) => [s.storey, s.beamMNegKnM, s.beamMPosKnM, s.beamVKn, s.columnPKn])));
  if (r.design) {
    parts.push(`<h2>${esc(t("Mabhas 9 RC design"))} — ${esc(t(r.design.status))}</h2>`);
    parts.push(table([t("Group"), "Mu⁻", "Mu⁺", "Vu", t("Top"), t("Bottom"), t("Stirrups"), t("D/C M"), t("D/C V"), "Status"],
      r.design.beams.map((b) => [b.group, b.Mu_neg_kn_m, b.Mu_pos_kn_m, b.Vu_kn, b.top_bars, b.bottom_bars, b.stirrups, b.DC_flexure, b.DC_shear, t(String(b.status))])));
    parts.push(table([t("Group"), "Pu", "Mu,y", "Mu,z", t("Bars"), t("Ties"), t("D/C"), "Status"],
      r.design.columns.map((c) => [c.group, c.Pu_kn, c.Mu_y_kn_m, c.Mu_z_kn_m, c.bars, c.ties, c.DC, t(String(c.status))])));
  }
  if (r.foundation) {
    const f = r.foundation;
    parts.push(`<h2>${esc(t("Foundation design (isolated footings)"))} — ${esc(t(f.status))}</h2>`);
    parts.push(`<p>${esc(t("Allowable bearing"))}: ${esc(f.qaKpa)} kPa${f.qaAssumed ? ` (${esc(t("assumed"))})` : ""}</p>`);
    parts.push(table([t("Group"), t("P service"), "B (m)", "h (m)", t("qu max (kPa)"), t("D/C bearing"), t("D/C punching"), t("Bars"), "Status"],
      f.rows.map((x) => [x.group, x.P_service_kn, x.B_m, x.h_m, x.q_max_kpa, x.bearing_dc, x.DC_punching, x.bars, t(String(x.status))])));
    if (f.recommendation) parts.push(`<p>${esc(f.recommendation)}</p>`);
  }
  if (r.assumptions.length) parts.push(`<h2>${esc(t("Assumptions"))}</h2><ul>${r.assumptions.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>`);
  if (r.warnings.length) parts.push(`<h2>${esc(t("Warnings"))}</h2><ul>${r.warnings.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>`);
  const css = `body{font-family:Segoe UI,Tahoma,sans-serif;margin:24px;color:#111;line-height:1.45}h1{font-size:22px}h2{font-size:16px;margin-top:22px;border-bottom:1px solid #ccc}
table{border-collapse:collapse;margin:8px 0;font-size:12px}td,th{border:1px solid #bbb;padding:3px 6px}th{background:#eef2f7}td{direction:ltr;unicode-bidi:plaintext}.meta{color:#555}.note{background:#fff7d6;padding:6px 8px}`;
  return `<!doctype html><html lang="${r.lang}" dir="${fa ? "rtl" : "ltr"}"><head><meta charset="utf-8"><title>STRAI report</title><style>${css}</style></head><body>${parts.join("\n")}</body></html>`;
}
