import { describe, expect, it } from "vitest";

import { mapFrame3dResults } from "../lib/chat-mappers";

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

  it("ignores other result kinds", () => {
    expect(mapFrame3dResults({ kind: "demo_rc_beam" })).toBeNull();
  });
});
