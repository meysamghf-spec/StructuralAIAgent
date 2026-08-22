"""Factory helpers for wiring application services to PostgreSQL repositories."""

from app.application.agent_approval_completion_service import AgentApprovalCompletionService
from app.application.agent_builder_approval_completion_service import (
    AgentBuilderApprovalCompletionService,
)
from app.application.agent_builder_service import AgentBuilderService
from app.application.composite_approval_completion_service import CompositeApprovalCompletionService
from app.application.agent_registry_service import AgentRegistryService
from app.application.agent_runtime_service import AgentRuntimeService
from app.application.agent_version_service import AgentVersionService
from app.application.ai_gateway_service import AIGatewayService
from app.application.analysis_engine_service import AnalysisEngineService
from app.application.code_engine_service import CodeEngineService
from app.application.compatibility_engine import CompatibilityEngine
from app.application.cad_generation_service import CadGenerationService
from app.application.design_engine_service import DesignEngineService
from app.application.engineering_result_service import EngineeringResultService
from app.application.optimization_engine_service import OptimizationEngineService
from app.application.document_indexing_service import DocumentIndexingService
from app.application.engineering_agent_handlers import build_engineering_agent_handlers
from app.application.file_ingestion_service import FileIngestionService
from app.application.file_registry_service import FileRegistryService
from app.application.human_approval_service import HumanApprovalService
from app.application.hybrid_orchestration_service import HybridOrchestrationService
from app.application.integration_service import IntegrationService
from app.application.traceability_service import TraceabilityService
from app.application.digital_payment_agent import DigitalPaymentAgent
from app.application.payment_service import PaymentService
from app.application.pem_model_service import PemModelService
from app.application.pem_revision_service import PemRevisionService
from app.application.project_context_assembly_service import ProjectContextAssemblyService
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.application.prompt_generation_service import PromptGenerationService
from app.application.report_generation_service import ReportGenerationService
from app.application.revision_service import RevisionService
from app.application.unit_conversion_service import UnitConversionService
from app.application.structural_solver_integration_service import StructuralSolverIntegrationService
from app.application.validation_engine_service import ValidationEngineService
from app.infrastructure.config import get_settings
from app.infrastructure.code_plugins import build_default_plugin_registry
from app.infrastructure.integrations import build_integration_adapters
from app.infrastructure.ai.stub_ai_provider import StubAIProvider
from app.domain.contracts.crypto_payment_gateway import CryptoPaymentGateway
from app.domain.models.ai_gateway import AIProviderKind
from app.infrastructure.parsers.stub_parser import StubTextParser
from app.infrastructure.repositories.postgres_payment_repository import PostgresPaymentRepository
from app.application.prompt_template_service import PromptTemplateService
from app.infrastructure.repositories.postgres_agent_builder_publication_repository import (
    PostgresAgentBuilderPublicationRepository,
)
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
from app.infrastructure.repositories.postgres_agent_version_test_repository import (
    PostgresAgentVersionTestRepository,
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
from app.infrastructure.repositories.postgres_analysis_repository import PostgresAnalysisRepository
from app.infrastructure.repositories.postgres_design_repository import PostgresDesignRepository
from app.infrastructure.repositories.postgres_cad_drawing_repository import PostgresCadDrawingRepository
from app.infrastructure.repositories.postgres_engineering_result_repository import (
    PostgresEngineeringResultRepository,
)
from app.infrastructure.repositories.postgres_integration_execution_repository import (
    PostgresIntegrationExecutionRepository,
)
from app.infrastructure.repositories.postgres_optimization_repository import (
    PostgresOptimizationRepository,
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


def _analysis_repository() -> PostgresAnalysisRepository:
    return PostgresAnalysisRepository()


def _engineering_result_repository() -> PostgresEngineeringResultRepository:
    return PostgresEngineeringResultRepository()


def _cad_drawing_repository() -> PostgresCadDrawingRepository:
    return PostgresCadDrawingRepository()


def _design_repository() -> PostgresDesignRepository:
    return PostgresDesignRepository()


def _optimization_repository() -> PostgresOptimizationRepository:
    return PostgresOptimizationRepository()


def _integration_execution_repository() -> PostgresIntegrationExecutionRepository:
    return PostgresIntegrationExecutionRepository()


def _agent_definition_repository() -> PostgresAgentDefinitionRepository:
    return PostgresAgentDefinitionRepository()


def _agent_version_repository() -> PostgresAgentVersionRepository:
    return PostgresAgentVersionRepository()


def _agent_execution_repository() -> PostgresAgentExecutionRepository:
    return PostgresAgentExecutionRepository()


def _agent_version_test_repository() -> PostgresAgentVersionTestRepository:
    return PostgresAgentVersionTestRepository()


def _agent_builder_publication_repository() -> PostgresAgentBuilderPublicationRepository:
    return PostgresAgentBuilderPublicationRepository()


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


def build_auth_service() -> AuthService:
    from app.application.auth_service import AuthService as AuthServiceImpl
    from app.infrastructure.repositories.postgres_user_repository import PostgresUserRepository

    return AuthServiceImpl(user_repository=PostgresUserRepository())


def build_project_access_service() -> ProjectAccessService:
    from app.application.project_access_service import ProjectAccessService as ProjectAccessServiceImpl

    return ProjectAccessServiceImpl(project_repository=_project_repository())


def build_entitlement_authorization_service() -> EntitlementAuthorizationService:
    from app.application.entitlement_authorization_service import (
        EntitlementAuthorizationService as EntitlementAuthorizationServiceImpl,
    )
    from app.infrastructure.repositories.postgres_payment_repository import PostgresPaymentRepository

    return EntitlementAuthorizationServiceImpl(repository=PostgresPaymentRepository())


def build_pem_service() -> PemService:
    return PemService(pem_repository=_pem_repository())


def build_pem_revision_service() -> PemRevisionService:
    return PemRevisionService(
        project_repository=_project_repository(),
        pem_repository=_pem_repository(),
        revision_repository=_revision_repository(),
    )


def build_pem_model_service() -> PemModelService:
    return PemModelService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        pem_revision_service=build_pem_revision_service(),
        approval_service=build_human_approval_service(),
        traceability_service=build_traceability_service(),
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
        engineering_result_service=build_engineering_result_service(),
        analysis_repository=_analysis_repository(),
        cad_generation_service=build_cad_generation_service(),
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


def build_agent_approval_completion_service() -> AgentApprovalCompletionService:
    return AgentApprovalCompletionService(
        execution_repository=_agent_execution_repository(),
        orchestration_service=build_hybrid_orchestration_service(),
        memory_service=build_project_memory_service(),
        traceability_service=build_traceability_service(),
        report_repository=_report_repository(),
    )


def build_agent_builder_approval_completion_service() -> AgentBuilderApprovalCompletionService:
    return AgentBuilderApprovalCompletionService(
        publication_repository=_agent_builder_publication_repository(),
        version_service=build_agent_version_service(),
        traceability_service=build_traceability_service(),
    )


def build_composite_approval_completion_service() -> CompositeApprovalCompletionService:
    return CompositeApprovalCompletionService(
        agent_execution_completion=build_agent_approval_completion_service(),
        agent_builder_completion=build_agent_builder_approval_completion_service(),
    )


def build_human_approval_service() -> HumanApprovalService:
    return HumanApprovalService(
        project_repository=_project_repository(),
        approval_repository=_human_approval_repository(),
        memory_service=build_project_memory_service(),
        traceability_service=build_traceability_service(),
        agent_completion_service=build_composite_approval_completion_service(),
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
        analysis_repository=_analysis_repository(),
        design_repository=_design_repository(),
        optimization_repository=_optimization_repository(),
        engineering_result_service=build_engineering_result_service(),
        cad_generation_service=build_cad_generation_service(),
    )


def build_integration_service() -> IntegrationService:
    return IntegrationService(adapters=build_integration_adapters())


def build_engineering_result_service() -> EngineeringResultService:
    return EngineeringResultService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        result_repository=_engineering_result_repository(),
        traceability_service=build_traceability_service(),
        memory_service=build_project_memory_service(),
    )


def build_cad_generation_service() -> CadGenerationService:
    return CadGenerationService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        drawing_repository=_cad_drawing_repository(),
        integration_service=build_integration_service(),
        traceability_service=build_traceability_service(),
    )


def build_structural_solver_integration_service() -> StructuralSolverIntegrationService:
    return StructuralSolverIntegrationService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        integration_service=build_integration_service(),
        execution_repository=_integration_execution_repository(),
        traceability_service=build_traceability_service(),
        memory_service=build_project_memory_service(),
        engineering_result_service=build_engineering_result_service(),
    )


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
        analysis_engine_service=build_analysis_engine_service(),
        design_engine_service=build_design_engine_service(),
        optimization_engine_service=build_optimization_engine_service(),
    )


def build_analysis_engine_service() -> AnalysisEngineService:
    return AnalysisEngineService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        analysis_repository=_analysis_repository(),
        traceability_service=build_traceability_service(),
        memory_service=build_project_memory_service(),
        solver_integration_service=build_structural_solver_integration_service(),
    )


def build_design_engine_service() -> DesignEngineService:
    return DesignEngineService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        design_repository=_design_repository(),
        analysis_repository=_analysis_repository(),
        code_engine_service=build_code_engine_service(),
        traceability_service=build_traceability_service(),
        memory_service=build_project_memory_service(),
        engineering_result_service=build_engineering_result_service(),
    )


def build_optimization_engine_service() -> OptimizationEngineService:
    return OptimizationEngineService(
        project_service=build_project_service(),
        pem_service=build_pem_service(),
        optimization_repository=_optimization_repository(),
        analysis_repository=_analysis_repository(),
        design_repository=_design_repository(),
        code_engine_service=build_code_engine_service(),
        traceability_service=build_traceability_service(),
        memory_service=build_project_memory_service(),
        engineering_result_service=build_engineering_result_service(),
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


def build_engineering_agent_services() -> EngineeringAgentServices:
    from app.application.engineering_agent_services import EngineeringAgentServices

    return EngineeringAgentServices(
        validation_engine=build_validation_engine_service(),
        analysis_engine=build_analysis_engine_service(),
        design_engine=build_design_engine_service(),
        optimization_engine=build_optimization_engine_service(),
        integration_service=build_integration_service(),
        code_engine=build_code_engine_service(),
        engineering_result_service=build_engineering_result_service(),
        cad_generation_service=build_cad_generation_service(),
        report_generation_service=build_report_generation_service(),
    )


def build_agent_orchestration_service() -> AgentOrchestrationService:
    from app.application.agent_orchestration_service import AgentOrchestrationService as AgentOrchestrationServiceImpl

    return AgentOrchestrationServiceImpl(
        definition_repository=_agent_definition_repository(),
        version_repository=_agent_version_repository(),
        execution_repository=_agent_execution_repository(),
        context_service=build_project_context_assembly_service(),
        prompt_generation_service=build_prompt_generation_service(),
        traceability_service=build_traceability_service(),
        approval_service=build_human_approval_service(),
        entitlement_service=build_entitlement_authorization_service(),
        orchestration_service=build_hybrid_orchestration_service(),
        handlers=build_engineering_agent_handlers(build_engineering_agent_services()),
    )


def build_agent_access_service() -> AgentAccessService:
    from app.application.agent_access_service import AgentAccessService as AgentAccessServiceImpl

    return AgentAccessServiceImpl(
        definition_repository=_agent_definition_repository(),
        project_access_service=build_project_access_service(),
    )


def build_agent_runtime_service() -> AgentRuntimeService:
    return AgentRuntimeService(
        execution_repository=_agent_execution_repository(),
        context_service=build_project_context_assembly_service(),
        prompt_generation_service=build_prompt_generation_service(),
        orchestration_service=build_agent_orchestration_service(),
    )


def build_agent_builder_service() -> AgentBuilderService:
    return AgentBuilderService(
        definition_repository=_agent_definition_repository(),
        registry_service=build_agent_registry_service(),
        version_service=build_agent_version_service(),
        capability_repository=_agent_capability_repository(),
        test_repository=_agent_version_test_repository(),
        publication_repository=_agent_builder_publication_repository(),
        runtime_service=build_agent_runtime_service(),
        approval_service=build_human_approval_service(),
        traceability_service=build_traceability_service(),
    )


_payment_gateway_instance: CryptoPaymentGateway | None = None


def get_crypto_payment_gateway() -> CryptoPaymentGateway:
    global _payment_gateway_instance
    if _payment_gateway_instance is None:
        from app.infrastructure.payments.payment_factory import create_crypto_payment_gateway

        _payment_gateway_instance = create_crypto_payment_gateway()
    return _payment_gateway_instance


def build_payment_service() -> PaymentService:
    from app.infrastructure.payments.payment_factory import create_exchange_rate_provider

    return PaymentService(
        repository=PostgresPaymentRepository(),
        gateway=get_crypto_payment_gateway(),
        exchange_rates=create_exchange_rate_provider(),
    )


def build_digital_payment_agent() -> DigitalPaymentAgent:
    return DigitalPaymentAgent(payment_service=build_payment_service())
