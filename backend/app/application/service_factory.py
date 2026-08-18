"""Factory helpers for wiring application services to PostgreSQL repositories."""

from app.application.agent_registry_service import AgentRegistryService
from app.application.agent_runtime_service import AgentRuntimeService
from app.application.agent_version_service import AgentVersionService
from app.application.ai_gateway_service import AIGatewayService
from app.application.analysis_engine_service import AnalysisEngineService
from app.application.code_engine_service import CodeEngineService
from app.application.compatibility_engine import CompatibilityEngine
from app.application.design_engine_service import DesignEngineService
from app.application.document_indexing_service import DocumentIndexingService
from app.application.file_ingestion_service import FileIngestionService
from app.application.file_registry_service import FileRegistryService
from app.application.human_approval_service import HumanApprovalService
from app.application.hybrid_orchestration_service import HybridOrchestrationService
from app.application.integration_service import IntegrationService
from app.application.traceability_service import TraceabilityService
from app.application.pem_revision_service import PemRevisionService
from app.application.project_context_assembly_service import ProjectContextAssemblyService
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.application.prompt_generation_service import PromptGenerationService
from app.application.report_generation_service import ReportGenerationService
from app.application.revision_service import RevisionService
from app.application.unit_conversion_service import UnitConversionService
from app.application.validation_engine_service import ValidationEngineService
from app.infrastructure.config import get_settings
from app.infrastructure.code_plugins import build_default_plugin_registry
from app.infrastructure.integrations import build_integration_adapters
from app.infrastructure.ai.stub_ai_provider import StubAIProvider
from app.domain.models.ai_gateway import AIProviderKind
from app.infrastructure.parsers.stub_parser import StubTextParser
from app.application.prompt_template_service import PromptTemplateService
from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)
from app.infrastructure.repositories.postgres_agent_definition_repository import (
    PostgresAgentDefinitionRepository,
)
from app.infrastructure.repositories.postgres_agent_execution_repository import (
    PostgresAgentExecutionRepository,
)
from app.infrastructure.repositories.postgres_agent_version_repository import (
    PostgresAgentVersionRepository,
)
from app.infrastructure.repositories.postgres_file_repository import PostgresFileRepository
from app.infrastructure.repositories.postgres_human_approval_repository import (
    PostgresHumanApprovalRepository,
)
from app.infrastructure.repositories.postgres_pem_repository import PostgresPemRepository
from app.infrastructure.repositories.postgres_project_memory_repository import (
    PostgresProjectMemoryRepository,
)
from app.infrastructure.repositories.postgres_project_repository import PostgresProjectRepository
from app.infrastructure.repositories.postgres_prompt_template_repository import (
    PostgresPromptTemplateRepository,
)
from app.infrastructure.repositories.postgres_report_repository import PostgresReportRepository
from app.infrastructure.repositories.postgres_revision_repository import PostgresRevisionRepository
from app.infrastructure.repositories.postgres_traceability_repository import (
    PostgresTraceabilityRepository,
)
from app.infrastructure.storage.local_file_storage import LocalFileStorage


def _project_repository() -> PostgresProjectRepository:
    return PostgresProjectRepository()


def _pem_repository() -> PostgresPemRepository:
    return PostgresPemRepository()


def _revision_repository() -> PostgresRevisionRepository:
    return PostgresRevisionRepository()


def _project_memory_repository() -> PostgresProjectMemoryRepository:
    return PostgresProjectMemoryRepository()


def _human_approval_repository() -> PostgresHumanApprovalRepository:
    return PostgresHumanApprovalRepository()


def _traceability_repository() -> PostgresTraceabilityRepository:
    return PostgresTraceabilityRepository()


def _report_repository() -> PostgresReportRepository:
    return PostgresReportRepository()


def _agent_definition_repository() -> PostgresAgentDefinitionRepository:
    return PostgresAgentDefinitionRepository()


def _agent_version_repository() -> PostgresAgentVersionRepository:
    return PostgresAgentVersionRepository()


def _agent_execution_repository() -> PostgresAgentExecutionRepository:
    return PostgresAgentExecutionRepository()


def _agent_capability_repository() -> PostgresAgentCapabilityRepository:
    return PostgresAgentCapabilityRepository()


def _prompt_template_repository() -> PostgresPromptTemplateRepository:
    return PostgresPromptTemplateRepository()


def _file_repository() -> PostgresFileRepository:
    return PostgresFileRepository()


def _file_storage() -> LocalFileStorage:
    settings = get_settings()
    return LocalFileStorage(settings.resolved_file_storage_root)


def build_file_registry_service() -> FileRegistryService:
    return FileRegistryService(
        project_service=build_project_service(),
        file_repository=_file_repository(),
    )


def build_file_ingestion_service() -> FileIngestionService:
    settings = get_settings()
    auto_index = settings.auto_index_files
    return FileIngestionService(
        project_service=build_project_service(),
        file_repository=_file_repository(),
        file_storage=_file_storage(),
        parsers=[StubTextParser()],
        max_upload_bytes=settings.max_upload_bytes,
        document_indexing_service=build_document_indexing_service() if auto_index else None,
        auto_index_on_extraction=auto_index,
    )


def build_project_service() -> ProjectService:
    return ProjectService(
        project_repository=_project_repository(),
        pem_repository=_pem_repository(),
        revision_repository=_revision_repository(),
    )


def build_pem_service() -> PemService:
    return PemService(pem_repository=_pem_repository())


def build_pem_revision_service() -> PemRevisionService:
    return PemRevisionService(
        project_repository=_project_repository(),
        pem_repository=_pem_repository(),
        revision_repository=_revision_repository(),
    )


def build_revision_service() -> RevisionService:
    return RevisionService(
        project_repository=_project_repository(),
        revision_repository=_revision_repository(),
    )


def build_project_memory_service() -> ProjectMemoryService:
    return ProjectMemoryService(
        project_repository=_project_repository(),
        memory_repository=_project_memory_repository(),
    )


def build_traceability_service() -> TraceabilityService:
    return TraceabilityService(
        project_repository=_project_repository(),
        traceability_repository=_traceability_repository(),
    )


def build_document_indexing_service() -> DocumentIndexingService:
    return DocumentIndexingService(
        file_registry_service=build_file_registry_service(),
        memory_service=build_project_memory_service(),
        traceability_service=build_traceability_service(),
    )


def build_project_context_assembly_service() -> ProjectContextAssemblyService:
    return ProjectContextAssemblyService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        memory_service=build_project_memory_service(),
        file_registry_service=build_file_registry_service(),
    )


def build_unit_conversion_service() -> UnitConversionService:
    return UnitConversionService()


def build_code_engine_service() -> CodeEngineService:
    return CodeEngineService(
        plugins=build_default_plugin_registry(),
        compatibility_engine=CompatibilityEngine(),
    )


def build_validation_engine_service() -> ValidationEngineService:
    return ValidationEngineService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        code_engine_service=build_code_engine_service(),
    )


def build_human_approval_service() -> HumanApprovalService:
    return HumanApprovalService(
        project_repository=_project_repository(),
        approval_repository=_human_approval_repository(),
        memory_service=build_project_memory_service(),
        traceability_service=build_traceability_service(),
    )


def build_report_generation_service() -> ReportGenerationService:
    return ReportGenerationService(
        project_repository=_project_repository(),
        report_repository=_report_repository(),
        context_service=build_project_context_assembly_service(),
        traceability_service=build_traceability_service(),
        approval_service=build_human_approval_service(),
        validation_service=build_validation_engine_service(),
        pem_service=build_pem_service(),
    )


def build_integration_service() -> IntegrationService:
    return IntegrationService(adapters=build_integration_adapters())


def build_ai_gateway_service() -> AIGatewayService:
    stub = StubAIProvider()
    return AIGatewayService(providers={AIProviderKind.STUB: stub})


def build_hybrid_orchestration_service() -> HybridOrchestrationService:
    return HybridOrchestrationService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        validation_service=build_validation_engine_service(),
        code_engine_service=build_code_engine_service(),
        unit_conversion_service=build_unit_conversion_service(),
        ai_gateway_service=build_ai_gateway_service(),
    )


def build_analysis_engine_service() -> AnalysisEngineService:
    return AnalysisEngineService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
    )


def build_design_engine_service() -> DesignEngineService:
    return DesignEngineService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
    )


def build_agent_registry_service() -> AgentRegistryService:
    return AgentRegistryService(definition_repository=_agent_definition_repository())


def build_agent_version_service() -> AgentVersionService:
    return AgentVersionService(
        definition_repository=_agent_definition_repository(),
        version_repository=_agent_version_repository(),
        capability_repository=_agent_capability_repository(),
    )


def build_prompt_template_service() -> PromptTemplateService:
    return PromptTemplateService(
        prompt_repository=_prompt_template_repository(),
        version_service=build_agent_version_service(),
    )


def build_prompt_generation_service() -> PromptGenerationService:
    return PromptGenerationService(ai_gateway=build_ai_gateway_service())


def build_agent_runtime_service() -> AgentRuntimeService:
    return AgentRuntimeService(
        definition_repository=_agent_definition_repository(),
        version_repository=_agent_version_repository(),
        execution_repository=_agent_execution_repository(),
        context_service=build_project_context_assembly_service(),
        prompt_generation_service=build_prompt_generation_service(),
        traceability_service=build_traceability_service(),
        approval_service=build_human_approval_service(),
    )
