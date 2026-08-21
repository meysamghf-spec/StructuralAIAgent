"""Deep CSI COM result extraction with capability-gated vendor parsing."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app.domain.models.csi_extraction import (
    CsiCategoryExtractionReport,
    CsiExtractionStatus,
    CsiExtractionSummary,
    CsiResultCategory,
)
from app.domain.models.integration import IntegrationSoftware


def extract_csi_results(
    sap_model: Any,
    *,
    software: IntegrationSoftware,
    vendor_model_identity: str | None = None,
    pem_version: int | None = None,
    member_ids: set[str] | None = None,
    joint_ids: set[str] | None = None,
    load_case_ids: set[str] | None = None,
    load_combination_ids: set[str] | None = None,
    include_shell_results: bool = False,
) -> tuple[dict[str, Any], CsiExtractionSummary]:
    """Extract vendor analysis results without fabricating missing data."""
    categories: list[CsiCategoryExtractionReport] = []
    validation_findings: list[dict[str, Any]] = []
    unmapped_all: list[str] = []
    raw: dict[str, Any] = {
        "execution_mode": "vendor",
        "external_model_identity": vendor_model_identity,
    }

    analyzed = _model_is_analyzed(sap_model)
    if not analyzed:
        summary = CsiExtractionSummary(
            overall_status=CsiExtractionStatus.NOT_ANALYZED,
            vendor=software.value,
            vendor_model_identity=vendor_model_identity,
            pem_version=pem_version,
            analyzed=False,
            categories=[
                CsiCategoryExtractionReport(
                    category=CsiResultCategory.FRAME_FORCES,
                    status=CsiExtractionStatus.NOT_ANALYZED,
                    message="Vendor model has not completed analysis.",
                )
            ],
            extracted_at=datetime.now(UTC),
        )
        return raw, summary

    load_cases, load_combos = _extract_load_definitions(sap_model)
    if load_cases:
        raw["load_cases"] = load_cases
        categories.append(
            CsiCategoryExtractionReport(
                category=CsiResultCategory.LOAD_CASES,
                status=CsiExtractionStatus.COMPLETE,
                row_count=len(load_cases),
            )
        )
    if load_combos:
        raw["load_combinations"] = load_combos
        categories.append(
            CsiCategoryExtractionReport(
                category=CsiResultCategory.LOAD_COMBINATIONS,
                status=CsiExtractionStatus.COMPLETE,
                row_count=len(load_combos),
            )
        )

    frame_rows, frame_report = _extract_frame_forces(
        sap_model,
        member_ids=member_ids,
        load_case_ids=load_case_ids,
        load_combination_ids=load_combination_ids,
    )
    if frame_rows:
        raw["member_forces"] = frame_rows
    categories.append(frame_report)
    unmapped_all.extend(frame_report.unmapped_entities)

    joint_rows, joint_report = _extract_joint_displacements(
        sap_model,
        joint_ids=joint_ids,
        load_case_ids=load_case_ids,
        load_combination_ids=load_combination_ids,
    )
    if joint_rows:
        raw["joint_displacements"] = joint_rows
    categories.append(joint_report)
    unmapped_all.extend(joint_report.unmapped_entities)

    reaction_rows, reaction_report = _extract_joint_reactions(
        sap_model,
        joint_ids=joint_ids,
        load_case_ids=load_case_ids,
        load_combination_ids=load_combination_ids,
    )
    if reaction_rows:
        raw["reactions"] = reaction_rows
    categories.append(reaction_report)
    unmapped_all.extend(reaction_report.unmapped_entities)

    if include_shell_results or software == IntegrationSoftware.SAFE:
        shell_rows, shell_report = _extract_shell_results(sap_model)
        if shell_rows:
            raw["shell_results"] = shell_rows
        categories.append(shell_report)

    modal_rows, modal_report = _extract_modal_periods(sap_model)
    if modal_rows:
        raw["modal_periods"] = modal_rows
    if modal_report.status != CsiExtractionStatus.NOT_SUPPORTED:
        categories.append(modal_report)

    drift_rows, drift_report = _extract_story_drifts(sap_model)
    if drift_rows:
        raw["story_drifts"] = drift_rows
    if drift_report.status != CsiExtractionStatus.NOT_SUPPORTED:
        categories.append(drift_report)

    for rows_key in ("member_forces", "joint_displacements", "reactions", "shell_results"):
        for index, row in enumerate(raw.get(rows_key, [])):
            _validate_row_numbers(rows_key, index, row, validation_findings)

    overall = _compute_overall_status(categories, validation_findings)
    summary = CsiExtractionSummary(
        overall_status=overall,
        vendor=software.value,
        vendor_model_identity=vendor_model_identity,
        pem_version=pem_version,
        analyzed=True,
        categories=categories,
        validation_findings=validation_findings,
        unmapped_entities=sorted(set(unmapped_all)),
        extracted_at=datetime.now(UTC),
    )
    return raw, summary


def _compute_overall_status(
    categories: list[CsiCategoryExtractionReport],
    findings: list[dict[str, Any]],
) -> CsiExtractionStatus:
    if any(item["severity"] == "ERROR" for item in findings):
        return CsiExtractionStatus.FAILED
    statuses = {item.status for item in categories}
    if not categories:
        return CsiExtractionStatus.FAILED
    if statuses == {CsiExtractionStatus.NOT_SUPPORTED}:
        return CsiExtractionStatus.NOT_SUPPORTED
    if CsiExtractionStatus.COMPLETE in statuses and len(statuses) == 1:
        return CsiExtractionStatus.COMPLETE
    if CsiExtractionStatus.COMPLETE in statuses or CsiExtractionStatus.PARTIAL in statuses:
        return CsiExtractionStatus.PARTIAL
    if CsiExtractionStatus.NOT_ANALYZED in statuses:
        return CsiExtractionStatus.NOT_ANALYZED
    return CsiExtractionStatus.FAILED


def _model_is_analyzed(sap_model: Any) -> bool:
    analyze = getattr(sap_model, "Analyze", None)
    if analyze is None:
        return False
    get_run_flag = getattr(analyze, "GetRunFlag", None)
    if not callable(get_run_flag):
        return False
    try:
        flag = get_run_flag()
    except Exception:  # noqa: BLE001
        return False
    return flag in (1, True, "1")


def _extract_load_definitions(sap_model: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    load_cases: list[dict[str, Any]] = []
    load_combos: list[dict[str, Any]] = []
    load_patterns = getattr(sap_model, "LoadPatterns", None)
    if load_patterns is not None:
        get_names = getattr(load_patterns, "GetNameList", None)
        if callable(get_names):
            names = _read_name_list(get_names)
            load_cases.extend({"vendor_name": name, "id": name} for name in sorted(names))
    load_combos_api = getattr(sap_model, "RespCombo", None)
    if load_combos_api is not None:
        get_names = getattr(load_combos_api, "GetNameList", None)
        if callable(get_names):
            names = _read_name_list(get_names)
            load_combos.extend({"vendor_name": name, "id": name} for name in sorted(names))
    return load_cases, load_combos


def _extract_frame_forces(
    sap_model: Any,
    *,
    member_ids: set[str] | None,
    load_case_ids: set[str] | None,
    load_combination_ids: set[str] | None,
) -> tuple[list[dict[str, Any]], CsiCategoryExtractionReport]:
    results = getattr(sap_model, "Results", None)
    if results is None:
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.FRAME_FORCES,
            status=CsiExtractionStatus.NOT_SUPPORTED,
            message="Vendor Results API is not available.",
        )

    frame_force = getattr(results, "FrameForce", None)
    if not callable(frame_force):
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.FRAME_FORCES,
            status=CsiExtractionStatus.NOT_SUPPORTED,
            message="FrameForce API is not available.",
        )

    _configure_output(results, load_case_ids, load_combination_ids)
    rows = _invoke_frame_force(frame_force, frame_name="ALL")
    if not rows:
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.FRAME_FORCES,
            status=CsiExtractionStatus.FAILED,
            message="FrameForce returned no rows.",
        )

    unmapped: list[str] = []
    normalized_rows: list[dict[str, Any]] = []
    for row in sorted(rows, key=_frame_sort_key):
        member_id = str(row.get("object_name") or row.get("frame_name") or row.get("id") or "")
        if member_ids and member_id and member_id not in member_ids:
            unmapped.append(member_id)
        load_ref = row.get("load_case") or row.get("load_combination")
        if load_case_ids and load_ref in load_case_ids:
            load_case = load_ref
            load_combo = None
        elif load_combination_ids and load_ref in load_combination_ids:
            load_case = None
            load_combo = load_ref
        else:
            load_case = load_ref
            load_combo = row.get("load_combination")

        p = row.get("axial_force", row.get("P"))
        v2 = row.get("shear_v2", row.get("V2"))
        v3 = row.get("shear_v3", row.get("V3"))
        torsion = row.get("torsion", row.get("T"))
        m2 = row.get("moment_m2", row.get("M2"))
        m3 = row.get("moment_m3", row.get("M3"))
        values = [p, v2, v3, torsion, m2, m3]
        normalized_rows.append(
            {
                "id": member_id,
                "frame_name": member_id,
                "object_name": member_id,
                "element_name": row.get("element_name") or row.get("Elm"),
                "story": row.get("story"),
                "load_case": load_case,
                "load_combination": load_combo,
                "step_type": row.get("step_type"),
                "step_number": row.get("step_number"),
                "station": row.get("station") or row.get("location"),
                "axial_force": p,
                "shear_v2": v2,
                "shear_v3": v3,
                "torsion": torsion,
                "moment_m2": m2,
                "moment_m3": m3,
                "values": values,
                "source_units": row.get("source_units")
                or {"force": "kN", "moment": "kN-m", "length": "m"},
            }
        )

    status = CsiExtractionStatus.COMPLETE
    if unmapped:
        status = CsiExtractionStatus.PARTIAL
    return normalized_rows, CsiCategoryExtractionReport(
        category=CsiResultCategory.FRAME_FORCES,
        status=status,
        row_count=len(normalized_rows),
        unmapped_entities=sorted(set(unmapped)),
        message=f"Extracted {len(normalized_rows)} frame force row(s).",
    )


def _extract_joint_displacements(
    sap_model: Any,
    *,
    joint_ids: set[str] | None,
    load_case_ids: set[str] | None,
    load_combination_ids: set[str] | None,
) -> tuple[list[dict[str, Any]], CsiCategoryExtractionReport]:
    results = getattr(sap_model, "Results", None)
    joint_displ = getattr(results, "JointDispl", None) if results else None
    if not callable(joint_displ):
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.JOINT_DISPLACEMENTS,
            status=CsiExtractionStatus.NOT_SUPPORTED,
            message="JointDispl API is not available.",
        )

    _configure_output(results, load_case_ids, load_combination_ids)
    rows = _invoke_joint_displ(joint_displ, joint_name="ALL")
    if not rows:
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.JOINT_DISPLACEMENTS,
            status=CsiExtractionStatus.FAILED,
            message="JointDispl returned no rows.",
        )

    unmapped: list[str] = []
    normalized: list[dict[str, Any]] = []
    for row in sorted(rows, key=_joint_sort_key):
        joint_id = str(row.get("joint_name") or row.get("id") or "")
        if joint_ids and joint_id and joint_id not in joint_ids:
            unmapped.append(joint_id)
        normalized.append(
            {
                "joint_name": joint_id,
                "id": joint_id,
                "load_case": row.get("load_case"),
                "load_combination": row.get("load_combination"),
                "step_type": row.get("step_type"),
                "step_number": row.get("step_number"),
                "displacement_ux": row.get("U1"),
                "displacement_uy": row.get("U2"),
                "displacement_uz": row.get("U3"),
                "rotation_rx": row.get("R1"),
                "rotation_ry": row.get("R2"),
                "rotation_rz": row.get("R3"),
                "values": [
                    row.get("U1"),
                    row.get("U2"),
                    row.get("U3"),
                    row.get("R1"),
                    row.get("R2"),
                    row.get("R3"),
                ],
                "source_units": row.get("source_units") or {"length": "m", "rotation": "rad"},
            }
        )

    status = CsiExtractionStatus.PARTIAL if unmapped else CsiExtractionStatus.COMPLETE
    return normalized, CsiCategoryExtractionReport(
        category=CsiResultCategory.JOINT_DISPLACEMENTS,
        status=status,
        row_count=len(normalized),
        unmapped_entities=sorted(set(unmapped)),
    )


def _extract_joint_reactions(
    sap_model: Any,
    *,
    joint_ids: set[str] | None,
    load_case_ids: set[str] | None,
    load_combination_ids: set[str] | None,
) -> tuple[list[dict[str, Any]], CsiCategoryExtractionReport]:
    results = getattr(sap_model, "Results", None)
    if results is None:
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.JOINT_REACTIONS,
            status=CsiExtractionStatus.NOT_SUPPORTED,
            message="Vendor Results API is not available.",
        )

    base_react = getattr(results, "BaseReact", None)
    joint_react = getattr(results, "JointReact", None)
    react_callable = joint_react if callable(joint_react) else base_react
    if not callable(react_callable):
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.JOINT_REACTIONS,
            status=CsiExtractionStatus.NOT_SUPPORTED,
            message="JointReact/BaseReact API is not available.",
        )

    _configure_output(results, load_case_ids, load_combination_ids)
    rows = _invoke_joint_reactions(react_callable)
    if not rows:
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.JOINT_REACTIONS,
            status=CsiExtractionStatus.FAILED,
            message="Reaction extraction returned no rows.",
        )

    unmapped: list[str] = []
    normalized: list[dict[str, Any]] = []
    for row in sorted(rows, key=_joint_sort_key):
        joint_id = str(row.get("joint_name") or row.get("id") or "")
        if joint_ids and joint_id and joint_id not in joint_ids:
            unmapped.append(joint_id)
        normalized.append(
            {
                "joint_name": joint_id,
                "id": joint_id,
                "load_case": row.get("load_case"),
                "load_combination": row.get("load_combination"),
                "force_fx": row.get("F1"),
                "force_fy": row.get("F2"),
                "force_fz": row.get("F3"),
                "moment_mx": row.get("M1"),
                "moment_my": row.get("M2"),
                "moment_mz": row.get("M3"),
                "values": [
                    row.get("F1"),
                    row.get("F2"),
                    row.get("F3"),
                    row.get("M1"),
                    row.get("M2"),
                    row.get("M3"),
                ],
                "source_units": row.get("source_units") or {"force": "kN", "moment": "kN-m"},
            }
        )

    status = CsiExtractionStatus.PARTIAL if unmapped else CsiExtractionStatus.COMPLETE
    return normalized, CsiCategoryExtractionReport(
        category=CsiResultCategory.JOINT_REACTIONS,
        status=status,
        row_count=len(normalized),
        unmapped_entities=sorted(set(unmapped)),
    )


def _extract_shell_results(sap_model: Any) -> tuple[list[dict[str, Any]], CsiCategoryExtractionReport]:
    results = getattr(sap_model, "Results", None)
    if results is None:
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.SHELL_RESULTS,
            status=CsiExtractionStatus.NOT_SUPPORTED,
            message="Vendor Results API is not available.",
        )

    for method_name in ("AreaForceShell", "AreaStressShell", "AreaStrainShell"):
        method = getattr(results, method_name, None)
        if callable(method):
            rows = _invoke_area_results(method)
            if rows:
                return rows, CsiCategoryExtractionReport(
                    category=CsiResultCategory.SHELL_RESULTS,
                    status=CsiExtractionStatus.COMPLETE,
                    row_count=len(rows),
                )

    return [], CsiCategoryExtractionReport(
        category=CsiResultCategory.SHELL_RESULTS,
        status=CsiExtractionStatus.NOT_SUPPORTED,
        message="No supported area/shell result API was available.",
    )


def _extract_modal_periods(sap_model: Any) -> tuple[list[dict[str, Any]], CsiCategoryExtractionReport]:
    results = getattr(sap_model, "Results", None)
    modal_period = getattr(results, "ModalPeriod", None) if results else None
    if not callable(modal_period):
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.MODAL_PERIODS,
            status=CsiExtractionStatus.NOT_SUPPORTED,
        )
    try:
        ret = modal_period()
    except TypeError:
        ret = modal_period("ALL")
    rows = _parse_simple_result(ret, "modal_period")
    if not rows:
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.MODAL_PERIODS,
            status=CsiExtractionStatus.FAILED,
        )
    return rows, CsiCategoryExtractionReport(
        category=CsiResultCategory.MODAL_PERIODS,
        status=CsiExtractionStatus.COMPLETE,
        row_count=len(rows),
    )


def _extract_story_drifts(sap_model: Any) -> tuple[list[dict[str, Any]], CsiCategoryExtractionReport]:
    results = getattr(sap_model, "Results", None)
    story_drifts = getattr(results, "StoryDrifts", None) if results else None
    if not callable(story_drifts):
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.STORY_DRIFTS,
            status=CsiExtractionStatus.NOT_SUPPORTED,
        )
    try:
        ret = story_drifts()
    except TypeError:
        ret = story_drifts("ALL")
    rows = _parse_simple_result(ret, "story_drift")
    if not rows:
        return [], CsiCategoryExtractionReport(
            category=CsiResultCategory.STORY_DRIFTS,
            status=CsiExtractionStatus.FAILED,
        )
    return rows, CsiCategoryExtractionReport(
        category=CsiResultCategory.STORY_DRIFTS,
        status=CsiExtractionStatus.COMPLETE,
        row_count=len(rows),
    )


def _configure_output(
    results: Any,
    load_case_ids: set[str] | None,
    load_combination_ids: set[str] | None,
) -> None:
    setup = getattr(results, "Setup", None)
    if setup is None:
        return
    deselect = getattr(setup, "DeselectAllCasesAndCombosForOutput", None)
    if callable(deselect):
        try:
            deselect()
        except Exception:  # noqa: BLE001
            pass
    set_case = getattr(setup, "SetCaseSelectedForOutput", None)
    if callable(set_case):
        for case_id in sorted(load_case_ids or []):
            try:
                set_case(str(case_id))
            except Exception:  # noqa: BLE001
                pass
    set_combo = getattr(setup, "SetComboSelectedForOutput", None)
    if callable(set_combo):
        for combo_id in sorted(load_combination_ids or []):
            try:
                set_combo(str(combo_id))
            except Exception:  # noqa: BLE001
                pass


def _invoke_frame_force(frame_force: Any, *, frame_name: str) -> list[dict[str, Any]]:
    out_arrays = {
        "object_name": [],
        "element_name": [],
        "load_case": [],
        "load_combination": [],
        "step_type": [],
        "step_number": [],
        "axial_force": [],
        "shear_v2": [],
        "shear_v3": [],
        "torsion": [],
        "moment_m2": [],
        "moment_m3": [],
        "station": [],
    }
    number_results = [0]
    try:
        ret = frame_force(
            frame_name,
            0,
            0,
            number_results,
            out_arrays["object_name"],
            out_arrays["element_name"],
            out_arrays["load_case"],
            out_arrays["step_type"],
            out_arrays["step_number"],
            out_arrays["axial_force"],
            out_arrays["shear_v2"],
            out_arrays["shear_v3"],
            out_arrays["torsion"],
            out_arrays["moment_m2"],
            out_arrays["moment_m3"],
            out_arrays["station"],
        )
        if ret not in (0, None) and not out_arrays["object_name"]:
            return []
    except TypeError:
        try:
            ret = frame_force(frame_name)
        except TypeError:
            ret = frame_force()
        return _parse_simple_result(ret, "frame_force", frame_name=frame_name)

    count = number_results[0] if number_results else len(out_arrays["object_name"])
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append({key: _value_at(values, index) for key, values in out_arrays.items()})
    return rows


def _invoke_joint_displ(joint_displ: Any, *, joint_name: str) -> list[dict[str, Any]]:
    out_arrays = {
        "joint_name": [],
        "load_case": [],
        "load_combination": [],
        "step_type": [],
        "step_number": [],
        "U1": [],
        "U2": [],
        "U3": [],
        "R1": [],
        "R2": [],
        "R3": [],
    }
    number_results = [0]
    try:
        ret = joint_displ(
            joint_name,
            0,
            number_results,
            out_arrays["joint_name"],
            out_arrays["load_case"],
            out_arrays["step_type"],
            out_arrays["step_number"],
            out_arrays["U1"],
            out_arrays["U2"],
            out_arrays["U3"],
            out_arrays["R1"],
            out_arrays["R2"],
            out_arrays["R3"],
        )
        if ret not in (0, None) and not out_arrays["joint_name"]:
            return []
    except TypeError:
        try:
            ret = joint_displ(joint_name)
        except TypeError:
            ret = joint_displ()
        parsed = _parse_simple_result(ret, "joint_displ", joint_name=joint_name)
        return parsed

    count = number_results[0] if number_results else len(out_arrays["joint_name"])
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append({key: _value_at(values, index) for key, values in out_arrays.items()})
    return rows


def _invoke_joint_reactions(react_callable: Any) -> list[dict[str, Any]]:
    out_arrays = {
        "joint_name": [],
        "load_case": [],
        "load_combination": [],
        "step_type": [],
        "step_number": [],
        "F1": [],
        "F2": [],
        "F3": [],
        "M1": [],
        "M2": [],
        "M3": [],
    }
    number_results = [0]
    try:
        ret = react_callable(
            0,
            number_results,
            out_arrays["joint_name"],
            out_arrays["load_case"],
            out_arrays["step_type"],
            out_arrays["step_number"],
            out_arrays["F1"],
            out_arrays["F2"],
            out_arrays["F3"],
            out_arrays["M1"],
            out_arrays["M2"],
            out_arrays["M3"],
        )
        if ret not in (0, None) and not out_arrays["joint_name"]:
            return []
    except TypeError:
        ret = react_callable()
        return _parse_simple_result(ret, "joint_react")

    count = number_results[0] if number_results else len(out_arrays["joint_name"])
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append({key: _value_at(values, index) for key, values in out_arrays.items()})
    return rows


def _invoke_area_results(method: Any) -> list[dict[str, Any]]:
    out_arrays = {
        "object_name": [],
        "element_name": [],
        "load_case": [],
        "step_type": [],
        "step_number": [],
        "values": [],
    }
    number_results = [0]
    try:
        ret = method(
            "ALL",
            0,
            number_results,
            out_arrays["object_name"],
            out_arrays["element_name"],
            out_arrays["load_case"],
            out_arrays["step_type"],
            out_arrays["step_number"],
            out_arrays["values"],
        )
        if ret not in (0, None) and not out_arrays["object_name"]:
            return []
    except TypeError:
        ret = method()
        return _parse_simple_result(ret, "shell_result")

    count = number_results[0] if number_results else len(out_arrays["object_name"])
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append({key: _value_at(values, index) for key, values in out_arrays.items()})
    return rows


def _parse_simple_result(
    ret: Any,
    result_type: str,
    *,
    frame_name: str | None = None,
    joint_name: str | None = None,
) -> list[dict[str, Any]]:
    if ret is None:
        return []
    if isinstance(ret, dict):
        row = dict(ret)
        if frame_name and "frame_name" not in row:
            row["frame_name"] = frame_name
            row["object_name"] = frame_name
        if joint_name and "joint_name" not in row:
            row["joint_name"] = joint_name
        return [row]
    if isinstance(ret, list):
        rows: list[dict[str, Any]] = []
        for item in ret:
            if isinstance(item, dict):
                rows.append(item)
            else:
                rows.append({"values": item, "result_type": result_type})
        return rows
    if isinstance(ret, tuple):
        if len(ret) >= 2 and isinstance(ret[1], (list, tuple)):
            return _zip_named_result(ret[1:], result_type)
        return [{"values": ret, "result_type": result_type}]
    return [{"values": ret, "result_type": result_type}]


def _zip_named_result(values: tuple[Any, ...], result_type: str) -> list[dict[str, Any]]:
    if not values:
        return []
    first = values[0]
    if isinstance(first, list):
        length = len(first)
        rows: list[dict[str, Any]] = []
        for index in range(length):
            rows.append({"values": [_value_at(value, index) for value in values], "result_type": result_type})
        return rows
    return [{"values": values, "result_type": result_type}]


def _read_name_list(get_names: Any) -> list[str]:
    number_names = [0]
    names: list[str] = []
    try:
        get_names(number_names, names)
    except TypeError:
        ret = get_names()
        if isinstance(ret, tuple) and len(ret) >= 2:
            names = list(ret[1])
        elif isinstance(ret, list):
            names = list(ret)
    count = number_names[0] if number_names else len(names)
    return [str(names[index]) for index in range(count)]


def _value_at(values: list[Any], index: int) -> Any:
    if index >= len(values):
        return None
    return values[index]


def _frame_sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("object_name") or row.get("frame_name") or ""),
        str(row.get("load_case") or row.get("load_combination") or ""),
        str(row.get("step_type") or ""),
        str(row.get("station") or row.get("location") or ""),
    )


def _joint_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("joint_name") or row.get("id") or ""),
        str(row.get("load_case") or row.get("load_combination") or ""),
        str(row.get("step_type") or ""),
    )


def _validate_row_numbers(rows_key: str, index: int, row: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    numbers: list[float] = []
    for key in ("values", "axial_force", "shear_v2", "shear_v3", "moment_m2", "moment_m3"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            numbers.append(float(value))
        elif isinstance(value, list):
            numbers.extend(float(item) for item in value if isinstance(item, (int, float)))
    for value in numbers:
        if math.isnan(value) or math.isinf(value):
            findings.append(
                {
                    "code": "NON_FINITE_VALUE",
                    "message": f"{rows_key}[{index}] contains non-finite numeric values",
                    "severity": "ERROR",
                }
            )
            return
