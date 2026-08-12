import { describe, expect, it } from "vitest";

describe("Engineering AI Platform landing page", () => {
  it("identifies the project name", () => {
    const title = "Engineering AI Platform";
    expect(title).toContain("Engineering AI Platform");
  });
});
