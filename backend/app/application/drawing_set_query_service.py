"""Read the current PEM drawing set without treating it as a second model."""

from __future__ import annotations

from uuid import UUID

from app.application.drawing.drawing_set_service import DrawingSetService
from app.application.exceptions import PemNotFoundError
from app.application.project_service import PemService
from app.domain.models.drawing import DrawingSet


class DrawingSetQueryService:
    """Build the sheet index and PDF from the current PEM snapshot."""

    def __init__(self, pem_service: PemService) -> None:
        self._pem = pem_service
        self._drawings = DrawingSetService()

    def current_drawing_set(self, project_id: UUID) -> DrawingSet:
        meta = self._pem.get_current_snapshot_meta(project_id)
        pem = self._pem.get_current_pem(project_id)
        if meta is None or pem is None:
            raise PemNotFoundError(project_id)
        return self._drawings.generate(
            pem,
            project_id=project_id,
            pem_version=meta.version,
            snapshot_id=meta.id,
        )
