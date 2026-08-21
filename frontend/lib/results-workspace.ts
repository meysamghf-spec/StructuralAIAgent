import { getValidationStatusLabel } from "./engineering-results-workspace";
import type { EngineeringResultSet } from "./engineering-results";
import type { TraceabilityLinkSummary } from "./api";
import { getTraceObjectLabel, getTraceRelationshipLabel } from "./workspace";

export function summarizeResultLineage(links: TraceabilityLinkSummary[]): string[] {
  return links.slice(0, 6).map(
    (link) =>
      `${getTraceObjectLabel(link.source_type)} ${getTraceRelationshipLabel(link.relationship_type).toLowerCase()} ${getTraceObjectLabel(link.target_type)}`,
  );
}

export function formatValidationFindings(summary: Record<string, unknown>): string[] {
  const findings = summary.findings;
  if (!Array.isArray(findings)) {
    return [];
  }
  return findings
    .slice(0, 5)
    .map((item) => {
      if (typeof item !== "object" || item === null) {
        return "";
      }
      const record = item as Record<string, unknown>;
      return typeof record.message === "string" ? record.message : "";
    })
    .filter(Boolean);
}

export function formatMissingRequirements(summary: Record<string, unknown>): string[] {
  const missing = summary.missing;
  if (!Array.isArray(missing)) {
    return [];
  }
  return missing.filter((item): item is string => typeof item === "string").slice(0, 5);
}

export function getResultReadinessMessage(
  validationStatus: string,
  engineeringResultsAvailable: boolean,
): string {
  if (engineeringResultsAvailable && validationStatus === "VALIDATED") {
    return "Validated analysis results are available for design and reporting.";
  }
  if (validationStatus === "REQUIRES_LOCAL_SOFTWARE") {
    return "Solver software is not available on this computer, so validated results are not available yet.";
  }
  if (validationStatus === "PARTIALLY_VALIDATED") {
    return "Some results need engineering review before they can be used downstream.";
  }
  return "Analysis results are not available yet.";
}

export function getResultTypeLabels(resultTypes: string[]): string[] {
  return resultTypes.map((item) => item.replaceAll("_", " "));
}

export function getSolverDisplayName(software: string, version: string): string {
  return `${software} ${version}`;
}

export function getNextStepMessage(
  validationStatus: string,
  engineeringResultsAvailable: boolean,
): string {
  if (engineeringResultsAvailable) {
    return "Open Design or Optimization to use these results, or generate a report.";
  }
  if (validationStatus === "REQUIRES_LOCAL_SOFTWARE") {
    return "Install and connect ETABS, SAP2000, or SAFE on this computer, then run analysis again.";
  }
  return "Run analysis from the Analysis workspace after the model is complete.";
}

export function getResultSourceLabel(result: EngineeringResultSet): string {
  const executionMode = result.provenance?.execution_mode;
  if (executionMode === "vendor") {
    return "Real CSI solver result";
  }
  if (result.validation_status === "REQUIRES_LOCAL_SOFTWARE") {
    return "Unavailable — solver not connected";
  }
  return "Platform calculation";
}

export function getExtractionStatusLabel(status: string | undefined): string {
  if (!status) {
    return "Extraction status not recorded";
  }
  return status.replaceAll("_", " ");
}

export function summarizeExtractionCategories(summary: Record<string, unknown> | undefined): string[] {
  if (!summary || !Array.isArray(summary.categories)) {
    return [];
  }
  return summary.categories
    .slice(0, 6)
    .map((item) => {
      if (typeof item !== "object" || item === null) {
        return "";
      }
      const record = item as Record<string, unknown>;
      const category = typeof record.category === "string" ? record.category.replaceAll("_", " ") : "result";
      const status = typeof record.status === "string" ? record.status : "UNKNOWN";
      const count = typeof record.row_count === "number" ? record.row_count : 0;
      return `${category}: ${status} (${count})`;
    })
    .filter(Boolean);
}

export { getValidationStatusLabel };
