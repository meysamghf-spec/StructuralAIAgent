import { getApiBaseUrl } from "./api";
import { getAuthHeaders } from "./auth-session";

export type DownloadKind = "table" | "figure" | "model" | "drawing" | "report";
export type DownloadItem = { kind: DownloadKind; name: string; label: string; labelFa: string; formats: string[] };
export type DownloadGroup = "analysis" | "design" | "foundation" | "optimization" | "figures" | "drawings" | "models" | "reports";

const T = (name: string, label: string, labelFa: string): DownloadItem => ({ kind: "table", name, label, labelFa, formats: ["xlsx", "csv"] });
const F = (name: string, label: string, labelFa: string): DownloadItem => ({ kind: "figure", name, label, labelFa, formats: ["png", "svg"] });

/** Every downloadable output of a frame run, grouped by the workspace section that shows it. */
export const DOWNLOADS: Record<DownloadGroup, DownloadItem[]> = {
  analysis: [
    T("joint_displacements", "Joint displacements", "تغییرمکان گره‌ها"),
    T("reactions", "Support reactions", "عکس‌العمل تکیه‌گاه‌ها"),
    T("member_forces", "Member forces N/V/M per combo", "نیروهای اعضا N/V/M"),
    T("storey_drift", "Storey drift", "جابجایی نسبی طبقات"),
    T("modal", "Modal periods + mass participation", "دوره‌های تناوب و مشارکت جرمی"),
    T("base_shear", "Base shear / 2800 checks", "برش پایه / کنترل‌های ۲۸۰۰"),
  ],
  design: [
    T("design_beams", "Beam design D/C + rebar", "طراحی تیرها D/C و میلگرد"),
    T("design_columns", "Column design D/C + rebar", "طراحی ستون‌ها D/C و میلگرد"),
    T("design_scwb", "Strong column / weak beam", "ستون قوی / تیر ضعیف"),
  ],
  foundation: [T("foundation", "Foundation groups", "گروه‌های فونداسیون"), T("footings", "Footings per column", "پی‌های منفرد")],
  optimization: [T("optimization", "Optimization summary", "خلاصهٔ بهینه‌سازی"), T("optimization_groups", "Optimized sections", "مقاطع بهینه")],
  figures: [
    F("view3d", "3D view", "نمای سه‌بعدی"),
    F("deformed", "Deformed shape", "شکل تغییرشکل‌یافته"),
    F("moment", "Moment diagram", "نمودار لنگر"),
    F("shear", "Shear diagram", "نمودار برش"),
    F("axial", "Axial force diagram", "نمودار نیروی محوری"),
    F("drift", "Drift plot", "نمودار دریفت"),
    F("mode1", "Mode shape 1", "شکل مود ۱"),
    F("mode2", "Mode shape 2", "شکل مود ۲"),
    F("mode3", "Mode shape 3", "شکل مود ۳"),
  ],
  drawings: [
    { kind: "drawing", name: "structural_set", label: "Structural drawing set", labelFa: "نقشه‌های اجرایی سازه", formats: ["pdf"] },
    { kind: "drawing", name: "dxf_plans", label: "Plans", labelFa: "پلان‌ها", formats: ["dxf", "pdf"] },
    { kind: "drawing", name: "dxf_rebar", label: "Rebar details", labelFa: "جزئیات آرماتوربندی", formats: ["dxf", "pdf"] },
    { kind: "drawing", name: "dxf_foundation", label: "Foundation details", labelFa: "جزئیات فونداسیون", formats: ["dxf", "pdf"] },
    { kind: "drawing", name: "dxf_3d", label: "3D wireframe", labelFa: "قاب سه‌بعدی", formats: ["dxf"] },
  ],
  models: [
    { kind: "model", name: "e2k", label: "ETABS model", labelFa: "مدل ETABS", formats: ["e2k"] },
    { kind: "model", name: "s2k", label: "SAP2000 model", labelFa: "مدل SAP2000", formats: ["s2k"] },
    { kind: "model", name: "f2k", label: "SAFE foundation", labelFa: "مدل SAFE", formats: ["f2k"] },
  ],
  reports: [
    { kind: "table", name: "all", label: "All tables (one workbook)", labelFa: "همهٔ جداول (یک فایل اکسل)", formats: ["xlsx"] },
    { kind: "report", name: "report_md", label: "Calculation report", labelFa: "گزارش محاسبات", formats: ["md"] },
    { kind: "report", name: "report_json", label: "Raw results", labelFa: "نتایج خام", formats: ["json"] },
  ],
};

export type DownloadContext = {
  inputs?: Record<string, unknown> | null;
  projectId?: string | null;
  optimization?: unknown;
  saveToFiles?: boolean;
};

function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function fail(res: Response): Promise<never> {
  const body = await res.json().catch(() => ({}));
  throw new Error(typeof body?.detail === "string" ? body.detail : body?.error?.message ?? `Download failed (${res.status})`);
}

export function filenameFrom(res: Response, fallback: string): string {
  const m = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "");
  return m?.[1] ?? fallback;
}

export function requestBody(ctx: DownloadContext, extra: Record<string, unknown> = {}): string {
  return JSON.stringify({
    inputs: ctx.inputs ?? null,
    project_id: ctx.projectId ?? null,
    optimization: ctx.optimization ?? null,
    save_to_files: Boolean(ctx.saveToFiles && ctx.projectId),
    ...extra,
  });
}

/** Fetch one output (returns blob + filename); `download` also saves it in the browser. */
export async function fetchDownload(item: Pick<DownloadItem, "kind" | "name">, format: string, ctx: DownloadContext) {
  const res = await fetch(`${getApiBaseUrl()}/api/v1/frame3d/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: requestBody(ctx, { kind: item.kind, name: item.name, format }),
    cache: "no-store",
  });
  if (!res.ok) await fail(res);
  return { blob: await res.blob(), filename: filenameFrom(res, `${item.name}.${format}`) };
}

export async function download(item: Pick<DownloadItem, "kind" | "name">, format: string, ctx: DownloadContext) {
  const { blob, filename } = await fetchDownload(item, format, ctx);
  save(blob, filename);
}

/** "Download all (ZIP)": every table, figure, drawing, model export and the report; also stored in project Files. */
export async function downloadAll(ctx: DownloadContext): Promise<{ files: number; saved: number }> {
  const res = await fetch(`${getApiBaseUrl()}/api/v1/frame3d/package`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: requestBody({ ...ctx, saveToFiles: ctx.saveToFiles ?? true }),
    cache: "no-store",
  });
  if (!res.ok) await fail(res);
  save(await res.blob(), filenameFrom(res, "frame-results.zip"));
  const ids = (res.headers.get("x-file-ids") ?? "").split(",").filter(Boolean);
  return { files: Number(res.headers.get("x-files") ?? 0), saved: ids.length };
}
