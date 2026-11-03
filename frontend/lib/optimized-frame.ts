/**
 * Optimized frame ↔ Model page bridge. After «بهینه کن» (chat) or the optimization page, the optimizer's
 * sections are re-analysed on the backend (`optimized_frame3d`, inputs carry `group_sections`). This module
 * stores that as the project's frame and remembers the original inputs so the Model page can toggle
 * «مدل اولیه / مدل بهینه‌شده».
 */
import { saveFrame3dInputs, saveFrame3dPayload } from "@/lib/frame3d-store";
import type { ChatRun } from "@/lib/chat-runs";
import { isUsableFrameRun, listProjectChatRuns } from "@/lib/chat-runs";

export type OptView = "original" | "optimized";
export type OptFrameRecord = {
  marker: string;
  original: Record<string, unknown>;
  optimized: Record<string, unknown>;
  view: OptView;
};

const recKey = (pid: string | null) => `sa:frame3d:optimized:${pid ?? "none"}`;

export function loadOptFrame(pid: string | null): OptFrameRecord | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(recKey(pid));
    return raw ? (JSON.parse(raw) as OptFrameRecord) : null;
  } catch {
    return null;
  }
}

function writeOptFrame(pid: string | null, rec: OptFrameRecord): void {
  if (typeof window === "undefined") return;
  try { window.localStorage.setItem(recKey(pid), JSON.stringify(rec)); } catch { /* quota */ }
}

/** Original inputs: given explicitly, else the optimized ones without the per-storey sections. */
export function originalOf(optimized: Record<string, unknown>, original?: unknown): Record<string, unknown> {
  if (original && typeof original === "object") return { ...(original as Record<string, unknown>) };
  const { group_sections: _gs, ...rest } = optimized;
  return rest;
}

export function hasGroupSections(inputs: Record<string, unknown> | null | undefined): boolean {
  const gs = inputs?.group_sections;
  return !!gs && typeof gs === "object" && Object.keys(gs as object).length > 0;
}

/** Make the optimized frame the project's frame (inputs, and the payload when we already have it). */
export function applyOptimizedFrame(
  pid: string | null,
  opt: { inputs: Record<string, unknown>; payload?: unknown; original?: unknown; marker: string },
): void {
  writeOptFrame(pid, { marker: opt.marker, optimized: opt.inputs, original: originalOf(opt.inputs, opt.original), view: "optimized" });
  saveFrame3dInputs(pid, opt.inputs);
  saveFrame3dPayload(pid, opt.payload ?? null);
}

/** Switch the stored view; returns the inputs to analyse (caller re-runs them). */
export function setOptView(pid: string | null, view: OptView): Record<string, unknown> | null {
  const rec = loadOptFrame(pid);
  if (!rec) return null;
  writeOptFrame(pid, { ...rec, view });
  return view === "optimized" ? rec.optimized : rec.original;
}

export const runMarker = (r: ChatRun) => `${r.message_id}|${r.created_at}`;

/** Newest usable frame run when it is an optimized one not yet applied on this device. */
export function pendingOptimizedRun(runs: ChatRun[], rec: OptFrameRecord | null): ChatRun | null {
  const newest = runs.filter(isUsableFrameRun).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0];
  if (!newest || !newest.optimized || !newest.inputs) return null;
  return rec?.marker === runMarker(newest) ? null : newest;
}

/** Pull a newer chat optimization into the project's frame. Returns the inputs applied, or null. */
export async function syncOptimizedFromServer(pid: string | null): Promise<Record<string, unknown> | null> {
  if (!pid) return null;
  const run = pendingOptimizedRun(await listProjectChatRuns(pid, true), loadOptFrame(pid));
  if (!run?.inputs) return null;
  applyOptimizedFrame(pid, { inputs: run.inputs, original: run.original_inputs, marker: runMarker(run) });
  return run.inputs;
}
