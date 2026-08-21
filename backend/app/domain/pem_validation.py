"""Deterministic PEM structural integrity validation."""

from __future__ import annotations

from collections import Counter

from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import StructuralModel
from app.domain.models.validation import ValidationCategory, ValidationFinding, ValidationStatus


def validate_structural_model(
    pem: ProjectEngineeringModel,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    model = pem.structural_model
    findings.extend(_validate_geometry(model))
    findings.extend(_validate_materials(model))
    findings.extend(_validate_sections(model))
    findings.extend(_validate_members(model))
    findings.extend(_validate_supports(model))
    findings.extend(_validate_loads(model))
    findings.extend(_validate_load_combinations(model))
    findings.extend(_validate_analysis_model(model))
    findings.extend(_validate_units_consistency(pem))
    return findings


def _duplicate_ids(values: list[str], code: str, label: str) -> list[ValidationFinding]:
    counts = Counter(values)
    duplicates = [item for item, count in counts.items() if count > 1]
    if not duplicates:
        return []
    return [
        ValidationFinding(
            category=ValidationCategory.INPUT,
            status=ValidationStatus.ERROR,
            code=code,
            message=f"Duplicate {label} identifiers: {', '.join(sorted(duplicates))}",
            details={"duplicates": duplicates},
        )
    ]


def _validate_geometry(model: StructuralModel) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    geometry = model.geometry

    findings.extend(_duplicate_ids([item.id for item in geometry.grids], "DUPLICATE_GRID_ID", "grid"))
    findings.extend(_duplicate_ids([item.id for item in geometry.levels], "DUPLICATE_LEVEL_ID", "level"))
    findings.extend(_duplicate_ids([item.id for item in geometry.points], "DUPLICATE_POINT_ID", "point"))
    findings.extend(_duplicate_ids([item.id for item in geometry.lines], "DUPLICATE_LINE_ID", "line"))
    findings.extend(_duplicate_ids([item.id for item in geometry.areas], "DUPLICATE_AREA_ID", "area"))

    level_ids = {level.id for level in geometry.levels}
    point_ids = {point.id for point in geometry.points}

    for point in geometry.points:
        if point.level_id and point.level_id not in level_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_POINT_LEVEL_REFERENCE",
                    message=f"Point '{point.id}' references missing level '{point.level_id}'",
                )
            )

    for line in geometry.lines:
        if line.start_point_id not in point_ids or line.end_point_id not in point_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_LINE_POINT_REFERENCE",
                    message=f"Line '{line.id}' references missing point endpoints",
                )
            )
        elif line.start_point_id == line.end_point_id:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_LINE_GEOMETRY",
                    message=f"Line '{line.id}' has identical start and end points",
                )
            )

    for area in geometry.areas:
        if area.level_id and area.level_id not in level_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_AREA_LEVEL_REFERENCE",
                    message=f"Area '{area.id}' references missing level '{area.level_id}'",
                )
            )
        missing_points = [pid for pid in area.boundary_point_ids if pid not in point_ids]
        if missing_points:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_AREA_BOUNDARY",
                    message=f"Area '{area.id}' references missing boundary points",
                    details={"missing_point_ids": missing_points},
                )
            )

    return findings


def _validate_materials(model: StructuralModel) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    all_ids = (
        [item.id for item in model.materials.concrete]
        + [item.id for item in model.materials.steel]
        + [item.id for item in model.materials.reinforcement]
    )
    findings.extend(_duplicate_ids(all_ids, "DUPLICATE_MATERIAL_ID", "material"))

    for concrete in model.materials.concrete:
        if concrete.compressive_strength <= 0:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_CONCRETE_STRENGTH",
                    message=f"Concrete material '{concrete.id}' must have positive compressive strength",
                )
            )

    for steel in model.materials.steel:
        if steel.yield_strength <= 0:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_STEEL_STRENGTH",
                    message=f"Steel material '{steel.id}' must have positive yield strength",
                )
            )

    return findings


def _validate_sections(model: StructuralModel) -> list[ValidationFinding]:
    all_ids = (
        [item.id for item in model.sections.beams]
        + [item.id for item in model.sections.columns]
        + [item.id for item in model.sections.walls]
        + [item.id for item in model.sections.slabs]
        + [item.id for item in model.sections.foundations]
    )
    return _duplicate_ids(all_ids, "DUPLICATE_SECTION_ID", "section")


def _validate_members(model: StructuralModel) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    findings.extend(
        _duplicate_ids(
            [item.id for item in model.members.members],
            "DUPLICATE_MEMBER_ID",
            "member",
        )
    )

    section_ids = {
        *[item.id for item in model.sections.beams],
        *[item.id for item in model.sections.columns],
        *[item.id for item in model.sections.walls],
        *[item.id for item in model.sections.slabs],
        *[item.id for item in model.sections.foundations],
    }
    material_ids = {
        *[item.id for item in model.materials.concrete],
        *[item.id for item in model.materials.steel],
        *[item.id for item in model.materials.reinforcement],
    }
    level_ids = {level.id for level in model.geometry.levels}
    point_ids = {point.id for point in model.geometry.points}
    line_ids = {line.id for line in model.geometry.lines}
    area_ids = {area.id for area in model.geometry.areas}

    for member in model.members.members:
        if member.section_id not in section_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="MISSING_MEMBER_SECTION",
                    message=f"Member '{member.id}' references missing section '{member.section_id}'",
                )
            )
        if member.material_id not in material_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="MISSING_MEMBER_MATERIAL",
                    message=f"Member '{member.id}' references missing material '{member.material_id}'",
                )
            )
        if member.level_id and member.level_id not in level_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_MEMBER_LEVEL",
                    message=f"Member '{member.id}' references missing level '{member.level_id}'",
                )
            )
        for point_ref in (member.start_point_id, member.end_point_id):
            if point_ref and point_ref not in point_ids:
                findings.append(
                    ValidationFinding(
                        category=ValidationCategory.INPUT,
                        status=ValidationStatus.ERROR,
                        code="INVALID_MEMBER_POINT",
                        message=f"Member '{member.id}' references missing point '{point_ref}'",
                    )
                )
        if member.line_id and member.line_id not in line_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_MEMBER_LINE",
                    message=f"Member '{member.id}' references missing line '{member.line_id}'",
                )
            )
        if member.area_id and member.area_id not in area_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_MEMBER_AREA",
                    message=f"Member '{member.id}' references missing area '{member.area_id}'",
                )
            )

    return findings


def _validate_supports(model: StructuralModel) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    findings.extend(
        _duplicate_ids([item.id for item in model.supports], "DUPLICATE_SUPPORT_ID", "support")
    )
    point_ids = {point.id for point in model.geometry.points}
    for support in model.supports:
        if support.point_id not in point_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_SUPPORT_POINT",
                    message=f"Support '{support.id}' references missing point '{support.point_id}'",
                )
            )
    return findings


def _validate_loads(model: StructuralModel) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    findings.extend(
        _duplicate_ids([item.id for item in model.load_cases], "DUPLICATE_LOAD_CASE_ID", "load case")
    )

    load_case_ids = {case.id for case in model.load_cases}
    point_ids = {point.id for point in model.geometry.points}
    line_ids = {line.id for line in model.geometry.lines}
    area_ids = {area.id for area in model.geometry.areas}
    member_ids = {member.id for member in model.members.members}

    for case in model.load_cases:
        load_ids = [load.id for load in case.loads]
        findings.extend(_duplicate_ids(load_ids, "DUPLICATE_LOAD_ID", "load"))
        for load in case.loads:
            if load.load_case_id != case.id:
                findings.append(
                    ValidationFinding(
                        category=ValidationCategory.INPUT,
                        status=ValidationStatus.ERROR,
                        code="LOAD_CASE_MISMATCH",
                        message=f"Load '{load.id}' does not belong to load case '{case.id}'",
                    )
                )
            if not load.unit.strip():
                findings.append(
                    ValidationFinding(
                        category=ValidationCategory.INPUT,
                        status=ValidationStatus.ERROR,
                        code="MISSING_LOAD_UNIT",
                        message=f"Load '{load.id}' is missing units",
                    )
                )
            if load.point_id and load.point_id not in point_ids:
                findings.append(
                    ValidationFinding(
                        category=ValidationCategory.INPUT,
                        status=ValidationStatus.ERROR,
                        code="INVALID_LOAD_POINT",
                        message=f"Load '{load.id}' references missing point '{load.point_id}'",
                    )
                )
            if load.line_id and load.line_id not in line_ids:
                findings.append(
                    ValidationFinding(
                        category=ValidationCategory.INPUT,
                        status=ValidationStatus.ERROR,
                        code="INVALID_LOAD_LINE",
                        message=f"Load '{load.id}' references missing line '{load.line_id}'",
                    )
                )
            if load.area_id and load.area_id not in area_ids:
                findings.append(
                    ValidationFinding(
                        category=ValidationCategory.INPUT,
                        status=ValidationStatus.ERROR,
                        code="INVALID_LOAD_AREA",
                        message=f"Load '{load.id}' references missing area '{load.area_id}'",
                    )
                )
            if load.member_id and load.member_id not in member_ids:
                findings.append(
                    ValidationFinding(
                        category=ValidationCategory.INPUT,
                        status=ValidationStatus.ERROR,
                        code="INVALID_LOAD_MEMBER",
                        message=f"Load '{load.id}' references missing member '{load.member_id}'",
                    )
                )

    return findings


def _validate_load_combinations(model: StructuralModel) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    findings.extend(
        _duplicate_ids(
            [item.id for item in model.load_combinations],
            "DUPLICATE_LOAD_COMBINATION_ID",
            "load combination",
        )
    )
    load_case_ids = {case.id for case in model.load_cases}
    for combination in model.load_combinations:
        if not combination.terms:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.WARNING,
                    code="EMPTY_LOAD_COMBINATION",
                    message=f"Load combination '{combination.id}' has no terms",
                )
            )
        for term in combination.terms:
            if term.load_case_id not in load_case_ids:
                findings.append(
                    ValidationFinding(
                        category=ValidationCategory.INPUT,
                        status=ValidationStatus.ERROR,
                        code="INVALID_COMBINATION_LOAD_CASE",
                        message=(
                            f"Combination '{combination.id}' references missing load case "
                            f"'{term.load_case_id}'"
                        ),
                    )
                )
    return findings


def _validate_analysis_model(model: StructuralModel) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    point_ids = {point.id for point in model.geometry.points}
    member_ids = {member.id for member in model.members.members}
    line_ids = {line.id for line in model.geometry.lines}
    load_case_ids = {case.id for case in model.load_cases}
    combination_ids = {combo.id for combo in model.load_combinations}

    for node in model.analysis_model.nodes:
        if node.point_id not in point_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_ANALYSIS_NODE",
                    message=f"Analysis node '{node.id}' references missing point '{node.point_id}'",
                )
            )

    for element in model.analysis_model.elements:
        if element.member_id and element.member_id not in member_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_ANALYSIS_ELEMENT_MEMBER",
                    message=f"Analysis element '{element.id}' references missing member",
                )
            )
        if element.line_id and element.line_id not in line_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_ANALYSIS_ELEMENT_LINE",
                    message=f"Analysis element '{element.id}' references missing line",
                )
            )

    for case_id in model.analysis_model.load_case_ids:
        if case_id not in load_case_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_ANALYSIS_LOAD_CASE",
                    message=f"Analysis model references missing load case '{case_id}'",
                )
            )

    for combo_id in model.analysis_model.load_combination_ids:
        if combo_id not in combination_ids:
            findings.append(
                ValidationFinding(
                    category=ValidationCategory.INPUT,
                    status=ValidationStatus.ERROR,
                    code="INVALID_ANALYSIS_LOAD_COMBINATION",
                    message=f"Analysis model references missing load combination '{combo_id}'",
                )
            )

    return findings


def _validate_units_consistency(pem: ProjectEngineeringModel) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    force_unit = pem.unit_configuration.force_unit

    for case in pem.structural_model.load_cases:
        for load in case.loads:
            if load.unit and force_unit and load.unit != force_unit and load.unit not in {
                force_unit,
                f"{force_unit}/ft",
                f"{force_unit}/m",
            }:
                findings.append(
                    ValidationFinding(
                        category=ValidationCategory.INPUT,
                        status=ValidationStatus.WARNING,
                        code="LOAD_UNIT_MISMATCH",
                        message=(
                            f"Load '{load.id}' uses unit '{load.unit}' which differs from project force unit "
                            f"'{force_unit}'"
                        ),
                    )
                )
    return findings
