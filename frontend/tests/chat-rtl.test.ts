import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AgentErrorCard } from "@/components/chat/AgentErrorCard";
import { AgentProgress } from "@/components/chat/AgentProgress";
import { MessageContent } from "@/components/chat/MessageContent";
import {
  chatT,
  conversationLang,
  detectLang,
  dirOf,
  messageLang,
  splitBidiRuns,
} from "@/lib/chat-i18n";

// components use the automatic JSX runtime under Next; vitest transpiles them with the classic one
(globalThis as unknown as { React: typeof React }).React = React;
const h = React.createElement;

describe("language detection", () => {
  it("detects Persian and English", () => {
    expect(detectLang("قاب ثبت نشده است")).toBe("fa");
    expect(detectLang("Optimize the frame")).toBe("en");
    expect(detectLang("1234 ./ 3.2")).toBeNull();
  });

  it("prefers the backend lang tag, then the text, then the fallback", () => {
    expect(messageLang("Status: completed", { lang: "fa" }, null)).toBe("fa");
    expect(messageLang("وضعیت: تکمیل شد", null, "en")).toBe("fa");
    expect(messageLang("12", null, "fa")).toBe("fa");
  });

  it("uses the last user message as the conversation language", () => {
    expect(
      conversationLang([
        { role: "user", content: "Hello" },
        { role: "user", content: "سازه را بهینه کن" },
      ]),
    ).toBe("fa");
  });

  it("maps lang to dir", () => {
    expect(dirOf("fa")).toBe("rtl");
    expect(dirOf("en")).toBe("ltr");
    expect(dirOf(null)).toBe("ltr");
  });
});

describe("bidi runs", () => {
  it("isolates numbers, units and paths", () => {
    const runs = splitBidiRuns("طول تیر 3.2 m و بار 10 kN در /workspace/model است");
    const ltr = runs.filter((r) => r.ltr).map((r) => r.text.trim());
    expect(ltr.join(" ")).toContain("3.2");
    expect(ltr.join(" ")).toContain("kN");
    expect(ltr.join(" ")).toContain("/workspace/model");
    expect(runs.map((r) => r.text).join("")).toBe("طول تیر 3.2 m و بار 10 kN در /workspace/model است");
  });
});

describe("chatT", () => {
  it("translates known Persian chrome and leaves English / unknown text alone", () => {
    expect(chatT("fa", "Copy")).not.toBe("Copy");
    expect(chatT("en", "Copy")).toBe("Copy");
    expect(chatT("fa", "some unknown free text")).toBe("some unknown free text");
    expect(chatT("fa", "COMPLETED")).toBe(chatT("fa", "completed"));
  });
});

describe("MessageContent RTL rendering", () => {
  const md = [
    "**وضعیت:** تکمیل شد",
    "",
    "## توصیه‌ها",
    "- طول 3.2 m را بررسی کنید",
    "1. مسیر /workspace/model",
    "",
    "| مقدار | واحد |",
    "| --- | --- |",
    "| 10 | kN |",
  ].join("\n");

  it("renders rtl container, rtl blocks and LTR-isolated runs", () => {
    const html = renderToStaticMarkup(h(MessageContent, { content: md, lang: "fa" }));
    expect(html).toContain('dir="rtl"');
    expect(html).toContain('<bdi dir="ltr" class="chat-ltr-run">');
    expect(html).toMatch(/<table[^>]*dir="rtl"/);
    expect(html).toContain("/workspace/model");
  });

  it("keeps English messages LTR with no bdi isolation", () => {
    const html = renderToStaticMarkup(
      h(MessageContent, { content: "**Status:** completed\n\n- beam 3.2 m", lang: "en" }),
    );
    expect(html).toContain('dir="ltr"');
    expect(html).not.toContain('dir="rtl"');
    expect(html).not.toContain("chat-ltr-run");
  });

  it("lets an English block inside a Persian message stay LTR", () => {
    const html = renderToStaticMarkup(
      h(MessageContent, { content: "سلام\n\nOptimize the frame now please", lang: "fa" }),
    );
    expect(html).toContain('dir="ltr"');
    expect(html).toContain('dir="rtl"');
  });
});

describe("cards", () => {
  it("AgentProgress is rtl and Persian for fa, unchanged for en", () => {
    const steps = [{ id: "1", label: "Understanding request", state: "completed" }] as never;
    const fa = renderToStaticMarkup(h(AgentProgress, { steps, lang: "fa" }));
    expect(fa).toContain('dir="rtl"');
    expect(fa).not.toContain("Understanding request");
    const en = renderToStaticMarkup(h(AgentProgress, { steps, lang: "en" }));
    expect(en).toContain("Understanding request");
    expect(en).not.toContain('dir="rtl"');
  });

  it("AgentErrorCard localizes known titles in Persian", () => {
    const html = renderToStaticMarkup(
      h(AgentErrorCard, { error: { title: "Engineering workflow failed", reason: "x" }, lang: "fa" }),
    );
    expect(html).toContain('dir="rtl"');
    expect(html).not.toContain("Engineering workflow failed");
  });
});

describe("bidi parenthesised Latin groups", () => {
  it("keeps 'INBC (Mabahes Melli)' as one LTR run", () => {
    const runs = splitBidiRuns("آیین‌نامه طراحی: INBC (Mabahes Melli) (تنظیم پروژه)");
    expect(runs.some((r) => r.ltr && r.text === "INBC (Mabahes Melli)")).toBe(true);
    expect(runs.map((r) => r.text).join("")).toBe("آیین‌نامه طراحی: INBC (Mabahes Melli) (تنظیم پروژه)");
  });
});
