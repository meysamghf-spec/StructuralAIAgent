"use client";

import { useEffect, useRef, type TouchEvent } from "react";

/**
 * Mobile drawer dismissal: Back button (history state + popstate), Esc, swipe-left.
 * Returns touch handlers to spread on the drawer and backdrop.
 */
export function useDrawerDismiss(open: boolean, close: () => void) {
  const closeRef = useRef(close);
  closeRef.current = close;
  const pushed = useRef(false);

  useEffect(() => {
    if (!open) {
      pushed.current = false;
      return;
    }
    // Push one history entry so the phone Back button closes the drawer. If the drawer was closed
    // from the UI, its entry is left in place (calling history.back() races with reopening) and reused.
    if (!pushed.current && !window.history.state?.__drawer) {
      window.history.pushState({ ...(window.history.state ?? {}), __drawer: true }, "");
    }
    pushed.current = true;
    const onPop = () => {
      pushed.current = false;
      closeRef.current();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeRef.current();
    };
    window.addEventListener("popstate", onPop);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("popstate", onPop);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const start = useRef<{ x: number; y: number } | null>(null);
  return {
    onTouchStart: (e: TouchEvent) => {
      const t = e.touches[0];
      start.current = t ? { x: t.clientX, y: t.clientY } : null;
    },
    onTouchEnd: (e: TouchEvent) => {
      const s = start.current;
      const t = e.changedTouches[0];
      start.current = null;
      if (!s || !t) return;
      const dx = t.clientX - s.x;
      const dy = t.clientY - s.y;
      if (dx < -50 && Math.abs(dx) > Math.abs(dy) * 1.2) closeRef.current();
    },
  };
}
