"""Standalone AISC 360 steel beam flexure check (compact F2 plastic moment).

Uses the existing CodeEngine AISC plugin and UnitConversionService.
Does not invent missing section properties, yield strength, or demands.
Does not call CSI/CAD software.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.application.code_engine_service import CodeEngineService
from app.application.unit_conversion_service import UnitConversionService
from app.domain.models.pem import CodeConfiguration, create_software_default_code_configuration
from app.domain.models.units import EngineeringQuantityType

AISC_STEEL_BEAM_KIND = "aisc_steel_beam"

_DESIGN_TERMS = (
    "design",
    "check",
    "capacity",
    "utilization",
    "φmn",
    "phimn",
    "phi mn",
    "aisc",
    "flexure",
    "plastic moment",
    "zx",
)
_STEEL_TERMS = (
    "steel",
    "aisc",
    "w-shape",
    "wide flange",
    "w shape",
)
_BEAM_TERMS = (
    "beam",
    "girder",
    "member",
    "w-shape",
    "wide flange",
)
_CONCRETE_TERMS = (
    "rc ",
    "rc beam",
    "reinforced concrete",
    "concrete",
    "aci",
    "rebar",
    "f'c",
    "fc'",
    "بتن",
)

_RANGES = {
    "span_m": (0.5, 50.0, "Span"),
    "uniform_load_kn_m": (0.01, 1000.0, "Uniform load"),
    "fy_ksi": (36.0, 100.0, "Steel yield Fy"),
    "zx_in3": (1.0, 4000.0, "Plastic section modulus Zx"),
    "mu_kipft": (0.01, 50000.0, "Factored moment Mu"),
}

REQUIRED_LABELS = {
    "fy_ksi": "Steel yield strength Fy",
    "zx_in3": "Plastic section modulus Zx",
    "demands": "Demand Mu, or span and uniform load",
}


@dataclass
class AiscSteelBeamParsedInputs:
    span_m: float | None = None
    uniform_load_kn_m: float | None = None
    fy_ksi: float | None = None
    zx_in3: float | None = None
    mu_kipft: float | None = None
    section_label: str | None = None
    provided: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AiscSteelBeamCheckOutcome:
    status: str
    payload: dict[str, Any]
    message: str
    requires_approval: bool
    validation_status: str | None


def is_aisc_steel_beam_check_request(user_request: str) -> bool:
    normalized = user_request.lower()
    if any(term in normalized for term in _CONCRETE_TERMS) and not any(
        term in normalized for term in ("steel", "aisc")
    ):
        return False
    if not any(term in normalized for term in _STEEL_TERMS) and not re.search(
        r"\bw\d+\s*x\s*\d+", normalized
    ):
        return False
    if not any(term in normalized for term in _DESIGN_TERMS):
        return False
    if not any(term in normalized for term in _BEAM_TERMS) and not re.search(
        r"\bw\d+\s*x\s*\d+", normalized
    ):
        return False
    return True


def resolve_aisc_plugin_id(code_configuration: CodeConfiguration) -> str | None:
    standard = code_configuration.steel_standard
    plugin_hint = getattr(standard, "plugin_id", None)
    if plugin_hint is None and isinstance(standard, dict):
        plugin_hint = standard.get("plugin_id")
    if plugin_hint == "AISC360-22":
        return "AISC360-22"

    token = "".join(
        part.upper().replace(" ", "")
        for part in (
            _standard_text(standard),
            code_configuration.steel_edition or "",
        )
    )
    if "AISC" not in token and "360" not in token:
        return None
    if "360" in token and ("22" in token or "2022" in token):
        return "AISC360-22"
    return None


def parse_aisc_steel_beam_inputs(
    user_request: str, parameters: dict[str, Any] | None = None
) -> AiscSteelBeamParsedInputs:
    parsed = AiscSteelBeamParsedInputs()
    source = parameters or {}
    nested = source.get("aisc_steel_beam") if isinstance(source.get("aisc_steel_beam"), dict) else {}
    units = UnitConversionService()

    def take_raw(name: str, aliases: tuple[str, ...] = ()) -> float | None:
        for key in (name, *aliases):
            raw = nested.get(key) if key in nested else source.get(key)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                parsed.provided.append(name)
                return float(raw)
        return None

    fy_ksi = take_raw("fy_ksi", ("Fy_ksi",))
    fy_mpa = take_raw("fy_mpa", ("fy",))
    if fy_ksi is not None:
        parsed.fy_ksi = fy_ksi
    elif fy_mpa is not None:
        parsed.fy_ksi = units.convert(
            fy_mpa, from_unit="MPa", to_unit="ksi", quantity_type=EngineeringQuantityType.STRESS
        ).value
        parsed.provided.append("fy_ksi")

    zx_in3 = take_raw("zx_in3", ("Zx_in3", "zx"))
    zx_mm3 = take_raw("zx_mm3", ("Zx_mm3",))
    zx_cm3 = take_raw("zx_cm3", ("Zx_cm3",))
    if zx_in3 is not None:
        parsed.zx_in3 = zx_in3
    elif zx_mm3 is not None:
        parsed.zx_in3 = units.convert(
            zx_mm3, from_unit="mm3", to_unit="in3", quantity_type=EngineeringQuantityType.VOLUME
        ).value
        parsed.provided.append("zx_in3")
    elif zx_cm3 is not None:
        parsed.zx_in3 = units.convert(
            zx_cm3, from_unit="cm3", to_unit="in3", quantity_type=EngineeringQuantityType.VOLUME
        ).value
        parsed.provided.append("zx_in3")

    mu_kipft = take_raw("mu_kipft", ("Mu_kipft",))
    mu_kn_m = take_raw("mu_kn_m", ("Mu_kn_m", "mu"))
    if mu_kipft is not None:
        parsed.mu_kipft = mu_kipft
    elif mu_kn_m is not None:
        parsed.mu_kipft = units.convert(
            mu_kn_m, from_unit="kN·m", to_unit="kip-ft", quantity_type=EngineeringQuantityType.MOMENT
        ).value
        parsed.provided.append("mu_kipft")

    span_m = take_raw("span_m", ("span",))
    span_ft = take_raw("span_ft")
    if span_m is not None:
        parsed.span_m = span_m
    elif span_ft is not None:
        parsed.span_m = units.convert(
            span_ft, from_unit="ft", to_unit="m", quantity_type=EngineeringQuantityType.LENGTH
        ).value
        parsed.provided.append("span_m")

    w_kn_m = take_raw("uniform_load_kn_m", ("w_kn_m", "uniform_load"))
    w_kip_ft = take_raw("uniform_load_kip_ft", ("w_kip_ft",))
    if w_kn_m is not None:
        parsed.uniform_load_kn_m = w_kn_m
    elif w_kip_ft is not None:
        parsed.uniform_load_kn_m = _linear_load_to_kn_m(w_kip_ft, "kip", "ft", units)
        parsed.provided.append("uniform_load_kn_m")

    label = nested.get("section_label") if "section_label" in nested else source.get("section_label")
    if isinstance(label, str) and label.strip():
        parsed.section_label = label.strip()
        parsed.provided.append("section_label")

    _fill_from_text(parsed, user_request or "", units)
    return parsed


def run_aisc_steel_beam_check(
    *,
    user_request: str,
    parameters: dict[str, Any] | None,
    context: dict[str, Any],
    code_engine: CodeEngineService,
    units: UnitConversionService | None = None,
) -> AiscSteelBeamCheckOutcome | None:
    if not is_aisc_steel_beam_check_request(user_request):
        return None

    units = units or UnitConversionService()
    code_configuration = _code_configuration(context)
    plugin_id = resolve_aisc_plugin_id(code_configuration)
    config_validation = code_engine.validate_configuration(code_configuration)
    if plugin_id is None:
        edition = code_configuration.steel_edition or _standard_text(code_configuration.steel_standard)
        return AiscSteelBeamCheckOutcome(
            status="UNSUPPORTED_CODE",
            payload=_base_payload(
                status="UNSUPPORTED_CODE",
                code=edition,
                missing=[],
                warnings=[],
            ),
            message=(
                f"AISC 360-22 steel beam flexure is not available for the configured steel code "
                f"'{edition}'. This capability currently supports ANSI/AISC 360-22 only. "
                "It does not pretend another standard was checked."
            ),
            requires_approval=False,
            validation_status=None,
        )

    parsed = parse_aisc_steel_beam_inputs(user_request, parameters)
    invalid = _invalid_ranges(parsed)
    if invalid:
        return AiscSteelBeamCheckOutcome(
            status="INVALID_INPUT",
            payload=_base_payload(
                status="INVALID_INPUT",
                code=code_configuration.steel_edition,
                missing=[],
                warnings=invalid,
            ),
            message="One or more inputs are outside the supported engineering range:\n"
            + "\n".join(f"- {item}" for item in invalid),
            requires_approval=False,
            validation_status=None,
        )

    missing = _missing_required(parsed)
    if missing:
        listed = "\n".join(f"• {REQUIRED_LABELS[key]}" for key in missing)
        extras = []
        if parsed.section_label and "zx_in3" in missing:
            extras.append(
                f"Section designation '{parsed.section_label}' was noted as a label only. "
                "This product does not contain an AISC shape database, so Zx is not inferred."
            )
        extra_text = ("\n\n" + " ".join(extras)) if extras else ""
        return AiscSteelBeamCheckOutcome(
            status="MISSING_REQUIRED_INPUT",
            payload=_base_payload(
                status="MISSING_REQUIRED_INPUT",
                code=code_configuration.steel_edition,
                missing=[REQUIRED_LABELS[key] for key in missing],
                warnings=extras,
            ),
            message=(
                "I need the following information before I can perform the AISC 360 steel beam flexure check:\n\n"
                f"{listed}\n\n"
                "Please provide the missing values. I will not invent Fy, Zx, or demands, "
                "and I will not look up W-shape properties. "
                "This check does not parse ETABS/SAP2000/SAFE/DWG files yet — attach them for context only."
                f"{extra_text}"
            ),
            requires_approval=False,
            validation_status=None,
        )

    mu_kipft = parsed.mu_kipft
    demand_source = "user_supplied"
    if mu_kipft is None:
        mu_kn_m = parsed.uniform_load_kn_m * parsed.span_m * parsed.span_m / 8.0
        mu_kipft = units.convert(
            mu_kn_m, from_unit="kN·m", to_unit="kip-ft", quantity_type=EngineeringQuantityType.MOMENT
        ).value
        demand_source = "simply_supported_udl"

    flexure = code_engine.run_check(
        plugin_id,
        "STEEL_BEAM_FLEXURE",
        {
            "Mu_kipft": mu_kipft,
            "Fy_ksi": parsed.fy_ksi,
            "Zx_in3": parsed.zx_in3,
        },
        code_configuration=code_configuration,
    )

    phi_mn_kipft = float(flexure.metadata.get("phiMn_kipft") or 0.0)
    flexure_util = float(flexure.metadata.get("utilization") or 0.0)
    phi_mn_kn_m = units.convert(
        phi_mn_kipft, from_unit="kip-ft", to_unit="kN·m", quantity_type=EngineeringQuantityType.MOMENT
    ).value
    mu_kn_m = units.convert(
        mu_kipft, from_unit="kip-ft", to_unit="kN·m", quantity_type=EngineeringQuantityType.MOMENT
    ).value
    fy_mpa = units.convert(
        parsed.fy_ksi, from_unit="ksi", to_unit="MPa", quantity_type=EngineeringQuantityType.STRESS
    ).value
    zx_mm3 = units.convert(
        parsed.zx_in3, from_unit="in3", to_unit="mm3", quantity_type=EngineeringQuantityType.VOLUME
    ).value
    status = "PASS" if flexure.outcome.value == "PASS" else "FAIL"

    payload = {
        "kind": AISC_STEEL_BEAM_KIND,
        "status": status,
        "demo": False,
        "disclaimer": (
            "Simplified AISC 360-22 Chapter F compact-section plastic moment (φb Mn = 0.90 Fy Zx). "
            "Lateral-torsional buckling, compactness, shear, deflection, and axial interaction are not checked. "
            "Not a construction document. Independent engineer review is required."
        ),
        "code": code_configuration.steel_edition,
        "plugin_id": plugin_id,
        "demand_source": demand_source,
        "section_label": parsed.section_label,
        "input_units": "as provided (SI or US customary)",
        "internal_units": "US customary for AISC plugin (ksi, in³, kip-ft)",
        "output_units": "SI and US customary",
        "inputs": {
            "span_m": parsed.span_m,
            "uniform_load_kn_m": parsed.uniform_load_kn_m,
            "fy_ksi": round(parsed.fy_ksi, 4),
            "fy_mpa": round(fy_mpa, 4),
            "zx_in3": round(parsed.zx_in3, 4),
            "zx_mm3": round(zx_mm3, 1),
            "section_label": parsed.section_label,
            "provided": list(dict.fromkeys(parsed.provided)),
        },
        "demands": {
            "mu_kipft": round(mu_kipft, 4),
            "mu_kn_m": round(mu_kn_m, 4),
        },
        "results": {
            "phi_mn_kipft": round(phi_mn_kipft, 4),
            "phi_mn_kn_m": round(phi_mn_kn_m, 4),
            "flexure_utilization": round(flexure_util, 4),
            "governing_utilization": round(flexure_util, 4),
            "flexure_outcome": flexure.outcome.value,
        },
        "code_configuration_validation": {
            "is_valid": config_validation.is_valid,
            "warnings": list(config_validation.warnings),
        },
        "checks": [flexure.model_dump(mode="json")],
        "assumptions": [
            "AISC 360-22 F2 compact I-shaped members bent about the major axis",
            "φb = 0.90; Mn = Mp = Fy Zx (LTB and FLB assumed not to govern)",
            "Unbraced length Lb, Cb, Sx, and compactness are not used",
            "Simply supported single span if Mu was computed from w and L (M=wL²/8)",
            "W-shape names are labels only; Zx is never looked up",
            "No CSI/ETABS/SAP2000/SAFE/AutoCAD execution",
        ],
        "warnings": [],
        "missing": [],
        "fields": [
            {"label": "Code", "value": code_configuration.steel_edition, "unit": None},
            *([{"label": "Section label", "value": parsed.section_label, "unit": None}] if parsed.section_label else []),
            {"label": "Fy", "value": f"{parsed.fy_ksi:.1f}", "unit": "ksi"},
            {"label": "Zx", "value": f"{parsed.zx_in3:.2f}", "unit": "in³"},
            {"label": "Mu", "value": f"{mu_kipft:.2f}", "unit": "kip-ft"},
            {"label": "φMn", "value": f"{phi_mn_kipft:.2f}", "unit": "kip-ft"},
            {"label": "Mu (SI)", "value": f"{mu_kn_m:.2f}", "unit": "kN·m"},
            {"label": "φMn (SI)", "value": f"{phi_mn_kn_m:.2f}", "unit": "kN·m"},
            {"label": "Flexure utilization", "value": f"{flexure_util:.3f}", "unit": None},
            {"label": "Governing check", "value": status, "unit": None},
        ],
    }
    return AiscSteelBeamCheckOutcome(
        status=status,
        payload=payload,
        message=_markdown(payload, status),
        requires_approval=True,
        validation_status=status,
    )


def _fill_from_text(parsed: AiscSteelBeamParsedInputs, text: str, units: UnitConversionService) -> None:
    shape = re.search(r"\b(W\s*\d+\s*x\s*\d+(?:\.\d+)?)\b", text, flags=re.IGNORECASE)
    if shape and parsed.section_label is None:
        parsed.section_label = re.sub(r"\s+", "", shape.group(1).upper().replace("X", "x"))
        parsed.provided.append("section_label")

    fy_match = re.search(r"\bFy\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(ksi|MPa)\b", text, flags=re.IGNORECASE)
    if parsed.fy_ksi is None and fy_match:
        value = float(fy_match.group(1))
        unit = fy_match.group(2).lower()
        parsed.fy_ksi = (
            value
            if unit == "ksi"
            else units.convert(
                value, from_unit="MPa", to_unit="ksi", quantity_type=EngineeringQuantityType.STRESS
            ).value
        )
        parsed.provided.append("fy_ksi")

    zx_match = re.search(
        r"\bZx\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(in(?:\^?3|³)|mm(?:\^?3|³)|cm(?:\^?3|³)|in3|mm3|cm3)\b",
        text,
        flags=re.IGNORECASE,
    )
    if parsed.zx_in3 is None and zx_match:
        value = float(zx_match.group(1))
        unit = zx_match.group(2).lower().replace("³", "3").replace("^3", "3")
        if unit in {"in3", "in"}:
            parsed.zx_in3 = value
        elif unit in {"mm3", "mm"}:
            parsed.zx_in3 = units.convert(
                value, from_unit="mm3", to_unit="in3", quantity_type=EngineeringQuantityType.VOLUME
            ).value
        else:
            parsed.zx_in3 = units.convert(
                value, from_unit="cm3", to_unit="in3", quantity_type=EngineeringQuantityType.VOLUME
            ).value
        parsed.provided.append("zx_in3")

    mu_match = re.search(
        r"\bMu\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(kip-ft|kip·ft|kN[·\-]m|kNm|kN m)\b",
        text,
        flags=re.IGNORECASE,
    )
    if parsed.mu_kipft is None and mu_match:
        value = float(mu_match.group(1))
        unit = mu_match.group(2).lower().replace("·", "-").replace(" ", "")
        if "kip" in unit:
            parsed.mu_kipft = value
        else:
            parsed.mu_kipft = units.convert(
                value, from_unit="kN·m", to_unit="kip-ft", quantity_type=EngineeringQuantityType.MOMENT
            ).value
        parsed.provided.append("mu_kipft")

    span_match = re.search(r"\bspan\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(m|ft)\b", text, flags=re.IGNORECASE)
    if parsed.span_m is None and span_match:
        value = float(span_match.group(1))
        unit = span_match.group(2).lower()
        parsed.span_m = (
            value
            if unit == "m"
            else units.convert(
                value, from_unit="ft", to_unit="m", quantity_type=EngineeringQuantityType.LENGTH
            ).value
        )
        parsed.provided.append("span_m")

    w_si = re.search(r"(\d+(?:\.\d+)?)\s*kN\s*/\s*m", text, flags=re.IGNORECASE)
    w_us = re.search(r"(\d+(?:\.\d+)?)\s*kip\s*/\s*ft", text, flags=re.IGNORECASE)
    if parsed.uniform_load_kn_m is None and w_si:
        parsed.uniform_load_kn_m = float(w_si.group(1))
        parsed.provided.append("uniform_load_kn_m")
    elif parsed.uniform_load_kn_m is None and w_us:
        parsed.uniform_load_kn_m = _linear_load_to_kn_m(float(w_us.group(1)), "kip", "ft", units)
        parsed.provided.append("uniform_load_kn_m")


def _linear_load_to_kn_m(
    value: float, force_unit: str, length_unit: str, units: UnitConversionService
) -> float:
    force_kn = units.convert(
        value, from_unit=force_unit, to_unit="kN", quantity_type=EngineeringQuantityType.FORCE
    ).value
    length_m = units.convert(
        1.0, from_unit=length_unit, to_unit="m", quantity_type=EngineeringQuantityType.LENGTH
    ).value
    return force_kn / length_m


def _missing_required(parsed: AiscSteelBeamParsedInputs) -> list[str]:
    missing: list[str] = []
    for key in ("fy_ksi", "zx_in3"):
        if getattr(parsed, key) is None:
            missing.append(key)
    has_moment = parsed.mu_kipft is not None
    has_udl = parsed.span_m is not None and parsed.uniform_load_kn_m is not None
    if not has_moment and not has_udl:
        missing.append("demands")
    return missing


def _invalid_ranges(parsed: AiscSteelBeamParsedInputs) -> list[str]:
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
        return " ".join(str(value.get(key) or "") for key in ("family", "edition", "full_designation"))
    return " ".join(
        str(getattr(value, key, "") or "") for key in ("family", "edition", "full_designation")
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
        "kind": AISC_STEEL_BEAM_KIND,
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
    demands = payload["demands"]
    return "\n".join(
        [
            "### AISC 360 steel beam flexure check",
            f"**Status:** {status}",
            f"**Code:** {payload['code']}",
            "",
            f"- Mu = {demands['mu_kipft']:.2f} kip-ft ({demands['mu_kn_m']:.2f} kN·m), "
            f"φMn = {results['phi_mn_kipft']:.2f} kip-ft ({results['phi_mn_kn_m']:.2f} kN·m) "
            f"(utilization {results['flexure_utilization']:.3f}, {results['flexure_outcome']})",
            "",
            "Assumptions:",
            *[f"- {item}" for item in payload["assumptions"]],
            "",
            f"*{payload['disclaimer']}*",
        ]
    )
