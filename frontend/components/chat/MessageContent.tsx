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
          const Tag = (block.level && block.level > 3 ? "h4" : "h3") as "h3" | "h4";
          return (
            <Tag key={index} className="chat-message-heading">
              <InlineText text={block.text} />
            </Tag>
          );
        }
        if (block.type === "table") {
          return (
            <div key={index} className="chat-md-table-wrap" tabIndex={0}>
              <table className="chat-md-table">
                <thead>
                  <tr>
                    {block.header.map((c, k) => (
                      <th key={k} style={block.align[k] ? { textAlign: block.align[k]! } : undefined}>
                        <InlineText text={c} />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((r, ri) => (
                    <tr key={ri}>
                      {r.map((c, k) => (
                        <td key={k} style={block.align[k] ? { textAlign: block.align[k]! } : undefined}>
                          <InlineText text={c} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (block.type === "ordered-item") {
          return (
            <p key={index} className="chat-message-list-item">
              <span className="chat-message-bullet">{block.n}.</span>
              <InlineText text={block.text} />
            </p>
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
