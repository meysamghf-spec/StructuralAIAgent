"use client";

import { parseMessageContent, renderInlineMarkdown } from "@/lib/chat";
import { chatT, detectLang, dirOf, isRtl, splitBidiRuns, type ChatLang } from "@/lib/chat-i18n";

type MessageContentProps = {
  content: string;
  /** Language of the message (backend tag / detection). Defaults to detecting it from the content. */
  lang?: ChatLang | null;
};

/** Text with numbers, units, paths and Latin words kept as LTR runs inside RTL text. */
function BidiText({ text, rtl }: { text: string; rtl: boolean }) {
  if (!rtl) {
    return <>{text}</>;
  }
  return (
    <>
      {splitBidiRuns(text).map((run, index) =>
        run.ltr ? (
          <bdi key={index} dir="ltr" className="chat-ltr-run">{run.text}</bdi>
        ) : (
          <span key={index}>{run.text}</span>
        ),
      )}
    </>
  );
}

function InlineText({ text, rtl = false }: { text: string; rtl?: boolean }) {
  const parts = renderInlineMarkdown(text);
  return (
    <>
      {parts.map((part, index) =>
        typeof part === "string" ? (
          <BidiText key={index} text={part} rtl={rtl} />
        ) : "bold" in part ? (
          <strong key={index}><BidiText text={part.bold} rtl={rtl} /></strong>
        ) : "italic" in part ? (
          <em key={index}><BidiText text={part.italic} rtl={rtl} /></em>
        ) : "code" in part ? (
          <code key={index} className="chat-md-inline-code" dir={detectLang(part.code) === "fa" ? "rtl" : "ltr"}>{part.code}</code>
        ) : (
          <a key={index} href={part.href} target="_blank" rel="noopener noreferrer"><BidiText text={part.link} rtl={rtl} /></a>
        ),
      )}
    </>
  );
}

export function MessageContent({ content, lang }: MessageContentProps) {
  const blocks = parseMessageContent(content);
  const base: ChatLang = lang ?? detectLang(content) ?? "en";
  // direction of one block: its own language, else the message language (so a bare "kN" line follows the message)
  const langOf = (text: string): ChatLang => detectLang(text) ?? base;

  return (
    <div className="chat-message-content" dir={dirOf(base)} lang={base} data-lang={base}>
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const Tag = (block.level && block.level > 3 ? "h4" : "h3") as "h3" | "h4";
          const hl = langOf(block.text);
          return (
            <Tag key={index} className="chat-message-heading" dir={dirOf(hl)}>
              <InlineText text={block.text} rtl={isRtl(hl)} />
            </Tag>
          );
        }
        if (block.type === "code") {
          return (
            <div key={index} className="chat-md-code" dir="ltr">
              <div className="chat-md-code-head">
                <span>{block.lang || "code"}</span>
                <button type="button" className="chat-md-code-copy" onClick={() => void navigator.clipboard?.writeText(block.text)}>
                  {chatT(base, "Copy")}
                </button>
              </div>
              <pre><code>{block.text}</code></pre>
            </div>
          );
        }
        if (block.type === "quote") {
          const ql = langOf(block.text);
          return (
            <blockquote key={index} className="chat-md-quote" dir={dirOf(ql)}>
              <InlineText text={block.text} rtl={isRtl(ql)} />
            </blockquote>
          );
        }
        if (block.type === "table") {
          // a Persian table reads right-to-left: the first column is on the right
          const tl = langOf([...block.header, ...block.rows.flat()].join(" "));
          const trtl = isRtl(tl);
          return (
            <div key={index} className="chat-md-table-wrap" tabIndex={0} dir={dirOf(tl)}>
              <table className="chat-md-table" dir={dirOf(tl)}>
                <thead>
                  <tr>
                    {block.header.map((c, k) => (
                      <th key={k} style={block.align[k] ? { textAlign: block.align[k]! } : undefined}>
                        <InlineText text={c} rtl={trtl} />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((r, ri) => (
                    <tr key={ri}>
                      {r.map((c, k) => (
                        <td key={k} style={block.align[k] ? { textAlign: block.align[k]! } : undefined}>
                          <InlineText text={c} rtl={trtl} />
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
          const ol = langOf(block.text);
          return (
            <p key={index} className="chat-message-list-item" dir={dirOf(ol)}>
              <bdi dir="ltr" className="chat-message-bullet">{block.n}.</bdi>
              <span className="chat-message-list-text"><InlineText text={block.text} rtl={isRtl(ol)} /></span>
            </p>
          );
        }
        if (block.type === "list-item") {
          const il = langOf(block.text);
          return (
            <p key={index} className="chat-message-list-item" dir={dirOf(il)}>
              <span className="chat-message-bullet" aria-hidden="true">•</span>
              <span className="chat-message-list-text"><InlineText text={block.text} rtl={isRtl(il)} /></span>
            </p>
          );
        }
        if (!block.text.trim()) {
          return <p key={index} className="chat-message-spacer">&nbsp;</p>;
        }
        const pl = langOf(block.text);
        return (
          <p key={index} dir={dirOf(pl)}>
            <InlineText text={block.text} rtl={isRtl(pl)} />
          </p>
        );
      })}
    </div>
  );
}
