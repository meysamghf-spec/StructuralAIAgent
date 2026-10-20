import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Layout can't be measured in jsdom, so this guards the CSS contract behind independent pane scrolling
// (browser-verified with a headless Chrome run; see PR). The scroll block is appended last so it wins the cascade.
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");
const block = css.slice(css.indexOf("Independent-scroll app shell"));

function rule(selectorPart: string): string {
  const re = new RegExp(`(^|\\n)[^{}]*${selectorPart.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[^{}]*\\{([^}]*)\\}`, "g");
  return Array.from(block.matchAll(re)).map((m) => m[2]).join(";");
}

describe("independent-scroll shell CSS", () => {
  it("locks the document so the window never scrolls", () => {
    expect(rule("body")).toMatch(/height:\s*100%/);
    expect(rule("body")).toMatch(/overflow:\s*hidden/);
  });

  it("sizes shells to the viewport with dvh", () => {
    for (const s of [".shell", ".chat-shell", ".chat-root"]) {
      expect(rule(s)).toMatch(/height:\s*100dvh/);
    }
  });

  it("makes every pane its own scroll container with min-height 0", () => {
    for (const s of [".sidebar", ".chat-sidebar", ".chat-context-panel", ".content", ".chat-main-body"]) {
      const r = rule(s);
      expect(r, s).toMatch(/min-height:\s*0/);
      expect(r, s).toMatch(/overflow-y:\s*auto/);
    }
  });

  it("pins the composer: chat main clips, only the thread body scrolls", () => {
    expect(rule(".chat-main")).toMatch(/overflow:\s*hidden/);
    expect(rule(".chat-composer")).toMatch(/flex:\s*0 0 auto/);
  });
});
