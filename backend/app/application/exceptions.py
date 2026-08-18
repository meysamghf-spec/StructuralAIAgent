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


class AgentNotFoundError(ApplicationError):
    def __init__(self, agent_id: UUID) -> None:
        super().__init__(
            "AGENT_NOT_FOUND",
            "Agent definition not found",
            status_code=404,
            details={"agent_id": str(agent_id)},
        )


class AgentKeyConflictError(ApplicationError):
    def __init__(self, key: str) -> None:
        super().__init__(
            "AGENT_KEY_CONFLICT",
            "Agent key already exists",
            status_code=409,
            details={"key": key},
        )


class AgentVersionNotFoundError(ApplicationError):
    def __init__(self, agent_id: UUID, version: int) -> None:
        super().__init__(
            "AGENT_VERSION_NOT_FOUND",
            "Agent version not found",
            status_code=404,
            details={"agent_id": str(agent_id), "version": version},
        )


class AgentVersionImmutableError(ApplicationError):
    def __init__(self, agent_id: UUID, version: int) -> None:
        super().__init__(
            "AGENT_VERSION_IMMUTABLE",
            "Active agent versions are immutable; create a new version instead",
            status_code=400,
            details={"agent_id": str(agent_id), "version": version},
        )


class InvalidLifecycleTransitionError(ApplicationError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(
            "INVALID_LIFECYCLE_TRANSITION",
            message,
            status_code=400,
            details=details or {},
        )


class PromptTemplateNotFoundError(ApplicationError):
    def __init__(self, agent_id: UUID, version: int, prompt_version: int) -> None:
        super().__init__(
            "PROMPT_TEMPLATE_NOT_FOUND",
            "Prompt template not found",
            status_code=404,
            details={
                "agent_id": str(agent_id),
                "agent_version": version,
                "prompt_version": prompt_version,
            },
        )


class CapabilityNotFoundError(ApplicationError):
    def __init__(self, capability_key: str) -> None:
        super().__init__(
            "CAPABILITY_NOT_FOUND",
            "Agent capability not found",
            status_code=404,
            details={"capability_key": capability_key},
        )


class ProjectMemoryNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, memory_id: UUID) -> None:
        super().__init__(
            "PROJECT_MEMORY_NOT_FOUND",
            "Project memory not found",
            status_code=404,
            details={"project_id": str(project_id), "memory_id": str(memory_id)},
        )


class ProjectFileNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, file_id: UUID) -> None:
        super().__init__(
            "PROJECT_FILE_NOT_FOUND",
            "Project file not found",
            status_code=404,
            details={"project_id": str(project_id), "file_id": str(file_id)},
        )


class InvalidUploadError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "INVALID_UPLOAD",
            message,
            status_code=400,
        )


class UploadTooLargeError(ApplicationError):
    def __init__(self, *, max_bytes: int, actual_bytes: int) -> None:
        super().__init__(
            "UPLOAD_TOO_LARGE",
            "Uploaded file exceeds maximum allowed size",
            status_code=413,
            details={"max_bytes": max_bytes, "actual_bytes": actual_bytes},
        )


class UnsupportedFileTypeError(ApplicationError):
    def __init__(self, *, filename: str, content_type: str | None) -> None:
        super().__init__(
            "UNSUPPORTED_FILE_TYPE",
            "File type is not supported",
            status_code=415,
            details={"filename": filename, "content_type": content_type},
        )


class ParserNotFoundError(ApplicationError):
    def __init__(self, *, file_type: str) -> None:
        super().__init__(
            "PARSER_NOT_FOUND",
            "No parser available for detected file type",
            status_code=500,
            details={"file_type": file_type},
        )


class FileStorageError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "FILE_STORAGE_ERROR",
            message,
            status_code=500,
        )


class FileNotReadyForIndexingError(ApplicationError):
    def __init__(self, project_id: UUID, file_id: UUID, *, reason: str) -> None:
        super().__init__(
            "FILE_NOT_READY_FOR_INDEXING",
            "Project file is not ready for document indexing",
            status_code=409,
            details={
                "project_id": str(project_id),
                "file_id": str(file_id),
                "reason": reason,
            },
        )


class UnsupportedUnitConversionError(ApplicationError):
    def __init__(self, *, from_unit: str, to_unit: str, quantity_type: str) -> None:
        super().__init__(
            "UNSUPPORTED_UNIT_CONVERSION",
            "Unit conversion is not supported for the requested units",
            status_code=400,
            details={
                "from_unit": from_unit,
                "to_unit": to_unit,
                "quantity_type": quantity_type,
            },
        )


class CodePluginNotFoundError(ApplicationError):
    def __init__(self, *, plugin_id: str) -> None:
        super().__init__(
            "CODE_PLUGIN_NOT_FOUND",
            "Code standard plugin was not found",
            status_code=404,
            details={"plugin_id": plugin_id},
        )


class CodeCheckNotFoundError(ApplicationError):
    def __init__(self, *, plugin_id: str, check_id: str) -> None:
        super().__init__(
            "CODE_CHECK_NOT_FOUND",
            "Code check was not found for the selected plugin",
            status_code=404,
            details={"plugin_id": plugin_id, "check_id": check_id},
        )


class IntegrationAdapterNotFoundError(ApplicationError):
    def __init__(self, *, software: str) -> None:
        super().__init__(
            "INTEGRATION_ADAPTER_NOT_FOUND",
            "Integration adapter was not found",
            status_code=404,
            details={"software": software},
        )


class IntegrationOperationNotSupportedError(ApplicationError):
    def __init__(self, *, software: str, operation: str) -> None:
        super().__init__(
            "INTEGRATION_OPERATION_NOT_SUPPORTED",
            "Integration operation is not supported by the adapter",
            status_code=400,
            details={"software": software, "operation": operation},
        )


class AIProviderNotFoundError(ApplicationError):
    def __init__(self, *, provider: str) -> None:
        super().__init__(
            "AI_PROVIDER_NOT_FOUND",
            "AI provider was not found",
            status_code=404,
            details={"provider": provider},
        )


class AIModelNotSupportedError(ApplicationError):
    def __init__(self, *, model: str, provider: str) -> None:
        super().__init__(
            "AI_MODEL_NOT_SUPPORTED",
            "AI model is not supported by the selected provider",
            status_code=400,
            details={"model": model, "provider": provider},
        )


class OrchestrationTaskNotSupportedError(ApplicationError):
    def __init__(self, *, task_type: str) -> None:
        super().__init__(
            "ORCHESTRATION_TASK_NOT_SUPPORTED",
            "Orchestration task type is not supported",
            status_code=400,
            details={"task_type": task_type},
        )
