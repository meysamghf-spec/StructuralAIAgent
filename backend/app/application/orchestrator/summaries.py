"""Compact, model-facing digests of engineering payloads. The model may quote numbers ONLY from these digests."""

from __future__ import annotations

from typing import Any


def _r(v: Any, n: int = 3) -> Any:
    return round(v, n) if isinstance(v, float) else v


def model_line(inp: dict[str, Any], fa: bool) -> str:
    try:
        s = (f"{inp['storeys']} طبقه، {inp['bays_x']}×{inp['bays_y']} دهانه ({inp['bay_x_m']:g}×{inp['bay_y_m']:g} m)، ارتفاع طبقه {inp['storey_height_m']:g} m"
             if fa else f"{inp['storeys']} storeys, {inp['bays_x']}×{inp['bays_y']} bays ({inp['bay_x_m']:g}×{inp['bay_y_m']:g} m), storey height {inp['storey_height_m']:g} m")
        return s
    except (KeyError, TypeError, ValueError):
        return ""


def model_digest(inp: dict[str, Any]) -> dict[str, Any]:
    keys = ("storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m", "storey_height_m", "column_b_m", "column_h_m", "beam_b_m", "beam_h_m",
            "slab_t_m", "fc_mpa", "fy_mpa", "dead_kn_m2", "live_kn_m2", "roof_live_kn_m2", "seismic_code", "seismic_c", "behaviour_r",
            "design_code", "zone", "soil", "importance", "system", "allowable_bearing_kpa", "foundation", "p_delta")
    return {k: inp.get(k) for k in keys if inp.get(k) is not None}


def analysis_digest(payload: dict[str, Any], assumed: list[str]) -> dict[str, Any]:
    res = payload.get("results") or {}
    seis = payload.get("seismic") or {}
    design = payload.get("design") or {}
    dsum = design.get("summary") if isinstance(design.get("summary"), dict) else {}
    fnd = payload.get("foundation") if isinstance(payload.get("foundation"), dict) else {}
    out: dict[str, Any] = {
        "analysis_status": payload.get("status"),
        "model": model_digest(payload.get("inputs") or {}),
        "assumed_by_platform": assumed,
        "seismic": {k: _r(seis.get(k)) for k in ("method", "zone", "A", "soil", "system_label", "R", "Cd", "I", "T_empirical_s", "C", "k")
                    if seis.get(k) is not None},
        "results": {k: _r(v) for k, v in res.items() if k in (
            "max_drift_amplified_pct", "max_drift_storey", "max_drift_direction", "beam_max_M_neg_kn_m", "beam_max_M_pos_kn_m",
            "beam_max_V_kn", "column_max_P_kn", "column_max_M_kn_m", "seismic_weight_kn")},
        "drift_check_vs_2800_limit": payload.get("drift_check"),
        "drift_limit_note": "2800 limit applies to the amplified (inelastic) drift ratio",
        "base_shear_check": (payload.get("base_shear_check") or {}).get("status"),
        "base_shear_kn": _r((payload.get("base_shear_check") or {}).get("V_expected_kn"), 1),
        "modal_T1_s": _r((payload.get("modal") or {}).get("T_fundamental_s")),
        "p_delta": (payload.get("p_delta") or {}).get("status"),
        "design_mabhas9": {"status": design.get("status"), "members": design.get("member_status"), "strong_column_weak_beam": design.get("scwb_status"),
                           **{k: _r(v) for k, v in dsum.items() if not isinstance(v, (list, dict))}} if design else None,
        "foundation": {"status": fnd.get("status"), "qa_kpa": fnd.get("qa_kpa")} if fnd else None,
        "warnings": [str(w)[:240] for w in (payload.get("warnings") or [])[:4]],
        "disclaimer": "Results are a preliminary engineering aid and need review by the responsible engineer.",
    }
    return {k: v for k, v in out.items() if v not in (None, {}, [])}


def optimization_digest(res: dict[str, Any]) -> dict[str, Any]:
    def s(ev: dict[str, Any] | None) -> dict[str, Any]:
        return {k: ev.get(k) for k in ("cost_toman", "weight_kg", "concrete_m3", "rebar_kg", "feasible", "max_drift_ratio")} if ev else {}

    return {
        "optimization_status": res.get("status"), "objective": (res.get("method") or {}).get("objective"),
        "savings_pct": res.get("savings_pct"), "savings_reference": res.get("savings_reference"),
        "initial": s(res.get("initial")), "optimal": s(res.get("optimal")),
        "optimal_sections": [{"group": g.get("group"), "type": g.get("type"), "section_cm": g.get("section_cm"),
                              "initial_section_cm": g.get("initial_section_cm"), "governing": g.get("governing_constraint")}
                             for g in (res.get("groups") or [])][:16],
        "evaluations": res.get("evaluations"), "elapsed_s": res.get("elapsed_s"),
        "note": "Optimal sections are a recommendation: they are NOT applied to the stored model unless the user rebuilds it with them.",
    }
