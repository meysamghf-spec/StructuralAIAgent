"use client";

import { assistantContext } from "@/lib/assistant-context";

type Props = {
  assistant: string;
  onPick: (text: string) => void;
  onClear: () => void;
  disabled?: boolean;
};

const hasFa = (value: string) => /[\u0600-\u06ff]/.test(value);

export function AssistantContextStrip({ assistant, onPick, onClear, disabled }: Props) {
  const ctx = assistantContext(assistant);
  if (!ctx) {
    return null;
  }
  const fa = typeof navigator !== "undefined" && /^fa/i.test(navigator.language ?? "");
  const starters = fa ? ctx.starters.fa : ctx.starters.en;
  return (
    <div className="assistant-strip" data-testid="assistant-strip">
      <div className="assistant-strip-head">
        <span className="assistant-strip-badge">Assistant</span>
        <strong>{ctx.title.en}</strong>
        <span className="muted" dir="rtl">{ctx.title.fa}</span>
        <button type="button" className="chat-attachment-remove" onClick={onClear} aria-label="Leave assistant mode">
          Leave
        </button>
      </div>
      <div className="assistant-strip-starters">
        {starters.map((text) => (
          <button
            key={text}
            type="button"
            className="button secondary assistant-starter"
            dir={hasFa(text) ? "rtl" : "ltr"}
            disabled={disabled}
            onClick={() => onPick(text)}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
