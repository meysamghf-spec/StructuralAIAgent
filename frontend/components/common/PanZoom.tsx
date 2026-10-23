"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

type T = { x: number; y: number; k: number };
const MIN = 0.5;
const MAX = 20;
const clampK = (k: number) => Math.min(MAX, Math.max(MIN, k));

/**
 * Generic pan/zoom surface: one-finger / mouse drag pans, two-finger pinch and
 * mouse wheel zoom around the gesture point, double-tap/double-click toggles 2.5x,
 * Reset button returns to fit. touch-action:none so page scroll never hijacks it.
 */
export function PanZoom({ children, height = 360, className = "" }: { children: ReactNode; height?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [t, setT] = useState<T>({ x: 0, y: 0, k: 1 });
  const tRef = useRef(t);
  tRef.current = t;
  const pts = useRef(new Map<number, { x: number; y: number }>());
  const last = useRef<{ cx: number; cy: number; dist: number } | null>(null);
  const lastTap = useRef(0);

  const zoomAt = useCallback((px: number, py: number, factor: number) => {
    setT((p) => {
      const k = clampK(p.k * factor);
      const f = k / p.k;
      return { k, x: px - (px - p.x) * f, y: py - (py - p.y) * f };
    });
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY > 0 ? 1 / 1.15 : 1.15);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  const gesture = () => {
    const a = [...pts.current.values()];
    if (a.length === 0) return null;
    if (a.length === 1) return { cx: a[0].x, cy: a[0].y, dist: 0 };
    return { cx: (a[0].x + a[1].x) / 2, cy: (a[0].y + a[1].y) / 2, dist: Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y) };
  };

  const reset = () => setT({ x: 0, y: 0, k: 1 });

  return (
    <div className={`panzoom ${className}`} style={{ height }}>
      <div
        ref={ref}
        className="panzoom-surface"
        data-testid="panzoom-surface"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          const r = e.currentTarget.getBoundingClientRect();
          pts.current.set(e.pointerId, { x: e.clientX - r.left, y: e.clientY - r.top });
          last.current = gesture();
          if (pts.current.size === 1) {
            const now = Date.now();
            if (now - lastTap.current < 300) {
              const p = last.current!;
              if (tRef.current.k > 1.05) reset();
              else zoomAt(p.cx, p.cy, 2.5);
              lastTap.current = 0;
            } else lastTap.current = now;
          }
        }}
        onPointerMove={(e) => {
          if (!pts.current.has(e.pointerId)) return;
          const r = e.currentTarget.getBoundingClientRect();
          pts.current.set(e.pointerId, { x: e.clientX - r.left, y: e.clientY - r.top });
          const g = gesture();
          const l = last.current;
          if (!g || !l) return;
          setT((p) => {
            let { x, y, k } = p;
            if (g.dist && l.dist) {
              const nk = clampK(k * (g.dist / l.dist));
              const f = nk / k;
              x = l.cx - (l.cx - x) * f;
              y = l.cy - (l.cy - y) * f;
              k = nk;
            }
            return { k, x: x + g.cx - l.cx, y: y + g.cy - l.cy };
          });
          last.current = g;
        }}
        onPointerUp={(e) => {
          pts.current.delete(e.pointerId);
          last.current = gesture();
        }}
        onPointerCancel={(e) => {
          pts.current.delete(e.pointerId);
          last.current = gesture();
        }}
      >
        <div className="panzoom-content" style={{ transform: `translate(${t.x}px, ${t.y}px) scale(${t.k})` }}>
          {children}
        </div>
      </div>
      <div className="panzoom-controls">
        <button type="button" aria-label="Zoom in" onClick={() => { const r = ref.current!.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1.5); }}>+</button>
        <button type="button" aria-label="Zoom out" onClick={() => { const r = ref.current!.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1 / 1.5); }}>−</button>
        <button type="button" aria-label="Reset view" onClick={reset}>⟲</button>
      </div>
    </div>
  );
}
