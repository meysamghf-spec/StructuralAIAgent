"""Elastic storey displacement and interstorey drift from a 3D analysis result."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.analysis.frame3d_solver import SpaceFrameResult
from app.domain.models.pem_structural import (
    DesignCheckStatus,
    DiaphragmDefinition,
    StoryDriftRecord,
    StructuralModel,
)


@dataclass
class DriftCheckResult:
    records: list[StoryDriftRecord]
    assumptions: list[str]
    warnings: list[str]
    code_limit: float | None
    amplified: bool


class StoryDriftService:
    """
    Elastic drift is always calculated when 3D displacements exist.

    Amplified inelastic drift Δ = Cd δ_xe / Ie and ASCE 7-22 Table 12.12-1
    comparison are applied only when Cd and Ie are supplied. Otherwise the
    code-limit status is NOT_CHECKED (never a false PASS).
    """

    def evaluate(
        self,
        structural: StructuralModel,
        result: SpaceFrameResult,
        diaphragms: list[DiaphragmDefinition],
        *,
        cd: float | None = None,
        ie: float = 1.0,
        risk_category: str = "II",
        case_name: str = "EQ",
    ) -> DriftCheckResult:
        levels = sorted(structural.geometry.levels, key=lambda item: item.elevation)
        points = {point.id: point for point in structural.geometry.points}
        records: list[StoryDriftRecord] = []
        assumptions = [
            "Storey displacement is the rigid-diaphragm mean of connected node ux/uy, or the mean of level nodes.",
            "Interstorey drift is the difference in mean displacement between adjacent levels.",
        ]
        warnings: list[str] = []
        table_limit = 0.020 if risk_category in {"I", "II"} else 0.015 if risk_category == "III" else 0.010
        can_check = cd is not None and cd > 0
        if can_check:
            assumptions.append(
                f"Inelastic drift Δ = Cd δ / Ie with Cd={cd}, Ie={ie}. Limit Δ/h = {table_limit} "
                f"(ASCE 7-22 Table 12.12-1, Risk Category {risk_category}, other than masonry)."
            )
        else:
            assumptions.append("Cd/Ie amplification is not applied; code drift status is NOT_CHECKED.")
            warnings.append("Elastic drift is reported. Table 12.12-1 PASS/FAIL is NOT_CHECKED without Cd.")

        previous_x = 0.0
        previous_y = 0.0
        previous_z = levels[0].elevation if levels else 0.0
        for index, level in enumerate(levels):
            node_ids = next((item.node_ids for item in diaphragms if item.level_id == level.id), None)
            if not node_ids:
                node_ids = [point.id for point in points.values() if point.level_id == level.id]
            ux_values = [result.displacements[nid][0] for nid in node_ids if nid in result.displacements]
            uy_values = [result.displacements[nid][1] for nid in node_ids if nid in result.displacements]
            ux = sum(ux_values) / len(ux_values) if ux_values else 0.0
            uy = sum(uy_values) / len(uy_values) if uy_values else 0.0
            height = max(level.elevation - previous_z, 1e-6) if index > 0 else max(level.elevation, 1e-6)
            raw_dx = ux - previous_x
            raw_dy = uy - previous_y
            if can_check:
                drift_x = (cd * raw_dx) / max(ie, 1e-9)
                drift_y = (cd * raw_dy) / max(ie, 1e-9)
            else:
                drift_x, drift_y = raw_dx, raw_dy
            ratio_x = abs(drift_x) / height
            ratio_y = abs(drift_y) / height
            governing = max(ratio_x, ratio_y)
            if index == 0:
                status = DesignCheckStatus.NOT_CHECKED
            elif can_check:
                status = DesignCheckStatus.PASS if governing <= table_limit else DesignCheckStatus.FAIL
            else:
                status = DesignCheckStatus.NOT_CHECKED
            records.append(
                StoryDriftRecord(
                    level_id=level.id,
                    story_name=level.name,
                    height_m=round(height, 4),
                    displacement_x_m=round(ux, 6),
                    displacement_y_m=round(uy, 6),
                    drift_x_m=round(drift_x, 6),
                    drift_y_m=round(drift_y, 6),
                    drift_ratio_x=round(ratio_x, 6),
                    drift_ratio_y=round(ratio_y, 6),
                    limit=table_limit if can_check else None,
                    status=status,
                    code_reference="ASCE 7-22 Table 12.12-1" if can_check else "ELASTIC_ONLY — Table 12.12-1 NOT_CHECKED",
                    assumptions=[f"Case {case_name}", f"elastic ux={ux:.5f} m, uy={uy:.5f} m"],
                    metadata={"index": index, "amplified": can_check},
                )
            )
            previous_x, previous_y, previous_z = ux, uy, level.elevation
        return DriftCheckResult(
            records=records,
            assumptions=assumptions,
            warnings=warnings,
            code_limit=table_limit if can_check else None,
            amplified=can_check,
        )
