"""Factory helpers for wiring application services to PostgreSQL repositories."""

from app.application.agent_registry_service import AgentRegistryService
from app.application.agent_version_service import AgentVersionService
from app.application.file_ingestion_service import FileIngestionService
from app.application.file_registry_service import FileRegistryService
from app.application.pem_revision_service import PemRevisionService
from app.application.project_service import PemService, ProjectService
from app.application.prompt_template_service import PromptTemplateService
from app.application.revision_service import RevisionService
from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)
from app.infrastructure.repositories.postgres_agent_definition_repository import (
    PostgresAgentDefinitionRepository,
)
from app.infrastructure.repositories.postgres_agent_version_repository import (
    PostgresAgentVersionRepository,
)
from app.infrastructure.parsers.stub_parser import StubTextParser
from app.infrastructure.repositories.postgres_file_repository import PostgresFileRepository
from app.infrastructure.repositories.postgres_pem_repository import PostgresPemRepository
from app.infrastructure.repositories.postgres_project_repository import PostgresProjectRepository
from app.infrastructure.repositories.postgres_prompt_template_repository import (
    PostgresPromptTemplateRepository,
)
from app.infrastructure.repositories.postgres_revision_repository import PostgresRevisionRepository
from app.infrastructure.storage.local_file_storage import LocalFileStorage
from app.infrastructure.config import get_settings


def _project_repository() -> PostgresProjectRepository:
    return PostgresProjectRepository()


def _pem_repository() -> PostgresPemRepository:
    return PostgresPemRepository()


def _revision_repository() -> PostgresRevisionRepository:
    return PostgresRevisionRepository()


def _agent_definition_repository() -> PostgresAgentDefinitionRepository:
    return PostgresAgentDefinitionRepository()


def _agent_version_repository() -> PostgresAgentVersionRepository:
    return PostgresAgentVersionRepository()


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
    return FileIngestionService(
        project_service=build_project_service(),
        file_repository=_file_repository(),
        file_storage=_file_storage(),
        parsers=[StubTextParser()],
        max_upload_bytes=settings.max_upload_bytes,
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
