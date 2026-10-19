import { describe, expect, it } from "vitest";

import { mapFrame3dResults } from "../lib/chat-mappers";
import { designCsv, orderExports } from "../components/chat/Frame3dResultCard";

describe("mapFrame3dResults", () => {
  it("maps a completed 3D frame payload", () => {
    const mapped = mapFrame3dResults({
      kind: "frame3d_analysis",
      status: "completed",
      seismic_code: "ASSUMED_C",
      design_code: "NONE",
      fields: [{ label: "Column max P", value: "1175.4", unit: "kN" }],
      drift: [{ direction: "X", storey: 2, drift_elastic_mm: 1.94, ratio_elastic_pct: 0.607, ratio_amplified_pct: 2.126 }],
      drift_reference_limit_pct: 2.5,
      beam_forces_by_storey: [{ storey: 1, M_neg_kn_m: 179.54, M_pos_kn_m: 89.55, V_kn: 130.27 }],
      column_forces_by_storey: [{ storey: 1, P_kn: 1175.42, M_kn_m: 198.5 }],
      base_shear_check: { status: "PASS" },
      geometry: { XS: [0, 5, 10], YS: [0, 5, 10], Z: [0, 3.2] },
    });
    expect(mapped?.drift[0]?.ratioAmplifiedPct).toBe(2.126);
    expect(mapped?.storeyForces[0]?.columnPKn).toBe(1175.42);
    expect(mapped?.gridX).toEqual([0, 5, 10]);
    expect(mapped?.baseShearStatus).toBe("PASS");
    expect(mapped?.seismicCode).toBe("ASSUMED_C");
  });

  it("maps modal and Mabhas 9 design sections", () => {
    const mapped = mapFrame3dResults({
      kind: "frame3d_analysis",
      status: "completed",
      drift_check: "PASS",
      modal: {
        T_fundamental_s: 0.829,
        modes: [{ mode: 1, T_s: 0.829, mass_x_pct: 83.3, mass_y_pct: 0, mass_rz_pct: 0 }],
        response_spectrum: { X: { V_dynamic_kn: 325, V_static_kn: 588, scale_factor: 1.538, drift: [{ ratio_amplified_pct: 1.9 }] } },
      },
      design: {
        code: "MABHAS9",
        status: "CHECK",
        ductility: "intermediate",
        beams: [{ group: "B-X-S1-edge", top_bars: "3Φ25", DC_flexure: 1.0, notes: ["a", "b"] }],
        columns: [{ group: "C-S1-corner", bars: "8Φ22", DC: 0.965 }],
        scwb: [{ level: 1, min_ratio: 1.27, status: "PASS" }],
        clauses_implemented: ["x"],
        clauses_simplified: ["y"],
      },
    });
    expect(mapped?.driftCheck).toBe("PASS");
    expect(mapped?.modal?.spectrum[0]?.scaleFactor).toBe(1.538);
    expect(mapped?.modal?.spectrum[0]?.maxDriftPct).toBe(1.9);
    expect(mapped?.design?.beams[0]?.notes).toBe("a; b");
    expect(mapped?.design?.columns[0]?.bars).toBe("8Φ22");
    expect(designCsv(mapped?.design?.beams ?? [])).toContain("B-X-S1-edge");
  });

  it("ignores other result kinds", () => {
    expect(mapFrame3dResults({ kind: "demo_rc_beam" })).toBeNull();
  });

  it("maps ETABS/SAFE/DXF export descriptors and keeps the inputs for the export endpoint", () => {
    const mapped = mapFrame3dResults({
      kind: "frame3d_analysis",
      status: "completed",
      inputs: { storeys: 3, bays_x: 2, bays_y: 2 },
      parsed_from_request: ["storeys", "bays_x", "bays_y"],
      export_requested: ["f2k"],
      model_from_project_memory: true,
      exports: [
        { format: "e2k", filename: "model.e2k", label: "ETABS model (.e2k)", requested: false, notes: ["unverified"] },
        { format: "f2k", filename: "foundation.f2k", label: "SAFE foundation loads (.f2k)", requested: true, notes: [] },
        { bogus: true },
      ],
    });
    expect(mapped?.exports.map((e) => e.format)).toEqual(["e2k", "f2k"]);
    expect(mapped?.exportRequested).toEqual(["f2k"]);
    expect(mapped?.modelFromProjectMemory).toBe(true);
    expect(mapped?.inputs).toEqual({ storeys: 3, bays_x: 2, bays_y: 2, _p: ["storeys", "bays_x", "bays_y"] });
    expect(orderExports(mapped?.exports ?? []).map((e) => e.filename)).toEqual(["foundation.f2k", "model.e2k"]);
  });
});
