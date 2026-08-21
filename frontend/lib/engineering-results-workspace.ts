const VALIDATION_STATUS_LABELS: Record<string, string> = {
  VALIDATED: "Validated",
  INVALID: "Invalid",
  INCOMPLETE: "Incomplete",
  PARTIALLY_VALIDATED: "Some results need engineering review",
  REQUIRES_ENGINEER_REVIEW: "Engineering review required",
  REQUIRES_LOCAL_SOFTWARE: "Local solver software required",
};

export function getValidationStatusLabel(status: string): string {
  return VALIDATION_STATUS_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getResultsAvailabilityMessage(available: boolean): string {
  return available
    ? "Analysis results are available from a validated solver run."
    : "Analysis results are not available yet.";
}

export function getResultTypeLabel(resultType: string): string {
  return resultType.replaceAll("_", " ");
}
