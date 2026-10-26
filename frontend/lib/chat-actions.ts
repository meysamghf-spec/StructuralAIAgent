/** Chat-first actions: the backend answers commands (downloads, project/assistant switches) with structured metadata. */
import { download, downloadAll, type DownloadContext, type DownloadItem } from "./frame3d-downloads";

export type ChatDownloadItem = { kind: DownloadItem["kind"]; name: string; format: string; label: string };
export type ChatDownloads = {
  zip: boolean;
  items: ChatDownloadItem[];
  inputs: Record<string, unknown> | null;
  projectId: string | null;
  lang: "fa" | "en";
  assumed: string[];
};
export type ChatActionMeta = {
  downloads: ChatDownloads | null;
  switchAssistant: string | null;
  projectSwitch: { id: string; name: string } | null;
};

const asString = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);

export function parseChatDownloads(metadata: Record<string, unknown> | null | undefined): ChatDownloads | null {
  const raw = metadata?.chat_downloads as Record<string, unknown> | undefined;
  if (!raw || typeof raw !== "object") return null;
  const items = Array.isArray(raw.items)
    ? (raw.items as Record<string, unknown>[])
        .map((i) => ({ kind: (asString(i.kind) ?? "") as DownloadItem["kind"], name: asString(i.name) ?? "", format: asString(i.format) ?? "", label: asString(i.label) ?? "" }))
        .filter((i) => i.kind && i.name && i.format)
    : [];
  const zip = raw.zip === true;
  if (!zip && items.length === 0) return null;
  return {
    zip,
    items,
    inputs: (raw.inputs as Record<string, unknown>) ?? null,
    projectId: asString(raw.project_id),
    lang: raw.lang === "fa" ? "fa" : "en",
    assumed: Array.isArray(raw.assumed) ? (raw.assumed as unknown[]).filter((x): x is string => typeof x === "string") : [],
  };
}

export function parseChatActionMeta(metadata: Record<string, unknown> | null | undefined): ChatActionMeta {
  const ps = metadata?.project_switch as Record<string, unknown> | undefined;
  const id = asString(ps?.id);
  return {
    downloads: parseChatDownloads(metadata),
    switchAssistant: asString(metadata?.switch_assistant),
    projectSwitch: id ? { id, name: asString(ps?.name) ?? "" } : null,
  };
}

const ctxOf = (d: ChatDownloads): DownloadContext => ({ inputs: d.inputs, projectId: d.projectId, saveToFiles: Boolean(d.projectId) });

/** Start the downloads a chat reply promised. Single files / the ZIP start straight away; many items are bundled. */
export async function runChatDownloads(d: ChatDownloads): Promise<void> {
  if (d.zip || d.items.length > 3) {
    await downloadAll(ctxOf(d));
    return;
  }
  for (const item of d.items) {
    await download(item, item.format, ctxOf(d));
  }
}

export async function runChatDownloadItem(d: ChatDownloads, item: ChatDownloadItem): Promise<void> {
  await download(item, item.format, ctxOf(d));
}
