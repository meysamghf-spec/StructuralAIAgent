# Engineering AI Platform — Documentation

## Phase 0

Architecture is frozen in `PHASE_0_ARCHITECTURE_ASSESSMENT.md` (do not modify without approval).

## Phase 1 — Milestones

| Milestone | Scope | Status |
|-----------|-------|--------|
| **M1** | Repository bootstrap, FastAPI health, Next.js landing, migration infrastructure | Complete |
| **M2** | PostgreSQL persistence, PEM snapshots (JSONB), revisions, domain models, repository protocols | Complete |
| **M3** | REST Project API (`/api/v1`), PEM revision traceability, API integration tests, OpenAPI `/docs` | Complete |
| **M4** | Agent Foundation — registry, versioning, capabilities, prompt templates, contracts only | Complete |
| **M5+** | Not started | — |

See root `README.md` for setup and API examples.

## M4 Agent Foundation

Purpose: database-backed, agent-neutral registry foundation for future Meta-Agent, Prompt Engineering Agent, and orchestration work (AG-44, AG-45).

- **Platform-scoped** agent definitions (not project-scoped)
- **Lifecycle:** DRAFT → ACTIVE → ARCHIVED (definitions); version lifecycle with one ACTIVE version per agent
- **Prompt templates:** versioned per agent version; historical versions retained
- **Contracts only:** `AgentExecution`, `HumanApprovalGate` — no LLM executor or approval workflow in M4
