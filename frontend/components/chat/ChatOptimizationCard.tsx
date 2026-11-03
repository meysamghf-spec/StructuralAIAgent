"use client";

import { OptResultView } from "@/components/optimization/OptResultView";
import type { ChatOptimizationFull } from "@/lib/chat-types";

/** Full section optimization started from the chat («بهینه کن»): sections, cost/weight breakdown and assumptions inline. */
export function ChatOptimizationCard({ data }: { data: ChatOptimizationFull }) {
  return (
    <section className="engineering-result-card" dir="rtl" lang="fa" data-testid="chat-optimization-full" aria-label="بهینه‌سازی کامل مقاطع">
      <header className="engineering-result-header">
        <div>
          <p className="eyebrow">بهینه‌سازی</p>
          <h3>بهینه‌سازی کامل مقاطع</h3>
        </div>
        <div className="engineering-result-badges">
          <span className={`chat-progress-badge ${data.result?.feasible ? "" : "warning"}`}>
            {data.status === "error" ? "خطا" : data.result?.feasible ? "قابل‌قبول" : "نیاز به بررسی"}
          </span>
        </div>
      </header>
      {data.sourceFa ? <p className="muted">منبع مدل: {data.sourceFa}</p> : null}
      {data.status === "error" || !data.result ? (
        <p role="alert" style={{ color: "#b91c1c" }}>{data.error ?? "بهینه‌سازی انجام نشد."}</p>
      ) : (
        <div style={{ overflowX: "auto" }}><OptResultView r={data.result} assumptionsOpen /></div>
      )}
      <p className="muted chat-disclaimer">این فقط پیشنهاد هوش مصنوعی است؛ تأیید نهایی با مهندس است.</p>
    </section>
  );
}
