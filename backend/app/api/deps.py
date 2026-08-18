"""FastAPI dependency injection for application services."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

from app.application.agent_registry_service import AgentRegistryService
from app.application.agent_runtime_service import AgentRuntimeService
from app.application.agent_version_service import AgentVersionService
from app.application.ai_gateway_service import AIGatewayService
from app.application.analysis_engine_service import AnalysisEngineService
from app.application.code_engine_service import CodeEngineService
from app.application.design_engine_service import DesignEngineService
from app.application.document_indexing_service import DocumentIndexingService
from app.application.file_ingestion_service import FileIngestionService
from app.application.file_registry_service import FileRegistryService
from app.application.human_approval_service import HumanApprovalService
from app.application.hybrid_orchestration_service import HybridOrchestrationService
from app.application.integration_service import IntegrationService
from app.application.pem_revision_service import PemRevisionService
from app.application.project_context_assembly_service import ProjectContextAssemblyService
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.application.prompt_template_service import PromptTemplateService
from app.application.revision_service import RevisionService
from app.application.unit_conversion_service import UnitConversionService
from app.application.validation_engine_service import ValidationEngineService
from app.application.traceability_service import TraceabilityService
from app.application.report_generation_service import ReportGenerationService
from app.application.service_factory import (
    build_agent_registry_service,
    build_agent_runtime_service,
    build_agent_version_service,
    build_ai_gateway_service,
    build_analysis_engine_service,
    build_code_engine_service,
    build_design_engine_service,
    build_document_indexing_service,
    build_file_ingestion_service,
    build_file_registry_service,
    build_hybrid_orchestration_service,
    build_human_approval_service,
    build_integration_service,
    build_pem_revision_service,
    build_pem_service,
    build_project_context_assembly_service,
    build_project_memory_service,
    build_project_service,
    build_prompt_template_service,
    build_report_generation_service,
    build_traceability_service,
    build_unit_conversion_service,
    build_validation_engine_service,
    build_revision_service,
)


def get_project_service() -> ProjectService:
    return build_project_service()


def get_pem_service() -> PemService:
    return build_pem_service()


def get_pem_revision_service() -> PemRevisionService:
    return build_pem_revision_service()


def get_revision_service() -> RevisionService:
    return build_revision_service()


def get_project_memory_service() -> ProjectMemoryService:
    return build_project_memory_service()


def get_project_context_assembly_service() -> ProjectContextAssemblyService:
    return build_project_context_assembly_service()


def get_actor_id(
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
) -> str:
    return x_actor_id or "api-client"


def get_agent_registry_service() -> AgentRegistryService:
    return build_agent_registry_service()


def get_agent_runtime_service() -> AgentRuntimeService:
    return build_agent_runtime_service()


def get_agent_version_service() -> AgentVersionService:
    return build_agent_version_service()


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


def get_ai_gateway_service() -> AIGatewayService:
    return build_ai_gateway_service()


def get_hybrid_orchestration_service() -> HybridOrchestrationService:
    return build_hybrid_orchestration_service()


def get_analysis_engine_service() -> AnalysisEngineService:
    return build_analysis_engine_service()


def get_design_engine_service() -> DesignEngineService:
    return build_design_engine_service()


def get_human_approval_service() -> HumanApprovalService:
    return build_human_approval_service()


def get_traceability_service() -> TraceabilityService:
    return build_traceability_service()


def get_report_generation_service() -> ReportGenerationService:
    return build_report_generation_service()
