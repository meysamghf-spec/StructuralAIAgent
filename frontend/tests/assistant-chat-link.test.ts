import { describe, expect, it } from "vitest";

import { assistantChatHref, buildAssistantProfiles } from "../lib/agent-workspace";
import { assistantContext } from "../lib/assistant-context";

describe("assistants are real, not 'In setup'", () => {
  it("treats DRAFT auto-provisioned registrations as Available with a real description", () => {
    const profiles = buildAssistantProfiles([
      {
        id: "a1",
        name: "Analysis",
        agent_type: "ANALYSIS_AGENT",
        status: "DRAFT",
        description: "Auto-provisioned handler for ANALYSIS_AGENT",
      } as never,
    ]);
    const analysis = profiles.find((p) => p.agentType === "ANALYSIS_AGENT");
    expect(analysis?.status).toBe("Available");
    expect(analysis?.description).not.toMatch(/auto-provisioned/i);
    expect(profiles.some((p) => (p.status as string) === "In setup")).toBe(false);
    expect(profiles.some((p) => p.agentType === "OPTIMIZATION_AGENT")).toBe(true);
  });

  it("builds the chat deep link with assistant and project", () => {
    expect(assistantChatHref("ANALYSIS_AGENT", "p-1")).toBe("/?assistant=ANALYSIS_AGENT&project=p-1");
    expect(assistantChatHref("SEISMIC_AGENT")).toBe("/?assistant=SEISMIC_AGENT");
  });

  it("has starter prompts in English and Persian for each assistant", () => {
    const ctx = assistantContext("load_assessment_agent");
    expect(ctx?.starters.en.length).toBeGreaterThan(0);
    expect(ctx?.starters.fa.length).toBeGreaterThan(0);
    expect(assistantContext("nope")).toBeNull();
  });
});
