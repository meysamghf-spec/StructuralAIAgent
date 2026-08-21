import { describe, expect, it } from "vitest";
import {
  getAvailabilityClass,
  getAvailabilityLabel,
  getConnectionHelpMessage,
  getSoftwareDisplayName,
} from "../lib/integrations-workspace";

describe("integrations workspace display helpers", () => {
  it("maps availability statuses to engineer-friendly labels", () => {
    expect(getAvailabilityLabel("AVAILABLE")).toBe("Available");
    expect(getAvailabilityLabel("NOT_INSTALLED")).toBe("Not installed");
  });

  it("provides Persian guidance for unavailable software", () => {
    expect(getAvailabilityLabel("REQUIRES_LOCAL_SOFTWARE", "fa")).toContain("نرم");
  });

  it("builds readable software titles and help messages", () => {
    expect(getSoftwareDisplayName("ETABS", "23")).toBe("ETABS 23");
    expect(getConnectionHelpMessage("ETABS", "23", "NOT_INSTALLED")).toContain("Install/connect");
    expect(getAvailabilityClass("AVAILABLE")).toBe("status-pass");
  });
});
