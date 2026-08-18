"""Factory helpers for wiring application services to PostgreSQL repositories."""

from app.application.pem_revision_service import PemRevisionService
from app.application.project_service import PemService, ProjectService
from app.application.revision_service import RevisionService
from app.infrastructure.repositories.postgres_pem_repository import PostgresPemRepository
from app.infrastructure.repositories.postgres_project_repository import PostgresProjectRepository
from app.infrastructure.repositories.postgres_revision_repository import PostgresRevisionRepository


def _project_repository() -> PostgresProjectRepository:
    return PostgresProjectRepository()


def _pem_repository() -> PostgresPemRepository:
    return PostgresPemRepository()


def _revision_repository() -> PostgresRevisionRepository:
    return PostgresRevisionRepository()


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
