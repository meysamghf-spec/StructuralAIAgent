"""AutoCAD adapter contract."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.domain.models.integration import IntegrationOperation, IntegrationResult


class CadAdapter(Protocol):
    @property
    def software_name(self) -> str: ...

    @property
    def software_version(self) -> str: ...

    def get_status(self) -> IntegrationResult: ...

    def generate_drawing(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult: ...

    def export_dxf(self, project_id: UUID, *, destination_path: str) -> IntegrationResult: ...

    def export_dwg(self, project_id: UUID, *, destination_path: str) -> IntegrationResult: ...

    def supports_operation(self, operation: IntegrationOperation) -> bool: ...
