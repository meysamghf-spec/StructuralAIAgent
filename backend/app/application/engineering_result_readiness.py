"""Shared helpers for validated engineering result readiness."""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from app.domain.models.analysis import AnalysisRun, AnalysisStatus


def analysis_run_has_validated_results(
    run: AnalysisRun,
    *,
    validated_run_ids: set[UUID] | None = None,
    checker: Callable[[UUID], bool] | None = None,
) -> bool:
    if run.status != AnalysisStatus.SUCCESS:
        return False
    if validated_run_ids is not None and run.id in validated_run_ids:
        return True
    if checker is not None and checker(run.id):
        return True
    return bool(run.outputs.get("engineering_results_available"))
