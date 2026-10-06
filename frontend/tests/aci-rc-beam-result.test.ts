import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("AciRcBeamResultCard", () => {
  it("is a dedicated structured card and does not reuse the RC Demo visualization", () => {
    const card = readFileSync(resolve(__dirname, "../components/chat/AciRcBeamResultCard.tsx"), "utf8");
    const thread = readFileSync(resolve(__dirname, "../components/chat/ChatThread.tsx"), "utf8");
    const demoCard = readFileSync(resolve(__dirname, "../components/chat/EngineeringResultCard.tsx"), "utf8");

    expect(card).toContain("ACI 318 RC beam check");
    expect(card).toContain("Validation");
    expect(card).toContain("Units");
    expect(card).not.toContain("RCDemoVisualization");
    expect(card).not.toContain("setTimeout");
    expect(thread).toContain("AciRcBeamResultCard");
    expect(thread).toContain("EngineeringResultCard");
    expect(demoCard).toContain("RCDemoVisualization");
  });
});
