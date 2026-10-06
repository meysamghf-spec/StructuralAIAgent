"use client";

import { parseMessageContent, renderInlineMarkdown } from "@/lib/chat";

type MessageContentProps = {
  content: string;
};

function InlineText({ text }: { text: string }) {
  const parts = renderInlineMarkdown(text);
  return (
    <>
      {parts.map((part, index) =>
        typeof part === "string" ? (
          <span key={index}>{part}</span>
        ) : (
          <strong key={index}>{part.bold}</strong>
        ),
      )}
    </>
  );
}

export function MessageContent({ content }: MessageContentProps) {
  const blocks = parseMessageContent(content);

  return (
    <div className="chat-message-content">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return (
            <h3 key={index} className="chat-message-heading">
              <InlineText text={block.text} />
            </h3>
          );
        }
        if (block.type === "list-item") {
          return (
            <p key={index} className="chat-message-list-item">
              <span className="chat-message-bullet">•</span>
              <InlineText text={block.text} />
            </p>
          );
        }
        if (!block.text.trim()) {
          return <p key={index} className="chat-message-spacer">&nbsp;</p>;
        }
        return (
          <p key={index}>
            <InlineText text={block.text} />
          </p>
        );
      })}
    </div>
  );
}
