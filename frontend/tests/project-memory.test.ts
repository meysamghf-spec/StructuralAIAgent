import { describe, expect, it } from "vitest";

import { projectMemoryLabel } from "@/lib/project-memory";

describe("projectMemoryLabel", () => {
  it("shows empty state in fa/en", () => {
    expect(projectMemoryLabel(null, true)).toContain("خالی");
    expect(projectMemoryLabel(null, false)).toContain("empty");
  });
  it("shows counts", () => {
    const m = { project_id: "p", text: "x", stats: { conversations: 2, messages: 9, recent_verbatim: 9, summarized: 0, facts: 1, chars: 1 } };
    expect(projectMemoryLabel(m, false)).toBe("Project memory: 2 other chats, 9 messages");
    expect(projectMemoryLabel(m, true)).toContain("9 پیام");
  });
});
