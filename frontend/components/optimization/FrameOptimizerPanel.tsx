"use client";

import { DownloadsPanel } from "@/components/frame3d/DownloadsPanel";
import { getCurrentProjectId } from "@/lib/current-project";

import {
  convergenceSeries,
  formatObjective,
  runFrameOptimization,
  type FrameOptimizationResult,
} from "@/lib/frame-optimizer";
import { useState } from "react";

const num = (v: string, d: number) => (Number.isFinite(Number(v)) && v.trim() !== "" ? Number(v) : d);

function ConvergenceChart({ res }: { res: FrameOptimizationResult }) {
  const pts = convergenceSeries(res);
  if (pts.length < 2) return null;
  const W = 600, H = 220, P = 36;
  const ys = pts.map((p) => p.y);
  const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
  const X = (i: number) => P + (i / (pts.length - 1)) * (W - 2 * P);
  const Y = (v: number) => H - P - ((v - lo) / span) * (H - 2 * P);
  const nf = res.convergence.fsd.length;
  const path = pts.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p.y).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Optimization convergence chart"
      style={{ width: "100%", height: "auto", maxWidth: "100%", display: "block" }}>
      <rect x={P} y={P / 2} width={W - 2 * P} height={H - 1.5 * P} fill="none" stroke="currentColor" opacity={0.15} />
      {nf > 0 && nf < pts.length ? (
        <line x1={X(nf - 0.5)} x2={X(nf - 0.5)} y1={P / 2} y2={H - P} stroke="currentColor" strokeDasharray="4 4" opacity={0.4} />
      ) : null}
      <path d={path} fill="none" stroke="#2563eb" strokeWidth={2.5} />
      {pts.map((p, i) => (
        <circle key={i} cx={X(i)} cy={Y(p.y)} r={3} fill={p.stage === "fsd" ? "#f59e0b" : "#2563eb"} />
      ))}
      <text x={P} y={H - 8} fontSize={12} fill="currentColor">FSD iterations (orange) → GA generations (blue)</text>
      <text x={W - P} y={14} fontSize={11} textAnchor="end" fill="currentColor">
        {formatObjective(hi, res.method.objective)} → {formatObjective(lo, res.method.objective)}
      </text>
    </svg>
  );
}

export function FrameOptimizerPanel() {
  const [f, setF] = useState({
    storeys: "3", bays_x: "2", bays_y: "2", bay_x_m: "5", bay_y_m: "5", storey_height_m: "3.2",
    zone: "HIGH", soil: "II", objective: "cost", concrete: "4500000", rebar: "45000", formwork: "900000",
    budget: "40", seed: "2026",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState<FrameOptimizationResult | null>(null);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function run() {
    setBusy(true); setError(""); setRes(null);
    try {
      setRes(await runFrameOptimization(
        {
          storeys: num(f.storeys, 3), bays_x: num(f.bays_x, 2), bays_y: num(f.bays_y, 2),
          bay_x_m: num(f.bay_x_m, 5), bay_y_m: num(f.bay_y_m, 5), storey_height_m: num(f.storey_height_m, 3.2),
          zone: f.zone, soil: f.soil,
        },
        {
          objective: f.objective === "weight" ? "weight" : "cost",
          prices: { concrete_m3: num(f.concrete, 4500000), rebar_kg: num(f.rebar, 45000), formwork_m2: num(f.formwork, 900000) },
          time_budget_s: num(f.budget, 40), seed: num(f.seed, 2026),
        },
      ));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function downloadReport() {
    if (!res?.report_markdown) return;
    const url = URL.createObjectURL(new Blob([res.report_markdown], { type: "text/markdown" }));
    const a = document.createElement("a");
    a.href = url; a.download = "frame-optimization-report.md"; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  const field = (label: string, k: keyof typeof f, mode: "decimal" | "numeric" = "decimal") => (
    <label className="field" style={{ minWidth: 0 }}>
      <span className="muted">{label}</span>
      <input className="input" inputMode={mode} value={f[k]} onChange={set(k)} style={{ width: "100%" }} />
    </label>
  );
  const grid = { display: "grid", gap: "0.6rem", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))" } as const;
  const obj = res?.method.objective;

  return (
    <section className="card" data-testid="frame-optimizer" style={{ minWidth: 0, overflowWrap: "anywhere" }}>
      <h3>3D frame section optimization</h3>
      <p className="muted">
        Fully-stressed design loop (resize → full 3D re-analysis → Mabhas 9 design) followed by a discrete
        genetic algorithm. Constraints: Mabhas 9 strength, Standard 2800 drift, deflection, column above ≤ below,
        beam width ≤ column width.
      </p>
      <div style={grid}>
        {field("Storeys", "storeys", "numeric")}
        {field("Bays X", "bays_x", "numeric")}
        {field("Bays Y", "bays_y", "numeric")}
        {field("Bay X (m)", "bay_x_m")}
        {field("Bay Y (m)", "bay_y_m")}
        {field("Storey height (m)", "storey_height_m")}
        <label className="field" style={{ minWidth: 0 }}>
          <span className="muted">Seismic zone</span>
          <select className="input" value={f.zone} onChange={set("zone")} style={{ width: "100%" }}>
            {["VERY_HIGH", "HIGH", "MEDIUM", "LOW"].map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </label>
        <label className="field" style={{ minWidth: 0 }}>
          <span className="muted">Soil</span>
          <select className="input" value={f.soil} onChange={set("soil")} style={{ width: "100%" }}>
            {["I", "II", "III", "IV"].map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </label>
        <label className="field" style={{ minWidth: 0 }}>
          <span className="muted">Objective</span>
          <select className="input" value={f.objective} onChange={set("objective")} style={{ width: "100%" }}>
            <option value="cost">Cost (toman)</option>
            <option value="weight">Weight (kg)</option>
          </select>
        </label>
        {field("Concrete /m³", "concrete", "numeric")}
        {field("Rebar /kg", "rebar", "numeric")}
        {field("Formwork /m²", "formwork", "numeric")}
        {field("Time budget (s)", "budget", "numeric")}
        {field("Seed", "seed", "numeric")}
      </div>
      <div className="form-row" style={{ marginTop: "0.8rem", flexWrap: "wrap" }}>
        <button className="button" type="button" onClick={run} disabled={busy}>
          {busy ? "Optimizing…" : "Run optimization"}
        </button>
        {res?.report_markdown ? (
          <button className="button secondary" type="button" onClick={downloadReport}>Download report</button>
        ) : null}
      </div>
      {error ? <p className="status-pill status-error">{error}</p> : null}

      {res ? (
        <div data-testid="frame-optimizer-result" style={{ marginTop: "1rem", minWidth: 0 }}>
          <div style={grid}>
            <div><span className="muted">Initial</span><br /><strong>{formatObjective(res.initial.objective, obj)}</strong>
              <br /><small className="muted">{res.initial.feasible ? "passes checks" : "fails checks"}</small></div>
            <div><span className="muted">Optimal</span><br /><strong>{formatObjective(res.optimal.objective, obj)}</strong>
              <br /><small className="muted">{res.optimal.feasible ? "passes checks" : "fails checks"}</small></div>
            <div><span className="muted">Saving</span><br /><strong>{res.savings_pct}%</strong>
              <br /><small className="muted">vs {res.savings_reference ?? "initial"}</small></div>
            <div><span className="muted">Runs</span><br /><strong>{res.evaluations} analyses</strong>
              <br /><small className="muted">{res.convergence.fsd.length} FSD it. · {res.convergence.ga.length} GA gen. · {res.elapsed_s}s</small></div>
            <div><span className="muted">Max drift</span><br /><strong>{res.optimal.max_drift_ratio}</strong>
              <br /><small className="muted">limit {res.drift_limit}</small></div>
          </div>
          <h4>Convergence</h4>
          <ConvergenceChart res={res} />
          <h4>Optimal sections</h4>
          <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
            {res.groups.map((g) => (
              <div key={g.group} className="card" style={{ padding: "0.6rem", minWidth: 0 }}>
                <strong>{g.group}</strong> <span className="muted">({g.type}, storeys {g.storeys.join(", ")})</span>
                <div>{g.initial_section_cm} → <strong>{g.section_cm}</strong> cm</div>
                <small className="muted">Governs: {g.governing_constraint} · util {g.utilization}</small>
              </div>
            ))}
          </div>
          <details className="meta-summary" style={{ marginTop: "0.8rem" }}>
            <summary>Method and limits</summary>
            <ul className="feature-list">
              {res.limits.map((l) => <li key={l}>{l}</li>)}
            </ul>
          </details>
          <DownloadsPanel
            inputs={(res as unknown as { frame?: Record<string, unknown> }).frame ?? null}
            projectId={getCurrentProjectId()}
            optimization={res}
            groups={["optimization", "analysis", "design", "figures"]}
            title="Optimization downloads"
          />
        </div>
      ) : null}
    </section>
  );
}
