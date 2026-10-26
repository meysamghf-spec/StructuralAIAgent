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
        ) : "bold" in part ? (
          <strong key={index}>{part.bold}</strong>
        ) : "italic" in part ? (
          <em key={index}>{part.italic}</em>
        ) : "code" in part ? (
          <code key={index} className="chat-md-inline-code">{part.code}</code>
        ) : (
          <a key={index} href={part.href} target="_blank" rel="noopener noreferrer">{part.link}</a>
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
        if (block.type === "code") {
          return (
            <div key={index} className="chat-md-code" dir="ltr">
              <div className="chat-md-code-head">
                <span>{block.lang || "code"}</span>
                <button type="button" className="chat-md-code-copy" onClick={() => void navigator.clipboard?.writeText(block.text)}>
                  Copy
                </button>
              </div>
              <pre><code>{block.text}</code></pre>
            </div>
          );
        }
        if (block.type === "quote") {
          return (
            <blockquote key={index} className="chat-md-quote" dir="auto">
              <InlineText text={block.text} />
            </blockquote>
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
          <p key={index} dir="auto">
            <InlineText text={block.text} />
          </p>
        );
      })}
    </div>
  );
}
