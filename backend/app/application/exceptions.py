"""Application-layer errors mapped to HTTP responses in the API layer."""

from __future__ import annotations

from uuid import UUID


class ApplicationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ProjectNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID) -> None:
        super().__init__(
            "PROJECT_NOT_FOUND",
            "Project not found",
            status_code=404,
            details={"project_id": str(project_id)},
        )


class PemNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, *, version: int | None = None) -> None:
        details: dict = {"project_id": str(project_id)}
        if version is not None:
            details["version"] = version
            super().__init__(
                "PEM_VERSION_NOT_FOUND",
                "PEM snapshot version not found",
                status_code=404,
                details=details,
            )
        else:
            super().__init__(
                "PEM_NOT_FOUND",
                "Current PEM not found",
                status_code=404,
                details=details,
            )


class RevisionNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, revision_number: int) -> None:
        super().__init__(
            "REVISION_NOT_FOUND",
            "Revision not found",
            status_code=404,
            details={
                "project_id": str(project_id),
                "revision_number": revision_number,
            },
        )


class PemProjectMismatchError(ApplicationError):
    def __init__(self, path_project_id: UUID, pem_project_id: UUID) -> None:
        super().__init__(
            "PEM_PROJECT_MISMATCH",
            "PEM project_id does not match path project_id",
            status_code=400,
            details={
                "path_project_id": str(path_project_id),
                "pem_project_id": str(pem_project_id),
            },
        )


class InvalidChangeTypeError(ApplicationError):
    def __init__(self, change_type: str) -> None:
        super().__init__(
            "INVALID_CHANGE_TYPE",
            "change_type INITIAL is not allowed for PEM updates",
            status_code=400,
            details={"change_type": change_type},
        )
