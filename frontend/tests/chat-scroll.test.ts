import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { countUserMessages, isManualScrollKey, lastUserMessageIndex, planReplyScroll, replyMessageIndex } from "@/lib/chat-scroll";

const base = { scrollTop: 0, clientHeight: 600, scrollHeight: 2000, replyTop: 900, replyHeight: 200, topOffset: 8, pinned: false };

describe("replyMessageIndex / countUserMessages", () => {
  it("finds the assistant reply that follows the latest user message", () => {
    const msgs = [{ role: "user" }, { role: "assistant" }, { role: "user" }, { role: "assistant" }];
    expect(replyMessageIndex(msgs)).toBe(3);
    expect(countUserMessages(msgs)).toBe(2);
  });
  it("finds the question (latest user message) the answer belongs to", () => {
    expect(lastUserMessageIndex([{ role: "user" }, { role: "assistant" }, { role: "user" }, { role: "assistant" }])).toBe(2);
    expect(lastUserMessageIndex([{ role: "assistant" }])).toBe(-1);
  });
  it("returns -1 while the reply has not started yet (placeholder phase) or with no messages", () => {
    expect(replyMessageIndex([{ role: "user" }, { role: "assistant" }, { role: "user" }])).toBe(-1);
    expect(replyMessageIndex([])).toBe(-1);
    expect(replyMessageIndex([{ role: "assistant" }])).toBe(-1);
  });
});

describe("planReplyScroll", () => {
  it("long answer: aligns the first line of the QUESTION (block start) to the top, not the end, and pins", () => {
    const plan = planReplyScroll({ ...base, replyHeight: 1500, scrollHeight: 2600 });
    expect(plan).toEqual({ top: 892, pinned: true });
  });

  it("long answer is clamped to the scrollable range", () => {
    const plan = planReplyScroll({ ...base, replyTop: 5300, replyHeight: 900, scrollHeight: 5800 });
    expect(plan.top).toBe(5200);
    expect(plan.pinned).toBe(true);
  });

  it("once pinned nothing else is scrolled while the answer keeps streaming (no fighting the reader)", () => {
    expect(planReplyScroll({ ...base, replyHeight: 3000, scrollTop: 1200, pinned: true })).toEqual({ top: null, pinned: true });
  });

  it("short answer: keeps it fully visible like before and does not pin", () => {
    const plan = planReplyScroll({ ...base, scrollTop: 300, replyHeight: 150, scrollHeight: 1200 });
    expect(plan.pinned).toBe(false);
    expect(plan.top).toBe(900 + 150 + 16 - 600);
  });

  it("short answer already visible: no scroll, and never scrolls upwards", () => {
    expect(planReplyScroll({ ...base, scrollTop: 700, replyTop: 900, replyHeight: 100 })).toEqual({ top: null, pinned: false });
  });

  it("a short answer that grows past the viewport switches to start-aligned exactly once", () => {
    const small = planReplyScroll({ ...base, replyHeight: 120 });
    expect(small.pinned).toBe(false);
    const grown = planReplyScroll({ ...base, scrollTop: small.top ?? 0, replyHeight: 640, scrollHeight: 2000 });
    expect(grown).toEqual({ top: 892, pinned: true });
  });

  it("accounts for a sticky header / scroll-padding via topOffset", () => {
    const plan = planReplyScroll({ ...base, replyHeight: 1500, scrollHeight: 2600, topOffset: 72 });
    expect(plan.top).toBe(828);
  });

  it("never returns a negative target (reply at the very top)", () => {
    expect(planReplyScroll({ ...base, replyTop: 0, scrollTop: 300, replyHeight: 1500, scrollHeight: 2600 }).top).toBe(0);
  });
});

describe("isManualScrollKey", () => {
  it("treats paging keys as manual scrolling but not while typing in the composer", () => {
    expect(isManualScrollKey("PageDown", "DIV")).toBe(true);
    expect(isManualScrollKey("End", "BODY")).toBe(true);
    expect(isManualScrollKey("ArrowDown", "TEXTAREA")).toBe(false);
    expect(isManualScrollKey(" ", "DIV", true)).toBe(false);
    expect(isManualScrollKey("a", "DIV")).toBe(false);
  });
});

describe("ChatThread wiring (source guard)", () => {
  const src = readFileSync(join(__dirname, "..", "components", "chat", "ChatThread.tsx"), "utf8");
  it("marks the reply element, plans the scroll from the reply start, and listens for manual scrolling", () => {
    expect(src).toContain('data-chat-reply');
    expect(src).toContain('data-chat-question');
    expect(src).toContain("planReplyScroll");
    expect(src).toMatch(/addEventListener\("wheel"/);
    expect(src).toMatch(/addEventListener\("touchmove"/);
  });
  it("no longer jumps to the end on every message update while a reply is being tracked", () => {
    expect(src).toContain("turnRef.current.active");
  });
});
