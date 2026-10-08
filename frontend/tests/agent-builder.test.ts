import { describe, expect, it } from "vitest";
import {
  getAssistantTypeLabel,
  getLifecycleLabel,
  getLifecycleStage,
  getProductLifecycle,
  getProductLifecycleLabel,
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

  it("maps persisted version state onto the product lifecycle", () => {
    expect(getProductLifecycle("DRAFT")).toBe("DRAFT");
    expect(getProductLifecycle("DRAFT", "PENDING_APPROVAL")).toBe("REVIEW");
    expect(getProductLifecycle("ACTIVE", null, "APPROVED")).toBe("PUBLISHED");
    expect(getProductLifecycle("INACTIVE", null, "APPROVED")).toBe("APPROVED");
    expect(getProductLifecycle("ARCHIVED")).toBe("ARCHIVED");
    expect(getProductLifecycleLabel("PUBLISHED")).toBe("Published");
  });
});
