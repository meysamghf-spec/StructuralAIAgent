"use client";

import { useEffect } from "react";

const RELOAD_KEY = "sa.chunkReloadAt";

function isChunkError(e: Error) {
  return /ChunkLoadError|Loading chunk|Failed to fetch dynamically imported module|Importing a module script failed/i.test(`${e?.name} ${e?.message}`);
}

/** Route-level fallback: replaces Next's blank "Application error" with a recoverable message. */
export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("[route-error]", error);
    // After a redeploy an open tab can request old JS chunks — reload once to pick up the new build.
    if (isChunkError(error)) {
      const last = Number(sessionStorage.getItem(RELOAD_KEY) ?? 0);
      if (Date.now() - last > 60_000) {
        sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
        window.location.reload();
      }
    }
  }, [error]);
  return (
    <main className="page" style={{ padding: 24 }} data-testid="route-error">
      <h2>Something went wrong on this page / خطایی در این صفحه رخ داد</h2>
      <p className="muted">Your data is safe. Try again, or reload the page. / اطلاعات شما محفوظ است؛ دوباره تلاش کنید.</p>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="button" type="button" onClick={() => reset()}>Try again / تلاش دوباره</button>
        <button className="button secondary" type="button" onClick={() => window.location.reload()}>Reload / بارگذاری مجدد</button>
      </div>
    </main>
  );
}
