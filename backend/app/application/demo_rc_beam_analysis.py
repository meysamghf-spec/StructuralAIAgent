"""Deterministic simply-supported RC beam Demo analysis.

This is an explicit demonstration workflow. It does not invoke ETABS, SAP2000,
SAFE, AutoCAD, or any live solver. Outputs are labeled as Demo calculations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

DEMO_DISCLAIMER = (
    "Demo calculation. Final engineering decisions require verification by a "
    "qualified engineer."
)

_DEFAULT_SPAN_M = 6.0
_DEFAULT_UDL_KN_M = 20.0
_DEFAULT_WIDTH_MM = 300.0
_DEFAULT_HEIGHT_MM = 500.0
_DEFAULT_EFFECTIVE_DEPTH_MM = 450.0
_DEFAULT_FC_MPA = 25.0
_DEFAULT_FY_MPA = 400.0

_BEAM_TERMS = ("beam", "تیر")
_ANALYSIS_TERMS = (
    "analyze",
    "analysis",
    "simply supported",
    "uniform load",
    "udl",
    "span",
    "kN/m",
    "kn/m",
    "reinforced concrete",
    "concrete",
    "rc ",
)


@dataclass(frozen=True)
class DemoRcBeamInputs:
    span_m: float
    uniform_load_kn_m: float
    width_mm: float
    height_mm: float
    effective_depth_mm: float
    fc_mpa: float
    fy_mpa: float
    parsed_from_request: tuple[str, ...]


@dataclass(frozen=True)
class DemoRcBeamResult:
    inputs: DemoRcBeamInputs
    max_moment_kn_m: float
    max_shear_kn: float
    moment_formula: str
    shear_formula: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "demo_rc_beam",
            "status": "completed",
            "label": "STRUCTURAL ANALYSIS",
            "demo": True,
            "disclaimer": DEMO_DISCLAIMER,
            "code": "Demo / configured project code profile",
            "inputs": {
                "span_m": self.inputs.span_m,
                "uniform_load_kn_m": self.inputs.uniform_load_kn_m,
                "width_mm": self.inputs.width_mm,
                "height_mm": self.inputs.height_mm,
                "effective_depth_mm": self.inputs.effective_depth_mm,
                "fc_mpa": self.inputs.fc_mpa,
                "fy_mpa": self.inputs.fy_mpa,
                "parsed_from_request": list(self.inputs.parsed_from_request),
            },
            "results": {
                "max_moment_kn_m": self.max_moment_kn_m,
                "max_shear_kn": self.max_shear_kn,
            },
            "calculations": {
                "moment": self.moment_formula,
                "shear": self.shear_formula,
            },
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
            "fields": [
                {"label": "Span", "value": f"{self.inputs.span_m:.2f}", "unit": "m"},
                {
                    "label": "Uniform Load",
                    "value": f"{self.inputs.uniform_load_kn_m:.2f}",
                    "unit": "kN/m",
                },
                {
                    "label": "Section",
                    "value": f"{self.inputs.width_mm:.0f} × {self.inputs.height_mm:.0f}",
                    "unit": "mm",
                },
                {
                    "label": "Effective depth",
                    "value": f"{self.inputs.effective_depth_mm:.0f}",
                    "unit": "mm",
                },
                {"label": "fc", "value": f"{self.inputs.fc_mpa:.0f}", "unit": "MPa"},
                {"label": "fy", "value": f"{self.inputs.fy_mpa:.0f}", "unit": "MPa"},
                {
                    "label": "Maximum Moment",
                    "value": f"{self.max_moment_kn_m:.2f}",
                    "unit": "kN·m",
                },
                {
                    "label": "Maximum Shear",
                    "value": f"{self.max_shear_kn:.2f}",
                    "unit": "kN",
                },
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            "### Structural analysis (Demo)",
            f"**Status:** Completed",
            "",
            f"- Span: {self.inputs.span_m:.2f} m",
            f"- Uniform load: {self.inputs.uniform_load_kn_m:.2f} kN/m",
            f"- Section: {self.inputs.width_mm:.0f} mm × {self.inputs.height_mm:.0f} mm",
            f"- Maximum moment: **{self.max_moment_kn_m:.2f} kN·m** ({self.moment_formula})",
            f"- Maximum shear: **{self.max_shear_kn:.2f} kN** ({self.shear_formula})",
            "",
            "Assumptions:",
            *[f"- {item}" for item in self.assumptions],
            "",
            f"*{DEMO_DISCLAIMER}*",
        ]
        return "\n".join(lines)

    def memory_summary(self) -> str:
        return (
            "Demo RC beam analysis: simply supported, "
            f"span {self.inputs.span_m:.2f} m, "
            f"uniform load {self.inputs.uniform_load_kn_m:.2f} kN/m, "
            f"Mmax={self.max_moment_kn_m:.2f} kN·m, "
            f"Vmax={self.max_shear_kn:.2f} kN. {DEMO_DISCLAIMER}"
        )


def is_demo_rc_beam_request(user_request: str) -> bool:
    normalized = user_request.lower()
    if not any(term in normalized for term in _BEAM_TERMS):
        return False
    return any(term in normalized for term in _ANALYSIS_TERMS)


def analyze_simply_supported_rc_beam(user_request: str) -> DemoRcBeamResult | None:
    if not is_demo_rc_beam_request(user_request):
        return None

    parsed: list[str] = []
    span_m = _parse_first_float(
        user_request,
        (r"(\d+(?:\.\d+)?)\s*m(?:eter)?s?\b", r"span\s*[:=]?\s*(\d+(?:\.\d+)?)"),
        _DEFAULT_SPAN_M,
        parsed,
        "span_m",
    )
    uniform_load = _parse_first_float(
        user_request,
        (
            r"(\d+(?:\.\d+)?)\s*kN\s*/\s*m",
            r"uniform(?:ly)?\s+load(?:ed|ing)?[^\d]{0,24}(\d+(?:\.\d+)?)",
        ),
        _DEFAULT_UDL_KN_M,
        parsed,
        "uniform_load_kn_m",
    )
    width_mm = _parse_first_float(
        user_request,
        (r"\bb\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm",),
        _DEFAULT_WIDTH_MM,
        parsed,
        "width_mm",
    )
    height_mm = _parse_first_float(
        user_request,
        (r"\bh\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm",),
        _DEFAULT_HEIGHT_MM,
        parsed,
        "height_mm",
    )
    effective_depth = _parse_first_float(
        user_request,
        (r"\bd\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm",),
        _DEFAULT_EFFECTIVE_DEPTH_MM,
        parsed,
        "effective_depth_mm",
    )
    fc_mpa = _parse_first_float(
        user_request,
        (r"fc['’]?\s*[:=]?\s*(\d+(?:\.\d+)?)", r"(\d+(?:\.\d+)?)\s*MPa"),
        _DEFAULT_FC_MPA,
        parsed,
        "fc_mpa",
    )
    fy_mpa = _parse_first_float(
        user_request,
        (r"fy\s*[:=]?\s*(\d+(?:\.\d+)?)", r"grade\s+(\d+(?:\.\d+)?)"),
        _DEFAULT_FY_MPA,
        parsed,
        "fy_mpa",
    )

    max_moment = uniform_load * span_m * span_m / 8.0
    max_shear = uniform_load * span_m / 2.0
    warnings: list[str] = []
    if effective_depth >= height_mm:
        warnings.append("Effective depth d is not less than overall height h.")

    inputs = DemoRcBeamInputs(
        span_m=span_m,
        uniform_load_kn_m=uniform_load,
        width_mm=width_mm,
        height_mm=height_mm,
        effective_depth_mm=effective_depth,
        fc_mpa=fc_mpa,
        fy_mpa=fy_mpa,
        parsed_from_request=tuple(parsed),
    )
    return DemoRcBeamResult(
        inputs=inputs,
        max_moment_kn_m=round(max_moment, 4),
        max_shear_kn=round(max_shear, 4),
        moment_formula="M = wL²/8",
        shear_formula="V = wL/2",
        assumptions=(
            "Simply supported single span",
            "Uniformly distributed load only (self-weight included in w if intended)",
            "Linear elastic beam theory; no continuity or pattern loading",
            "Section and material values are demonstration defaults unless stated",
            "No CSI/ETABS/SAP2000/SAFE/AutoCAD execution was performed",
        ),
        warnings=tuple(warnings),
    )


def _parse_first_float(
    text: str,
    patterns: tuple[str, ...],
    default: float,
    parsed: list[str],
    field_name: str,
) -> float:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            parsed.append(field_name)
            return float(match.group(1))
    return default
