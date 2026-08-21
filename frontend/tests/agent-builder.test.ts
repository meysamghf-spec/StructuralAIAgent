import { describe, expect, it } from "vitest";
import {
  getAssistantTypeLabel,
  getLifecycleLabel,
  getLifecycleStage,
  getPublicationStatusLabel,
  getVersionStatusLabel,
} from "../lib/agent-builder";

describe("agent builder display helpers", () => {
  it("maps assistant types to engineer-friendly labels", () => {
    expect(getAssistantTypeLabel("VALIDATION_AGENT")).toBe("Design validation");
    expect(getAssistantTypeLabel(null)).toBe("Not selected");
  });

  it("maps version and publication statuses without enum noise", () => {
    expect(getVersionStatusLabel("DRAFT")).toBe("Draft");
    expect(getPublicationStatusLabel("PENDING_APPROVAL")).toBe("Awaiting review");
  });

  it("derives lifecycle stages for the builder UI", () => {
    expect(getLifecycleStage("DRAFT", false)).toBe("draft");
    expect(getLifecycleStage("DRAFT", true)).toBe("tested");
    expect(getLifecycleStage("DRAFT", false, "PENDING_APPROVAL")).toBe("review");
    expect(getLifecycleStage("ACTIVE", true)).toBe("active");
    expect(getLifecycleLabel("review")).toBe("Review");
  });
});
