"""Factory helpers for wiring application services to PostgreSQL repositories."""

from app.application.project_service import PemService, ProjectService
from app.infrastructure.repositories.postgres_pem_repository import PostgresPemRepository
from app.infrastructure.repositories.postgres_project_repository import PostgresProjectRepository
from app.infrastructure.repositories.postgres_revision_repository import PostgresRevisionRepository


def build_project_service() -> ProjectService:
    return ProjectService(
        project_repository=PostgresProjectRepository(),
        pem_repository=PostgresPemRepository(),
        revision_repository=PostgresRevisionRepository(),
    )


def build_pem_service() -> PemService:
    return PemService(pem_repository=PostgresPemRepository())
