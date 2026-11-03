"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Frame3dResultCard } from "@/components/chat/Frame3dResultCard";
import { OptResultView } from "@/components/optimization/OptResultView";
import { mapFrame3dResults } from "@/lib/chat-mappers";
import type { ChatOptimizationFull } from "@/lib/chat-types";
import { getCurrentProjectId } from "@/lib/current-project";
import { applyOptimizedFrame } from "@/lib/optimized-frame";

/** The optimized model (sections from the optimizer, re-analysed) and a button to make it the project's model. */
function OptimizedFrameSection({ data }: { data: ChatOptimizationFull }) {
  const results = useMemo(() => (data.optimizedFrame ? mapFrame3dResults(data.optimizedFrame) : null), [data.optimizedFrame]);
  const [applied, setApplied] = useState(false);
  const inputs = (data.optimizedFrame as { inputs?: Record<string, unknown> } | null)?.inputs;
  if (!results || !inputs) return null;
  return (
    <div data-testid="chat-optimized-frame" style={{ marginTop: 12 }}>
      <h4>مدل بهینه‌شده (تحلیل مجدد با مقاطع بهینه)</h4>
      <Frame3dResultCard results={results} downloads={false} />
      <p>
        <button
          type="button"
          className="button"
          data-testid="apply-optimized-frame"
          onClick={() => {
            applyOptimizedFrame(getCurrentProjectId(), {
              inputs, payload: data.optimizedFrame, original: data.originalInputs, marker: `chat|${JSON.stringify(inputs.group_sections ?? {})}`,
            });
            setApplied(true);
          }}
        >
          {applied ? "در مدل پروژه اعمال شد" : "اعمال در مدل پروژه"}
        </button>{" "}
        <Link className="button secondary" href="/workspace/model">مشاهده در صفحه مدل</Link>
      </p>
    </div>
  );
}

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
      {data.status === "done" ? <OptimizedFrameSection data={data} /> : null}
      <p className="muted chat-disclaimer">این فقط پیشنهاد هوش مصنوعی است؛ تأیید نهایی با مهندس است.</p>
    </section>
  );
}
