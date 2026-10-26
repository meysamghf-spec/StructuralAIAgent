import { describe, expect, it } from "vitest";
import { parseChatActionMeta, parseChatDownloads } from "@/lib/chat-actions";

describe("chat actions metadata", () => {
  it("parses a ZIP download command", () => {
    const d = parseChatDownloads({ chat_downloads: { zip: true, items: [], inputs: { storeys: 3 }, project_id: "p1", lang: "fa", assumed: ["3 storeys"] } });
    expect(d).toMatchObject({ zip: true, projectId: "p1", lang: "fa", assumed: ["3 storeys"] });
  });
  it("parses specific files and drops malformed items", () => {
    const d = parseChatDownloads({ chat_downloads: { zip: false, items: [{ kind: "model", name: "e2k", format: "e2k", label: "ETABS" }, { kind: "x" }] } });
    expect(d?.items).toHaveLength(1);
    expect(d?.lang).toBe("en");
  });
  it("ignores messages without downloads", () => {
    expect(parseChatDownloads({ mode: "agent_execution" })).toBeNull();
    expect(parseChatDownloads({ chat_downloads: { zip: false, items: [] } })).toBeNull();
  });
  it("parses assistant and project switches", () => {
    const a = parseChatActionMeta({ switch_assistant: "SEISMIC_AGENT", project_switch: { id: "x", name: "Tower" } });
    expect(a.switchAssistant).toBe("SEISMIC_AGENT");
    expect(a.projectSwitch).toEqual({ id: "x", name: "Tower" });
    expect(parseChatActionMeta({}).projectSwitch).toBeNull();
  });
});
