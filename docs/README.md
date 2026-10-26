# SAIA — Documentation

**Current product:** chat-first structural engineering workspace. Run instructions and the RC beam graphical Demo are in [DEMO.md](DEMO.md). The live ACI 318 RC beam check: [ACI_RC_BEAM_CHECK.md](ACI_RC_BEAM_CHECK.md). Agent progress, lifecycle, and capability boundaries: [AGENT_WORKSPACE.md](AGENT_WORKSPACE.md). What the product can and cannot do (inspection): [CAPABILITY_AUDIT.md](CAPABILITY_AUDIT.md).

Phase 0 architecture is frozen in `PHASE_0_ARCHITECTURE_ASSESSMENT.md` (do not modify without approval). Product vs World boundaries: [PRODUCT_BOUNDARIES.md](PRODUCT_BOUNDARIES.md).

## Phase 1 — Historical milestones

| Milestone | Scope | Status |
|-----------|-------|--------|
| **M1** | Repository bootstrap, FastAPI health, Next.js landing, migration infrastructure | Complete |
| **M2** | PostgreSQL persistence, PEM snapshots (JSONB), revisions, domain models, repository protocols | Complete |
| **M3** | REST Project API (`/api/v1`), PEM revision traceability, API integration tests, OpenAPI `/docs` | Complete |
| **M4** | Agent Foundation — registry, versioning, capabilities, prompt templates | Complete (`71486c9`) |
| **M5** | File Ingestion Foundation — project files, local storage, parsers | Implemented (in working tree with later Demo work) |

Later committed work added engineering runtime, agent workflow UX, CAD/CSI/optimization/payments, authentication, and deployment hardening. The uncommitted working tree adds chat/conversations, document extraction, the RC beam Demo, and the graphical chat visualization.

See root `README.md` for setup. See [DEMO.md](DEMO.md) for the Demo script.

## M4 Agent Foundation

Purpose: database-backed, agent-neutral registry foundation for Meta-Agent, Prompt Engineering Agent, and orchestration work (AG-44, AG-45).

- **Platform-scoped** agent definitions (not project-scoped)
- **Lifecycle:** DRAFT → ACTIVE → ARCHIVED (definitions); version lifecycle with one ACTIVE version per agent
- **Prompt templates:** versioned per agent version; historical versions retained

## M5 File Ingestion Foundation

Purpose: project-scoped file/artifact registration and synchronous ingestion foundation (Phase 0 Section J direction).

- **Project-scoped** `project_files` table with parsing/extraction status metadata
- **Local filesystem** storage via `FILE_STORAGE_ROOT` (not in source tree)
- Text, PDF, DOCX, and spreadsheet parsers are present in the current tree; CSI/CAD binaries remain stored/limited rather than executed
- **REST:** `POST/GET /api/v1/projects/{project_id}/files`, content download endpoint
