import { describe, expect, it } from "vitest";
import { parseMessageContent, renderInlineMarkdown } from "@/lib/chat";

describe("rich chat markdown", () => {
  it("parses fenced code, including an unclosed streaming fence", () => {
    const blocks = parseMessageContent("Hi\n```python\nx = 1\n```\nbye");
    expect(blocks[1]).toEqual({ type: "code", lang: "python", text: "x = 1" });
    expect(blocks[2]).toEqual({ type: "paragraph", text: "bye" });
    expect(parseMessageContent("```\nopen")[0]).toEqual({ type: "code", lang: "", text: "open" });
  });
  it("renders inline code, italic, links and keeps $math$ untouched", () => {
    const parts = renderInlineMarkdown("Use `Mu` and *this* see [docs](https://x.io/a) with $M_u * phi$ done");
    expect(parts).toContainEqual({ code: "Mu" });
    expect(parts).toContainEqual({ italic: "this" });
    expect(parts).toContainEqual({ link: "docs", href: "https://x.io/a" });
    expect(parts).toContain("$M_u * phi$");
  });
  it("keeps bold and block quotes", () => {
    expect(renderInlineMarkdown("a **b** c")).toContainEqual({ bold: "b" });
    expect(parseMessageContent("> note")[0]).toEqual({ type: "quote", text: "note" });
  });
});
