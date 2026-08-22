"""FastAPI dependency injection for application services."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Query

from app.application.agent_builder_service import AgentBuilderService
from app.application.auth_service import AuthService
from app.application.entitlement_authorization_service import EntitlementAuthorizationService
from app.application.agent_access_service import AgentAccessService
from app.application.project_access_service import ProjectAccessService
from app.application.agent_registry_service import AgentRegistryService
from app.application.agent_runtime_service import AgentRuntimeService
from app.application.agent_version_service import AgentVersionService
from app.application.ai_gateway_service import AIGatewayService
from app.application.analysis_engine_service import AnalysisEngineService
from app.application.code_engine_service import CodeEngineService
from app.application.design_engine_service import DesignEngineService
from app.application.cad_generation_service import CadGenerationService
from app.application.engineering_result_service import EngineeringResultService
from app.application.optimization_engine_service import OptimizationEngineService
from app.application.digital_payment_agent import DigitalPaymentAgent
from app.application.file_ingestion_service import FileIngestionService
from app.application.file_registry_service import FileRegistryService
from app.application.human_approval_service import HumanApprovalService
from app.application.hybrid_orchestration_service import HybridOrchestrationService
from app.application.integration_service import IntegrationService
from app.application.pem_model_service import PemModelService
from app.application.pem_revision_service import PemRevisionService
from app.application.project_context_assembly_service import ProjectContextAssemblyService
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.application.prompt_template_service import PromptTemplateService
from app.application.revision_service import RevisionService
from app.application.unit_conversion_service import UnitConversionService
from app.application.validation_engine_service import ValidationEngineService
from app.application.traceability_service import TraceabilityService
from app.application.structural_solver_integration_service import StructuralSolverIntegrationService
from app.application.report_generation_service import ReportGenerationService
from app.application.service_factory import (
    build_agent_builder_service,
    build_agent_registry_service,
    build_agent_runtime_service,
    build_agent_version_service,
    build_ai_gateway_service,
    build_analysis_engine_service,
    build_auth_service,
    build_code_engine_service,
    build_cad_generation_service,
    build_design_engine_service,
    build_engineering_result_service,
    build_optimization_engine_service,
    build_digital_payment_agent,
    build_document_indexing_service,
    build_file_ingestion_service,
    build_file_registry_service,
    build_hybrid_orchestration_service,
    build_human_approval_service,
    build_integration_service,
    build_pem_model_service,
    build_pem_revision_service,
    build_pem_service,
    build_entitlement_authorization_service,
    build_agent_access_service,
    build_project_access_service,
    build_project_context_assembly_service,
    build_project_memory_service,
    build_project_service,
    build_prompt_template_service,
    build_structural_solver_integration_service,
    build_report_generation_service,
    build_traceability_service,
    build_unit_conversion_service,
    build_validation_engine_service,
    build_revision_service,
)
from app.application.exceptions import AuthenticationError
from app.domain.models.platform_features import PlatformFeature
from app.domain.models.project import Project
from app.domain.models.user import AuthenticatedAccount
from app.infrastructure.config import get_settings


def get_project_service() -> ProjectService:
    return build_project_service()


def get_pem_service() -> PemService:
    return build_pem_service()


def get_pem_revision_service() -> PemRevisionService:
    return build_pem_revision_service()


def get_pem_model_service() -> PemModelService:
    return build_pem_model_service()


def get_revision_service() -> RevisionService:
    return build_revision_service()


def get_project_memory_service() -> ProjectMemoryService:
    return build_project_memory_service()


def get_project_context_assembly_service() -> ProjectContextAssemblyService:
    return build_project_context_assembly_service()


def get_auth_service() -> AuthService:
    return build_auth_service()


def get_project_access_service() -> ProjectAccessService:
    return build_project_access_service()


def get_current_account(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    authorization: Annotated[str | None, Header()] = None,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
) -> AuthenticatedAccount:
    settings = get_settings()
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        return auth_service.authenticate_bearer(token)
    if x_actor_id:
        if not settings.auth_allow_legacy_actor:
            raise AuthenticationError("Legacy X-Actor-Id authentication is disabled")
        return auth_service.resolve_legacy_actor(x_actor_id)
    if settings.auth_required:
        raise AuthenticationError()
    return auth_service.resolve_legacy_actor("api-client")


def get_actor_id(
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> str:
    return account.account_id


def get_accessible_project(
    project_id: UUID,
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
) -> Project:
    return access.require_project(project_id, account)


def get_accessible_project_from_query(
    project_id: Annotated[UUID, Query()],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
) -> Project:
    return access.require_project(project_id, account)


def get_optional_accessible_project_from_query(
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
    project_id: Annotated[UUID | None, Query()] = None,
) -> Project | None:
    if project_id is None:
        return None
    return access.require_project(project_id, account)


def get_entitlement_authorization_service() -> EntitlementAuthorizationService:
    return build_entitlement_authorization_service()


def get_agent_access_service() -> AgentAccessService:
    from app.application.agent_access_service import AgentAccessService

    return build_agent_access_service()


def require_platform_feature(feature: PlatformFeature):
    def _dependency(
        account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
        entitlements: Annotated[
            EntitlementAuthorizationService, Depends(get_entitlement_authorization_service)
        ],
    ) -> None:
        entitlements.require_feature(account.account_id, feature)

    return _dependency


def get_agent_registry_service() -> AgentRegistryService:
    return build_agent_registry_service()


def get_agent_runtime_service() -> AgentRuntimeService:
    return build_agent_runtime_service()


def get_agent_version_service() -> AgentVersionService:
    return build_agent_version_service()


def get_agent_builder_service() -> AgentBuilderService:
    return build_agent_builder_service()


def get_prompt_template_service() -> PromptTemplateService:
    return build_prompt_template_service()


def get_file_registry_service() -> FileRegistryService:
    return build_file_registry_service()


def get_file_ingestion_service() -> FileIngestionService:
    return build_file_ingestion_service()


def get_document_indexing_service() -> DocumentIndexingService:
    return build_document_indexing_service()


def get_unit_conversion_service() -> UnitConversionService:
    return build_unit_conversion_service()


def get_code_engine_service() -> CodeEngineService:
    return build_code_engine_service()


def get_validation_engine_service() -> ValidationEngineService:
    return build_validation_engine_service()


def get_integration_service() -> IntegrationService:
    return build_integration_service()


def get_structural_solver_integration_service() -> StructuralSolverIntegrationService:
    return build_structural_solver_integration_service()


def get_ai_gateway_service() -> AIGatewayService:
    return build_ai_gateway_service()


def get_hybrid_orchestration_service() -> HybridOrchestrationService:
    return build_hybrid_orchestration_service()


def get_analysis_engine_service() -> AnalysisEngineService:
    return build_analysis_engine_service()


def get_design_engine_service() -> DesignEngineService:
    return build_design_engine_service()


def get_optimization_engine_service() -> OptimizationEngineService:
    return build_optimization_engine_service()


def get_engineering_result_service() -> EngineeringResultService:
    return build_engineering_result_service()


def get_cad_generation_service() -> CadGenerationService:
    return build_cad_generation_service()


def get_human_approval_service() -> HumanApprovalService:
    return build_human_approval_service()


def get_traceability_service() -> TraceabilityService:
    return build_traceability_service()


def get_report_generation_service() -> ReportGenerationService:
    return build_report_generation_service()


def get_digital_payment_agent() -> DigitalPaymentAgent:
    return build_digital_payment_agent()
