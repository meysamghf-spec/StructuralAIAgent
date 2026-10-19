"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Frame3dResults } from "@/lib/chat-types";
import {
  DC_LEGEND,
  autoDeformScale,
  baseReactions,
  dcColor,
  diagramValues,
  explorerTree,
  gridLabelX,
  gridLabelY,
  loadOptions,
  maxAbs,
  memberForces,
  memberLength,
  nodeDisplacement,
  type DiagramKind,
  type ViewerData,
  type ViewerMember,
} from "@/lib/frame3d-viewer";

type T = (key: string) => string;
type ViewPreset = "3D" | "PLAN" | "ELEV_X" | "ELEV_Y";
type Display = "NONE" | DiagramKind | "DC";

const BG = 0x1f2a38;

export default function Frame3dViewer({ data, results, t, onClose }: { data: ViewerData; results: Frame3dResults; t: T; onClose: () => void }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<{ setView: (v: ViewPreset) => void } | null>(null);
  const camRef = useRef<{ pos: number[]; target: number[]; rotate: boolean } | null>(null);
  const [view, setView] = useState<ViewPreset>("3D");
  const [storey, setStorey] = useState<number | null>(null);
  const [jointLabels, setJointLabels] = useState(false);
  const [frameLabels, setFrameLabels] = useState(false);
  const [extruded, setExtruded] = useState(false);
  const [showDeformed, setShowDeformed] = useState(false);
  const [animate, setAnimate] = useState(false);
  const [display, setDisplay] = useState<Display>(data.members.some((m) => m.dc !== null) ? "DC" : "NONE");
  const loads = useMemo(() => loadOptions(data), [data]);
  const [load, setLoad] = useState<string>(loads.find((l) => l.startsWith("1.2D+1.6L")) ?? loads[0] ?? "D");
  const baseScale = useMemo(() => autoDeformScale(data, load), [data, load]);
  const [scaleMul, setScaleMul] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number; text: string } | null>(null);
  const [panel, setPanel] = useState<"drift" | "forces" | "reactions">("drift");
  const rtl = results.lang === "fa";

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let disposed = false;
    let cleanup = () => {};
    void (async () => {
      const THREE = await import("three");
      const { OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js");
      const { CSS2DRenderer, CSS2DObject } = await import("three/examples/jsm/renderers/CSS2DRenderer.js");
      if (disposed) return;
      const w = host.clientWidth || 800;
      const h = host.clientHeight || 600;
      const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(w, h);
      renderer.setClearColor(BG);
      host.appendChild(renderer.domElement);
      const labelRenderer = new CSS2DRenderer();
      labelRenderer.setSize(w, h);
      Object.assign(labelRenderer.domElement.style, { position: "absolute", top: "0", left: "0", pointerEvents: "none" });
      host.appendChild(labelRenderer.domElement);

      const scene = new THREE.Scene();
      scene.add(new THREE.AmbientLight(0xffffff, 0.65));
      const sun = new THREE.DirectionalLight(0xffffff, 0.9);
      sun.position.set(30, -40, 60);
      scene.add(sun);

      const xs = data.xs, ys = data.ys, zs = data.zs;
      const cx = (xs[0] + xs[xs.length - 1]) / 2, cy = (ys[0] + ys[ys.length - 1]) / 2, cz = (zs[0] + zs[zs.length - 1]) / 2;
      const size = Math.max(xs[xs.length - 1] - xs[0], ys[ys.length - 1] - ys[0], zs[zs.length - 1] - zs[0], 1);
      const camera = new THREE.PerspectiveCamera(40, w / h, 0.05, size * 50);
      camera.up.set(0, 0, 1);
      const controls = new OrbitControls(camera, renderer.domElement);
      controls.target.set(cx, cy, cz);
      controls.enableDamping = true;
      controls.screenSpacePanning = true;

      const setPreset = (v: ViewPreset) => {
        const d = size * 2.2;
        const tz = v === "PLAN" && storey !== null ? zs[storey] ?? cz : cz;
        controls.target.set(cx, cy, tz);
        if (v === "3D") camera.position.set(cx + d * 0.8, cy - d * 1.0, cz + d * 0.7);
        if (v === "PLAN") camera.position.set(cx, cy - 0.001, tz + d * 1.2);
        if (v === "ELEV_X") camera.position.set(cx, cy - d * 1.3, cz);
        if (v === "ELEV_Y") camera.position.set(cx + d * 1.3, cy, cz);
        controls.enableRotate = v === "3D";
        controls.update();
      };
      apiRef.current = { setView: setPreset };
      if (camRef.current) {
        camera.position.fromArray(camRef.current.pos);
        controls.target.fromArray(camRef.current.target);
        controls.enableRotate = camRef.current.rotate;
        controls.update();
      } else {
        setPreset(view);
      }

      const nodeById = new Map(data.nodes.map((n) => [n.id, n]));
      const label = (text: string, cls: string, pos: [number, number, number]) => {
        const el = document.createElement("div");
        el.className = cls;
        el.textContent = text;
        const o = new CSS2DObject(el);
        o.position.set(...pos);
        scene.add(o);
        return o;
      };

      // grids with bubbles at the base level
      const gridMat = new THREE.LineDashedMaterial({ color: 0x8fa3bf, dashSize: 0.3, gapSize: 0.2 });
      const ext = 1.5;
      const gz = storey !== null && view === "PLAN" ? zs[storey] ?? 0 : 0;
      xs.forEach((x, i) => {
        const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, ys[0] - ext, gz), new THREE.Vector3(x, ys[ys.length - 1] + ext, gz)]);
        const l = new THREE.Line(g, gridMat);
        l.computeLineDistances();
        scene.add(l);
        label(gridLabelX(i), "v3d-bubble", [x, ys[0] - ext - 0.4, gz]);
      });
      ys.forEach((y, j) => {
        const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(xs[0] - ext, y, gz), new THREE.Vector3(xs[xs.length - 1] + ext, y, gz)]);
        const l = new THREE.Line(g, gridMat);
        l.computeLineDistances();
        scene.add(l);
        label(gridLabelY(j), "v3d-bubble", [xs[0] - ext - 0.4, y, gz]);
      });

      // rigid diaphragms
      for (const k of data.levels) {
        if (storey !== null && k !== storey) continue;
        const z = zs[k];
        if (z === undefined) continue;
        const plane = new THREE.Mesh(
          new THREE.PlaneGeometry(xs[xs.length - 1] - xs[0], ys[ys.length - 1] - ys[0]),
          new THREE.MeshBasicMaterial({ color: 0x5fa8ff, transparent: true, opacity: 0.07, side: THREE.DoubleSide, depthWrite: false }),
        );
        plane.position.set(cx, cy, z);
        scene.add(plane);
      }

      // supports and footings
      const supMat = new THREE.MeshLambertMaterial({ color: 0x7ee08a });
      for (const sid of data.supports) {
        const n = nodeById.get(sid);
        if (!n) continue;
        const cone = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.3, 4), supMat);
        cone.rotation.x = Math.PI / 2;
        cone.position.set(n.x, n.y, n.z - 0.15);
        scene.add(cone);
      }
      const ftgMat = new THREE.MeshLambertMaterial({ color: 0xb08d57, transparent: true, opacity: 0.85 });
      const pickables: Array<import("three").Object3D> = [];
      for (const f of data.footings) {
        const box = new THREE.Mesh(new THREE.BoxGeometry(f.B, f.B, f.h), ftgMat);
        box.position.set(f.x, f.y, -0.3 - f.h / 2);
        box.userData = { id: `F-${f.column}` };
        scene.add(box);
        pickables.push(box);
        scene.add(new THREE.LineSegments(new THREE.EdgesGeometry(box.geometry), new THREE.LineBasicMaterial({ color: 0x3b2a12 })).translateX(f.x).translateY(f.y).translateZ(-0.3 - f.h / 2));
      }

      const visible = data.members.filter((m) => storey === null || (view === "PLAN" ? m.storey === storey && m.type === "beam" || (m.storey === storey && m.type === "column") : true));
      const memberColor = (m: ViewerMember) =>
        display === "DC" ? new THREE.Color(dcColor(m.dc)) : new THREE.Color(m.type === "column" ? 0xe0e6ef : 0x7fc4ff);

      // members (line or extruded)
      const objs: Array<{ m: ViewerMember; obj: import("three").Object3D }> = [];
      for (const m of visible) {
        const a = nodeById.get(m.i), b = nodeById.get(m.j);
        if (!a || !b) continue;
        const A = new THREE.Vector3(a.x, a.y, a.z), B = new THREE.Vector3(b.x, b.y, b.z);
        let obj: import("three").Object3D;
        if (extruded) {
          const len = A.distanceTo(B);
          const geo = new THREE.BoxGeometry(m.b, m.h, len);
          const mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ color: memberColor(m), transparent: showDeformed, opacity: showDeformed ? 0.35 : 1 }));
          mesh.position.copy(A.clone().add(B).multiplyScalar(0.5));
          const dir = B.clone().sub(A).normalize();
          mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), dir);
          if (m.type === "beam") mesh.translateY(0); // centreline at joint level
          obj = mesh;
        } else {
          const geo = new THREE.BufferGeometry().setFromPoints([A, B]);
          obj = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: memberColor(m), transparent: showDeformed, opacity: showDeformed ? 0.35 : 1 }));
        }
        obj.userData = { id: m.id };
        scene.add(obj);
        pickables.push(obj);
        objs.push({ m, obj });
        if (frameLabels) {
          const mid = A.clone().add(B).multiplyScalar(0.5);
          label(`${m.id} · ${m.section}`, "v3d-frame-label", [mid.x, mid.y, mid.z]);
        }
      }
      if (jointLabels) {
        for (const n of data.nodes) {
          if (storey !== null && view === "PLAN" && Math.abs(n.z - (zs[storey] ?? 0)) > 1e-6) continue;
          label(n.id, "v3d-joint-label", [n.x, n.y, n.z]);
        }
      }

      // force diagrams
      if (display === "M3" || display === "V2" || display === "P") {
        let gmax = 0;
        const vals = visible.map((m) => {
          const v = diagramValues(memberForces(data, load, m.id), memberLength(data, m), display);
          gmax = Math.max(gmax, maxAbs(v));
          return v;
        });
        const k = gmax > 0 ? (0.12 * size) / gmax : 0;
        visible.forEach((m, idx) => {
          const a = nodeById.get(m.i), b = nodeById.get(m.j);
          if (!a || !b) return;
          const A = new THREE.Vector3(a.x, a.y, a.z), B = new THREE.Vector3(b.x, b.y, b.z);
          const perp = m.type === "beam" ? new THREE.Vector3(0, 0, 1) : view === "ELEV_Y" ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
          const v = vals[idx];
          const pos: number[] = [], col: number[] = [];
          const pts: import("three").Vector3[] = [];
          for (let s = 0; s < v.length; s++) {
            const p = A.clone().lerp(B, s / (v.length - 1));
            const q = p.clone().addScaledVector(perp, (m.type === "beam" ? -1 : 1) * v[s] * k);
            pts.push(q);
            if (s > 0) {
              const p0 = A.clone().lerp(B, (s - 1) / (v.length - 1));
              const q0 = pts[s - 1];
              const c = new THREE.Color(v[s] + v[s - 1] >= 0 ? 0xff5a5a : 0x5aa0ff);
              for (const P of [p0, p, q, p0, q, q0]) { pos.push(P.x, P.y, P.z); col.push(c.r, c.g, c.b); }
            }
          }
          const g = new THREE.BufferGeometry();
          g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
          g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
          const fill = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false }));
          fill.userData = { id: m.id, diagram: v };
          scene.add(fill);
          pickables.push(fill);
          scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0xffffff })));
        });
      }

      // deformed shape (lines), animated when requested
      const deformed: Array<{ line: import("three").Line; m: ViewerMember }> = [];
      if (showDeformed) {
        for (const m of visible) {
          const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineBasicMaterial({ color: 0xffd54f }));
          scene.add(line);
          deformed.push({ line, m });
        }
      }
      const placeDeformed = (f: number) => {
        for (const { line, m } of deformed) {
          const arr: number[] = [];
          for (const nid of [m.i, m.j]) {
            const n = nodeById.get(nid)!;
            const u = nodeDisplacement(data, load, nid);
            const s = (baseScale * scaleMul * f) / 1000;
            arr.push(n.x + u[0] * s, n.y + u[1] * s, n.z + u[2] * s);
          }
          line.geometry.setAttribute("position", new THREE.Float32BufferAttribute(arr, 3));
          line.geometry.attributes.position.needsUpdate = true;
        }
      };
      placeDeformed(1);

      // selection highlight
      for (const { m, obj } of objs) {
        if (m.id === selected) {
          const mat = (obj as import("three").Mesh).material as import("three").MeshBasicMaterial;
          mat.color = new THREE.Color(0xff00ff);
        }
      }

      // picking
      const ray = new THREE.Raycaster();
      ray.params.Line = { threshold: 0.12 };
      const ndc = new THREE.Vector2();
      const pick = (ev: PointerEvent) => {
        const r = renderer.domElement.getBoundingClientRect();
        ndc.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
        ray.setFromCamera(ndc, camera);
        const hit = ray.intersectObjects(pickables, false)[0];
        return { hit, r };
      };
      const onMove = (ev: PointerEvent) => {
        const { hit, r } = pick(ev);
        if (!hit) return setHover(null);
        const id = String(hit.object.userData.id);
        let text = id;
        const m = data.members.find((x) => x.id === id);
        if (m && display !== "NONE" && display !== "DC") {
          const v = diagramValues(memberForces(data, load, id), memberLength(data, m), display);
          const unit = display === "M3" ? "kN·m" : "kN";
          text = `${id} · ${display}: i ${v[0].toFixed(1)} / mid ${v[Math.floor(v.length / 2)].toFixed(1)} / j ${v[v.length - 1].toFixed(1)} ${unit}`;
        } else if (m) {
          text = `${id} · ${m.section}${m.dc !== null ? ` · D/C ${m.dc.toFixed(2)}` : ""}`;
        }
        setHover({ x: ev.clientX - r.left + 12, y: ev.clientY - r.top + 12, text });
      };
      const onClick = (ev: PointerEvent) => {
        const { hit } = pick(ev);
        if (hit) setSelected(String(hit.object.userData.id));
      };
      renderer.domElement.addEventListener("pointermove", onMove);
      renderer.domElement.addEventListener("click", onClick as EventListener);

      const onResize = () => {
        const W = host.clientWidth, H = host.clientHeight;
        camera.aspect = W / H;
        camera.updateProjectionMatrix();
        renderer.setSize(W, H);
        labelRenderer.setSize(W, H);
      };
      window.addEventListener("resize", onResize);

      let raf = 0;
      const t0 = performance.now();
      const loop = () => {
        raf = requestAnimationFrame(loop);
        if (showDeformed && animate) placeDeformed(Math.sin(((performance.now() - t0) / 1000) * Math.PI));
        controls.update();
        renderer.render(scene, camera);
        labelRenderer.render(scene, camera);
      };
      loop();
      (window as unknown as { __v3dReady?: boolean }).__v3dReady = true;

      cleanup = () => {
        camRef.current = { pos: camera.position.toArray(), target: controls.target.toArray(), rotate: controls.enableRotate };
        cancelAnimationFrame(raf);
        window.removeEventListener("resize", onResize);
        renderer.domElement.removeEventListener("pointermove", onMove);
        controls.dispose();
        renderer.dispose();
        renderer.domElement.remove();
        labelRenderer.domElement.remove();
      };
    })();
    return () => {
      disposed = true;
      cleanup();
    };
    // camera preset is applied separately; everything else rebuilds the scene
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, storey, jointLabels, frameLabels, extruded, showDeformed, animate, display, load, scaleMul, baseScale, selected, view === "PLAN"]);

  useEffect(() => {
    apiRef.current?.setView(view);
  }, [view]);

  const sel = data.members.find((m) => m.id === selected) ?? null;
  const selFooting = data.footings.find((f) => `F-${f.column}` === selected) ?? null;
  const selForces = sel ? memberForces(data, load, sel.id) : null;
  const tree = explorerTree(data);
  const reactions = baseReactions(data, load);
  const drift = results.drift;
  const driftMax = Math.max(0.01, ...drift.map((d) => d.ratioAmplifiedPct ?? 0), results.driftReferenceLimitPct ?? 0);

  return (
    <div className="v3d-overlay" dir={rtl ? "rtl" : "ltr"} lang={results.lang} role="dialog" aria-label={t("3D model view")}>
      <div className="v3d-toolbar">
        <strong>{t("3D model view")}</strong>
        {(["3D", "PLAN", "ELEV_X", "ELEV_Y"] as ViewPreset[]).map((v) => (
          <button key={v} type="button" className={view === v ? "v3d-btn v3d-on" : "v3d-btn"} onClick={() => setView(v)}>
            {t(v === "3D" ? "3D" : v === "PLAN" ? "Plan" : v === "ELEV_X" ? "Elevation X" : "Elevation Y")}
          </button>
        ))}
        <label>
          {t("Story")}{" "}
          <select value={storey ?? ""} onChange={(e) => setStorey(e.target.value === "" ? null : Number(e.target.value))}>
            <option value="">{t("All")}</option>
            {data.levels.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="v3d-btn" disabled={storey === null} onClick={() => setView("PLAN")}>
          {t("Plan at story")}
        </button>
        <label><input type="checkbox" checked={jointLabels} onChange={(e) => setJointLabels(e.target.checked)} /> {t("Joint labels")}</label>
        <label><input type="checkbox" checked={frameLabels} onChange={(e) => setFrameLabels(e.target.checked)} /> {t("Frame labels")}</label>
        <label><input type="checkbox" checked={extruded} onChange={(e) => setExtruded(e.target.checked)} /> {t("Extruded")}</label>
        <span className="v3d-sep" />
        <label>
          {t("Load")}{" "}
          <select value={load} onChange={(e) => setLoad(e.target.value)}>
            {loads.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("Display")}{" "}
          <select value={display} onChange={(e) => setDisplay(e.target.value as Display)}>
            <option value="NONE">{t("Model")}</option>
            <option value="M3">M3</option>
            <option value="V2">V2</option>
            <option value="P">{t("Axial")}</option>
            <option value="DC">{t("Design D/C")}</option>
          </select>
        </label>
        <label><input type="checkbox" checked={showDeformed} onChange={(e) => setShowDeformed(e.target.checked)} /> {t("Deformed")}</label>
        <input type="range" min={0.2} max={5} step={0.1} value={scaleMul} onChange={(e) => setScaleMul(Number(e.target.value))} aria-label={t("Scale")} />
        <label><input type="checkbox" checked={animate} onChange={(e) => setAnimate(e.target.checked)} /> {t("Animate")}</label>
        <button type="button" className="v3d-btn v3d-close" onClick={onClose}>
          {t("Close")}
        </button>
      </div>
      <div className="v3d-body">
        <aside className="v3d-tree">
          <p className="v3d-h">{t("Model explorer")}</p>
          {tree.map((g) => (
            <details key={g.key} open={g.key.endsWith("-C") && g.key === tree[0]?.key}>
              <summary>
                {g.label.replace("Story", t("Story")).replace("Columns", t("Columns")).replace("Beams", t("Beams")).replace("Footings", t("Footings"))} ({g.items.length})
              </summary>
              <ul>
                {g.items.map((id) => (
                  <li key={id}>
                    <button type="button" className={id === selected ? "v3d-item v3d-on" : "v3d-item"} onClick={() => setSelected(id)}>
                      {id}
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </aside>
        <div className="v3d-canvas" ref={hostRef}>
          {hover ? (
            <div className="v3d-tip" style={{ left: hover.x, top: hover.y }} dir="ltr">
              {hover.text}
            </div>
          ) : null}
          {display === "DC" ? (
            <div className="v3d-legend">
              <p>{t("Design D/C")}</p>
              {DC_LEGEND.map(([c, l]) => (
                <div key={c}>
                  <span style={{ background: c }} /> {l === "—" ? t("not designed") : l}
                </div>
              ))}
            </div>
          ) : null}
          <div className="v3d-status" dir="ltr">
            {load}
            {showDeformed ? ` · ×${(baseScale * scaleMul).toFixed(0)}` : ""}
          </div>
        </div>
        <aside className="v3d-props">
          <p className="v3d-h">{t("Properties")}</p>
          {sel ? (
            <dl>
              <dt>{t("Member")}</dt><dd dir="ltr">{sel.id}</dd>
              <dt>{t("Type")}</dt><dd>{t(sel.type === "beam" ? "Beam" : "Column")}</dd>
              <dt>{t("Story")}</dt><dd dir="ltr">{sel.storey}</dd>
              <dt>{t("Section")}</dt><dd dir="ltr">{sel.section}</dd>
              <dt>{t("Joints")}</dt><dd dir="ltr">{sel.i} → {sel.j}</dd>
              <dt>{t("Length")}</dt><dd dir="ltr">{memberLength(data, sel).toFixed(2)} m</dd>
              {selForces ? (
                <>
                  <dt>P ({load})</dt><dd dir="ltr">{selForces[0].toFixed(1)} kN</dd>
                  <dt>V2 i</dt><dd dir="ltr">{selForces[1].toFixed(1)} kN</dd>
                  <dt>M3 i / j</dt><dd dir="ltr">{selForces[2].toFixed(1)} / {selForces[3].toFixed(1)} kN·m</dd>
                </>
              ) : null}
              <dt>{t("Design group")}</dt><dd dir="ltr">{sel.group ?? "—"}</dd>
              <dt>D/C</dt><dd dir="ltr" style={{ color: dcColor(sel.dc) }}>{sel.dc !== null ? sel.dc.toFixed(2) : "—"}</dd>
              <dt>{t("Status")}</dt><dd>{sel.designStatus ? t(sel.designStatus) : "—"}</dd>
              <dt>{t("Rebar")}</dt><dd dir="ltr">{sel.rebar ?? "—"}</dd>
            </dl>
          ) : selFooting ? (
            <dl>
              <dt>{t("Footing")}</dt><dd dir="ltr">F-{selFooting.column}</dd>
              <dt>B × B × h</dt><dd dir="ltr">{selFooting.B} × {selFooting.B} × {selFooting.h} m</dd>
              <dt>{t("Position")}</dt><dd>{t(selFooting.position)}</dd>
            </dl>
          ) : (
            <p className="v3d-muted">{t("Click a member to see its properties.")}</p>
          )}
          <div className="v3d-tabs">
            {(["drift", "forces", "reactions"] as const).map((p) => (
              <button key={p} type="button" className={panel === p ? "v3d-btn v3d-on" : "v3d-btn"} onClick={() => setPanel(p)}>
                {t(p === "drift" ? "Story drift" : p === "forces" ? "Story forces" : "Base reactions")}
              </button>
            ))}
          </div>
          {panel === "drift" ? (
            <svg viewBox="0 0 220 160" className="v3d-drift" role="img" aria-label={t("Story drift")}>
              {results.driftReferenceLimitPct ? (
                <line x1={20 + (180 * results.driftReferenceLimitPct) / driftMax} x2={20 + (180 * results.driftReferenceLimitPct) / driftMax} y1={10} y2={140} stroke="#e53935" strokeDasharray="4 3" />
              ) : null}
              {(["X", "Y"] as const).map((dir, di) => {
                const rows = drift.filter((d) => d.direction === dir).sort((a, b) => a.storey - b.storey);
                const n = Math.max(1, data.levels.length);
                const pts = [[20, 140], ...rows.map((r) => [20 + (180 * (r.ratioAmplifiedPct ?? 0)) / driftMax, 140 - (130 * r.storey) / n])];
                return <polyline key={dir} points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={di ? "#ffd54f" : "#5fa8ff"} strokeWidth={2} />;
              })}
              <line x1={20} y1={140} x2={200} y2={140} stroke="#9aa4b1" />
              <line x1={20} y1={10} x2={20} y2={140} stroke="#9aa4b1" />
              <text x={200} y={155} fill="#cfd8e3" fontSize={9} textAnchor="end">{driftMax.toFixed(2)}%</text>
              <text x={30} y={20} fill="#5fa8ff" fontSize={9}>X</text>
              <text x={45} y={20} fill="#ffd54f" fontSize={9}>Y</text>
            </svg>
          ) : null}
          {panel === "forces" ? (
            <table className="v3d-table" dir="ltr">
              <thead><tr><th>{t("Story")}</th><th>F (kN)</th><th>V (kN)</th></tr></thead>
              <tbody>
                {results.storeyLateral.map((r) => (
                  <tr key={r.storey}><td>{r.storey}</td><td>{r.forceKn.toFixed(1)}</td><td>{r.shearKn.toFixed(1)}</td></tr>
                ))}
              </tbody>
            </table>
          ) : null}
          {panel === "reactions" ? (
            <table className="v3d-table" dir="ltr">
              <thead><tr><th>{t("Joint")}</th><th>FX</th><th>FY</th><th>FZ</th><th>MX</th><th>MY</th></tr></thead>
              <tbody>
                {reactions.map((r) => (
                  <tr key={r.node}><td>{r.node}</td>{r.values.slice(0, 5).map((v, k) => <td key={k}>{v.toFixed(1)}</td>)}</tr>
                ))}
                <tr className="v3d-sum"><td>Σ</td>{[0, 1, 2].map((k) => <td key={k}>{reactions.reduce((s, r) => s + r.values[k], 0).toFixed(1)}</td>)}<td /><td /></tr>
              </tbody>
            </table>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
