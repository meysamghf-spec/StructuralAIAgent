/**
 * Scroll policy for chat threads: when an assistant reply arrives (streaming or not) the START of the reply
 * is brought into view instead of jumping to the end of a long answer. Pure helpers, no DOM access in the
 * planner, so the behaviour is unit-testable without a browser.
 */

export type RoleLike = { role: string };

/** Index of the assistant reply that belongs to the latest user message, or -1 when there is none yet. */
export function replyMessageIndex(messages: RoleLike[]): number {
  let lastUser = -1;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === "user") {
      lastUser = i;
      break;
    }
  }
  if (lastUser === -1) {
    return -1;
  }
  for (let i = messages.length - 1; i > lastUser; i -= 1) {
    if (messages[i].role === "assistant") {
      return i;
    }
  }
  return -1;
}

/** Index of the latest user message (the question the current answer belongs to), or -1. */
export function lastUserMessageIndex(messages: RoleLike[]): number {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === "user") {
      return i;
    }
  }
  return -1;
}

/** Number of user messages; it grows by exactly one when the user sends (optimistic -> real swaps keep it stable). */
export function countUserMessages(messages: RoleLike[]): number {
  return messages.reduce((n, m) => (m.role === "user" ? n + 1 : n), 0);
}

export type ReplyScrollInput = {
  scrollTop: number;
  clientHeight: number;
  scrollHeight: number;
  /** Top of the question (start of the block) measured from the top of the scroller's content (not the viewport). */
  replyTop: number;
  /** Height from the top of the question to the bottom of the (growing) answer. */
  replyHeight: number;
  /** Space kept above the question's first line (sticky headers / scroll-padding + a small gap). */
  topOffset: number;
  /** Space kept below the reply while it still fits on screen. */
  bottomGap?: number;
  /** True once the start of a long reply has been aligned; nothing else is scrolled afterwards. */
  pinned: boolean;
};

export type ReplyScrollPlan = { top: number | null; pinned: boolean };

/**
 * "Reply block" = the user's question plus the assistant answer below it. `replyTop`/`replyHeight` describe that
 * whole block, so the question's first line is what gets aligned to the top.
 * - Block fits in the viewport (short answer): keep it fully visible, never scroll upwards (same as before).
 * - Block is taller than the viewport: align the question's first line to the top once, then leave the scroll alone so
 *   the reader can read while it streams.
 */
export function planReplyScroll(input: ReplyScrollInput): ReplyScrollPlan {
  if (input.pinned) {
    return { top: null, pinned: true };
  }
  const bottomGap = input.bottomGap ?? 16;
  const maxTop = Math.max(0, input.scrollHeight - input.clientHeight);
  if (input.replyHeight + input.topOffset > input.clientHeight) {
    const top = Math.min(maxTop, Math.max(0, Math.round(input.replyTop - input.topOffset)));
    return { top: Math.abs(top - input.scrollTop) < 1 ? null : top, pinned: true };
  }
  const bottomTarget = Math.min(
    maxTop,
    Math.ceil(input.replyTop + input.replyHeight + bottomGap - input.clientHeight),
  );
  if (bottomTarget > input.scrollTop + 1) {
    return { top: bottomTarget, pinned: false };
  }
  return { top: null, pinned: false };
}

const SCROLL_KEYS = new Set(["PageUp", "PageDown", "Home", "End", "ArrowUp", "ArrowDown", " ", "Spacebar"]);

/** Keys that scroll the page by hand — ignored while typing in the composer. */
export function isManualScrollKey(key: string, targetTag?: string | null, editable = false): boolean {
  if (!SCROLL_KEYS.has(key)) {
    return false;
  }
  const tag = (targetTag ?? "").toLowerCase();
  if (editable || tag === "input" || tag === "textarea" || tag === "select") {
    return false;
  }
  return true;
}
