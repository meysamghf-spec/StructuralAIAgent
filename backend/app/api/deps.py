"""FastAPI dependency injection for application services."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

from app.application.pem_revision_service import PemRevisionService
from app.application.project_service import PemService, ProjectService
from app.application.revision_service import RevisionService
from app.application.service_factory import (
    build_pem_revision_service,
    build_pem_service,
    build_project_service,
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


def get_actor_id(
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
) -> str:
    return x_actor_id or "api-client"
