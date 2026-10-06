"""Standalone ACI 318 RC beam flexure + shear check.

Uses the existing CodeEngine ACI plugin and UnitConversionService.
Does not invent missing engineering inputs or call CSI/CAD software.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.application.code_engine_service import CodeEngineService
from app.application.unit_conversion_service import UnitConversionService
from app.domain.models.pem import CodeConfiguration, create_software_default_code_configuration
from app.domain.models.units import EngineeringQuantityType

ACI_RC_BEAM_KIND = "aci_rc_beam"

_DESIGN_TERMS = (
    "design",
    "check",
    "capacity",
    "utilization",
    "φmn",
    "phimn",
    "phi mn",
    "aci",
    "flexure",
    "shear check",
    "reinforcement",
    "rebar",
)
_BEAM_TERMS = (
    "beam",
    "rc beam",
    "تیر",
)
_EXPLICIT_CONCRETE_TERMS = (
    "rc ",
    "rc beam",
    "reinforced concrete",
    "concrete",
    "aci",
    "rebar",
    "f'c",
    "fc'",
    "fc=",
    "بتن",
)
_NON_BEAM_MEMBERS = ("column", "slab", "wall", "footing", "foundation")

_RANGES = {
    "span_m": (0.5, 50.0, "Span"),
    "uniform_load_kn_m": (0.01, 1000.0, "Uniform load"),
    "width_mm": (100.0, 2000.0, "Width b"),
    "height_mm": (150.0, 3000.0, "Height h"),
    "effective_depth_mm": (50.0, 2800.0, "Effective depth d"),
    "fc_mpa": (15.0, 80.0, "Concrete strength f'c"),
    "fy_mpa": (280.0, 600.0, "Reinforcement yield fy"),
    "as_mm2": (50.0, 20000.0, "Tension steel area As"),
    "mu_kn_m": (0.01, 50000.0, "Factored moment Mu"),
    "vu_kn": (0.01, 20000.0, "Factored shear Vu"),
}

REQUIRED_LABELS = {
    "width_mm": "Width b",
    "height_mm": "Overall height h",
    "effective_depth_mm": "Effective depth d",
    "fc_mpa": "Concrete strength f'c",
    "fy_mpa": "Reinforcement steel strength fy",
    "as_mm2": "Tension reinforcement area As",
    "demands": "Demands (Mu and Vu, or span and uniform load)",
}


@dataclass
class AciRcBeamParsedInputs:
    span_m: float | None = None
    uniform_load_kn_m: float | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    effective_depth_mm: float | None = None
    fc_mpa: float | None = None
    fy_mpa: float | None = None
    as_mm2: float | None = None
    mu_kn_m: float | None = None
    vu_kn: float | None = None
    provided: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AciRcBeamCheckOutcome:
    status: str
    payload: dict[str, Any]
    message: str
    requires_approval: bool
    validation_status: str | None


def is_aci_rc_beam_check_request(user_request: str, *, require_explicit_concrete: bool = False) -> bool:
    normalized = user_request.lower()
    if any(term in normalized for term in _NON_BEAM_MEMBERS) and "beam" not in normalized:
        return False
    if "steel" in normalized and not any(term in normalized for term in _EXPLICIT_CONCRETE_TERMS):
        return False
    if not any(term in normalized for term in _DESIGN_TERMS):
        return False
    if not any(term in normalized for term in _BEAM_TERMS):
        return False
    if require_explicit_concrete:
        return any(term in normalized for term in _EXPLICIT_CONCRETE_TERMS)
    return True


def resolve_aci_plugin_id(code_configuration: CodeConfiguration) -> str | None:
    standard = code_configuration.concrete_standard
    plugin_hint = getattr(standard, "plugin_id", None)
    if plugin_hint is None and isinstance(standard, dict):
        plugin_hint = standard.get("plugin_id")
    if plugin_hint == "ACI318-25":
        return "ACI318-25"

    token = "".join(
        part.upper().replace(" ", "")
        for part in (
            _standard_text(standard),
            code_configuration.concrete_edition or "",
        )
    )
    if "ACI" not in token and "318" not in token:
        return None
    if "318" in token and ("25" in token or "2025" in token):
        return "ACI318-25"
    return None


def parse_aci_rc_beam_inputs(user_request: str, parameters: dict[str, Any] | None = None) -> AciRcBeamParsedInputs:
    parsed = AciRcBeamParsedInputs()
    source = parameters or {}
    nested = source.get("aci_rc_beam") if isinstance(source.get("aci_rc_beam"), dict) else {}

    def take(name: str, aliases: tuple[str, ...] = ()) -> float | None:
        for key in (name, *aliases):
            raw = nested.get(key) if key in nested else source.get(key)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                parsed.provided.append(name)
                return float(raw)
        return None

    parsed.span_m = take("span_m", ("span",))
    parsed.uniform_load_kn_m = take("uniform_load_kn_m", ("w_kn_m", "uniform_load"))
    parsed.width_mm = take("width_mm", ("b_mm",))
    parsed.height_mm = take("height_mm", ("h_mm",))
    parsed.effective_depth_mm = take("effective_depth_mm", ("d_mm",))
    parsed.fc_mpa = take("fc_mpa", ("fc",))
    parsed.fy_mpa = take("fy_mpa", ("fy",))
    parsed.as_mm2 = take("as_mm2", ("As_mm2", "as"))
    parsed.mu_kn_m = take("mu_kn_m", ("Mu_kn_m", "mu"))
    parsed.vu_kn = take("vu_kn", ("Vu_kn", "vu"))

    text = user_request or ""
    _fill_from_text(parsed, text)
    return parsed


def run_aci_rc_beam_check(
    *,
    user_request: str,
    parameters: dict[str, Any] | None,
    context: dict[str, Any],
    code_engine: CodeEngineService,
    units: UnitConversionService | None = None,
) -> AciRcBeamCheckOutcome | None:
    if not is_aci_rc_beam_check_request(user_request):
        return None

    units = units or UnitConversionService()
    code_configuration = _code_configuration(context)
    plugin_id = resolve_aci_plugin_id(code_configuration)
    config_validation = code_engine.validate_configuration(code_configuration)
    if plugin_id is None:
        edition = code_configuration.concrete_edition or _standard_text(code_configuration.concrete_standard)
        return AciRcBeamCheckOutcome(
            status="UNSUPPORTED_CODE",
            payload=_base_payload(
                status="UNSUPPORTED_CODE",
                code=edition,
                missing=[],
                warnings=[],
            ),
            message=(
                f"ACI 318-25 RC beam flexure/shear is not available for the configured concrete code "
                f"'{edition}'. This capability currently supports ACI CODE-318-25 only. "
                "It does not pretend another standard was checked."
            ),
            requires_approval=False,
            validation_status=None,
        )

    parsed = parse_aci_rc_beam_inputs(user_request, parameters)
    invalid = _invalid_ranges(parsed)
    if invalid:
        return AciRcBeamCheckOutcome(
            status="INVALID_INPUT",
            payload=_base_payload(
                status="INVALID_INPUT",
                code=code_configuration.concrete_edition,
                missing=[],
                warnings=invalid,
            ),
            message="One or more inputs are outside the supported engineering range:\n" + "\n".join(f"- {item}" for item in invalid),
            requires_approval=False,
            validation_status=None,
        )

    missing = _missing_required(parsed)
    if missing:
        listed = "\n".join(f"• {REQUIRED_LABELS[key]}" for key in missing)
        return AciRcBeamCheckOutcome(
            status="MISSING_REQUIRED_INPUT",
            payload=_base_payload(
                status="MISSING_REQUIRED_INPUT",
                code=code_configuration.concrete_edition,
                missing=[REQUIRED_LABELS[key] for key in missing],
                warnings=[],
            ),
            message=(
                "I need the following information before I can perform the ACI 318 RC beam check:\n\n"
                f"{listed}\n\n"
                "Please provide the missing values. I will not invent engineering parameters. "
                "This check does not parse ETABS/SAP2000/SAFE/DWG files yet — attach them for context only."
            ),
            requires_approval=False,
            validation_status=None,
        )

    mu_kn_m = parsed.mu_kn_m
    vu_kn = parsed.vu_kn
    demand_source = "user_supplied"
    if mu_kn_m is None or vu_kn is None:
        mu_kn_m = parsed.uniform_load_kn_m * parsed.span_m * parsed.span_m / 8.0
        vu_kn = parsed.uniform_load_kn_m * parsed.span_m / 2.0
        demand_source = "simply_supported_udl"

    width_in = units.convert(
        parsed.width_mm, from_unit="mm", to_unit="in", quantity_type=EngineeringQuantityType.LENGTH
    ).value
    height_in = units.convert(
        parsed.height_mm, from_unit="mm", to_unit="in", quantity_type=EngineeringQuantityType.LENGTH
    ).value
    d_in = units.convert(
        parsed.effective_depth_mm, from_unit="mm", to_unit="in", quantity_type=EngineeringQuantityType.LENGTH
    ).value
    fc_psi = units.convert(
        parsed.fc_mpa, from_unit="MPa", to_unit="psi", quantity_type=EngineeringQuantityType.STRESS
    ).value
    fy_psi = units.convert(
        parsed.fy_mpa, from_unit="MPa", to_unit="psi", quantity_type=EngineeringQuantityType.STRESS
    ).value
    as_in2 = units.convert(
        parsed.as_mm2, from_unit="mm2", to_unit="in2", quantity_type=EngineeringQuantityType.AREA
    ).value
    mu_kipft = units.convert(
        mu_kn_m, from_unit="kN·m", to_unit="kip-ft", quantity_type=EngineeringQuantityType.MOMENT
    ).value
    vu_kip = units.convert(
        vu_kn, from_unit="kN", to_unit="kip", quantity_type=EngineeringQuantityType.FORCE
    ).value

    warnings: list[str] = []
    if parsed.effective_depth_mm >= parsed.height_mm:
        warnings.append("Effective depth d must be less than overall height h.")
        return AciRcBeamCheckOutcome(
            status="INVALID_INPUT",
            payload=_base_payload(
                status="INVALID_INPUT",
                code=code_configuration.concrete_edition,
                missing=[],
                warnings=warnings,
            ),
            message="Effective depth d is not less than overall height h.",
            requires_approval=False,
            validation_status=None,
        )

    flexure = code_engine.run_check(
        plugin_id,
        "CONCRETE_BEAM_FLEXURE",
        {
            "Mu_kipft": mu_kipft,
            "fc_psi": fc_psi,
            "fy_psi": fy_psi,
            "width_in": width_in,
            "depth_in": height_in,
            "d_in": d_in,
            "As_in2": as_in2,
        },
        code_configuration=code_configuration,
    )
    shear = code_engine.run_check(
        plugin_id,
        "CONCRETE_BEAM_SHEAR",
        {
            "Vu_kip": vu_kip,
            "fc_psi": fc_psi,
            "width_in": width_in,
            "depth_in": height_in,
            "d_in": d_in,
        },
        code_configuration=code_configuration,
    )

    phi_mn_kipft = float(flexure.metadata.get("phiMn_kipft") or 0.0)
    phi_vc_kip = float(shear.metadata.get("phiVc_kip") or 0.0)
    phi_mn_kn_m = units.convert(
        phi_mn_kipft, from_unit="kip-ft", to_unit="kN·m", quantity_type=EngineeringQuantityType.MOMENT
    ).value
    phi_vc_kn = units.convert(
        phi_vc_kip, from_unit="kip", to_unit="kN", quantity_type=EngineeringQuantityType.FORCE
    ).value
    flexure_util = float(flexure.metadata.get("utilization") or 0.0)
    shear_util = float(shear.metadata.get("utilization") or 0.0)
    governing = max(flexure_util, shear_util)
    passed = flexure.outcome.value == "PASS" and shear.outcome.value == "PASS"
    status = "PASS" if passed else "FAIL"

    payload = {
        "kind": ACI_RC_BEAM_KIND,
        "status": status,
        "demo": False,
        "disclaimer": (
            "Simplified ACI 318-25 beam check. φ is fixed (0.90 flexure, 0.75 shear). "
            "Shear is concrete capacity φVc only — stirrups are not designed. "
            "Not a construction document. Independent engineer review is required."
        ),
        "code": code_configuration.concrete_edition,
        "plugin_id": plugin_id,
        "demand_source": demand_source,
        "input_units": "SI (mm, MPa, kN, kN·m, mm²)",
        "internal_units": "US customary for ACI plugin (in, psi, kip, kip-ft, in²)",
        "output_units": "SI and US customary",
        "inputs": {
            "span_m": parsed.span_m,
            "uniform_load_kn_m": parsed.uniform_load_kn_m,
            "width_mm": parsed.width_mm,
            "height_mm": parsed.height_mm,
            "effective_depth_mm": parsed.effective_depth_mm,
            "fc_mpa": parsed.fc_mpa,
            "fy_mpa": parsed.fy_mpa,
            "as_mm2": parsed.as_mm2,
            "provided": list(dict.fromkeys(parsed.provided)),
        },
        "demands": {
            "mu_kn_m": round(mu_kn_m, 4),
            "vu_kn": round(vu_kn, 4),
            "mu_kipft": round(mu_kipft, 4),
            "vu_kip": round(vu_kip, 4),
        },
        "results": {
            "phi_mn_kn_m": round(phi_mn_kn_m, 4),
            "phi_vc_kn": round(phi_vc_kn, 4),
            "phi_mn_kipft": round(phi_mn_kipft, 4),
            "phi_vc_kip": round(phi_vc_kip, 4),
            "flexure_utilization": round(flexure_util, 4),
            "shear_utilization": round(shear_util, 4),
            "governing_utilization": round(governing, 4),
            "flexure_outcome": flexure.outcome.value,
            "shear_outcome": shear.outcome.value,
        },
        "code_configuration_validation": {
            "is_valid": config_validation.is_valid,
            "warnings": list(config_validation.warnings),
        },
        "checks": [flexure.model_dump(mode="json"), shear.model_dump(mode="json")],
        "assumptions": [
            "Simply supported single span if Mu/Vu were computed from w and L (M=wL²/8, V=wL/2)",
            "ACI 318-25 Whitney rectangular stress block with provided As",
            "φMn uses φ = 0.90 (tension-controlled assumed; strain check is not performed)",
            "φVc = 0.75 · 2√f'c · b · d (concrete only; no Vs, λ, or Av)",
            "No CSI/ETABS/SAP2000/SAFE/AutoCAD execution",
        ],
        "warnings": warnings,
        "missing": [],
        "fields": [
            {"label": "Code", "value": code_configuration.concrete_edition, "unit": None},
            {"label": "Section", "value": f"{parsed.width_mm:.0f} × {parsed.height_mm:.0f}", "unit": "mm"},
            {"label": "Effective depth", "value": f"{parsed.effective_depth_mm:.0f}", "unit": "mm"},
            {"label": "f'c", "value": f"{parsed.fc_mpa:.1f}", "unit": "MPa"},
            {"label": "fy", "value": f"{parsed.fy_mpa:.0f}", "unit": "MPa"},
            {"label": "As", "value": f"{parsed.as_mm2:.0f}", "unit": "mm²"},
            {"label": "Mu", "value": f"{mu_kn_m:.2f}", "unit": "kN·m"},
            {"label": "φMn", "value": f"{phi_mn_kn_m:.2f}", "unit": "kN·m"},
            {"label": "Flexure utilization", "value": f"{flexure_util:.3f}", "unit": None},
            {"label": "Vu", "value": f"{vu_kn:.2f}", "unit": "kN"},
            {"label": "φVc", "value": f"{phi_vc_kn:.2f}", "unit": "kN"},
            {"label": "Shear utilization", "value": f"{shear_util:.3f}", "unit": None},
            {"label": "Governing check", "value": status, "unit": None},
        ],
    }
    message = _markdown(payload, status)
    return AciRcBeamCheckOutcome(
        status=status,
        payload=payload,
        message=message,
        requires_approval=True,
        validation_status=status,
    )


def _fill_from_text(parsed: AciRcBeamParsedInputs, text: str) -> None:
    pairs: list[tuple[str, tuple[str, ...]]] = [
        ("span_m", (r"span\s*[:=]?\s*(\d+(?:\.\d+)?)\s*m", r"(\d+(?:\.\d+)?)\s*m(?:eter)?s?\b")),
        ("uniform_load_kn_m", (r"(\d+(?:\.\d+)?)\s*kN\s*/\s*m",)),
        ("width_mm", (r"\bb\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm",)),
        ("height_mm", (r"\bh\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm",)),
        ("effective_depth_mm", (r"\bd\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm",)),
        ("fc_mpa", (r"fc['’]?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*MPa", r"fc['’]?\s*[:=]?\s*(\d+(?:\.\d+)?)")),
        ("fy_mpa", (r"fy\s*[:=]?\s*(\d+(?:\.\d+)?)\s*MPa", r"fy\s*[:=]?\s*(\d+(?:\.\d+)?)")),
        ("as_mm2", (r"As\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm", r"As\s*[:=]?\s*(\d+(?:\.\d+)?)")),
        ("mu_kn_m", (r"Mu\s*[:=]?\s*(\d+(?:\.\d+)?)\s*kN", r"Mu\s*[:=]?\s*(\d+(?:\.\d+)?)")),
        ("vu_kn", (r"Vu\s*[:=]?\s*(\d+(?:\.\d+)?)\s*kN", r"Vu\s*[:=]?\s*(\d+(?:\.\d+)?)")),
    ]
    section = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm",
        text,
        flags=re.IGNORECASE,
    )
    if section and parsed.width_mm is None:
        parsed.width_mm = float(section.group(1))
        parsed.provided.append("width_mm")
    if section and parsed.height_mm is None:
        parsed.height_mm = float(section.group(2))
        parsed.provided.append("height_mm")
    for name, patterns in pairs:
        if getattr(parsed, name) is not None:
            continue
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                setattr(parsed, name, float(match.group(1)))
                parsed.provided.append(name)
                break


def _missing_required(parsed: AciRcBeamParsedInputs) -> list[str]:
    missing: list[str] = []
    for key in ("width_mm", "height_mm", "effective_depth_mm", "fc_mpa", "fy_mpa", "as_mm2"):
        if getattr(parsed, key) is None:
            missing.append(key)
    has_forces = parsed.mu_kn_m is not None and parsed.vu_kn is not None
    has_udl = parsed.span_m is not None and parsed.uniform_load_kn_m is not None
    if not has_forces and not has_udl:
        missing.append("demands")
    return missing


def _invalid_ranges(parsed: AciRcBeamParsedInputs) -> list[str]:
    issues: list[str] = []
    for key, (low, high, label) in _RANGES.items():
        value = getattr(parsed, key)
        if value is None:
            continue
        if value < low or value > high:
            issues.append(f"{label} must be between {low:g} and {high:g}.")
    return issues


def _standard_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(
            str(value.get(key) or "")
            for key in ("family", "edition", "full_designation")
        )
    return " ".join(
        str(getattr(value, key, "") or "")
        for key in ("family", "edition", "full_designation")
    )


def _code_configuration(context: dict[str, Any]) -> CodeConfiguration:
    raw = context.get("code_configuration")
    if isinstance(raw, dict):
        try:
            return CodeConfiguration.model_validate(raw)
        except Exception:
            pass
    return create_software_default_code_configuration()


def _base_payload(*, status: str, code: str | None, missing: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "kind": ACI_RC_BEAM_KIND,
        "status": status,
        "demo": False,
        "code": code,
        "missing": missing,
        "warnings": warnings,
        "fields": [],
        "assumptions": [],
        "results": {},
    }


def _markdown(payload: dict[str, Any], status: str) -> str:
    results = payload["results"]
    return "\n".join(
        [
            "### ACI 318 RC beam check",
            f"**Status:** {status}",
            f"**Code:** {payload['code']}",
            "",
            f"- Mu = {payload['demands']['mu_kn_m']:.2f} kN·m, φMn = {results['phi_mn_kn_m']:.2f} kN·m "
            f"(utilization {results['flexure_utilization']:.3f}, {results['flexure_outcome']})",
            f"- Vu = {payload['demands']['vu_kn']:.2f} kN, φVc = {results['phi_vc_kn']:.2f} kN "
            f"(utilization {results['shear_utilization']:.3f}, {results['shear_outcome']})",
            "",
            "Assumptions:",
            *[f"- {item}" for item in payload["assumptions"]],
            "",
            f"*{payload['disclaimer']}*",
        ]
    )
