"use client";

import type { AciRcBeamResults } from "@/lib/chat-types";

type AciRcBeamResultCardProps = {
  results: AciRcBeamResults;
};

export function AciRcBeamResultCard({ results }: AciRcBeamResultCardProps) {
  const checkComplete = results.status === "PASS" || results.status === "FAIL";
  const validationLabel = validationCopy(results.status);

  return (
    <section className="engineering-result-card" aria-label="ACI 318 RC beam check">
      <header className="engineering-result-header">
        <div>
          <p className="eyebrow">Concrete design</p>
          <h3>ACI 318 RC beam check</h3>
        </div>
        <div className="engineering-result-badges">
          <span className={`chat-progress-badge ${badgeClass(results.status)}`}>
            {results.status.replace(/_/g, " ")}
          </span>
        </div>
      </header>

      {results.code ? <p className="muted engineering-result-code">Code: {results.code}</p> : null}

      {results.missing.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Required inputs</p>
          <ul>
            {results.missing.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {checkComplete && results.fields.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Inputs and results</p>
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
        </div>
      ) : null}

      {checkComplete ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Validation</p>
          <ul>
            <li>Calculation completed</li>
            <li>{validationLabel}</li>
            {results.numericResults?.flexureOutcome ? (
              <li>Flexure {results.numericResults.flexureOutcome}</li>
            ) : null}
            {results.numericResults?.shearOutcome ? (
              <li>Shear {results.numericResults.shearOutcome}</li>
            ) : null}
          </ul>
        </div>
      ) : null}

      {results.inputUnits || results.internalUnits || results.outputUnits ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">Units</p>
          <ul>
            {results.inputUnits ? <li>Input: {results.inputUnits}</li> : null}
            {results.internalUnits ? <li>Internal: {results.internalUnits}</li> : null}
            {results.outputUnits ? <li>Output: {results.outputUnits}</li> : null}
          </ul>
        </div>
      ) : null}

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

      {results.disclaimer ? <p className="muted chat-disclaimer">{results.disclaimer}</p> : null}
    </section>
  );
}

function badgeClass(status: string): string {
  if (status === "PASS") {
    return "";
  }
  if (status === "FAIL" || status === "INVALID_INPUT" || status === "UNSUPPORTED_CODE") {
    return "warning";
  }
  return "warning";
}

function validationCopy(status: string): string {
  if (status === "PASS") {
    return "Design checks passed";
  }
  if (status === "FAIL") {
    return "Design check failed";
  }
  return status.replace(/_/g, " ");
}
