import { REQUIRED_GEOMETRY } from "@/lib/input-labels";

/** Defaults used when a geometry value is in neither the form nor the project's chats (same as the backend DEFAULTS). */
export const GEOMETRY_DEFAULTS: Record<string, number> = { storeys: 4, bays_x: 3, bays_y: 3, bay_x_m: 5, bay_y_m: 5 };

export type PrefillInfo = { fromChat: string[]; assumed: string[]; chatTitle: string | null; sourceLabel?: { en: string; fa: string } };

const blank = (v: string | undefined) => !v || !v.trim();

/**
 * Fill only the blank geometry fields: first from the project's chat frame, then with defaults.
 * Never overwrites what the user typed or what was already restored for this project.
 */
export function prefillGeometry(
  values: Record<string, string>,
  chat: { inputs: Record<string, unknown>; from_chat: string[] } | null,
): { values: Record<string, string>; fromChat: string[]; assumed: string[] } {
  const out = { ...values };
  const fromChat: string[] = [];
  const assumed: string[] = [];
  for (const k of REQUIRED_GEOMETRY) {
    if (!blank(out[k])) continue;
    const v = chat?.inputs?.[k];
    if (chat && chat.from_chat.includes(k) && v !== null && v !== undefined && String(v).trim() !== "") {
      out[k] = String(v);
      fromChat.push(k);
    } else {
      out[k] = String(GEOMETRY_DEFAULTS[k]);
      assumed.push(k);
    }
  }
  return { values: out, fromChat, assumed };
}
