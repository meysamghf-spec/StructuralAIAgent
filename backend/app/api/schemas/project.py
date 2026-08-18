"""Project API request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.api.schemas.common import ProjectResponse, RevisionResponse


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class CreateProjectResponse(BaseModel):
    project: ProjectResponse
    pem_version: int
    snapshot_id: str
    revision: RevisionResponse


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
