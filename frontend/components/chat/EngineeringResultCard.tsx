"use client";

import { RCDemoVisualization } from "@/components/chat/demo/RCDemoVisualization";
import { chatT, dirOf, type ChatLang } from "@/lib/chat-i18n";
import type { DemoEngineeringResults } from "@/lib/chat-types";
import { parseRcBeamDemoModel } from "@/lib/rc-beam-visualization";

type EngineeringResultCardProps = {
  results: DemoEngineeringResults;
  lang?: ChatLang | null;
};

export function EngineeringResultCard({ results, lang = null }: EngineeringResultCardProps) {
  const model = parseRcBeamDemoModel(results);

  return (
    <section className="engineering-result-card" aria-label={chatT(lang, "Structural analysis results")} dir={dirOf(lang)} lang={lang ?? undefined}>
      {model ? (
        <RCDemoVisualization results={results} model={model} />
      ) : (
        <TextualEngineeringFallback results={results} lang={lang} />
      )}

      {results.assumptions.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{chatT(lang, "Assumptions")}</p>
          <ul>
            {results.assumptions.map((item) => (
              <li key={item} dir="auto">{chatT(lang, item)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {results.warnings.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{chatT(lang, "Warnings")}</p>
          <ul>
            {results.warnings.map((item) => (
              <li key={item} dir="auto">{chatT(lang, item)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {results.disclaimer ? (
        <p className="muted chat-disclaimer" dir="auto">{chatT(lang, results.disclaimer)}</p>
      ) : null}
    </section>
  );
}

function TextualEngineeringFallback({ results, lang }: { results: DemoEngineeringResults; lang: ChatLang | null }) {
  return (
    <>
      <header className="engineering-result-header">
        <div>
          <p className="eyebrow">{chatT(lang, "Structural analysis")}</p>
          <h3>{chatT(lang, "RC beam results")}</h3>
        </div>
        <div className="engineering-result-badges">
          {results.demo ? <span className="chat-progress-badge warning">{chatT(lang, "Demo")}</span> : null}
          <span className="chat-progress-badge">{chatT(lang, results.status.replace(/_/g, " "))}</span>
        </div>
      </header>
      <p className="muted">
        {chatT(lang, "Graphical analysis becomes available after a valid engineering result is returned.")}
      </p>
      {results.code ? <p className="muted engineering-result-code">{chatT(lang, "Code")}: <bdi dir="ltr">{results.code}</bdi></p> : null}
      {results.fields.length > 0 ? (
        <dl className="engineering-result-grid">
          {results.fields.map((field) => (
            <div key={`${field.label}-${field.value}`} className="engineering-result-field">
              <dt dir="auto">{field.label}</dt>
              <dd>
                {field.value}
                {field.unit ? <span className="engineering-result-unit"> {field.unit}</span> : null}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </>
  );
}
