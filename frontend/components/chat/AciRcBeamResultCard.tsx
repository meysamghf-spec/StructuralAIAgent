"use client";

import { chatT, dirOf, type ChatLang } from "@/lib/chat-i18n";
import type { AciRcBeamResults } from "@/lib/chat-types";

type AciRcBeamResultCardProps = {
  results: AciRcBeamResults;
  lang?: ChatLang | null;
};

export function AciRcBeamResultCard({ results, lang = null }: AciRcBeamResultCardProps) {
  const checkComplete = results.status === "PASS" || results.status === "FAIL";
  const validationLabel = validationCopy(results.status);

  return (
    <section className="engineering-result-card" aria-label={chatT(lang, "ACI 318 RC beam check")} dir={dirOf(lang)} lang={lang ?? undefined}>
      <header className="engineering-result-header">
        <div>
          <p className="eyebrow">{chatT(lang, "Concrete design")}</p>
          <h3>{chatT(lang, "ACI 318 RC beam check")}</h3>
        </div>
        <div className="engineering-result-badges">
          <span className={`chat-progress-badge ${badgeClass(results.status)}`}>
            {chatT(lang, results.status.replace(/_/g, " "))}
          </span>
        </div>
      </header>

      {results.code ? <p className="muted engineering-result-code">{chatT(lang, "Code")}: <bdi dir="ltr">{results.code}</bdi></p> : null}

      {results.missing.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{chatT(lang, "Required inputs")}</p>
          <ul>
            {results.missing.map((item) => (
              <li key={item} dir="auto">{chatT(lang, item)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {checkComplete && results.fields.length > 0 ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{chatT(lang, "Inputs and results")}</p>
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
        </div>
      ) : null}

      {checkComplete ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{chatT(lang, "Validation")}</p>
          <ul>
            <li>{chatT(lang, "Calculation completed")}</li>
            <li>{chatT(lang, validationLabel)}</li>
            {results.numericResults?.flexureOutcome ? (
              <li>{chatT(lang, `Flexure ${results.numericResults.flexureOutcome}`)}</li>
            ) : null}
            {results.numericResults?.shearOutcome ? (
              <li>{chatT(lang, `Shear ${results.numericResults.shearOutcome}`)}</li>
            ) : null}
          </ul>
        </div>
      ) : null}

      {results.inputUnits || results.internalUnits || results.outputUnits ? (
        <div className="engineering-result-block">
          <p className="engineering-result-label">{chatT(lang, "Units")}</p>
          <ul>
            {results.inputUnits ? <li>{chatT(lang, "Input")}: <bdi dir="ltr">{results.inputUnits}</bdi></li> : null}
            {results.internalUnits ? <li>{chatT(lang, "Internal")}: <bdi dir="ltr">{results.internalUnits}</bdi></li> : null}
            {results.outputUnits ? <li>{chatT(lang, "Output")}: <bdi dir="ltr">{results.outputUnits}</bdi></li> : null}
          </ul>
        </div>
      ) : null}

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

      {results.disclaimer ? <p className="muted chat-disclaimer" dir="auto">{chatT(lang, results.disclaimer)}</p> : null}
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
