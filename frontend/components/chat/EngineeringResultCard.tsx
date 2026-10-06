"use client";

import { RCDemoVisualization } from "@/components/chat/demo/RCDemoVisualization";
import type { DemoEngineeringResults } from "@/lib/chat-types";
import { parseRcBeamDemoModel } from "@/lib/rc-beam-visualization";

type EngineeringResultCardProps = {
  results: DemoEngineeringResults;
};

export function EngineeringResultCard({ results }: EngineeringResultCardProps) {
  const model = parseRcBeamDemoModel(results);

  return (
    <section className="engineering-result-card" aria-label="Structural analysis results">
      {model ? (
        <RCDemoVisualization results={results} model={model} />
      ) : (
        <TextualEngineeringFallback results={results} />
      )}

      {results.assumptions.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Assumptions</p>
          <ul>
            {results.assumptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {results.warnings.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Warnings</p>
          <ul>
            {results.warnings.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {results.disclaimer ? (
        <p className="muted chat-disclaimer">{results.disclaimer}</p>
      ) : null}
    </section>
  );
}

function TextualEngineeringFallback({ results }: { results: DemoEngineeringResults }) {
  return (
    <>
      <header className="engineering-result-header">
        <div>
          <p className="eyebrow">Structural analysis</p>
          <h3>RC beam results</h3>
        </div>
        <div className="engineering-result-badges">
          {results.demo ? <span className="chat-progress-badge warning">Demo</span> : null}
          <span className="chat-progress-badge">{results.status.replace(/_/g, " ")}</span>
        </div>
      </header>
      <p className="muted">
        Graphical analysis becomes available after a valid engineering result is returned.
      </p>
      {results.code ? <p className="muted engineering-result-code">Code: {results.code}</p> : null}
      {results.fields.length > 0 ? (
        <dl className="engineering-result-grid">
          {results.fields.map((field) => (
            <div key={`${field.label}-${field.value}`} className="engineering-result-field">
              <dt>{field.label}</dt>
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
