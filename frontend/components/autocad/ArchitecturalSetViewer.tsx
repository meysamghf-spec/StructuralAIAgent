"use client";

import { DxfViewer } from "@/components/cad/DxfViewer";
import { downloadArchFile, fetchArchFile, type ArchSetMeta } from "@/lib/autocad";
import { useEffect, useRef, useState } from "react";

/** One architectural set: sheet tabs, rendered preview (pan/zoom) or live DXF viewer, downloads. */
export function ArchitecturalSetViewer({ set, compact = false }: { set: ArchSetMeta; compact?: boolean }) {
  const [idx, setIdx] = useState(0);
  const [mode, setMode] = useState<"render" | "dxf">("render");
  const [img, setImg] = useState<string | null>(null);
  const [dxf, setDxf] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [view, setView] = useState({ s: 1, x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);
  const sheet = set.sheets[idx];

  useEffect(() => {
    let url: string | null = null;
    let live = true;
    setImg(null); setDxf(null); setErr(""); setView({ s: 1, x: 0, y: 0 });
    if (!sheet) return;
    if (mode === "render" && sheet.png) {
      fetchArchFile(set.id, sheet.png)
        .then((b) => { url = URL.createObjectURL(b); if (live) setImg(url); })
        .catch((e) => live && setErr(String(e?.message ?? e)));
    } else {
      fetchArchFile(set.id, sheet.dxf).then((b) => b.text()).then((t) => live && setDxf(t))
        .catch((e) => live && setErr(String(e?.message ?? e)));
    }
    return () => { live = false; if (url) URL.revokeObjectURL(url); };
  }, [set.id, sheet, mode]);

  const dl = async (name: string) => {
    setBusy(name);
    try { await downloadArchFile(set.id, name); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    setBusy("");
  };
  const zoom = (f: number) => setView((v) => ({ ...v, s: Math.min(12, Math.max(1, v.s * f)) }));

  return (
    <div className="arch-set" data-testid="arch-set">
      <div className="arch-tabs" role="tablist">
        {set.sheets.map((s, i) => (
          <button key={s.no} type="button" role="tab" aria-selected={i === idx}
            className={`arch-tab${i === idx ? " active" : ""}`} onClick={() => setIdx(i)} title={`${s.title_en} — ${s.title_fa}`}>
            <b>{s.no}</b> <span>{s.title_en}</span>
          </button>
        ))}
      </div>
      {sheet ? (
        <>
          <div className="arch-toolbar">
            <span className="arch-title">{sheet.no} · {sheet.title_en} · <span dir="rtl">{sheet.title_fa}</span>{sheet.scale > 1 ? ` · 1:${sheet.scale}` : ""}</span>
            <span className="arch-actions">
              {sheet.png ? (
                <button type="button" className="button secondary small" onClick={() => setMode(mode === "render" ? "dxf" : "render")}>
                  {mode === "render" ? "Layers view" : "Rendered view"}
                </button>
              ) : null}
              {mode === "render" ? (
                <>
                  <button type="button" className="button secondary small" onClick={() => zoom(1.4)} aria-label="Zoom in">+</button>
                  <button type="button" className="button secondary small" onClick={() => zoom(1 / 1.4)} aria-label="Zoom out">−</button>
                  <button type="button" className="button secondary small" onClick={() => setView({ s: 1, x: 0, y: 0 })}>Fit</button>
                </>
              ) : null}
              <button type="button" className="button small" disabled={!!busy} onClick={() => dl(sheet.dxf)}>DXF</button>
              {sheet.pdf ? <button type="button" className="button secondary small" disabled={!!busy} onClick={() => dl(sheet.pdf!)}>PDF</button> : null}
            </span>
          </div>
          {err ? <p className="alert error">{err}</p> : null}
          {mode === "render" && sheet.png ? (
            <div className="arch-canvas" style={{ height: compact ? 300 : undefined }}
              onWheel={(e) => { e.preventDefault(); zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15); }}
              onPointerDown={(e) => { drag.current = { x: e.clientX - view.x, y: e.clientY - view.y }; (e.target as Element).setPointerCapture?.(e.pointerId); }}
              onPointerMove={(e) => { if (drag.current) { const d = drag.current; setView((v) => ({ ...v, x: e.clientX - d.x, y: e.clientY - d.y })); } }}
              onPointerUp={() => { drag.current = null; }}>
              {img ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={img} alt={`${sheet.no} ${sheet.title_en}`} draggable={false}
                  style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})` }} />
              ) : <p className="muted">Loading sheet…</p>}
            </div>
          ) : dxf ? (
            <DxfViewer text={dxf} filename={sheet.dxf} height={compact ? 300 : 520} />
          ) : !err ? <p className="muted">Loading DXF…</p> : null}
        </>
      ) : null}
      <div className="button-row arch-downloads">
        {set.pdf ? <button type="button" className="button" disabled={!!busy} onClick={() => dl(set.pdf!)}>Combined PDF</button> : null}
        {set.zip ? <button type="button" className="button secondary" disabled={!!busy} onClick={() => dl(set.zip!)}>All DXF + PDF (ZIP)</button> : null}
      </div>
    </div>
  );
}
