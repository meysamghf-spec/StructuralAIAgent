"use client";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  if (typeof window !== "undefined") console.error("[global-error]", error);
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: 24 }}>
        <h2>Something went wrong / خطایی رخ داد</h2>
        <p>Please reload the page. / لطفاً صفحه را دوباره بارگذاری کنید.</p>
        <button type="button" onClick={() => reset()}>Try again</button>{" "}
        <button type="button" onClick={() => window.location.reload()}>Reload</button>
      </body>
    </html>
  );
}
