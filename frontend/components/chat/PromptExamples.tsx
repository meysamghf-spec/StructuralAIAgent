"use client";

import { ENGINEERING_PROMPT_EXAMPLES } from "@/lib/chat-types";

type PromptExamplesProps = {
  onSelect: (text: string) => void;
  disabled?: boolean;
};

export function PromptExamples({ onSelect, disabled = false }: PromptExamplesProps) {
  return (
    <div className="chat-prompt-examples-wrap">
      <p className="chat-prompt-examples-label">Example engineering tasks</p>
      <div className="chat-prompt-examples" role="group" aria-label="Example engineering prompts">
        {ENGINEERING_PROMPT_EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            className="chat-prompt-example"
            disabled={disabled}
            aria-label={`Use example prompt: ${example}`}
            onClick={() => onSelect(example)}
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
