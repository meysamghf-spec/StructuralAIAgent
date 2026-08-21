import { describe, expect, it } from "vitest";
import { buildAssistantProfiles } from "../lib/agent-workspace";

describe("agent workspace loading expectations", () => {
  it("loads friendly assistant profiles without enum names", () => {
    const profiles = buildAssistantProfiles([]);
    expect(profiles.length).toBeGreaterThan(0);
    expect(profiles.every((profile) => !profile.title.includes("_AGENT"))).toBe(true);
  });
});
