from __future__ import annotations

from app.application.platform_assistants import PLATFORM_ASSISTANTS, ensure_platform_assistants, provision_platform_assistant
from app.application.service_factory import build_agent_access_service
from app.domain.models.agent import AgentDefinitionStatus, EngineeringAgentType
from app.infrastructure.repositories.postgres_agent_definition_repository import PostgresAgentDefinitionRepository


def test_placeholder_draft_assistants_become_real_and_active() -> None:
    repo = PostgresAgentDefinitionRepository()
    for t in (EngineeringAgentType.LOAD_ASSESSMENT_AGENT, EngineeringAgentType.ANALYSIS_AGENT):
        for d in repo.list_by_agent_type(t):
            pass
    # simulate the old placeholder the orchestrator used to create (status DRAFT)
    bad = repo.create(key="ph_load_x", name="Load Assessment Agent", description="Auto-provisioned handler for LOAD_ASSESSMENT_AGENT",
                      agent_type=EngineeringAgentType.LOAD_ASSESSMENT_AGENT, configuration={"auto_provisioned": True})
    assert bad.status == AgentDefinitionStatus.DRAFT
    ensure_platform_assistants(repo)
    fixed = repo.get_by_id(bad.id)
    assert fixed is not None
    assert fixed.status == AgentDefinitionStatus.ACTIVE or any(
        d.status == AgentDefinitionStatus.ACTIVE for d in repo.list_by_agent_type(EngineeringAgentType.LOAD_ASSESSMENT_AGENT)
    )
    for t in PLATFORM_ASSISTANTS:
        rows = [d for d in repo.list_global() if d.agent_type == t]
        assert rows, t
        assert any(r.status == AgentDefinitionStatus.ACTIVE for r in rows), t
        assert not any((r.description or "").startswith("Auto-provisioned") and r.status == AgentDefinitionStatus.ACTIVE for r in rows)


def test_provision_is_idempotent() -> None:
    repo = PostgresAgentDefinitionRepository()
    a = provision_platform_assistant(repo, EngineeringAgentType.SEISMIC_AGENT)
    b = provision_platform_assistant(repo, EngineeringAgentType.SEISMIC_AGENT)
    assert a.id == b.id and b.status == AgentDefinitionStatus.ACTIVE
    assert "Auto-provisioned" not in (b.description or "")
