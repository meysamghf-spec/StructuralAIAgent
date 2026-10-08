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


class ProjectAuthorizationError(ApplicationError):
    def __init__(self, project_id: UUID, account_id: str) -> None:
        super().__init__(
            "PROJECT_FORBIDDEN",
            "You are not authorized to access this project",
            status_code=403,
            details={"project_id": str(project_id), "account_id": account_id},
        )


class AuthenticationError(ApplicationError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            "AUTHENTICATION_REQUIRED",
            message,
            status_code=401,
        )


class InvalidCredentialsError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "INVALID_CREDENTIALS",
            "Invalid email or password",
            status_code=401,
        )


class DuplicateUserError(ApplicationError):
    def __init__(self, email: str) -> None:
        super().__init__(
            "DUPLICATE_USER",
            "A user with this email already exists",
            status_code=409,
            details={"email": email},
        )


class UserNotFoundError(ApplicationError):
    def __init__(self, user_id: UUID) -> None:
        super().__init__(
            "USER_NOT_FOUND",
            "User not found",
            status_code=404,
            details={"user_id": str(user_id)},
        )


class FeatureAccessDeniedError(ApplicationError):
    def __init__(self, feature: str, *, upgrade_product_id: str | None = None) -> None:
        details: dict[str, str] = {"feature": feature}
        if upgrade_product_id is not None:
            details["upgrade_product_id"] = upgrade_product_id
        super().__init__(
            "FEATURE_ACCESS_DENIED",
            "Upgrade entitlement is required for this capability",
            status_code=403,
            details=details,
        )


class SecurityConfigurationError(ApplicationError):
    def __init__(self, message: str, *, issues: list[str]) -> None:
        super().__init__(
            "SECURITY_CONFIGURATION_ERROR",
            message,
            status_code=503,
            details={"issues": issues},
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


class PemValidationError(ApplicationError):
    def __init__(self, project_id: UUID, validation_report) -> None:
        super().__init__(
            "PEM_VALIDATION_FAILED",
            "Project engineering model failed validation",
            status_code=400,
            details={
                "project_id": str(project_id),
                "overall_status": validation_report.overall_status.value,
                "findings": [finding.model_dump(mode="json") for finding in validation_report.findings],
            },
        )


class AnalysisRunNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, run_id: UUID) -> None:
        super().__init__(
            "ANALYSIS_RUN_NOT_FOUND",
            "Analysis run not found",
            status_code=404,
            details={
                "project_id": str(project_id),
                "run_id": str(run_id),
            },
        )


class DesignRunNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, run_id: UUID) -> None:
        super().__init__(
            "DESIGN_RUN_NOT_FOUND",
            "Design run not found",
            status_code=404,
            details={
                "project_id": str(project_id),
                "run_id": str(run_id),
            },
        )


class IntegrationExecutionNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, execution_id: UUID) -> None:
        super().__init__(
            "INTEGRATION_EXECUTION_NOT_FOUND",
            "Integration execution not found",
            status_code=404,
            details={
                "project_id": str(project_id),
                "execution_id": str(execution_id),
            },
        )


class OptimizationRunNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, run_id: UUID) -> None:
        super().__init__(
            "OPTIMIZATION_RUN_NOT_FOUND",
            "Optimization run not found",
            status_code=404,
            details={
                "project_id": str(project_id),
                "run_id": str(run_id),
            },
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


class AgentExecutionNotFoundError(ApplicationError):
    def __init__(self, execution_id: UUID) -> None:
        super().__init__(
            "AGENT_EXECUTION_NOT_FOUND",
            "Agent execution not found",
            status_code=404,
            details={"execution_id": str(execution_id)},
        )


class AgentHandlerNotFoundError(ApplicationError):
    def __init__(self, agent_type: str) -> None:
        super().__init__(
            "AGENT_HANDLER_NOT_FOUND",
            "No handler registered for agent type",
            status_code=400,
            details={"agent_type": agent_type},
        )


class AgentExecutionBlockedError(ApplicationError):
    def __init__(self, *, reason: str, missing_inputs: list[str] | None = None) -> None:
        details: dict[str, object] = {"reason": reason}
        if missing_inputs:
            details["missing_inputs"] = missing_inputs
        super().__init__(
            "AGENT_EXECUTION_BLOCKED",
            reason,
            status_code=409,
            details=details,
        )


class AgentCapabilityUnavailableError(ApplicationError):
    def __init__(self, *, capability: str, message: str) -> None:
        super().__init__(
            "AGENT_CAPABILITY_UNAVAILABLE",
            message,
            status_code=503,
            details={"capability": capability},
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


class AgentNotExecutableError(ApplicationError):
    def __init__(self, agent_id: UUID, message: str, *, details: dict | None = None) -> None:
        payload = {"agent_id": str(agent_id)}
        if details:
            payload.update(details)
        super().__init__(
            "AGENT_NOT_EXECUTABLE",
            message,
            status_code=409,
            details=payload,
        )


class AgentBuilderInvalidStateError(ApplicationError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(
            "AGENT_BUILDER_INVALID_STATE",
            message,
            status_code=400,
            details=details or {},
        )


class AgentBuilderValidationFailedError(ApplicationError):
    def __init__(self, agent_id: UUID, version: int, validation) -> None:
        super().__init__(
            "AGENT_BUILDER_VALIDATION_FAILED",
            "Agent version failed validation",
            status_code=400,
            details={
                "agent_id": str(agent_id),
                "version": version,
                "issues": [issue.model_dump() for issue in validation.issues],
            },
        )


class AgentAuthorizationError(ApplicationError):
    def __init__(self, agent_id: UUID, message: str = "Agent mutation not allowed") -> None:
        super().__init__(
            "AGENT_FORBIDDEN",
            message,
            status_code=403,
            details={"agent_id": str(agent_id)},
        )


class ProjectAgentScopeError(ApplicationError):
    def __init__(self, agent_id: UUID, project_id: UUID) -> None:
        super().__init__(
            "PROJECT_AGENT_SCOPE_MISMATCH",
            "Assistant does not belong to the selected project",
            status_code=403,
            details={"agent_id": str(agent_id), "project_id": str(project_id)},
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


class EngineeringResultNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, result_set_id: UUID) -> None:
        super().__init__(
            "ENGINEERING_RESULT_NOT_FOUND",
            "Engineering result set was not found",
            status_code=404,
            details={
                "project_id": str(project_id),
                "result_set_id": str(result_set_id),
            },
        )


class CadDrawingNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, drawing_id: UUID) -> None:
        super().__init__(
            "CAD_DRAWING_NOT_FOUND",
            "CAD drawing was not found",
            status_code=404,
            details={
                "project_id": str(project_id),
                "drawing_id": str(drawing_id),
            },
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


class AIProviderRequestError(ApplicationError):
    def __init__(self, *, provider: str, message: str, status_code: int = 502) -> None:
        super().__init__(
            "AI_PROVIDER_REQUEST_FAILED",
            message,
            status_code=status_code,
            details={"provider": provider},
        )


class OrchestrationTaskNotSupportedError(ApplicationError):
    def __init__(self, *, task_type: str) -> None:
        super().__init__(
            "ORCHESTRATION_TASK_NOT_SUPPORTED",
            "Orchestration task type is not supported",
            status_code=400,
            details={"task_type": task_type},
        )


class ApprovalNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, request_id: UUID) -> None:
        super().__init__(
            "APPROVAL_NOT_FOUND",
            "Approval request not found",
            status_code=404,
            details={
                "project_id": str(project_id),
                "request_id": str(request_id),
            },
        )


class ApprovalInvalidStateError(ApplicationError):
    def __init__(
        self,
        project_id: UUID,
        request_id: UUID,
        *,
        current_status: str,
    ) -> None:
        super().__init__(
            "APPROVAL_INVALID_STATE",
            "Approval request is not in a valid state for this operation",
            status_code=409,
            details={
                "project_id": str(project_id),
                "request_id": str(request_id),
                "current_status": current_status,
            },
        )


class ReportNotFoundError(ApplicationError):
    def __init__(self, project_id: UUID, report_id: UUID, *, version: int | None = None) -> None:
        details: dict = {
            "project_id": str(project_id),
            "report_id": str(report_id),
        }
        if version is not None:
            details["version"] = version
        super().__init__(
            "REPORT_NOT_FOUND",
            "Report not found",
            status_code=404,
            details=details,
        )


class UpgradeProductNotFoundError(ApplicationError):
    def __init__(self, product_id: str) -> None:
        super().__init__(
            "UPGRADE_PRODUCT_NOT_FOUND",
            "Upgrade product not found",
            status_code=404,
            details={"upgrade_product_id": product_id},
        )


class PaymentNotFoundError(ApplicationError):
    def __init__(self, payment_id: UUID) -> None:
        super().__init__(
            "PAYMENT_NOT_FOUND",
            "Payment not found",
            status_code=404,
            details={"payment_id": str(payment_id)},
        )


class PaymentAuthorizationError(ApplicationError):
    def __init__(self, payment_id: UUID) -> None:
        super().__init__(
            "PAYMENT_FORBIDDEN",
            "You are not authorized to access this payment",
            status_code=403,
            details={"payment_id": str(payment_id)},
        )


class UnsupportedPaymentCurrencyError(ApplicationError):
    def __init__(self, currency: str) -> None:
        super().__init__(
            "UNSUPPORTED_PAYMENT_CURRENCY",
            "Payment currency is not supported",
            status_code=400,
            details={"currency": currency},
        )


class UnsupportedPaymentNetworkError(ApplicationError):
    def __init__(self, currency: str, network: str) -> None:
        super().__init__(
            "UNSUPPORTED_PAYMENT_NETWORK",
            "Payment network is not supported for the selected currency",
            status_code=400,
            details={"currency": currency, "network": network},
        )


class DuplicatePaymentTransactionError(ApplicationError):
    def __init__(self, transaction_hash: str, network: str) -> None:
        super().__init__(
            "DUPLICATE_PAYMENT_TRANSACTION",
            "Transaction hash has already been used for a payment",
            status_code=409,
            details={"transaction_hash": transaction_hash, "network": network},
        )


class InvalidWebhookSignatureError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "INVALID_WEBHOOK_SIGNATURE",
            "Webhook signature verification failed",
            status_code=401,
        )


class PaymentStateError(ApplicationError):
    def __init__(self, message: str, *, payment_id: UUID, status: str) -> None:
        super().__init__(
            "INVALID_PAYMENT_STATE",
            message,
            status_code=409,
            details={"payment_id": str(payment_id), "status": status},
        )


class PaymentConfigurationError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "PAYMENT_CONFIGURATION_ERROR",
            message,
            status_code=503,
        )


class ConversationNotFoundError(ApplicationError):
    def __init__(self, conversation_id: UUID) -> None:
        super().__init__(
            "CONVERSATION_NOT_FOUND",
            "Conversation not found",
            status_code=404,
            details={"conversation_id": str(conversation_id)},
        )


class ConversationForbiddenError(ApplicationError):
    def __init__(self, message: str = "You do not have access to this conversation") -> None:
        super().__init__(
            "CONVERSATION_FORBIDDEN",
            message,
            status_code=403,
        )


class MetaAgentApprovalRequiredError(ApplicationError):
    def __init__(
        self,
        message: str = "Human approval is required before a new agent may be created or built.",
        *,
        details: dict | None = None,
    ) -> None:
        super().__init__(
            "META_AGENT_APPROVAL_REQUIRED",
            message,
            status_code=403,
            details=details,
        )


class MetaAgentUnsupportedRequestError(ApplicationError):
    def __init__(self, message: str = "Meta-Agent request is unsupported.") -> None:
        super().__init__(
            "META_AGENT_UNSUPPORTED",
            message,
            status_code=400,
        )


class BuildingBriefIncompleteError(ApplicationError):
    def __init__(self, missing_inputs: list[str]) -> None:
        super().__init__(
            "BUILDING_BRIEF_INCOMPLETE",
            "The building brief is missing inputs required to generate a layout.",
            status_code=400,
            details={"missing_inputs": missing_inputs},
        )


class BuildingLayoutInfeasibleError(ApplicationError):
    def __init__(self, reason: str, *, details: dict | None = None) -> None:
        super().__init__(
            "BUILDING_LAYOUT_INFEASIBLE",
            reason,
            status_code=422,
            details=details,
        )


class BuildingModelNotGeneratedError(ApplicationError):
    def __init__(self, project_id: UUID) -> None:
        super().__init__(
            "BUILDING_MODEL_NOT_GENERATED",
            "This project has no generated building model yet.",
            status_code=404,
            details={"project_id": str(project_id)},
        )


class StructuralAnalysisFailedError(ApplicationError):
    def __init__(self, reason: str, *, details: dict | None = None) -> None:
        super().__init__(
            "STRUCTURAL_ANALYSIS_FAILED",
            reason,
            status_code=422,
            details=details,
        )


class LearningRecordNotFoundError(ApplicationError):
    def __init__(self, record_id: UUID, *, project_id: UUID | None = None) -> None:
        details = {"record_id": str(record_id)}
        if project_id is not None:
            details["project_id"] = str(project_id)
        super().__init__(
            "LEARNING_RECORD_NOT_FOUND",
            "Learning record not found",
            status_code=404,
            details=details,
        )


class LearningInvalidStateError(ApplicationError):
    def __init__(self, record_id: UUID, *, current_status: str) -> None:
        super().__init__(
            "LEARNING_INVALID_STATE",
            "Learning record is not in a valid state for this operation",
            status_code=409,
            details={"record_id": str(record_id), "current_status": current_status},
        )


class LearningAuthorizationError(ApplicationError):
    def __init__(self, record_id: UUID) -> None:
        super().__init__(
            "LEARNING_FORBIDDEN",
            "You are not authorized to review this learning record",
            status_code=403,
            details={"record_id": str(record_id)},
        )


class LearningSafetyError(ApplicationError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(
            "LEARNING_SAFETY_REJECTED",
            message,
            status_code=422,
            details=details,
        )
