"""Structural software adapter contract (ETABS, SAP2000, SAFE)."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.domain.models.integration import IntegrationOperation, IntegrationResult


class StructuralSoftwareAdapter(Protocol):
    @property
    def software_name(self) -> str: ...

    @property
    def software_version(self) -> str: ...

    def get_status(self) -> IntegrationResult: ...

    def import_model(self, project_id: UUID, *, source_path: str) -> IntegrationResult: ...

    def export_model(self, project_id: UUID, *, destination_path: str) -> IntegrationResult: ...

    def run_analysis(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult: ...

    def extract_results(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult: ...

    def supports_operation(self, operation: IntegrationOperation) -> bool: ...
