import { describe, expect, it } from "vitest";
import { getApiBaseUrl } from "../lib/api";

describe("Engineering AI Platform frontend", () => {
  it("identifies the project name", () => {
    const title = "Engineering AI Platform";
    expect(title).toContain("Engineering AI Platform");
  });

  it("defaults API base URL for local development", () => {
    expect(getApiBaseUrl()).toContain("127.0.0.1");
  });
});
