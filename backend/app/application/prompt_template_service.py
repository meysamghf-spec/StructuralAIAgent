"""Application service — versioned prompt templates per AgentVersion."""

from __future__ import annotations

from uuid import UUID

from app.application.agent_version_service import AgentVersionService
from app.application.exceptions import PromptTemplateNotFoundError
from app.domain.models.prompt_template import PromptTemplate, PromptTemplateStatus
from app.domain.repositories.agent_protocols import PromptTemplateRepository


class PromptTemplateService:
    def __init__(
        self,
        prompt_repository: PromptTemplateRepository,
        version_service: AgentVersionService,
    ) -> None:
        self._prompts = prompt_repository
        self._versions = version_service

    def create_prompt(
        self,
        agent_id: UUID,
        agent_version_number: int,
        *,
        name: str,
        template: str,
        variables_schema: dict | None = None,
        created_by: str | None = None,
    ) -> PromptTemplate:
        version_detail = self._versions.get_version(agent_id, agent_version_number)
        self._versions.ensure_mutable(agent_id, agent_version_number)
        return self._prompts.create(
            version_detail.version.id,
            name=name,
            template=template,
            variables_schema=variables_schema,
            created_by=created_by,
            status=PromptTemplateStatus.DRAFT,
        )

    def list_prompts(self, agent_id: UUID, agent_version_number: int) -> list[PromptTemplate]:
        version_detail = self._versions.get_version(agent_id, agent_version_number)
        return self._prompts.list_for_version(version_detail.version.id)

    def get_prompt(
        self,
        agent_id: UUID,
        agent_version_number: int,
        prompt_version: int,
    ) -> PromptTemplate:
        version_detail = self._versions.get_version(agent_id, agent_version_number)
        prompt = self._prompts.get_by_version_and_number(
            version_detail.version.id, prompt_version
        )
        if prompt is None:
            raise PromptTemplateNotFoundError(agent_id, agent_version_number, prompt_version)
        return prompt
