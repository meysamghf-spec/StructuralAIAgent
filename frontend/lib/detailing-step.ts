/** "Detailing" workflow step: it follows Design and is wired to the real rebar-detailing / structural-set outputs.
 *
 *  Status is honest and derived, never faked:
 *  - not_run : no Mabhas 9 design exists yet, so there is nothing to detail.
 *  - ready   : a design exists (and the plan allows rebar sheets) but no detailing output has been produced yet.
 *  - done    : a rebar-detail DXF/PDF or the structural drawing set was actually generated for this project
 *              (remembered in this browser; the files themselves are also stored in the project's Files when saved).
 *  - locked  : the account's plan does not include rebar sheets (the backend answers 402 regardless).
 */
import type { Frame3dLang } from "./frame3d-i18n";

export type DetailingStatus = "not_run" | "ready" | "done" | "locked";

/** Items whose successful generation counts as "detailing done". */
export const DETAILING_ITEMS = ["dxf_rebar", "structural_set"] as const;
export const DETAILING_FEATURE = "rebar_sheets";
/** The chat commands that trigger the same generator (see backend chat_actions.parse_download). */
export const DETAILING_COMMAND: Record<Frame3dLang, string> = { en: "detail the rebar", fa: "دیتیلینگ آرماتور را بده" };

const KEY = "saia.detailing.done";
const GLOBAL = "_";

export function isDetailingItem(name: string): boolean {
  return (DETAILING_ITEMS as readonly string[]).includes(name);
}

function readMap(): Record<string, string> {
  try {
    const raw = typeof localStorage === "undefined" ? null : localStorage.getItem(KEY);
    const v = raw ? JSON.parse(raw) : {};
    return v && typeof v === "object" ? (v as Record<string, string>) : {};
  } catch {
    return {};
  }
}

/** Remember that detailing output was generated for this project (ISO timestamp). */
export function markDetailingDone(projectId: string | null | undefined, at: Date = new Date()): void {
  try {
    const map = readMap();
    map[projectId || GLOBAL] = at.toISOString();
    localStorage.setItem(KEY, JSON.stringify(map));
    if (typeof window !== "undefined") window.dispatchEvent(new Event(DETAILING_EVENT));
  } catch {
    /* storage unavailable: the status then simply stays "ready" */
  }
}

export function detailingDoneAt(projectId: string | null | undefined): string | null {
  const map = readMap();
  return map[projectId || GLOBAL] ?? null;
}

export const DETAILING_EVENT = "saia:detailing-changed";

export type DetailingInput = {
  /** A design (Mabhas 9 beams/columns) exists for the model being shown. */
  hasDesign: boolean;
  /** Plan limits `design_sheets` (null/undefined = not loaded / unlimited). */
  designSheets?: string[] | null;
  /** The plan check is enforced (billing `enforcement`); when false everything is allowed. */
  enforcement?: boolean;
  doneAt?: string | null;
};

export function detailingStatus(i: DetailingInput): DetailingStatus {
  if (!i.hasDesign) return "not_run";
  if (i.enforcement !== false && Array.isArray(i.designSheets) && !i.designSheets.includes(DETAILING_FEATURE)) return "locked";
  return i.doneAt ? "done" : "ready";
}

const LABEL: Record<DetailingStatus, Record<Frame3dLang, string>> = {
  not_run: { en: "Not run", fa: "اجرا نشده" },
  ready: { en: "Ready", fa: "آماده" },
  done: { en: "Done", fa: "انجام شد" },
  locked: { en: "Upgrade needed", fa: "نیازمند ارتقای پلن" },
};

export function detailingStatusLabel(s: DetailingStatus, lang: Frame3dLang): string {
  return LABEL[s][lang];
}

/** The Assistants-page glance value ("Not run" / "Ready" / "Available") -> status. */
export function detailingFromGlance(value: string | null | undefined): DetailingStatus {
  const v = (value ?? "").trim().toLowerCase();
  if (v === "available" || v === "done") return "done";
  if (v === "ready") return "ready";
  return "not_run";
}
