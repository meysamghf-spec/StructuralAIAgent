"use client";

import { useState } from "react";
import {
  runChatDownloadItem,
  runChatDownloads,
  type ChatDownloads,
} from "@/lib/chat-actions";

/** Working download buttons for a chat command (ZIP of all outputs, or the specific files that were asked for). */
export function ChatDownloadsCard({ downloads }: { downloads: ChatDownloads }) {
  const fa = downloads.lang === "fa";
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : fa ? "دانلود انجام نشد" : "Download failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="chat-downloads" dir={fa ? "rtl" : "ltr"} data-testid="chat-downloads">
      <div className="chat-downloads-buttons">
        {downloads.zip || downloads.items.length > 3 ? (
          <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={() => void run("zip", () => runChatDownloads(downloads))}>
            {busy === "zip" ? (fa ? "در حال آماده‌سازی…" : "Preparing…") : fa ? "دانلود همه (ZIP)" : "Download all (ZIP)"}
          </button>
        ) : null}
        {!downloads.zip
          ? downloads.items.map((item) => (
              <button
                type="button"
                key={`${item.kind}-${item.name}`}
                className="btn btn-secondary"
                disabled={busy !== null}
                onClick={() => void run(item.name, () => runChatDownloadItem(downloads, item))}
              >
                {busy === item.name ? (fa ? "در حال آماده‌سازی…" : "Preparing…") : item.label}
              </button>
            ))
          : null}
      </div>
      {error ? <p className="chat-downloads-error" role="alert">{error}</p> : null}
    </div>
  );
}
