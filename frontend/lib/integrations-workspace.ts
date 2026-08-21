const AVAILABILITY_LABELS: Record<string, string> = {
  AVAILABLE: "Available",
  NOT_INSTALLED: "Not installed",
  VERSION_MISMATCH: "Version mismatch",
  NOT_ACCESSIBLE: "Requires local software",
  REQUIRES_LOCAL_SOFTWARE: "Requires local software",
};

const AVAILABILITY_LABELS_FA: Record<string, string> = {
  NOT_INSTALLED: "نصب نشده است",
  VERSION_MISMATCH: "نسخه نرم‌افزار با پیکربندی پلتفرم مطابقت ندارد",
  NOT_ACCESSIBLE: "برای اجرای تحلیل، نرم‌افزار محلی باید در دسترس باشد",
  REQUIRES_LOCAL_SOFTWARE: "برای اجرای تحلیل واقعی، نرم‌افزار محلی مورد نیاز است",
  AVAILABLE: "در دسترس است",
};

export function getAvailabilityLabel(status: string, locale: "en" | "fa" = "en"): string {
  if (locale === "fa" && AVAILABILITY_LABELS_FA[status]) {
    return AVAILABILITY_LABELS_FA[status];
  }
  return AVAILABILITY_LABELS[status] ?? status.replaceAll("_", " ").toLowerCase();
}

export function getAvailabilityClass(status: string): string {
  if (status === "AVAILABLE") return "status-pass";
  if (status === "VERSION_MISMATCH") return "status-warning";
  return "status-review";
}

export function getSoftwareDisplayName(software: string, version: string): string {
  return `${software} ${version}`;
}

export function getConnectionHelpMessage(software: string, version: string, status: string): string {
  if (status === "AVAILABLE") {
    return `${software} ${version} is available on this computer.`;
  }
  if (status === "NOT_INSTALLED") {
    return `${software} ${version} is not available on this computer. Install/connect ${software} ${version} to run analysis.`;
  }
  if (status === "VERSION_MISMATCH") {
    return `${software} was detected, but the installed version does not match the expected ${version} integration profile.`;
  }
  return `${software} could not be connected. Check that the application is installed and accessible.`;
}
