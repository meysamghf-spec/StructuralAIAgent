import { describe, expect, it } from "vitest";

import { parseMessageContent } from "@/lib/chat";

describe("chat markdown", () => {
  it("parses pipe tables with alignment, headings and lists", () => {
    const md = ["## نتایج", "| Story | Drift | OK |", "|:---|---:|:--:|", "| 1 | 0.0042 | ✓ |", "| 2 | 0.0051 | ✓ |", "", "1. first", "- bullet"].join("\n");
    const b = parseMessageContent(md);
    expect(b[0]).toEqual({ type: "heading", text: "نتایج", level: 2 });
    expect(b[1]).toEqual({ type: "table", header: ["Story", "Drift", "OK"], rows: [["1", "0.0042", "✓"], ["2", "0.0051", "✓"]], align: ["left", "right", "center"] });
    expect(b[3]).toEqual({ type: "ordered-item", n: "1", text: "first" });
    expect(b[4]).toEqual({ type: "list-item", text: "bullet" });
  });

  it("keeps plain lines with pipes as paragraphs when there is no separator row", () => {
    expect(parseMessageContent("a | b")).toEqual([{ type: "paragraph", text: "a | b" }]);
  });
});
