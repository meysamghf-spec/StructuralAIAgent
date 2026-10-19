"""Common, structure-type-independent assumptions registry + one shared prompt parser.

Every engineering module (RC frame / Mabhas 9, rebar detailing, Standard 2800, foundation, AISC steel, ACI, ...)
registers its assumption keys with type, unit, default, valid range and English/Persian aliases:

    register_module("mabhas9", [AssumptionSpec("stirrup_db", "int", 10, unit="mm", rng=(8, 16), aliases=[...]), ...])

`parse(text, modules)` then turns a free-text prompt (Persian or English, Persian digits OK) into
{module: {key: value}} plus range errors, without any module-specific parsing code. `target` says where a value
lives: "assumption" (the per-project assumptions record) or "input" (a model/input field of the module's run).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")
NUM = r"(\d+(?:\.\d+)?)"
GAP = r"[^\d\n.,،;؛]{0,14}?"  # words between an alias and its value


def norm(text: str) -> str:
    return (text or "").translate(_DIGITS).replace("\u200c", " ").replace("×", "x").lower()


@dataclass(frozen=True)
class AssumptionSpec:
    key: str
    kind: str  # number | int | choice | list
    default: Any
    label_en: str = ""
    label_fa: str = ""
    unit: str = ""
    rng: tuple[float, float] | None = None
    aliases: tuple[str, ...] = ()          # regex fragments naming the quantity (en + fa)
    choices: dict[str, str] = field(default_factory=dict)  # value -> regex fragment
    standalone_choices: bool = False      # a choice word alone is enough (e.g. "ln/4")
    value_before_alias: bool = False       # "9 m stock bars"
    unit_scale: dict[str, float] = field(default_factory=dict)  # "cm": 10 -> converted to `unit`
    target: str = "assumption"            # assumption | input
    field_name: str | None = None          # input field name when target == "input"
    side_effects: dict[str, dict[str, Any]] = field(default_factory=dict)  # choice -> extra {target_field: value}


_REGISTRY: dict[str, list[AssumptionSpec]] = {}


def register_module(module: str, specs: list[AssumptionSpec]) -> None:
    _REGISTRY[module] = list(specs)


def modules() -> list[str]:
    return list(_REGISTRY)


def specs(module: str) -> list[AssumptionSpec]:
    return list(_REGISTRY.get(module, []))


def defaults(module_list: list[str]) -> dict[str, Any]:
    return {s.key: s.default for m in module_list for s in specs(m) if s.target == "assumption"}


def _alias(spec: AssumptionSpec) -> str:
    return "(?:" + "|".join(spec.aliases) + ")"


def _parse_one(spec: AssumptionSpec, t: str) -> Any:
    al = _alias(spec) if spec.aliases else None
    if spec.kind == "choice":
        for value, pat in spec.choices.items():
            if (spec.standalone_choices and re.search(pat, t)) or (al and re.search(rf"{al}[^\n.;؛]{{0,30}}?(?:{pat})|(?:{pat})[^\n.;؛]{{0,12}}{al}", t)):
                return value
        return None
    if not al:
        return None
    if spec.kind == "list":
        m = re.search(rf"{al}[^\n.;؛]{{0,22}}?([Φφø]?\s*\d+(?:\s*(?:,|،|و|and|/|-)\s*[Φφø]?\s*\d+)*)", t)
        if not m:
            return None
        vals = sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
        return vals or None
    units = "|".join(re.escape(u) for u in [*spec.unit_scale, spec.unit] if u)
    upat = rf"\s*({units})?" if units else "()"
    m = re.search(rf"{al}{GAP}[=:]?\s*[Φφø]?\s*{NUM}{upat}", t)
    if not m and spec.value_before_alias:
        m = re.search(rf"{NUM}{upat}[^\d\n]{{0,6}}{al}", t)
    if not m:
        return None
    v = float(m.group(1)) * spec.unit_scale.get(m.group(2) or "", 1.0)
    return int(round(v)) if spec.kind == "int" else v


def parse(text: str, module_list: list[str] | None = None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Shared prompt parser -> ({module: {key: value}}, range errors). Unregistered modules are ignored."""
    t = norm(text)
    out: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for module in module_list or modules():
        for spec in specs(module):
            v = _parse_one(spec, t)
            if v is None:
                continue
            if spec.rng and spec.kind in ("number", "int") and not (spec.rng[0] <= v <= spec.rng[1]):
                errors.append(f"{spec.label_en or spec.key} = {v:g} {spec.unit} is outside {spec.rng[0]:g}–{spec.rng[1]:g} (ignored)")
                continue
            if spec.rng and spec.kind == "list" and any(not (spec.rng[0] <= x <= spec.rng[1]) for x in v):
                errors.append(f"{spec.label_en or spec.key} {v} outside {spec.rng[0]:g}–{spec.rng[1]:g} (ignored)")
                continue
            out.setdefault(module, {})[spec.key] = v
    return out, errors


def split_targets(parsed: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """{module: {key: v}} -> (assumption record updates, input-field updates), applying choice side effects."""
    a: dict[str, Any] = {}
    inputs: dict[str, Any] = {}
    for module, vals in parsed.items():
        by_key = {s.key: s for s in specs(module)}
        for k, v in vals.items():
            s = by_key[k]
            if s.target == "input":
                inputs[s.field_name or k] = v
            else:
                a[k] = v
            inputs.update(s.side_effects.get(str(v), {}))
    return a, inputs


def fmt_value(v: Any) -> str:
    if isinstance(v, list):
        return ", ".join(f"Φ{x}" for x in v)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return "—" if v is None else str(v)


def describe(module_list: list[str], record: dict[str, Any] | None, inputs: dict[str, Any] | None = None,
             lang: str = "en", changed: set[str] | None = None) -> list[str]:
    """Current value of every registered key of these modules (record > input field > default)."""
    rec, inputs = record or {}, inputs or {}
    rows, seen = [], set()
    for module in module_list:
        for s in specs(module):
            if s.key in seen:
                continue
            seen.add(s.key)
            v = inputs.get(s.field_name or s.key, s.default) if s.target == "input" else rec.get(s.key, s.default)
            unit = f" {s.unit}" if s.unit and s.kind != "choice" else ""
            mark = " *" if changed and (s.key in changed or (s.field_name or "") in changed) else ""
            rows.append(f"{(s.label_fa if lang == 'fa' else s.label_en) or s.key}: {fmt_value(v)}{unit}{mark}")
    return rows


SHOW_PATTERN = (r"show (?:the )?(?:current )?assumptions|list (?:the )?assumptions|current assumptions|what are the assumptions"
                r"|فرض.?ها(?:ی فعلی)?(?: را)? نشان|فرضیات(?: را)? نشان|فرض.?های فعلی|نمایش فرض")


def is_show_command(text: str) -> bool:
    return bool(re.search(SHOW_PATTERN, norm(text)))
