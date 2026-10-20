"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { bounds, filterEntities, layerColor, parseDxf, project, type Projection } from "@/lib/dxf";
import { useUiLang } from "@/hooks/useUiLang";

/** Built-in DXF viewer: layer toggles, sheet/story selector, pan (drag) / zoom (wheel), fit, download. */
export function DxfViewer({ text, filename, height = 560 }: { text: string; filename: string; height?: number }) {
  const { t } = useUiLang();
  const doc = useMemo(() => parseDxf(text), [text]);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [sheetIdx, setSheetIdx] = useState<number>(-1);
  const [proj, setProj] = useState<Projection>(doc.is3d ? "iso" : "top");
  const visible = useMemo(() => new Set(doc.layers.filter((l) => !hidden.has(l))), [doc, hidden]);
  const sheet = sheetIdx >= 0 ? doc.sheets[sheetIdx] ?? null : null;
  const ents = useMemo(() => filterEntities(doc, visible, sheet), [doc, visible, sheet]);
  const fit = useMemo(() => {
    const [x, y, w, h] = bounds(ents, proj);
    const pad = Math.max(w, h) * 0.05;
    return [x - pad, y - pad, w + 2 * pad, h + 2 * pad];
  }, [ents, proj]);
  const [vb, setVb] = useState(fit);
  useEffect(() => setVb(fit), [fit]);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; vb: number[] } | null>(null);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      setVb((v) => {
        const k = e.deltaY > 0 ? 1.15 : 1 / 1.15;
        const fx = (e.clientX - r.left) / r.width, fy = 1 - (e.clientY - r.top) / r.height;
        const w = v[2] * k, h = v[3] * k;
        return [v[0] + (v[2] - w) * fx, v[1] + (v[3] - h) * fy, w, h];
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // DXF y is up, SVG y is down: draw at (x, -y)
  const P = (p: number[]) => {
    const [x, y] = project(p, proj);
    return [x, -y];
  };
  const viewBox = `${vb[0]} ${-(vb[1] + vb[3])} ${vb[2]} ${vb[3]}`;
  const stroke = Math.max(vb[2], vb[3]) / 900;

  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: "application/dxf" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="dxf-viewer">
      <div className="dxf-toolbar">
        <strong dir="ltr">{filename}</strong>
        {doc.sheets.length ? (
          <label>
            {t("Sheet")}{" "}
            <select value={sheetIdx} onChange={(e) => setSheetIdx(Number(e.target.value))} aria-label={t("Sheet")}>
              <option value={-1}>{t("All")}</option>
              {doc.sheets.map((s, k) => (
                <option key={s.name + k} value={k}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <label>
          {t("View")}{" "}
          <select value={proj} onChange={(e) => setProj(e.target.value as Projection)}>
            <option value="top">{t("Top")}</option>
            <option value="iso">{t("Isometric")}</option>
          </select>
        </label>
        <button type="button" className="button secondary" onClick={() => setVb(fit)}>
          {t("Fit")}
        </button>
        <button type="button" className="button secondary" onClick={download}>
          {t("Download")} DXF
        </button>
      </div>
      <div className="dxf-layers">
        {doc.layers.map((l) => (
          <label key={l} style={{ color: layerColor(l) }}>
            <input
              type="checkbox"
              checked={!hidden.has(l)}
              onChange={(e) => {
                const next = new Set(hidden);
                if (e.target.checked) next.delete(l);
                else next.add(l);
                setHidden(next);
              }}
            />{" "}
            {l}
          </label>
        ))}
      </div>
      <svg
        ref={svgRef}
        className="dxf-canvas"
        style={{ height }}
        viewBox={viewBox}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={filename}
        onPointerDown={(e) => {
          drag.current = { x: e.clientX, y: e.clientY, vb };
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          const el = svgRef.current;
          if (!d || !el) return;
          const r = el.getBoundingClientRect();
          const s = Math.max(d.vb[2] / r.width, d.vb[3] / r.height);
          setVb([d.vb[0] - (e.clientX - d.x) * s, d.vb[1] + (e.clientY - d.y) * s, d.vb[2], d.vb[3]]);
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerLeave={() => (drag.current = null)}
      >
        {ents.map((e, k) => {
          const c = layerColor(e.layer);
          if (e.type === "LINE" || e.type === "POLY") {
            const pts = e.pts.map(P).map((p) => p.join(",")).join(" ");
            return e.type === "POLY" && e.closed ? (
              <polygon key={k} points={pts} fill={e.fill ? c : "none"} fillOpacity={e.fill ? 0.35 : undefined} stroke={c} strokeWidth={stroke} />
            ) : (
              <polyline key={k} points={pts} fill="none" stroke={c} strokeWidth={stroke} />
            );
          }
          if (e.type === "CIRCLE") {
            const [x, y] = P(e.c);
            return <circle key={k} cx={x} cy={y} r={e.r} fill="none" stroke={c} strokeWidth={stroke} />;
          }
          const [x, y] = P(e.p);
          return (
            <text key={k} x={x} y={y} fontSize={e.h} fill={c} textAnchor={e.center ? "middle" : "start"} dominantBaseline={e.center ? "middle" : "auto"}>
              {e.text}
            </text>
          );
        })}
      </svg>
      <p className="muted dxf-hint">{t("Drag to pan, mouse wheel to zoom.")}</p>
    </div>
  );
}
