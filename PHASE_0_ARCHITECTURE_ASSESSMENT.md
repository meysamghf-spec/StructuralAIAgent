# PHASE 0 — Current-State and Architecture Assessment

**Project:** StructuralAIAgent — Engineering AI Platform *(Structural Engineering: initial domain)*  
**Assessment Date:** 2026-08-10  
**Last Updated:** 2026-08-12 (Phase 0 Architecture Freeze — AG-01 through AG-75 RESOLVED)  
**Phase:** 0 (Architecture Documentation — No Implementation)  
**Phase 0 Status:** **FROZEN / FREEZE CANDIDATE APPROVED**  
**Authoritative Specification:** `MASTER PROMPT V2.md`  
**Supplementary Requirements:** Design Code Selection Policy (Section M.1), Unit System Policy (Section M.2), Default US Code Profile (Section M.3), Platform Architecture Freeze (Section U)  
**Status:** **FROZEN** — Phase 0 complete. Implementation **NOT STARTED**. Phase 1 **NOT AUTHORIZED**.

---

## A. Executive Summary

### FACTS

- The workspace at `C:\Users\ASUS\Desktop\StructuralAIAgent` is a **greenfield project**.
- The repository contains **two files**: `MASTER PROMPT V2.md` and `PHASE_0_ARCHITECTURE_ASSESSMENT.md`.
- There is **no git repository**, no application source code, no dependency manifests, no configuration files, no tests, no documentation beyond the master prompt, and no `Project_Specification.md`.
- The master specification defines an ambitious, production-grade, multi-agent AI engineering platform with CAD ingestion, structural analysis software integration (ETABS, SAP2000, SAFE), traceability, validation, optimization, and human-in-the-loop approval workflows.
- Phase 0 deliverables per the user directive: this document only. No code, dependencies, or framework initialization were created or modified.
- A **mandatory Design Code Selection Policy** has been incorporated into this assessment (Section M.1). Key facts: default jurisdiction is **United States (US)**; design codes are **project-scoped and user-controlled**; codes must **never be hard-coded globally or silently changed**.
- A **mandatory Unit System Policy** has been incorporated into this assessment (Section M.2). Key facts: default unit system is **US Customary**; **SI/Metric** is fully supported; unit system is **project-scoped and user-controlled**; must **never be globally hard-coded**; all engineering quantities require explicit unit metadata.
- A **mandatory Default US Code Profile** has been incorporated into this assessment (Section M.3). **AG-30 resolved (2026-08-11):** policy rules 1–28 documented; software defaults **IBC 2024, ASCE 7-22, ACI CODE-318-25, AISC 360-22**; `CodeConfiguration` schema defined (rule 16); no code/CodeEngine implementation in Phase 0 (rules 26–28). **AG-31 updated:** MVP CodeEngine plugin priority aligned to US default profile (M.3.4).
- **Technology stack decisions resolved (2026-08-11):** **AG-32** Python + FastAPI (backend); **AG-33** Next.js + React + TypeScript (frontend); **AG-34** PostgreSQL (database); **AG-35** Git + GitHub (version control). **Not yet implemented** — technology decisions only; Phase 1 not authorized.
- **AI configuration decisions resolved (2026-08-11):** **AG-36** provider-agnostic AI Gateway architecture with Provider Adapter Layer, configurable model routing, external API + local/self-hosted support, fallback capability; **AG-37** hybrid agent orchestration combining deterministic workflow/state-machine control with controlled AI planning/routing. **Not yet implemented** — architectural decisions only; Phase 1 not authorized.
- **External software integration scope resolved (2026-08-11):** **AG-40** CSI products — ETABS 23, SAP2000 27, SAFE 23 (user's available local environment); **AG-41** AutoCAD 2027 with DXF and DWG output formats. Adapter-based Integration Service boundary preserved. **Not yet implemented** — configuration decisions only; Phase 1 not authorized.
- **Agent & platform architecture resolved (2026-08-12):** **AG-42** through **AG-49** — agent extensibility, domain isolation, Agent Registry, Agent Contract, orchestration/collaboration, shared platform services, UnitConversionService, CompatibilityEngine + expanded CodeConfiguration. **Not yet implemented.**
- **Phase 0 Architecture Freeze (2026-08-12):** **AG-01 through AG-75** — all architectural decisions **RESOLVED**. Platform vision, Project Workspace, engineering data architecture (requirements, geometry, materials, calculations, solvers, verification, provenance, assumptions, domain plugins, code intelligence, optimization, change impact, execution safety) documented in Section U. **Documentation only — implementation NOT authorized.**

### ASSUMPTIONS

- The user intends to build the platform described in `MASTER PROMPT V2.md` from scratch within this workspace.
- Development will follow the phased, approval-gated process defined in the specification.
- The target deployment environment is likely **Windows-centric** given CSI software (ETABS/SAP2000/SAFE) COM/OAPI requirements, though this is not explicitly stated in the spec.

### RECOMMENDATIONS (High Level)

- Treat this as a **greenfield architecture** project; no existing code needs preservation.
- **Core technology stack resolved (AG-32–AG-35):** Python + FastAPI backend, Next.js + React + TypeScript frontend, PostgreSQL database, Git + GitHub version control. CSI/CAD integration remains adapter-based via isolated Integration Service (Section L).
- **Phase 0 architecture is FROZEN (AG-01–AG-75).** All architectural decisions recorded. **Implementation NOT STARTED.** Phase 1 requires a **future explicit authorization** beyond this freeze (see AG-53).
- Implement strictly according to the 12-phase roadmap in the master specification, starting with Phase 1 (Foundation) — **only after explicit Phase 1 implementation authorization**.

### Overall Feasibility Verdict

**Technically feasible**, but **high complexity and high integration risk**. The core agent orchestration, domain model, file ingestion, validation, and traceability systems are achievable with modern software engineering practices. The highest-risk areas are: (1) reliable CSI software automation, (2) production-quality editable DWG generation, (3) engineering correctness and multi-jurisdiction code-standard coverage (US, Iranian, Eurocode families), and (4) preventing AI hallucination of engineering results or silent code conflict resolution.

---

## B. Current Repository State

### Directory Inventory


| Path                                 | Type          | Size / Notes                                     |
| ------------------------------------ | ------------- | ------------------------------------------------ |
| `MASTER PROMPT V2.md`                | Specification | ~1,533 lines; complete product/architecture spec |
| `PHASE_0_ARCHITECTURE_ASSESSMENT.md` | Documentation | This file (Phase 0 deliverable)                  |


### What Was Inspected

- Full workspace file glob (all extensions)
- Hidden files and directories (none found)
- Git repository status (**not initialized**)
- `Project_Specification.md` (**not present**)
- Dependency manifests: `package.json`, `pubspec.yaml`, `requirements.txt`, `pyproject.toml`, `*.csproj`, `*.sln` (**none found**)
- Source code directories: `src/`, `lib/`, `app/`, `backend/`, `frontend/` (**none found**)
- Configuration: `.env`, `docker-compose.yml`, CI/CD configs (**none found**)
- Tests: `test/`, `tests/`, `*_test.*` (**none found**)

### Build / Runtime / Dependency Status


| Check                | Result                                 |
| -------------------- | -------------------------------------- |
| Build system         | **N/A** — no buildable artifacts exist |
| Dependencies         | **N/A** — no dependency manifests      |
| Compilation          | **N/A**                                |
| Runtime              | **N/A**                                |
| Tests                | **None**                               |
| CI/CD                | **None**                               |
| Linter configuration | **None**                               |


### Conclusion

The repository is a **specification-only greenfield**. Phase 1 will establish the first application structure, tooling, and persistence layer.

---

## C. Technology Stack

### Current Stack


| Layer                | Technology                                 | Status                                    |
| -------------------- | ------------------------------------------ | ----------------------------------------- |
| Backend              | **Python + FastAPI** (AG-32)               | **Approved — not implemented**            |
| Frontend             | **Next.js + React + TypeScript** (AG-33)   | **Approved — not implemented**            |
| Database             | **PostgreSQL** (AG-34)                     | **Approved — not implemented**            |
| Version control      | **Git + GitHub** (AG-35)                   | **Approved — repository not initialized** |
| AI / LLM integration | **Provider-agnostic AI Gateway** (AG-36)   | **Approved — not implemented**            |
| Agent orchestration  | **Hybrid orchestration** (AG-37)           | **Approved — not implemented**            |
| CAD libraries        | —                                          | **None**                                  |
| CSI integration      | **ETABS 23, SAP2000 27, SAFE 23** (AG-40)  | **Approved — not implemented**            |
| CAD integration      | **AutoCAD 2027; DXF + DWG output** (AG-41) | **Approved — not implemented**            |
| Containerization     | —                                          | **None**                                  |


### Specification Guidance on Technology

The master specification states (Section 34):

> "Use the technologies already present in the repository whenever reasonable."

**FACT:** No technologies are present. Technology selection is entirely open.

The specification also states (Section 26):

> "If the existing application is Flutter, preserve Flutter and improve the existing architecture rather than rewriting everything."

**FACT:** No Flutter application exists. This conditional guidance does not apply.

### Approved Technology Stack (AG-32–AG-35 — RESOLVED)

**Status:** User-approved technology decisions (2026-08-11). **Documentation only — no implementation authorized.**


| AG        | Layer           | Approved Technology              | Implementation Status                                     |
| --------- | --------------- | -------------------------------- | --------------------------------------------------------- |
| **AG-32** | Backend         | **Python + FastAPI**             | Not implemented                                           |
| **AG-33** | Frontend        | **Next.js + React + TypeScript** | Not implemented                                           |
| **AG-34** | Database        | **PostgreSQL**                   | Not implemented (no schemas, migrations, or dependencies) |
| **AG-35** | Version control | **Git + GitHub**                 | Not initialized (no `git init`, commit, or push)          |


**Traceability:** AG-32 through AG-35 were **explicitly approved by the user** on **2026-08-11**. Resolving these items records technology decisions only — it does **NOT** authorize Phase 1 implementation.

#### AG-32 — Backend (Python + FastAPI)

**Rationale:**

- Suitable for AI/agent orchestration
- Strong Python ecosystem for engineering computation and file processing
- Suitable for REST APIs and asynchronous workloads
- Suitable for future integration services and engineering software adapters
- Compatible with future ETABS/SAP2000/SAFE/CAD integration services via isolated Integration Service adapters

**Constraint:** Defines backend technology only. Do **not** implement FastAPI until Phase 1 is explicitly authorized.

#### AG-33 — Frontend (Next.js + React + TypeScript)

**Rationale:**

- Production-grade web application foundation
- Strong TypeScript support
- Suitable for complex engineering dashboards and project workspaces
- Suitable for file upload and project management interfaces
- Suitable for interactive engineering configuration and review workflows
- Suitable for future CAD/model/result visualization interfaces

**Constraint:** Do **not** create the frontend until Phase 1 is explicitly authorized.

#### AG-34 — Database (PostgreSQL)

PostgreSQL is the **primary persistent relational database**. It must eventually support:

- Projects, users, project configuration
- `CodeConfiguration`, `UnitConfiguration`
- `ProjectEngineeringModel` metadata
- File metadata, document/version metadata
- Agent execution metadata, audit/traceability metadata
- Engineering assumptions, decision records, revision history

**Constraints:** Do **not** create database schemas, migrations, install PostgreSQL dependencies, or implement database access until Phase 1 is explicitly authorized.

#### AG-35 — Version Control (Git + GitHub)

**Approved:** Git for version control; GitHub for repository hosting.

**Distinction:** AG-35 is an approved technology/process decision. Git repository initialization is **deferred** — do **not** run `git init`, `git add`, `git commit`, or `git push` until Phase 1 is explicitly authorized.

#### Architectural Consistency (Technology Decisions)

These technology decisions are **compatible** with the previously approved Phase 0 architecture. No architectural redesign is required:


| Architectural Principle                                   | Compatibility                                                                          |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `ProjectEngineeringModel` (PEM) as Single Source of Truth | PostgreSQL stores PEM metadata and snapshots; FastAPI serves PEM via REST              |
| `CodeConfiguration` as first-class PEM entity             | Stored in PEM (JSONB) with PostgreSQL metadata and revision linkage                    |
| `UnitConfiguration` as first-class PEM entity             | Same as CodeConfiguration                                                              |
| Agents communicate indirectly through PEM                 | FastAPI orchestration layer; agents read/write PEM, not each other directly            |
| Integration Service isolated from core domain             | Python FastAPI core; CSI/CAD adapters remain separate services (Section L)             |
| CSI/CAD integrations adapter-based                        | Adapter pattern unchanged; future Windows COM adapters may run as separate processes   |
| `CodeEngine` modular                                      | Python plugin architecture within FastAPI backend                                      |
| `CompatibilityEngine` modular                             | Independent service/module within backend                                              |
| `UnitConversionService` modular                           | Independent service/module within backend                                              |
| Extensible for future engineering software integrations   | Adapter + plugin model preserved                                                       |
| Phase 0 policies (M.1, M.2, M.3)                          | No technology decision violates existing policies                                      |
| Provider-agnostic AI (AG-36)                              | AI Gateway + Provider Adapter Layer; agents isolated from providers                    |
| Hybrid orchestration (AG-37)                              | Deterministic workflow state machine + bounded AI planning; PEM-mediated collaboration |


### Historical Stack Options (Pre-Decision Analysis — Superseded by AG-32–AG-35)

The following options were evaluated during Phase 0 assessment. **AG-32–AG-35 supersede these recommendations:**


| Layer            | Option A                                            | Option B                                 | Option C                                                     |
| ---------------- | --------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------ |
| Backend core     | **Python 3.12+** (FastAPI) — strong AI/ML ecosystem | **C# / .NET 8** — native CSI COM interop | **Hybrid**: Python agent layer + C# integration microservice |
| Frontend         | **Flutter** (matches spec UI mention)               | **React/Next.js** — rich web UI          | **Flutter + Web** via Flutter Web                            |
| Database         | **PostgreSQL** — production multi-user              | **SQLite** — local single-user MVP       | **PostgreSQL + Redis** — persistence + cache/queue           |
| AI orchestration | **Custom AgentOrchestrator** + tool registry        | LangGraph / similar framework            | Cursor SDK / external agent runtime                          |
| File storage     | Local filesystem with project isolation             | S3-compatible object storage             | Hybrid local + cloud                                         |
| Message/queue    | In-process (Phase 1–4) → Redis/RabbitMQ (later)     | —                                        | —                                                            |


**Note:** Option C (hybrid Python + C# integration microservice) remains architecturally valid for CSI COM adapters via isolated Integration Service. AG-32 selects **Python + FastAPI** as the **core backend**; adapter isolation is unchanged.

---

## D. Existing Components

### Application Components

**None.** No modules, services, agents, adapters, UI screens, or domain models exist.

### Infrastructure Components

**None.** No Docker, CI, logging framework, or deployment scripts.

### Documentation


| Document                     | Status                                                       |
| ---------------------------- | ------------------------------------------------------------ |
| `MASTER PROMPT V2.md`        | Present — authoritative                                      |
| `Project_Specification.md`   | Missing (referenced in spec Section 33)                      |
| `ARCHITECTURE_ASSESSMENT.md` | Not created (superseded by this document per user directive) |
| `IMPLEMENTATION_ROADMAP.md`  | Not created (content merged into Section S of this document) |
| Phase reports                | None                                                         |


### Integrations


| Integration          | Status      |
| -------------------- | ----------- |
| ETABS                | Not present |
| SAP2000              | Not present |
| SAFE                 | Not present |
| AutoCAD / DWG / DXF  | Not present |
| PDF / Excel / Office | Not present |
| LLM provider         | Not present |


---

## E. Missing Components

Everything required by the specification is missing. Grouped by master-spec module:

### Core Platform (Phase 1)

- [ ] Project structure and solution layout
- [ ] `ProjectEngineeringModel` domain model (including `CodeConfiguration`, `UnitConfiguration`)
- [ ] Project management (CRUD, metadata)
- [ ] File management (upload registry, metadata)
- [ ] Persistence layer (database + repositories)
- [ ] Configuration system
- [ ] Logging framework
- [ ] Error handling conventions
- [ ] Unit test infrastructure

### File Ingestion (Phase 2)

- [ ] Unified ingestion pipeline
- [ ] File type detection
- [ ] Parser interfaces (`DWGAdapter`, `DXFAdapter`, `PDFAdapter`, `ExcelAdapter`)
- [ ] Extraction and normalization pipeline
- [ ] Source tracking and confidence metadata

### Project Memory (Phase 3)

- [ ] Persistent project-scoped memory
- [ ] Document indexing
- [ ] Decision / assumption / rejection history
- [ ] Memory retrieval for agent context

### Agent Framework (Phase 4)

- [ ] Agent interface and base classes
- [ ] `AgentOrchestrator`
- [ ] Tool registry with JSON schemas
- [ ] Permission system
- [ ] Agent state management
- [ ] Agent activity log (user-visible, no chain-of-thought)
- [ ] Human approval gate framework

### Specialized Agents (Phases 5–6)

- [ ] Architecture Agent
- [ ] Structural Engineering Agent
- [ ] Engineering Validation Agent
- [ ] Optimization Agent
- [ ] Documentation Agent

### Engineering Engines

- [ ] `ValidationEngine` (including code conflict detection)
- [ ] `CodeEngine` (modular, multi-jurisdiction plugin architecture)
- [ ] `CodeConfiguration` management (project-scoped, revision-tracked)
- [ ] `UnitConfiguration` management (project-scoped, user-controlled)
- [ ] Unit conversion service (deterministic, loss-controlled, traceable)
- [ ] Dimensional consistency validation (force, moment, length, stress unit families)
- [ ] Code change impact analysis and recalculation trigger service
- [ ] `CompatibilityEngine` (edition mismatch detection, reference relationship modeling)
- [ ] Code profile type management (Software Default, Project Selected, Jurisdictionally Adopted, Supplementary, Historical/Legacy)
- [ ] `NEWER_EDITION_AVAILABLE` notification (non-migrating)
- [ ] Historical code profile retention for legacy project evaluation
- [ ] Pre-design code disclosure workflow
- [ ] `OptimizationEngine`

### External Adapters (Phases 7–8)

- [ ] `ETABSAdapter`
- [ ] `SAP2000Adapter`
- [ ] `SAFEAdapter`
- [ ] `AutoCADAdapter` / CAD abstraction
- [ ] `OfficeAdapter`

### Output Generation (Phase 10)

- [ ] Report generation (DOCX, PDF, XLSX, CSV)
- [ ] Drawing generation pipeline
- [ ] Schedule generation

### Cross-Cutting

- [ ] Traceability chain storage and UI
- [ ] Revision management (version, compare, restore, undo/redo; **incl. CodeConfiguration changes**)
- [ ] Security layer (tool permission enforcement)
- [ ] User interface (Dashboard and all spec screens)
- [ ] End-to-end integration tests (Phase 11)
- [ ] Production hardening (Phase 12)

---

## F. Proposed System Architecture

Based on the master specification (Sections 2, 11, 23–25). This describes the **target architecture**, not current state.

```text
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│  Dashboard | Projects | Agents | Files | Architecture |        │
│  Structure | ETABS | SAP2000 | SAFE | CAD | Design | Validation |       │
│  Design Standards / Code Config | Reports | Revisions | Settings      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS / WebSocket
┌──────────────────────────▼──────────────────────────────────────┐
│                      API / APPLICATION LAYER                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   AgentOrchestrator                       │   │
│  │  • Route tasks to agents                                  │   │
│  │  • Manage approval gates                                  │   │
│  │  • Coordinate tool execution                              │   │
│  │  • Never direct OS/file access from LLM                   │   │
│  └────────────┬────────────────────────────────────────────┘   │
│               │                                                  │
│  ┌────────────▼──────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  Specialized Agents    │  │ Tool Registry │  │  Approval   │  │
│  │  • Architecture        │  │ (schema-valid │  │  Gate Mgr   │  │
│  │  • Structural          │  │  permissions) │  │             │  │
│  │  • Validation          │  └──────────────┘  └─────────────┘  │
│  │  • Optimization        │                                       │
│  │  • Documentation       │                                       │
│  └────────────┬───────────┘                                       │
└───────────────┼───────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────┐
│                     DOMAIN / ENGINE LAYER                          │
│  ┌──────────────────┐ ┌─────────────┐ ┌──────────────────────┐  │
│  │ ProjectEngineering│ │ Validation  │ │ CodeEngine           │  │
│  │ Model (SSOT)      │ │ Engine      │ │ (multi-standard)     │  │
│  └──────────────────┘ └─────────────┘ └──────────────────────┘  │
│  ┌──────────────────┐ ┌─────────────┐ ┌──────────────────────┐  │
│  │ Optimization     │ │ Revision    │ │ Traceability         │  │
│  │ Engine           │ │ Manager     │ │ Service              │  │
│  └──────────────────┘ └─────────────┘ └──────────────────────┘  │
└───────────────┬───────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────┐
│                   INTEGRATION ADAPTER LAYER                        │
│  ┌────────┐ ┌─────────┐ ┌──────┐ ┌─────────┐ ┌──────┐ ┌───────┐ │
│  │ ETABS  │ │ SAP2000 │ │ SAFE │ │ DWG/DXF │ │ PDF  │ │ Excel │ │
│  │Adapter │ │ Adapter │ │Adapt.│ │ Adapter │ │Adapt.│ │Adapt. │ │
│  └────┬───┘ └────┬────┘ └──┬───┘ └────┬────┘ └──┬───┘ └───┬───┘ │
└───────┼──────────┼─────────┼──────────┼─────────┼─────────┼─────┘
        │          │         │          │         │         │
┌───────▼──────────▼─────────▼──────────▼─────────▼─────────▼─────┐
│              EXTERNAL SOFTWARE / FILE SYSTEM                       │
│  ETABS.exe | SAP2000.exe | SAFE.exe | AutoCAD | Filesystem        │
└───────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     PERSISTENCE LAYER                            │
│  Database (projects, PEM, revisions, memory) | File Storage      │
└─────────────────────────────────────────────────────────────────┘
```

### Key Architectural Principles (from spec)

1. **Single Source of Truth:** `ProjectEngineeringModel` centralizes all project data.
2. **Adapter isolation:** Core domain never depends directly on CSI or CAD vendor APIs.
3. **Tool-gated execution:** LLM → validated tool → permission check → controlled execution.
4. **No silent assumptions:** Critical missing data triggers user questions, not silent defaults.
5. **No fabricated results:** Mock adapters must be explicitly labeled; unavailable integrations report `INTEGRATION_UNAVAILABLE`.
6. **Human-in-the-loop:** Major engineering decisions require explicit user approval.
7. **Project-scoped code configuration:** Design codes are user-controlled per project, default to US jurisdiction, and are never hard-coded globally or silently changed (Section M.1).
8. **Project-scoped unit system:** Unit system is user-controlled per project, defaults to US Customary, supports SI/Metric fully, and is never globally hard-coded (Section M.2).
9. **Provider-agnostic AI:** Agents never communicate directly with LLM providers; all model access routed through AI Gateway (Section G.1, AG-36).
10. **Hybrid orchestration:** Engineering-critical workflows controlled by deterministic state machine; AI assists planning/routing within explicit boundaries only (Section G.2, AG-37).
11. **Agent extensibility:** Two agents in initial implementation scope; platform core must support future agents via registry/contract-based extension (Section G.6, AG-42).

---

## G. Agent Architecture

### G.1 AI Gateway Architecture (AG-36 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-11). **Documentation only — not implemented.**

**Decision:** Provider-agnostic LLM architecture with AI Gateway and Provider Adapter Layer.

#### Architectural Principle

**Agents MUST NOT communicate directly with a specific LLM provider.**

All LLM access is routed through the AI Gateway:

```text
User / Application
        ↓
   AI Gateway
        ↓
 Provider Adapter Layer
        ↓
 Selected LLM Provider / Local Model
```

#### AI Gateway Responsibilities


| Capability                          | Description                                                                                               |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Provider Adapter Layer**          | Isolates provider-specific APIs from domain agents                                                        |
| **Configurable model routing**      | Route requests to appropriate model by task type, capability, or policy                                   |
| **Provider-specific configuration** | Configuration isolated from agents; agents reference capabilities, not providers                          |
| **Fallback capability**             | Degrade or reroute when primary provider unavailable, restricted, or rate-limited                         |
| **External API providers**          | Support commercial cloud LLM APIs                                                                         |
| **Local/self-hosted models**        | Support on-premises or local inference endpoints                                                          |
| **Vision-capable routing**          | Route document/drawing analysis to vision-capable models where appropriate                                |
| **Reasoning-capable routing**       | Route complex engineering analysis to reasoning-capable models where appropriate                          |
| **Secrets management**              | API keys and credentials via secure configuration/environment mechanisms — **never hard-coded in source** |


#### Operational Adaptability Requirements

The architecture must **NOT** depend on a single provider. The platform must remain operationally adaptable when:

- An external provider is unavailable
- Access is restricted by deployment environment or policy
- Rate limits are encountered
- A provider is replaced or deprecated

**No final production model is selected or hard-coded** unless separately approved.

#### Future Scenarios Supported

- External commercial LLM APIs
- Alternative LLM providers
- Self-hosted/local models
- Provider fallback chains
- Task-type-based model routing (extraction, classification, reasoning, vision)
- Provider or model change **without modifying domain agents**

### G.2 Hybrid Agent Orchestration (AG-37 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-11). **Documentation only — not implemented.**

**Decision:** Hybrid agent orchestration combining deterministic workflow control with controlled AI assistance.

#### Orchestration Model


| Layer                                      | Control Type      | Scope                                                                                |
| ------------------------------------------ | ----------------- | ------------------------------------------------------------------------------------ |
| **Deterministic workflow / state machine** | Hard control      | Engineering-critical workflows                                                       |
| **AI-driven planning / routing**           | Assisted, bounded | Task interpretation, prioritization, decomposition — within explicit boundaries only |


**Engineering-critical steps MUST NOT depend on unrestricted autonomous AI behavior.**

AI may assist with planning, interpretation, routing, prioritization, and task decomposition, but **MUST NOT silently bypass** mandatory engineering workflow stages.

#### Orchestrator Enforcement Requirements

The orchestrator must enforce:

- Workflow state
- Required inputs and preconditions
- Required approvals and postconditions
- Validation gates
- Error handling and retry policy
- Human approval gates where required
- Traceability, versioning, and audit history

#### Updated Orchestration Flow

```text
User Request
     ↓
AgentOrchestrator (Hybrid — AG-37)
     ├─ 0. Load PEM + workflow state (authoritative context)
     ├─ 1. Evaluate workflow state machine — determine permitted next steps
     ├─ 2. AI-assisted planning/routing (bounded; via AI Gateway — AG-36)
     ├─ 3. Assess ProjectEngineeringModel state; identify missing/ambiguous data
     ├─ 3a. Enforce CodeConfiguration as engineering constraint (Section M.1)
     ├─ 4. Select agent(s) via Agent Registry + Contract (AG-44, AG-45) and tool(s) — within workflow boundaries only
     ├─ 5. Execute via tool registry (schema-validated)
     ├─ 6. Run ValidationEngine (independent when possible)
     ├─ 7. Check approval requirements — block if gate not satisfied
     ├─ 8. Update ProjectEngineeringModel + Memory + Revisions
     └─ 9. Emit agent activity log (concise, no chain-of-thought)
```

### G.3 Agent Collaboration Model (Preserved — AG-37)

**FACT (previously approved, preserved):** Agents **MUST NOT** communicate through uncontrolled direct agent-to-agent calls.

Agents collaborate indirectly through:

1. `**ProjectEngineeringModel` (PEM)** — structured engineering data (Single Source of Truth)
2. **Controlled orchestration / workflow state** — deterministic state machine
3. **Traceable events and results** — audit log, revisions, activity records

#### Conceptual Agent Roles (Not Yet Implemented)

**AG-42 scope:** Initial implementation targets **two agents only**. The roles below include both initial-scope and **future extension-point** roles — only the two initial agents are in scope for implementation; others are architectural placeholders only.

The architecture supports specialized agents as **conceptual roles**:


| Conceptual Role                  | Primary Concern                                             |
| -------------------------------- | ----------------------------------------------------------- |
| **Architecture Agent**           | Architectural model, space planning, layout                 |
| **Structural Engineering Agent** | Structural systems, analysis, design                        |
| **Code/Standards Agent**         | Code configuration, standards interpretation, compatibility |
| **Document/File Agent**          | File ingestion, extraction, document processing             |
| **QA/Verification Agent**        | Independent validation, verification, review                |


These map to the agent roster in spec Section 3 (Architecture, Structural, Validation, Documentation agents) and may be refined during implementation. **Do not implement agents until Phase 1+ authorization.**

### G.4 PEM Relationship and Agent Output Traceability (AG-37)

**FACT (preserved):** `ProjectEngineeringModel` (PEM) = **Single Source of Truth**.

The orchestrator must use the PEM and versioned project state as the **authoritative engineering context**.

Agent outputs must eventually be:


| Attribute                  | Requirement                                                                      |
| -------------------------- | -------------------------------------------------------------------------------- |
| Agent attribution          | Which agent produced the output                                                  |
| Model/provider attribution | Which model/provider was used (where applicable)                                 |
| Versioning                 | Linked to PEM snapshot / revision                                                |
| Traceability               | Linked to inputs, assumptions, and workflow step                                 |
| Project state association  | Reflects project state at time of generation                                     |
| Assumption linkage         | Associated with relevant assumptions                                             |
| Result classification      | Distinguishable: **AI-generated suggestion** vs. **verified engineering result** |


### G.5 Engineering Safety Principle (AG-37)

**FACT:** The AI orchestration layer must **never** be treated as the engineering calculation engine.


| AI May               | AI Must NOT                                                   |
| -------------------- | ------------------------------------------------------------- |
| Interpret            | Fabricate engineering results                                 |
| Plan and route tasks | Perform deterministic code checks (CodeEngine responsibility) |
| Suggest and classify | Replace validated calculation engines                         |
| Extract and explain  | Bypass verification workflows                                 |
| Decompose tasks      | Silently invent critical engineering parameters               |


Engineering calculations and verification must eventually rely on:

- Deterministic engineering services
- Validated calculation engines
- Approved `CodeEngine` implementations
- Approved external engineering software adapters (CSI, CAD)
- Explicit verification workflows

#### Missing or Ambiguous Information Handling

If required information is missing or ambiguous, the workflow must:

1. **Identify** the missing information
2. **Record** the uncertainty in project state / memory
3. **Request clarification** when required
4. **Apply only explicitly permitted assumptions** (user-approved)
5. **Never silently invent** critical engineering parameters

### G.6 Agent Extensibility Architecture (AG-42 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-12). **Documentation only — not implemented.**

**Decision:** The platform shall initially implement **ONLY TWO agents**. The agent architecture must remain **extensible** so additional engineering-domain agents can be added later **without rewriting the platform core**.

#### Current vs. Future Scope

| Scope | Description |
|-------|-------------|
| **Current implementation target** | **Two agents only** |
| **Future architectural capability** | Up to **~20 agents or more** without core rewrite (AG-55) |
| **Phase 0 / now** | Extension points documented only — **no future agents implemented** |

**Goal:** *Two agents now, extensible architecture for future agents.*

#### Stable Extension Points (Conceptual — Not Implemented)

The architecture defines stable extension points for:

- **Agent Registry** (AG-44)
- **Agent Contract / Interface** (AG-45)
- **Agent Orchestrator** (AG-37, AG-46)
- **Agent Capabilities**
- **Agent versioning**
- **Agent input/output contracts**
- **Agent execution policy**
- **Agent-to-platform service access** (AG-47)
- **Agent lifecycle and registration**

#### Extensibility Rules

| # | Rule | Type |
|---|------|------|
| 1 | Platform must **NOT** be designed around a fixed number of agents | FACT |
| 2 | Core platform must **NOT** contain hard-coded logic assuming only the current two agents will ever exist | FACT |
| 3 | Future agents are **architectural extension points only** — not implemented in Phase 0 | FACT |
| 4 | Do **NOT** create placeholder implementations for hypothetical future agents | FACT |
| 5 | Do **NOT** add unnecessary complexity solely for hypothetical future agents | FACT |

#### Potential Future Domains (Extension Points Only — Not Implemented)

Mechanical Engineering, Electrical Engineering, Computer Engineering, Industrial Engineering, and other engineering disciplines may be supported in future via Agent Registry and Agent Contract — **do not create these agents now**.

### G.7 Agent Boundaries and Domain Isolation (AG-43 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-12). **Documentation only — not implemented.**

**Decision:** Each agent must maintain **clear domain boundaries**.

| # | Rule | Type |
|---|------|------|
| 1 | Agent-specific engineering logic remains **inside the corresponding agent/domain boundary** | FACT |
| 2 | Agents must **not duplicate** shared platform services unnecessarily | FACT |
| 3 | Shared capabilities remain at **platform/service level** where appropriate (AG-47) | FACT |
| 4 | Multiple engineering-domain agents may use **common infrastructure** without coupling domain logic | FACT |
| 5 | Architecture must **avoid** a monolithic "super-agent" containing all engineering disciplines | FACT |
| 6 | Initial two-agent scope remains the **only implementation scope** for now | FACT |

### G.8 Agent Registry (AG-44 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-12). **Documentation only — not implemented.**

**Decision:** Agent discovery and selection use **registry/contract-based mechanisms** rather than hard-coded agent-specific branching.

#### Agent Registry Responsibilities

The Agent Registry maintains available agent definitions and metadata.

#### Conceptual Agent Registry Entry

```text
AgentRegistryEntry
├── agent_id: string
├── name: string
├── version: string
├── capabilities: Capability[]
├── supported_task_types: TaskType[]
├── input_contract: ContractSchema
├── output_contract: ContractSchema
├── status: enum [REGISTERED, ACTIVE, DEPRECATED, DISABLED]
├── required_tools: string[]
├── required_services: string[]          ← e.g., PEM, ValidationEngine, AI Gateway
└── configuration_metadata: object
```

**Constraint:** Do **not** implement the registry until Phase 4+ authorization.

### G.9 Agent Contract / Interface (AG-45 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-12). **Documentation only — not implemented.**

**Decision:** Each agent exposes a **stable, domain-neutral** conceptual contract.

#### Agent Contract Responsibilities

| Operation | Description |
|-----------|-------------|
| Receive validated task/context | Accept orchestrator-provided, schema-validated input |
| Declare capabilities | Expose supported task types and constraints |
| Access authorized platform services | Consume shared services via defined boundaries only (AG-47) |
| Produce structured outputs | Return schema-validated results for PEM integration |
| Report execution status | Progress, completion, cancellation |
| Report errors/warnings | Structured error codes; no silent failures |
| Provide traceability metadata | Agent ID, model/provider (if applicable), revision linkage |

#### Domain Neutrality Requirement

The contract must **not** embed Structural Engineering-specific assumptions that would prevent future Mechanical, Electrical, Computer, Industrial, or other engineering agents from using the platform.

**Constraint:** Do **not** implement the interface until Phase 4+ authorization.

### G.10 Agent Orchestration and Collaboration (AG-46 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-12). **Extends AG-37.** **Documentation only — not implemented.**

**Decision:** Preserve and extend **Hybrid Agent Orchestration** (G.2, AG-37).

| Mechanism | Role |
|-----------|------|
| **Deterministic workflow / state machine** | Engineering-critical workflows — hard control |
| **Bounded AI planning/routing** | Task interpretation, prioritization, decomposition — within explicit boundaries |
| **PEM-mediated collaboration** | Agents collaborate through PEM, not direct calls |
| **Validation and approval gates** | Mandatory; AI must not bypass |
| **Engineering safety principle** | AI is **not** the calculation engine (G.5) |

#### Collaboration Rules

- Agents **MUST NOT** directly call other agents.
- Collaboration occurs through **ProjectEngineeringModel (PEM)** and/or **controlled orchestration mechanisms**.
- Orchestrator must route work between the **current two agents** and **future agents** without changing core orchestration architecture.
- Agent selection uses **Agent Registry + Agent Contract** (AG-44, AG-45), not hard-coded branching.

**Constraint:** Do **not** implement orchestration until Phase 4+ authorization.

### G.11 Shared Platform Services and Agent Access (AG-47 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-12). **Documentation only — not implemented.**

**Decision:** Agents consume shared platform services through **defined service boundaries**.

#### Shared Platform Services

| Service | Role |
|---------|------|
| **ProjectEngineeringModel (PEM)** | Single Source of Truth; structured engineering context |
| **Project Memory** | Decisions, context, history |
| **CodeEngine** | Deterministic code checks (plugin-based) |
| **CompatibilityEngine** | Configuration/code compatibility (AG-49) — not a calculation engine |
| **UnitConversionService** | Deterministic unit conversion (AG-48) |
| **ValidationEngine** | Independent validation across categories |
| **AI Gateway** | Provider-agnostic LLM access (AG-36) |
| **File / Artifact services** | Upload, storage, ingestion metadata |
| **Integration Service** | CSI/CAD/external software adapters (Section L, AG-40, AG-41) |

#### Access Rules

| # | Rule | Type |
|---|------|------|
| 1 | Agent-specific logic must **not reimplement** shared services without explicit architectural reason | FACT |
| 2 | External engineering software integrations remain **isolated behind adapter/service boundaries** | FACT |
| 3 | Agents must **not** directly couple core domain to ETABS, SAP2000, SAFE, AutoCAD, or specific vendors | FACT |
| 4 | Unit conversion logic must **not** be duplicated inside agents (AG-48) | FACT |

**Constraint:** Do **not** implement any shared service until authorized by phase.

### G.12 UnitConversionService Architecture (AG-48 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-12). **Documentation only — not implemented.**

**Decision:** `UnitConversionService` is an **independent platform service** (see also M.2.5).

#### Responsibilities

- Deterministic unit conversion
- Dimensional consistency checking
- Explicit unit metadata handling
- Safe conversion between supported unit systems
- Prevention/detection of invalid dimensional operations

#### Independence Rules

| # | Rule | Type |
|---|------|------|
| 1 | Unit conversion logic must **not** be duplicated independently inside agents | FACT |
| 2 | Service must remain **independent** from individual engineering agents | FACT |
| 3 | Existing **Unit System Policy** (Section M.2) remains authoritative | FACT |
| 4 | Project-scoped unit configuration and **canonical storage principles** preserved (AG-12–AG-16) | FACT |

**Constraint:** Do **not** implement UnitConversionService until later phase authorization.

### G.13 CompatibilityEngine and Expanded CodeConfiguration (AG-49 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-12). **Documentation only — not implemented.**

#### CompatibilityEngine

**Decision:** `CompatibilityEngine` is an **independent platform-level service**.

**Responsibility:** Determine whether project configurations, engineering configurations, and selected codes/standards are **compatible**.

May evaluate compatibility involving, where applicable:

- Code family, code name, code version
- Jurisdiction, design method, unit system
- Materials, sections, load/combination configuration
- Supported features, project configuration constraints
- External software compatibility metadata

#### Compatibility Result Categories (Conceptual)

| Result | Meaning |
|--------|---------|
| **compatible** | Configuration passes compatibility rules |
| **incompatible** | Configuration violates compatibility rules |
| **warning** | Potential issue requiring review |

Each result must be **explainable** and **traceable** to an explicit rule or compatibility condition.

#### CompatibilityEngine Boundaries

| CompatibilityEngine IS | CompatibilityEngine IS NOT |
|------------------------|----------------------------|
| Deterministic compatibility evaluator | Engineering design calculation engine |
| Traceable rule-based checker | Structural design calculator |
| Edition/reference mismatch detector | CodeEngine substitute |

#### Expanded CodeConfiguration (Extensible Schema)

Extends Section H and M.3.1.2. Where applicable, `CodeConfiguration` conceptually includes:

```text
CodeConfiguration (AG-49 extensions — additive to Section H schema)
├── codeFamily: string | null
├── codeName: string | null
├── version: string | null                    ← aligns with governing_code_edition / role editions
├── jurisdiction: ...                         ← existing
├── designMethod: string | null
├── unitSystem: UnitSystemReference | null  ← links to UnitConfiguration
├── enabledFeatures: FeatureFlag[]
├── requiredInputs: RequiredInput[]
├── compatibility_metadata: CompatibilityMetadata
├── compatibility_rules: CompatibilityRule[]  ← separated from calculation rules
└── revision/history: ...                     ← via revision_id, CodeConfigurationRevision
```

#### CodeConfiguration Requirements (AG-49)

| # | Requirement | Type |
|---|-------------|------|
| 1 | Remains **project-scoped** | FACT |
| 2 | Remains **version-aware** | FACT |
| 3 | Remains **extensible** | FACT |
| 4 | Remains **traceable** | FACT |
| 5 | Adding a new supported code must **not** require rewriting platform core | FACT |
| 6 | Compatibility rules **separated** from engineering calculation rules | FACT |

**Constraint:** Do **not** implement CompatibilityEngine or expanded schema runtime until later phase authorization.

### G.14 Architectural Boundaries Summary (AG-42–AG-49)

| Component | Boundary |
|-----------|----------|
| **AI Gateway** (AG-36) | Provider-agnostic; no provider hard-coding in agents; no API keys in source |
| **Agent Orchestration** (AG-37, AG-46) | Hybrid orchestration; deterministic workflow + bounded AI routing |
| **PEM** | Central project engineering context and collaboration/traceability mechanism |
| **UnitConversionService** (AG-48) | Independent deterministic service |
| **CompatibilityEngine** (AG-49) | Independent compatibility service — **NOT** a calculation engine |
| **External software** (AG-40, AG-41) | Isolated through Integration Service / adapter boundaries |
| **Agents** (AG-42, AG-43) | Domain-specific; extensible; no direct agent-to-agent calls |
| **Platform Core** (AG-42) | Must not depend on a fixed number of agents |

### Agent Roster (from spec Section 3)


| Agent                            | Primary Inputs                                                     | Primary Outputs                                              | Approval Gates                                                                                             |
| -------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| **Architecture Agent**           | Requirements, DWG/DXF/PDF/images                                   | Architectural model, ambiguity reports, alternatives         | Model approval before structural handoff                                                                   |
| **Structural Engineering Agent** | Approved architectural model, **project CodeConfiguration**, loads | Structural system proposals, analysis models, design results | System selection, major parameter changes; **must not begin design until code configuration is confirmed** |
| **Engineering Validation Agent** | Any agent output, **CodeConfiguration conflicts**                  | PASS/WARNING/ERROR/REQUIRES_ENGINEER_REVIEW                  | Independent from generating agent                                                                          |
| **Optimization Agent**           | Design results, constraints                                        | Alternatives with comparison metrics                         | Before applying major optimizations                                                                        |
| **Documentation Agent**          | All approved project data                                          | Reports, schedules, indexes, revision docs                   | Report release approval                                                                                    |


### Orchestration Flow

See **G.2 Hybrid Agent Orchestration (AG-37)** for the authoritative orchestration flow.

### Tool Architecture (from spec Section 24)

Every tool requires:

- Input schema (JSON Schema or equivalent)
- Output schema
- Pre-execution validation
- Error handling with structured error codes
- Audit logging
- Permission declaration

Example tool categories:

- **Project:** `read_project`, `create_project`
- **File:** `read_file`, `parse_dwg`, `parse_dxf`, `parse_pdf`, `parse_excel`
- **Architecture:** `create_architectural_model`, `validate_architectural_model`
- **Structure:** `propose_structural_system`, `create_structural_model`, `validate_structural_model`
- **CSI:** `create_etabs_model`, `run_etabs_analysis`, `read_etabs_results` (and SAP2000/SAFE equivalents)
- **CAD:** `create_cad_drawing`, `modify_cad_drawing`
- **Engineering:** `get_code_configuration`, `set_code_configuration`, `validate_code_configuration`, `analyze_code_change_impact`, `get_unit_configuration`, `set_unit_configuration`, `convert_units`, `run_code_check`, `optimize_design`, `validate_design`
- **Output:** `generate_report`, `generate_schedule`, `compare_revisions`

### RECOMMENDATION: Agent Communication Pattern

**FACT (AG-37, preserved):** Agents should **not communicate directly with each other**. All collaboration occurs through:

1. `ProjectEngineeringModel` (structured data — SSOT)
2. Project Memory (decisions, context)
3. AgentOrchestrator (controlled workflow state + bounded AI routing)
4. AI Gateway (all LLM access — AG-36)

This prevents circular dependencies and ensures traceability.

### AI Behavior Constraints (Design Code Policy)

Per Section M.1, agents must:

- Treat the user's selected `CodeConfiguration` as a **hard engineering constraint**, not a suggestion.
- **Never silently change** the user's selected code configuration.
- **Ask for clarification** when project information is insufficient to determine a required code parameter.
- **Never silently resolve** conflicts between selected standards; escalate to user/engineer.

---

## H. ProjectEngineeringModel

The central domain model (spec Section 4). This is the **most critical data structure** in the platform.

### Proposed Top-Level Schema

```text
ProjectEngineeringModel
├── id: UUID
├── metadata: ProjectMetadata
├── requirements: Requirements
├── architecture: ArchitecturalModel
│   ├── geometry: GeometryCollection
│   ├── levels: Level[]
│   ├── grids: Grid[]
│   ├── rooms: Room[]
│   ├── walls: Wall[]
│   ├── openings: Opening[]
│   └── constraints: Constraint[]
├── structural_system: StructuralSystem
│   ├── materials: Material[]
│   ├── sections: Section[]
│   ├── members: Member[]
│   ├── loads: Load[]
│   ├── load_combinations: LoadCombination[]
│   └── foundations: Foundation[]
├── analysis_models: AnalysisModel[]
├── design_results: DesignResult[]
├── code_configuration: CodeConfiguration   ← project-scoped, user-controlled (Section M.1)
├── unit_configuration: UnitConfiguration     ← project-scoped, user-controlled (Section M.2)
├── codes: CodeReference[]                  ← traceability records per calculation/check
├── drawings: Drawing[]
├── documents: Document[]
├── quantities: Quantity[]
├── validation_results: ValidationResult[]
├── optimization_results: OptimizationResult[]
├── decisions: Decision[]
├── assumptions: Assumption[]
├── revisions: Revision[]
└── traceability: TraceabilityLink[]
```

### Parameter Metadata (every important value)

```text
ParameterMetadata
├── name: string
├── value: any                                    ← canonical stored value (physical quantity)
├── dimension: enum [LENGTH, FORCE, MOMENT, STRESS, AREA, VOLUME, ...]  ← physical dimension (Section M.2)
├── unit: string                                  ← unit of stored value; required for engineering quantities
├── display_unit: string | null                   ← UI display unit if different from stored unit
├── source: enum [USER_INPUT, UPLOADED_FILE, EXTRACTED, CODE, CALCULATED, ASSUMED, OPTIMIZED, IMPORTED_MODEL]
├── source_file: string | null
├── confidence: float (0.0–1.0)
├── status: enum [KNOWN, ASSUMED, UNCERTAIN, CRITICAL_MISSING]
├── created_at: datetime
├── updated_at: datetime
├── author: string (user | agent_id)
└── derivation: string | null (human-readable provenance)
```

**FACT (user-mandated, Section M.2):** Every engineering quantity must have an **unambiguous physical dimension and unit**. The internal PEM stores the canonical physical value; changing display/input units must **not** alter the underlying engineering value.

### RECOMMENDATIONS

1. Implement PEM as **versioned, immutable snapshots** — each revision creates a new snapshot rather than mutating in place.
2. Use a **document-store-friendly schema** (JSON/BSON) for flexibility, with indexed relational tables for queries.
3. Define a **PEM JSON Schema** early in Phase 1 as the contract between all modules.
4. All agents read/write PEM through a **repository service**, never directly.
5. `CodeConfiguration` is a **first-class PEM entity**, versioned in revision history, visible and editable in the UI.
6. `UnitConfiguration` is a **first-class PEM entity**, versioned in revision history, always visible in the UI.

### CodeConfiguration Entity (Mandatory)

```text
CodeConfiguration
├── profile_type: enum [
│       SOFTWARE_DEFAULT,              ← platform out-of-box defaults (Section M.3)
│       PROJECT_SELECTED,              ← user-confirmed project configuration
│       JURISDICTIONALLY_ADOPTED,      ← state/local legally adopted code
│       SUPPLEMENTARY,                  ← supplementary/referenced standards
│       HISTORICAL_LEGACY               ← frozen profile for legacy project evaluation
│   ]
├── jurisdiction: enum [US, IRAN, EU, ...]           ← default: US
├── project_location: LocationReference | null      ← state/local when user provides
├── governing_building_code: StandardReference      ← e.g., IBC 2024
├── governing_code_edition: string                    ← explicit edition
├── loading_standard: StandardReference               ← e.g., ASCE/SEI 7-22
├── loading_edition: string
├── seismic_standard: StandardReference | null
├── seismic_edition: string | null
├── concrete_standard: StandardReference              ← e.g., ACI CODE-318-25
├── concrete_edition: string
├── steel_standard: StandardReference                 ← e.g., ANSI/AISC 360-22
├── steel_edition: string
├── foundation_standards: StandardReference[]         ← geotechnical/foundation, where applicable
├── supplementary_standards: StandardReference[]
├── standard_relationships: StandardRelationship[]    ← explicit reference/compatibility links
├── compatibility_status: enum [COMPATIBLE, EDITION_MISMATCH, CONFLICT, REQUIRES_REVIEW]
├── compatibility_issues: CompatibilityIssue[]
├── adoption_metadata: AdoptionMetadata | null        ← jurisdictionally adopted code metadata
├── effective_date: date | null
├── supplements: CodeSupplement[]                     ← errata, amendments, interpretations
├── source_metadata: SourceMetadata                   ← source/reference metadata
├── revision_id: UUID | null                          ← linked project revision
├── configured_by: string (user | agent_id)
├── configured_at: datetime
├── status: enum [SOFTWARE_DEFAULT, USER_CONFIRMED, MODIFIED_PENDING_VALIDATION, HISTORICAL]
└── metadata: ParameterMetadata

StandardReference
├── family: string                                    ← e.g., "IBC", "ASCE 7", "ACI 318", "AISC 360"
├── edition: string                                   ← explicit edition identifier
├── full_designation: string                          ← e.g., "2024 International Building Code"
├── publication_status: enum [PUBLISHED, ADOPTED, FUTURE, DEPRECATED]
└── plugin_id: string | null                          ← CodeEngine plugin reference

CompatibilityIssue
├── issue_type: enum [EDITION_MISMATCH, REFERENCE_CONFLICT, SUPERSEDED, REQUIRES_ENGINEER_REVIEW]
├── description: string
├── affected_standards: StandardReference[]
├── reference_relationship: string | null
├── code_references: string[]
└── resolution_status: enum [OPEN, USER_CONFIRMED, RESOLVED]
```

**FACT (user-mandated):** Selecting a jurisdiction does **not** automatically bundle or mix all standards from that jurisdiction. Each standard role (governing, loading, seismic, concrete, steel, foundation, supplementary) is independently configurable with **explicit edition** stored for each.

**FACT (user-mandated):** If the user does not explicitly select a jurisdiction or code configuration, the system applies the **Software Default Code Profile** (Section M.3): IBC 2024, ASCE 7-22, ACI CODE-318-25, AISC 360-22.

**FACT (user-mandated):** Software defaults must **NOT** be described as automatically being the legally adopted codes for every US location. US code compliance is **jurisdiction-dependent**.

**FACT (AG-30, rule 16):** The `CodeConfiguration` model must support all fields listed in Section M.3.1.2. Schema structure only in Phase 0/Phase 1 — no CodeEngine implementation until later phases (M.3.8).

### UnitConfiguration Entity (Mandatory)

```text
UnitConfiguration
├── system: enum [US_CUSTOMARY, SI_METRIC]         ← default: US_CUSTOMARY if not explicitly set
├── length_unit: string                           ← e.g., ft (US) or m (SI)
├── force_unit: string                            ← e.g., kip (US) or kN (SI)
├── moment_unit: string                           ← e.g., kip-ft (US) or kN-m (SI)
├── stress_unit: string                           ← e.g., ksi (US) or MPa (SI)
├── area_unit: string                             ← e.g., in² (US) or mm² (SI)
├── volume_unit: string                           ← e.g., ft³ (US) or m³ (SI)
├── configured_by: string (user | agent_id)
├── configured_at: datetime
├── status: enum [DEFAULT, USER_CONFIRMED, MODIFIED_PENDING_VALIDATION]
└── metadata: ParameterMetadata
```

**FACT (user-mandated):** Default project unit system is **US Customary**. The platform must also **fully support SI / Metric**. Unit system selection is **project-scoped and user-controlled** and must **not** be globally hard-coded.

---

## I. Shared Memory and Knowledge Architecture

### Project Memory (spec Section 17)

Project-scoped persistent memory preserving:


| Memory Type           | Purpose                                                              | Retention                       |
| --------------------- | -------------------------------------------------------------------- | ------------------------------- |
| User decisions        | Approved choices with rationale                                      | Permanent                       |
| Approved assumptions  | Non-critical defaults accepted by user                               | Permanent until overridden      |
| Rejected alternatives | Systems/designs explicitly rejected                                  | Permanent (prevent re-proposal) |
| Project requirements  | Original and evolving requirements                                   | Versioned                       |
| Design choices        | Material, system, **code configuration**, **unit system** selections | Versioned                       |
| Model versions        | PEM snapshots                                                        | Full history                    |
| Conversations         | Important Q&A exchanges                                              | Indexed, searchable             |
| Extracted information | Raw + normalized extraction results                                  | Linked to source files          |
| Validation results    | All validation runs                                                  | Full history                    |
| Revisions             | All change records                                                   | Full history                    |


### Isolation Requirement

**FACT (from spec):** Project A must never influence Project B.

**RECOMMENDATION:** Enforce isolation at three levels:

1. **Database:** `project_id` foreign key on all tables; row-level security if multi-tenant.
2. **Filesystem:** Separate directory per project for uploaded/processed files.
3. **Agent context:** Orchestrator injects only current project's memory into agent prompts.

### Memory vs. PEM Distinction


|                | ProjectEngineeringModel     | Project Memory                   |
| -------------- | --------------------------- | -------------------------------- |
| **Nature**     | Structured engineering data | Contextual knowledge and history |
| **Mutability** | Versioned snapshots         | Append-heavy log                 |
| **Query**      | By engineering entity       | By semantic search / timeline    |
| **Used by**    | Tools, validators, adapters | Agents (context), UI (history)   |


---

## J. File Ingestion Architecture

### Pipeline (spec Section 16)

```text
Uploaded File
      ↓
File Type Detection (extension + magic bytes + MIME)
      ↓
Parser Selection (DWG | DXF | PDF | XLSX | DOCX | IMAGE)
      ↓
Extraction (geometry, text, tables, metadata)
      ↓
Normalization (units, coordinate systems, naming)
      ↓
Validation (completeness, consistency)
      ↓
ProjectEngineeringModel (structured entities)
      ↓
Project Memory (extraction record + confidence)
```

### File Registry Entity

```text
FileRecord
├── id: UUID
├── filename: string
├── type: enum [DWG, DXF, PDF, XLSX, DOCX, PNG, JPG, ...]
├── version: int
├── project_id: UUID
├── source: enum [USER_UPLOAD, AGENT_GENERATED, IMPORTED]
├── upload_time: datetime
├── extraction_status: enum [PENDING, IN_PROGRESS, COMPLETE, FAILED]
├── parsing_status: enum [PENDING, IN_PROGRESS, COMPLETE, FAILED]
├── confidence: float
├── relationships: FileRelationship[] (derived from, supersedes, etc.)
└── storage_path: string
```

### Parser Strategy


| Format     | Complexity | Recommended Approach                                                     |
| ---------- | ---------- | ------------------------------------------------------------------------ |
| **DXF**    | Medium     | Open-source libraries (ezdxf, netDxf); well-documented format            |
| **DWG**    | High       | ODA/Teigha SDK (C++), Aspose.CAD (commercial), or convert DWG→DXF first  |
| **PDF**    | Medium     | pdfplumber / PyMuPDF for text+tables; OCR for scanned drawings           |
| **XLSX**   | Low        | openpyxl / pandas                                                        |
| **Images** | Medium     | Vision LLM for layout understanding; low confidence without verification |


### RISKS

- **DWG parsing** is the highest-risk ingestion item. Full geometry extraction from arbitrary architectural DWGs is unreliable without commercial SDKs.
- **Scanned PDF drawings** require OCR + vision AI; extraction confidence will often be low.
- **Unit/coordinate normalization** across mixed file sources is error-prone.

---

## K. CAD / DWG Architecture

### K.1 AutoCAD and CAD Output (AG-41 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-11). **Documentation only — not implemented.**

#### Current AutoCAD Environment


| Item                        | Value            |
| --------------------------- | ---------------- |
| **AutoCAD version**         | **AutoCAD 2027** |
| **Approved output formats** | **DXF**, **DWG** |


#### CAD Output Policy


| #   | Requirement                                                                                | Type |
| --- | ------------------------------------------------------------------------------------------ | ---- |
| 1   | **DXF** supported as interoperability-oriented output format                               | FACT |
| 2   | **DWG** supported for AutoCAD-oriented workflows                                           | FACT |
| 3   | Architecture must support **both formats** without changing the core platform              | FACT |
| 4   | CAD generation/export must eventually be isolated behind an **adapter/service boundary**   | FACT |
| 5   | AutoCAD-specific functionality must **not** be hard-coded into the core engineering domain | FACT |
| 6   | Future CAD tools/formats must be addable through the **modular integration architecture**  | FACT |


**Constraints:** Do **not** implement CAD export, create DXF/DWG files, or configure AutoCAD until Phase 7+ authorization.

### CAD Abstraction (spec Section 15)

The platform requires a CAD abstraction layer supporting:

- Read/write: DWG, DXF
- Entities: layers, blocks, lines, polylines, dimensions, text, annotations, hatches, tables, title blocks
- Output types: structural plans, sections, elevations, reinforcement drawings, schedules
- **Requirement:** Editable CAD geometry, not screenshots

### Proposed Adapter Interface

```text
CADAdapter (interface)
├── open_document(path) → CADDocument
├── create_document(template) → CADDocument
├── add_layer(name, properties) → Layer
├── add_line(start, end, layer) → Entity
├── add_polyline(points, layer) → Entity
├── add_text(position, content, style) → Entity
├── add_dimension(type, points, layer) → Entity
├── add_block(name, entities) → Block
├── insert_block(block, position, rotation) → Entity
├── add_hatch(boundary, pattern) → Entity
├── export(path, format) → ExportResult
└── get_entities(filter) → Entity[]
```

### Implementation Options


| Option               | Editable DWG         | Cost                     | Risk                            |
| -------------------- | -------------------- | ------------------------ | ------------------------------- |
| **AutoCAD .NET API** | Full                 | Requires AutoCAD license | Low (official API)              |
| **ODA/Teigha SDK**   | Full                 | Commercial license       | Medium                          |
| **DXF-only output**  | DXF yes, DWG no      | Free                     | Medium — many firms require DWG |
| **Aspose.CAD**       | Read + limited write | Commercial               | Medium                          |
| **LibreDWG**         | Partial              | Free                     | High — incomplete spec support  |


### RECOMMENDATION

**AG-41 resolved:** Both **DXF** and **DWG** are approved output formats. With **AutoCAD 2027** available locally, `AutoCADAdapter` via COM/.NET is the primary path for production DWG output when implemented (Phase 8). DXF remains the interoperability fallback.

1. Phase 8: Implement CAD abstraction behind adapter/service boundary.
2. Support **DXF** (interoperability) and **DWG** (AutoCAD-oriented workflows) without core platform changes.
3. Use **AutoCAD 2027** automation where licensed; never hard-code AutoCAD specifics into core domain.

---

## L. ETABS / SAP2000 / SAFE Integration Strategy

### L.1 CSI Products and Versions (AG-40 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-11). **Documentation only — not implemented.**

#### Currently Available CSI Products (User Environment)


| Product     | Version | Adapter (Future) |
| ----------- | ------- | ---------------- |
| **ETABS**   | **23**  | `ETABSAdapter`   |
| **SAP2000** | **27**  | `SAP2000Adapter` |
| **SAFE**    | **23**  | `SAFEAdapter`    |


These versions represent the user's **currently available local engineering software environment**.

#### CSI Integration Policy


| #   | Requirement                                                                               | Type |
| --- | ----------------------------------------------------------------------------------------- | ---- |
| 1   | Integration must use **isolated adapter-based architecture**                              | FACT |
| 2   | CSI products must **not** be directly coupled to the core domain                          | FACT |
| 3   | **Integration Service** remains the approved boundary for external engineering software   | FACT |
| 4   | Product/version information must remain **configurable and project/environment specific** | FACT |
| 5   | Future CSI versions must be **addable without changing core architecture**                | FACT |
| 6   | Version compatibility must be **explicitly tracked** when integration is implemented      | FACT |


**Constraints:** Do **not** implement CSI adapters, install CSI SDKs, or configure CSI software until Phase 7+ authorization.

### CSI API Facts

- ETABS, SAP2000, and SAFE are published by **Computers and Structures, Inc. (CSI)**.
- All three expose **OAPI** (Open Application Programming Interface).
- OAPI on Windows is primarily **COM-based** (.NET interop via `ETABSv1.dll`, `SAP2000v1.dll`, `SAFEv1.dll`).
- Requires ** licensed, installed software** on the execution machine.
- The API is extensive but **undocumented methods must never be invented** (spec Section 12).

### Proposed Adapter Interface (Common Pattern)

```text
StructuralAnalysisAdapter (interface)
├── connect() → ConnectionResult
├── disconnect() → void
├── is_available() → bool
├── create_model(name) → ModelHandle
├── open_model(path) → ModelHandle
├── define_material(properties) → MaterialId
├── define_section(properties) → SectionId
├── add_frame(start, end, section) → FrameId
├── add_area(points, section) → AreaId
├── define_load_cases(cases) → void
├── define_load_combinations(combos) → void
├── run_analysis(options) → AnalysisResult
├── extract_results(result_types) → ResultSet
├── run_design(code) → DesignResult
├── save_model(path) → SaveResult
└── get_model_info() → ModelInfo
```

Each concrete adapter (`ETABSAdapter`, `SAP2000Adapter`, `SAFEAdapter`) implements this interface.

### Availability Detection

```text
if not adapter.is_available():
    return IntegrationResult(
        status="INTEGRATION_UNAVAILABLE",
        message="ETABS vXX not installed or licensed on this machine"
    )
```

Never claim successful execution when the software is not running.

### Mock Adapter Requirements (spec Section 6)

During development, mock adapters:

- Must be labeled `MOCK`, `SIMULATION`, or `TEST ONLY`
- Must return synthetic data clearly marked as non-engineering
- Must never be presented to users as real results without explicit labeling
- Useful for Phase 6 (Structural Agent workflow testing)

### RISKS


| Risk                                            | Severity | Mitigation                                         |
| ----------------------------------------------- | -------- | -------------------------------------------------- |
| CSI software not installed on dev/test machines | High     | Mock adapters + interface-first design             |
| COM threading/apartment issues                  | High     | Dedicated integration service process              |
| API version differences across ETABS versions   | Medium   | Version detection + adapter versioning             |
| Analysis hangs/timeouts                         | Medium   | Timeout enforcement, process isolation             |
| License server dependency                       | Medium   | Graceful degradation to `INTEGRATION_UNAVAILABLE`  |
| Windows-only COM restriction                    | Medium   | Accept Windows target or use COM-to-service bridge |


### RECOMMENDATION

Implement a **dedicated Integration Service** (C# .NET Windows Service or child process) that:

1. Owns all COM interactions with CSI products.
2. Exposes a REST/gRPC API to the Python/agent backend.
3. Runs analysis jobs in isolated processes with timeouts.
4. Reports `INTEGRATION_UNAVAILABLE` when software is missing.

---

## M. Engineering Rules and Code/Standard Management

### CodeEngine (spec Section 20)

Modular engine supporting multiple structural design standards without hard-coding into UI or global application configuration.

### M.1 Design Code Selection Policy (Mandatory Requirement)

**Status:** FACT — user-mandated architectural requirement, incorporated into Phase 0 assessment. **Not yet implemented.**

#### M.1.1 Policy Rules


| #   | Rule                                                                                                                                                                                                                                                                                                             | Type |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- |
| 1   | Default design-code jurisdiction is **United States (US)**                                                                                                                                                                                                                                                       | FACT |
| 2   | User has **full control** over applicable design codes for each project                                                                                                                                                                                                                                          | FACT |
| 3   | Design codes must be **configurable independently per project**; must **not** be hard-coded globally                                                                                                                                                                                                             | FACT |
| 4   | If user does not explicitly select jurisdiction or code configuration, system uses **US standards** as default                                                                                                                                                                                                   | FACT |
| 5   | Before any structural design begins, system must clearly show: jurisdiction, governing building/design code, code edition/version, loading standards, seismic standard, concrete/material standards, steel/material standards, foundation/geotechnical standards (where applicable)                              | FACT |
| 6   | User may change code configuration before and during project, subject to engineering validation                                                                                                                                                                                                                  | FACT |
| 7   | System must **NEVER silently change** user's selected code                                                                                                                                                                                                                                                       | FACT |
| 8   | If user changes governing code, system must identify affected assumptions, loads, load combinations, materials, detailing rules, checks, calculations, and results; must trigger recalculation where required                                                                                                    | FACT |
| 9   | Architecture must use modular, extensible `CodeEngine`; new codes added without rewriting core AI-agent architecture                                                                                                                                                                                             | FACT |
| 10  | Platform must support at minimum: US standards, Iranian National Building Regulations, Standard 2800, ACI, AISC, ASCE, Eurocodes, and additional standards via plugin extension                                                                                                                                  | FACT |
| 11  | Selecting a jurisdiction must **NOT** automatically mix all standards from that jurisdiction; system must explicitly model relationships between governing building code, load standards, seismic standards, concrete standards, steel standards, foundation/geotechnical standards, and supplementary standards | FACT |
| 12  | If selected standards conflict, system must **NOT** silently guess or resolve; must identify conflict, explain affected engineering decision, identify relevant code references when available, and request clarification from user/engineer when necessary                                                      | FACT |
| 13  | Important engineering decisions and calculations must maintain traceability to: code family, edition/version, applicable section/clause (when available), input parameters, assumptions, calculation/check, resulting decision                                                                                   | FACT |
| 14  | Selected code configuration must be part of `ProjectEngineeringModel` and project revision history                                                                                                                                                                                                               | FACT |
| 15  | Changing code configuration must create a **traceable project revision**                                                                                                                                                                                                                                         | FACT |
| 16  | UI and project model must make selected code configuration **visible and editable**                                                                                                                                                                                                                              | FACT |
| 17  | AI must treat user's selected code configuration as an **engineering constraint**, not a suggestion                                                                                                                                                                                                              | FACT |
| 18  | AI must ask for clarification whenever project information is insufficient to determine a required code parameter                                                                                                                                                                                                | FACT |


#### M.1.2 Minimum Supported Standard Families


| Standard Family                           | Role(s)                                     | Notes                                                                   |
| ----------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------- |
| **US standards**                          | Jurisdiction default                        | IBC, ASCE 7, ACI, AISC, etc. — individually selectable per role         |
| **Iranian National Building Regulations** | Governing building code (Iran jurisdiction) | Must not auto-bundle with other Iranian standards                       |
| **Standard 2800**                         | Seismic standard (Iran)                     | Independent selection; explicit relationship to governing code required |
| **ACI**                                   | Concrete design/material standard           | Cross-jurisdiction use allowed if user selects                          |
| **AISC**                                  | Steel design/material standard              | Cross-jurisdiction use allowed if user selects                          |
| **ASCE**                                  | Loading/seismic standard                    | Cross-jurisdiction use allowed if user selects                          |
| **Eurocodes**                             | Full family (EC0–EC8, etc.)                 | Each part selectable per role; not auto-mixed                           |
| **Additional standards**                  | Plugin-extensible                           | Added via `CodeEngine` plugins without core rewrite                     |


#### M.1.3 Standard Relationship Model

Jurisdiction selection provides **defaults only** — not an immutable bundle. The system must explicitly model:

```text
StandardRelationship
├── role: enum [GOVERNING, LOADING, SEISMIC, CONCRETE, STEEL, FOUNDATION, SUPPLEMENTARY]
├── standard: StandardReference
├── relationship_type: enum [REFERENCED_BY, REFERENCES, AMENDS, SUPERSEDES, CONFLICTS_WITH]
├── source: StandardReference | null               ← governing or parent standard
├── code_section: string | null                      ← applicable section/clause when known
├── jurisdiction_hint: string | null                 ← suggested by jurisdiction, overridable by user
├── depends_on: StandardReference[]                  ← explicit dependencies
├── conflicts_with: StandardReference[]              ← detected conflicts, never silently resolved
└── user_override: bool
```

**Example — Software Default Code Profile (US, user has not configured):**


| Role                    | Default Standard                                                                                | Edition         |
| ----------------------- | ----------------------------------------------------------------------------------------------- | --------------- |
| Profile type            | SOFTWARE_DEFAULT                                                                                | —               |
| Jurisdiction            | US                                                                                              | —               |
| Governing building code | 2024 International Building Code                                                                | IBC 2024        |
| Loading                 | ASCE/SEI 7-22 — Minimum Design Loads and Associated Criteria for Buildings and Other Structures | ASCE 7-22       |
| Seismic                 | ASCE/SEI 7-22 (Ch. 11–23, as applicable)                                                        | ASCE 7-22       |
| Concrete                | ACI CODE-318-25 — Building Code for Structural Concrete                                         | ACI CODE-318-25 |
| Steel                   | ANSI/AISC 360-22 — Specification for Structural Steel Buildings                                 | AISC 360-22     |
| Foundation              | *(as applicable; user/project to confirm)*                                                      | —               |


**RECOMMENDATION:** UI must label this profile clearly as **"Software Default — not necessarily jurisdictionally adopted"**.

**Example — Jurisdictionally adopted profile (user provides US project location):**


| Role                    | Example                                                        |
| ----------------------- | -------------------------------------------------------------- |
| Profile type            | JURISDICTIONALLY_ADOPTED                                       |
| Jurisdiction            | US — e.g., State X, City Y                                     |
| Governing building code | IBC 2021 *(as adopted locally)*                                |
| Concrete                | ACI 318-19 *(as referenced by adopted IBC)*                    |
| Steel                   | AISC 360-16 *(as referenced by adopted IBC)*                   |
| Compatibility status    | EDITION_MISMATCH if user previously selected IBC 2024 defaults |


**Example — Iran configuration (user explicitly selects):**


| Role                    | User-Selected Standard                      |
| ----------------------- | ------------------------------------------- |
| Jurisdiction            | Iran                                        |
| Governing building code | Iranian National Building Regulations       |
| Seismic                 | Standard 2800                               |
| Concrete                | ACI or local — **user selects explicitly**  |
| Steel                   | AISC or local — **user selects explicitly** |


#### M.1.4 Pre-Design Code Disclosure Gate

Before the Structural Engineering Agent begins any design work, the system must present and require user acknowledgment of:

1. Selected jurisdiction
2. Governing building/design code and edition/version
3. Applicable loading standards
4. Seismic standard
5. Concrete/material standards
6. Steel/material standards
7. Foundation/geotechnical standards (where applicable)

This is a **mandatory approval gate** in the architecture ↔ structure workflow (extends spec Section 8).

```text
Approved Architectural Model
        ↓
CodeConfiguration Review & Confirmation   ← NEW GATE (mandatory)
        ↓
Preliminary Structural Assessment
        ↓
...
```

#### M.1.5 Code Change Impact Analysis

When the user modifies `CodeConfiguration`, the system must:

```text
CodeConfiguration Change
        ↓
Impact Analysis Service
        ├─ Identify affected: assumptions, loads, load combinations,
        │   materials, detailing rules, checks, calculations, results
        ├─ Classify impact: NO_IMPACT | REQUIRES_REVIEW | REQUIRES_RECALCULATION
        ├─ Create traceable Revision record
        └─ Present impact summary to user for approval
                ↓
        User Approval (if recalculation required)
                ↓
        Trigger recalculation / invalidation of stale results
```

Stale results from prior code configuration must be marked `INVALIDATED_BY_CODE_CHANGE` — never silently retained as current.

#### M.1.6 Code Conflict Handling

```text
Conflict Detected (e.g., Eurocode loads + ACI concrete with incompatible load factors)
        ↓
ValidationEngine → status: REQUIRES_ENGINEER_REVIEW
        ↓
System presents:
  • Conflict description
  • Affected engineering decision(s)
  • Relevant code references (when available; PROVISION_TEXT_UNAVAILABLE if not)
  • Recommended user actions
        ↓
User/Engineer resolves — system does NOT auto-resolve
```

### Proposed CodeEngine Architecture

```text
CodeEngine
├── register_standard(code_id, StandardPlugin)
├── get_provision(code_id, section_ref) → Provision
├── run_check(check_id, inputs, code_configuration) → CheckResult
├── validate_configuration(code_configuration) → ValidationResult
├── detect_conflicts(code_configuration) → ConflictReport[]
├── analyze_change_impact(old_config, new_config, pem) → ImpactReport
├── get_defaults(jurisdiction) → CodeConfiguration        ← US defaults; not hard-coded elsewhere
└── list_available_standards() → StandardInfo[]

StandardPlugin (interface)
├── id: string (e.g., "ACI318-19", "AISC360-16", "Eurocode2", "Standard2800", "IranianNBR")
├── family: string
├── roles: StandardRole[]                                  ← which roles this plugin can fill
├── provisions: ProvisionRegistry
├── checks: CheckRegistry
├── get_reference(section) → ReferenceText
└── get_compatible_with(standard_ref) → CompatibilityInfo
```

### Every Code Calculation Records (Extended Traceability)

Per policy rule 13, every important calculation must record:

- **Code family** (e.g., ACI, AISC, ASCE, Eurocode, Standard 2800)
- **Edition/version**
- **Applicable section/clause** (when available; `UNAVAILABLE` if not)
- **Input parameters** with units and source metadata
- **Assumptions** used
- **Calculation/check** identifier and equation/rule applied
- **Resulting decision** or check outcome
- Source status: `EXACT`, `APPROXIMATE`, `UNAVAILABLE`

### RISKS


| Risk                                                   | Impact                                        | Mitigation                                                                         |
| ------------------------------------------------------ | --------------------------------------------- | ---------------------------------------------------------------------------------- |
| Code provisions are legally protected text             | Cannot reproduce full code text               | Reference section numbers only; `PROVISION_TEXT_UNAVAILABLE` when text unavailable |
| Multi-jurisdiction support is vast scope               | High implementation cost                      | Plugin architecture; phased rollout per standard family                            |
| AI may hallucinate code provisions                     | Critical engineering error                    | CodeEngine deterministic; LLM cannot be code source                                |
| Cross-jurisdiction standard mixing by user             | Invalid engineering combinations              | Conflict detection (M.1.6); never silent resolution                                |
| US default may be wrong for non-US projects            | Incorrect designs if user skips configuration | Pre-design disclosure gate; visible editable UI; default clearly labeled           |
| Standard 2800 / Iranian NBR availability in CodeEngine | Plugin implementation effort                  | Interface-first; document plugin requirements per phase                            |
| Code change impact analysis complexity                 | Incomplete invalidation of stale results      | Explicit `INVALIDATED_BY_CODE_CHANGE` status; revision-linked PEM snapshots        |


### RECOMMENDATIONS

- Phase 1: Include `CodeConfiguration` entity in PEM schema (structure only; no check implementations).
- Phase 4: Add code configuration tools (`get_code_configuration`, `set_code_configuration`, `validate_code_configuration`) to tool registry.
- Phase 6: Implement CodeEngine plugin interface; ship US default configuration helper; implement pre-design disclosure gate.
- Phase 6+: Add standard plugins incrementally per MVP priority (Section M.3.4).
- All code checks must be **deterministic, auditable functions** — never LLM-generated.
- When exact provision text is unavailable, return explicit `PROVISION_TEXT_UNAVAILABLE` status.
- AI must **never** claim code compliance based on latest published edition alone; compliance claims must reference project's selected/governing `CodeConfiguration` (Section M.3).

### M.3 Default US Code Profile Policy (Mandatory Requirement)

**Status:** RESOLVED — **AG-30** user-approved (2026-08-11). Policy rules 1–28 documented. **Not yet implemented** — Phase 0 documentation only (rules 26–28).

**Scope note (FACT):** This policy defines the **Software Default Code Profile**. It does **NOT** override the legally adopted code of a specific project jurisdiction.

#### M.3.1 Software Default Code Profile (AG-30 — RESOLVED)

**Status:** RESOLVED — user-approved policy (2026-08-11). Defines the **Software Default Code Profile** only; does **NOT** override the legally adopted code of a specific project jurisdiction.


| #   | Policy Rule                             | Requirement                                                                                                                                                                                                                                   | Type |
| --- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- |
| 1   | Default jurisdiction                    | **United States (US)**                                                                                                                                                                                                                        | FACT |
| 2   | Default US building code                | **2024 International Building Code (IBC 2024)**                                                                                                                                                                                               | FACT |
| 3   | Default US loading standard             | **ASCE/SEI 7-22** — Minimum Design Loads and Associated Criteria for Buildings and Other Structures                                                                                                                                           | FACT |
| 4   | Default US structural concrete standard | **ACI CODE-318-25** — Building Code for Structural Concrete — Code Requirements and Commentary                                                                                                                                                | FACT |
| 5   | Default US structural steel standard    | **ANSI/AISC 360-22** — Specification for Structural Steel Buildings                                                                                                                                                                           | FACT |
| 6   | Explicit storage                        | All editions above (rules 2–5) must be stored **explicitly** in the project's `CodeConfiguration`                                                                                                                                             | FACT |
| 7   | No false adoption claims                | System must **NOT** describe these defaults as automatically being the legally adopted codes for every US location                                                                                                                            | FACT |
| 8   | Jurisdiction dependency                 | US code compliance is **jurisdiction-dependent**                                                                                                                                                                                              | FACT |
| 9   | Profile-type distinction                | Project workflow must distinguish: **(A)** Software Default Code Profile, **(B)** Project Selected Code Profile, **(C)** Jurisdictionally Adopted / Governing Code, **(D)** Supplementary Standards, **(E)** Historical / Legacy Code Profile | FACT |
| 10  | Project location                        | When user provides a specific US project location, system must treat applicable state/local jurisdiction and its adopted code editions as a **project-level requirement**                                                                     | FACT |
| 11  | User override                           | System must allow user to **override** default editions                                                                                                                                                                                       | FACT |
| 12  | No silent replacement                   | If user explicitly selects a different edition, user's selection becomes project configuration and must **not be silently replaced**                                                                                                          | FACT |
| 13  | No silent edition substitution          | If selected building code references an older edition of a structural standard, system must **NOT silently substitute** the newest edition                                                                                                    | FACT |
| 14  | Edition mismatch workflow               | On mismatch, system must: identify reference relationship, identify edition mismatch, explain potential compatibility issue, show affected standards, request confirmation when engineering judgment is required                              | FACT |
| 15  | Explicit compatibility model            | Code compatibility must be modeled **explicitly** in `CodeConfiguration` (see M.3.1.1)                                                                                                                                                        | FACT |
| 16  | CodeConfiguration model fields          | Model must support all required fields (see M.3.1.2)                                                                                                                                                                                          | FACT |
| 17  | Supplements and amendments              | System must support code supplements, errata, interpretations, and amendments as **traceable metadata** where applicable                                                                                                                      | FACT |
| 18  | Latest vs. governing edition            | System must distinguish **"Latest Published Edition"** from **"Currently Adopted / Governing Edition"** — these are NOT necessarily the same                                                                                                  | FACT |
| 19  | No false compliance claims              | AI must **never** claim code compliance merely because latest published edition is used                                                                                                                                                       | FACT |
| 20  | Governing configuration basis           | Code compliance claims must be based on project's **selected and governing CodeConfiguration**                                                                                                                                                | FACT |
| 21  | Historical code profiles                | System must maintain **historical code profiles** so legacy projects can be evaluated under the code configuration that governed them                                                                                                         | FACT |
| 22  | Extensible architecture                 | Future editions must be **addable without changing core architecture** (plugin/versioned packages)                                                                                                                                            | FACT |
| 23  | No automatic replacement                | When newer edition becomes available, it is added as a **new version** — existing project configurations are **not automatically replaced**                                                                                                   | FACT |
| 24  | NEWER_EDITION_AVAILABLE flag            | Platform must flag `**NEWER_EDITION_AVAILABLE**` without automatically migrating the project                                                                                                                                                  | FACT |
| 25  | Future edition packages                 | 2027 I-Codes and future AISC/other future editions are **future/versioned code packages** until officially published and approved for platform use                                                                                            | FACT |
| 26  | No implementation yet                   | Do **NOT** implement any code or CodeEngine functionality yet                                                                                                                                                                                 | FACT |
| 27  | Phase 0 documentation only              | Only update Phase 0 documentation and the approval gate                                                                                                                                                                                       | FACT |
| 28  | No Phase 1 authorization                | Do **NOT** proceed to Phase 1 without explicit user approval                                                                                                                                                                                  | FACT |


**When no user configuration exists**, the platform applies rules 1–5 as the Software Default Code Profile. See M.3.2 for profile-type definitions, M.3.1.2 for required model fields, and M.3.5 for edition mismatch workflow.

#### M.3.1.1 Code Compatibility Representation (Rule 15)

The system must be able to represent the following explicitly in `CodeConfiguration.standard_relationships`, `compatibility_status`, and `compatibility_issues`:

**Example 1 — Governing code references a specific structural standard edition:**

```text
StandardRelationship
├── role: CONCRETE
├── standard: ACI 318-19
├── relationship_type: REFERENCED_BY
├── source: IBC 2021 (Jurisdictionally Adopted)
├── code_section: "§1901.1"
└── user_override: false
```

**Example 2 — Edition mismatch between governing code and project-selected standard:**

```text
CompatibilityIssue
├── issue_type: EDITION_MISMATCH
├── description: "Adopted IBC 2021 references ACI 318-19; project has ACI CODE-318-25 (Software Default)"
├── affected_standards: [IBC 2021, ACI 318-19, ACI CODE-318-25]
├── reference_relationship: "IBC 2021 §1901.1 → ACI 318-19"
├── code_references: ["IBC 2021 §1901.1"]
└── resolution_status: OPEN → requires user confirmation (M.3.5)
```

**Example 3 — Loading standard linked to governing building code:**

```text
StandardRelationship
├── role: LOADING
├── standard: ASCE 7-22
├── relationship_type: REFERENCED_BY
├── source: IBC 2024 (Software Default or Project Selected)
├── code_section: "§1608.1"
└── user_override: true   ← user may override independently per role
```

**Example 4 — Supplementary standard (local amendment):**

```text
StandardRelationship
├── role: SUPPLEMENTARY
├── standard: "State X Building Code Amendment 2023"
├── relationship_type: AMENDS
├── source: IBC 2021 (Jurisdictionally Adopted)
├── depends_on: [IBC 2021]
└── user_override: false
```

**Example 5 — Historical / legacy frozen profile:**

```text
CodeConfiguration
├── profile_type: HISTORICAL_LEGACY
├── governing_building_code: IBC 2018
├── concrete_standard: ACI 318-14
├── steel_standard: AISC 360-10
├── compatibility_status: COMPATIBLE   ← frozen set; evaluated as-is
└── status: HISTORICAL                 ← immutable for legacy evaluation
```

**Example 6 — Latest published vs. governing edition flag:**

```text
CompatibilityIssue
├── issue_type: SUPERSEDED
├── description: "IBC 2024 is latest published; jurisdiction has adopted IBC 2021"
├── affected_standards: [IBC 2024, IBC 2021]
└── resolution_status: OPEN → informational; triggers NEWER_EDITION_AVAILABLE (M.3.7)
```

**Example 7 — Jurisdiction where adopted building code requires different editions (rule 15):**

A US state has adopted IBC 2021 (not the Software Default IBC 2024). The adopted IBC 2021 references older structural standard editions. The system must represent this full profile without substituting Software Default editions:

```text
CodeConfiguration
├── profile_type: JURISDICTIONALLY_ADOPTED
├── jurisdiction: US
├── project_location: { state: "State X", city: "City Y" }
├── governing_building_code: IBC 2021
├── governing_code_edition: "2021"
├── loading_standard: ASCE/SEI 7-16
├── loading_edition: "2016"
├── seismic_standard: ASCE/SEI 7-16
├── seismic_edition: "2016"
├── concrete_standard: ACI 318-19
├── concrete_edition: "2019"
├── steel_standard: ANSI/AISC 360-16
├── steel_edition: "2016"
├── foundation_standards: [applicable geotechnical standard — user/project to confirm]
├── supplementary_standards: ["State X Building Code Amendment 2022"]
├── adoption_metadata: { adopting_body: "State X", adoption_date: "2022-01-01", ... }
├── effective_date: 2022-01-01
├── compatibility_status: COMPATIBLE   ← internally consistent adopted set
├── standard_relationships: [
│     { role: CONCRETE, standard: ACI 318-19, relationship_type: REFERENCED_BY, source: IBC 2021, code_section: "§1901.1" },
│     { role: STEEL, standard: AISC 360-16, relationship_type: REFERENCED_BY, source: IBC 2021, code_section: "§2203.1" },
│     { role: LOADING, standard: ASCE 7-16, relationship_type: REFERENCED_BY, source: IBC 2021, code_section: "§1608.1" }
│   ]
├── revision_id: <linked project revision>
├── source_metadata: { source: "State X adopted code database", ... }
└── status: USER_CONFIRMED
```

If this jurisdictionally adopted profile is compared against the Software Default Code Profile (IBC 2024 / ASCE 7-22 / ACI CODE-318-25 / AISC 360-22), the system must flag `**NEWER_EDITION_AVAILABLE**` on individual standards without migrating the project (rules 24–25).

#### M.3.1.2 CodeConfiguration Required Fields (Rule 16)

The `CodeConfiguration` model must support the following fields. All map to the schema in Section H (`CodeConfiguration` entity):


| #   | Required Field                    | Schema Location                                                              | Notes                                               |
| --- | --------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------- |
| 1   | Jurisdiction                      | `jurisdiction`, `project_location`                                           | Default US; state/local when user provides location |
| 2   | Governing building code           | `governing_building_code`                                                    | e.g., IBC 2024                                      |
| 3   | Code edition                      | `governing_code_edition`                                                     | Explicit edition string                             |
| 4   | Loading standard                  | `loading_standard`                                                           | e.g., ASCE/SEI 7-22                                 |
| 5   | Loading edition                   | `loading_edition`                                                            | Explicit edition string                             |
| 6   | Concrete standard                 | `concrete_standard`                                                          | e.g., ACI CODE-318-25                               |
| 7   | Concrete edition                  | `concrete_edition`                                                           | Explicit edition string                             |
| 8   | Steel standard                    | `steel_standard`                                                             | e.g., ANSI/AISC 360-22                              |
| 9   | Steel edition                     | `steel_edition`                                                              | Explicit edition string                             |
| 10  | Seismic standard                  | `seismic_standard`, `seismic_edition`                                        | Nullable when not applicable                        |
| 11  | Foundation/geotechnical standards | `foundation_standards[]`                                                     | Where applicable                                    |
| 12  | Supplementary standards           | `supplementary_standards[]`, `supplements[]`                                 | Amendments, errata, interpretations                 |
| 13  | Adoption metadata                 | `adoption_metadata`                                                          | Jurisdictionally adopted code metadata              |
| 14  | Effective date                    | `effective_date`                                                             | When governing code is in effect                    |
| 15  | Project revision                  | `revision_id`                                                                | Linked to project revision history                  |
| 16  | Source/reference metadata         | `source_metadata`                                                            | Provenance and reference tracking                   |
| 17  | Compatibility status              | `compatibility_status`, `compatibility_issues[]`, `standard_relationships[]` | Explicit compatibility modeling (rule 15)           |


#### M.3.2 Code Profile Types

The project workflow must distinguish five profile categories:


| ID    | Profile Type                                  | Description                                               | Mutability                                                                 |
| ----- | --------------------------------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------- |
| **A** | **Software Default Code Profile**             | Platform out-of-box defaults (M.3.1)                      | Applied at project creation; overridable by user                           |
| **B** | **Project Selected Code Profile**             | User-confirmed configuration for the project              | User-controlled; never silently replaced                                   |
| **C** | **Jurisdictionally Adopted / Governing Code** | State/local legally adopted code editions                 | Set when user provides project location; may differ from software defaults |
| **D** | **Supplementary Standards**                   | Referenced/additional standards (supplements, amendments) | Traceable metadata; linked to governing profile                            |
| **E** | **Historical / Legacy Code Profile**          | Frozen configuration for existing/legacy projects         | Immutable for evaluation; preserved in revision history                    |


#### M.3.3 Extended Policy Rules (Compliance, Supplements, and Future Editions)

Rules 1–28 are defined in **M.3.1 (AG-30)**. Detailed elaboration for rules 17–25:


| #     | Rule                                                                   | Detail Section                                              |
| ----- | ---------------------------------------------------------------------- | ----------------------------------------------------------- |
| 17    | Supplements, errata, interpretations, amendments as traceable metadata | `supplements[]`, `CodeSupplement` entity; Section H         |
| 18    | Latest Published vs. Currently Adopted / Governing Edition             | M.3.6                                                       |
| 19–20 | AI compliance claim constraints                                        | M.3.6; Section G (Validation Agent)                         |
| 21    | Historical code profiles                                               | M.3.2 profile type **E**; `profile_type: HISTORICAL_LEGACY` |
| 22–25 | Future edition handling                                                | M.3.7; `StandardReference.publication_status: FUTURE`       |
| 26–28 | Phase 0 constraints — no implementation                                | M.3.8                                                       |


#### M.3.4 MVP CodeEngine Plugin Priority (AG-31 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-11). Priority list aligned to US Default Code Profile (M.3.1).

**FACT (user-mandated):** The architecture must remain **modular** so this priority list can evolve **without changing the core platform**. New standards are added via `CodeEngine` plugins only — no core rewrite.


| Priority       | Standard Plugins                                                                                                                                     | Scope                                                                                |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **Priority 1** | **IBC**, **ASCE 7**, **ACI 318**, **AISC 360**                                                                                                       | Core US Software Default Code Profile (M.3.1 rules 2–5); first implementation target |
| **Priority 2** | **AISC 341**, **AISC 303**, applicable **ASCE/SEI** standards, applicable **concrete, steel, masonry, wood, foundation, and geotechnical** standards | Extended US structural design coverage                                               |
| **Priority 3** | **Iranian NBR**, **Standard 2800**, **Eurocodes**, other **jurisdictional standards**                                                                | International/jurisdictional expansion                                               |


**RECOMMENDATION:** Phase 6 implements Priority 1 plugin **interfaces and stubs** only; Priority 1 deterministic checks added incrementally post-Phase 6. Priority 2 and 3 added as plugins without core architecture changes. **No CodeEngine implementation in Phase 0** (AG-30 rule 26).

#### M.3.5 Edition Mismatch Workflow

```text
Building code references ACI 318-19
Project configuration has ACI CODE-318-25 (Software Default or user-selected)
        ↓
CompatibilityEngine detects EDITION_MISMATCH
        ↓
System presents:
  • Reference relationship (IBC §XXXX → ACI 318-19)
  • Edition mismatch details
  • Potential compatibility issue explanation
  • Affected standards and downstream checks
        ↓
User/Engineer confirms:
  • Keep referenced edition (ACI 318-19), OR
  • Override with user judgment (documented), OR
  • Update governing building code to match
        ↓
Resolution recorded in CodeConfiguration + Revision + Traceability
```

**FACT:** System must **never** silently substitute newest edition when governing code references an older edition.

#### M.3.6 Latest Published vs. Adopted / Governing Edition


| Concept                                   | Meaning                                              | Platform Behavior                                                                                           |
| ----------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **Latest Published Edition**              | Most recent publication from standards body          | Available as selectable option; may trigger `NEWER_EDITION_AVAILABLE` flag on projects using older editions |
| **Currently Adopted / Governing Edition** | Edition legally in effect for project's jurisdiction | Set via Jurisdictionally Adopted profile; drives compliance claims                                          |
| **Software Default Edition**              | Platform out-of-box default (M.3.1)                  | Starting point only; not a compliance claim                                                                 |


#### M.3.7 Future Edition Handling

- **2027 I-Codes**, future **AISC** editions, and other unreleased standards: registered as `FUTURE` publication status in `StandardReference`.
- Not selectable for engineering calculations until **published and platform-approved**.
- When approved, added as new versioned plugin package — no automatic migration of existing projects.
- Projects using older editions receive `**NEWER_EDITION_AVAILABLE**` informational flag only.

#### M.3.8 Phase 0 Constraints (Rules 26–28)


| #   | Constraint                                                               | Status                                    |
| --- | ------------------------------------------------------------------------ | ----------------------------------------- |
| 26  | Do **NOT** implement any code or CodeEngine functionality yet            | ENFORCED — Phase 0 documentation only     |
| 27  | Only update Phase 0 documentation and the approval gate                  | ENFORCED — this document update           |
| 28  | Do **NOT** proceed to Phase 1 without explicit user approval (**AG-53**) | ENFORCED — awaiting **"APPROVE PHASE 1"** |


### RISKS (Default US Code Profile)


| Risk                                                 | Impact                         | Mitigation                                                             |
| ---------------------------------------------------- | ------------------------------ | ---------------------------------------------------------------------- |
| User assumes software defaults are legally adopted   | Invalid compliance claims      | Clear UI labeling; Jurisdictionally Adopted profile workflow (M.3.2-C) |
| Edition mismatch between IBC and referenced ACI/AISC | Incorrect design checks        | CompatibilityEngine + explicit user confirmation (M.3.5)               |
| Automatic migration to newer editions                | Breaks legacy project validity | `NEWER_EDITION_AVAILABLE` flag only; no auto-migration (M.3.7)         |
| AI claims compliance based on latest edition         | Engineering liability          | Policy rules 19–20; compliance tied to governing CodeConfiguration     |
| State/local adoption lag vs. latest I-Codes          | Wrong code for jurisdiction    | Project location → Jurisdictionally Adopted profile (M.3.3 rule 10)    |


### RECOMMENDATIONS (Default US Code Profile)

- Phase 1: Include full `CodeConfiguration` schema with `profile_type`, edition fields, and `compatibility_status` (structure only).
- Phase 4: Add tools: `get_software_default_profile`, `set_project_code_profile`, `check_code_compatibility`, `get_adopted_code_for_location`.
- Phase 6: Implement CompatibilityEngine; ship Software Default Code Profile helper; implement Priority 1 plugin interfaces.

### M.2 Unit System Policy (Mandatory Requirement)

**Status:** FACT — user-mandated architectural requirement, incorporated into Phase 0 assessment. **Not yet implemented.**

#### M.2.1 Policy Rules


| #   | Rule                                                                                                                                                                 | Type |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- |
| 1   | Default project unit system shall be **US Customary units**                                                                                                          | FACT |
| 2   | Platform must also **fully support SI / Metric units**                                                                                                               | FACT |
| 3   | Unit system selection must be **project-scoped and user-controlled**                                                                                                 | FACT |
| 4   | Unit system must **NOT** be globally hard-coded                                                                                                                      | FACT |
| 5   | User must be able to change project unit system **when technically safe**                                                                                            | FACT |
| 6   | Internal `ProjectEngineeringModel` must use **explicit unit metadata** for all engineering quantities                                                                | FACT |
| 7   | Every engineering quantity must have an **unambiguous physical dimension and unit**                                                                                  | FACT |
| 8   | Unit conversion must be **deterministic and loss-controlled**                                                                                                        | FACT |
| 9   | Changing display/input unit system must **NOT** change the underlying physical engineering value                                                                     | FACT |
| 10  | System must prevent dimensional inconsistencies (e.g., kN vs lb, kN-m vs kip-ft, m vs ft, mm vs in, MPa vs ksi)                                                      | FACT |
| 11  | Code-specific calculations must use units required by the selected calculation engine/code configuration while maintaining traceability to the project's unit system | FACT |
| 12  | Unit conversions and normalization must be **traceable**                                                                                                             | FACT |
| 13  | UI must **always display the active project unit system clearly**                                                                                                    | FACT |


#### M.2.2 Supported Unit Systems


| System           | Primary Units                            | Status          |
| ---------------- | ---------------------------------------- | --------------- |
| **US Customary** | ft, in, kip, kip-ft, ksi, psi, lb, lb-ft | Default         |
| **SI / Metric**  | m, mm, kN, kN-m, MPa, Pa, kg, N-m        | Fully supported |


**FACT:** Both systems are first-class. The default is US Customary; the user may select SI/Metric per project.

#### M.2.3 Canonical Value Storage Model

The PEM stores **canonical physical values** with explicit dimension and unit metadata. Display and input units are a presentation layer.

```text
EngineeringQuantity
├── value: number                                 ← canonical stored value
├── dimension: PhysicalDimension                  ← e.g., FORCE, LENGTH, MOMENT, STRESS
├── unit: string                                  ← unit of stored canonical value
├── display_unit: string | null                   ← active display unit (may differ)
└── metadata: ParameterMetadata
```

**Conversion rule (FACT):** `display_value = convert(canonical_value, stored_unit → display_unit)`. Changing `display_unit` or `UnitConfiguration.system` converts presentation only — the canonical `value` in stored `unit` is unchanged unless an explicit user edit occurs.

#### M.2.4 Dimensional Consistency Enforcement

The `ValidationEngine` must detect and reject dimensional inconsistencies:


| Dimension | Incompatible Mix Examples                 | Detection              |
| --------- | ----------------------------------------- | ---------------------- |
| Force     | kN mixed with lb/kip without conversion   | Dimension tag mismatch |
| Moment    | kN-m mixed with kip-ft without conversion | Dimension tag mismatch |
| Length    | m mixed with ft/mm/in without conversion  | Dimension tag mismatch |
| Stress    | MPa mixed with ksi/psi without conversion | Dimension tag mismatch |


Operations combining quantities must verify matching `dimension` and compatible `unit` (or apply explicit, traceable conversion).

#### M.2.5 Unit Conversion Service (AG-48 — RESOLVED)

**Status:** RESOLVED — user-approved (2026-08-12). Independent platform service. See Section G.12. **Not implemented.**

```text
UnitConversionService
├── convert(value, from_unit, to_unit) → ConversionResult
├── normalize(quantity, target_unit) → EngineeringQuantity
├── validate_dimensional_consistency(quantities[]) → ValidationResult
└── record_conversion(conversion) → TraceabilityLink   ← traceable per policy rule 12

ConversionResult
├── original_value: number
├── original_unit: string
├── converted_value: number
├── converted_unit: string
├── dimension: PhysicalDimension
├── loss: enum [EXACT, ROUNDED, LOSSY]              ← loss-controlled per policy rule 8
├── precision: int | null
└── traceability_id: UUID
```

**RECOMMENDATION:** Use a well-established unit library (e.g., Pint for Python, similar for other stacks) wrapped in the platform's traceable conversion service — never ad-hoc conversion factors in agent or UI code.

#### M.2.6 Code Engine Unit Interaction

Per policy rule 11, when `CodeEngine` runs a check:

1. Inputs are read from PEM in canonical stored units with dimension metadata.
2. CodeEngine converts to the **units required by the selected standard/calculation** (e.g., ACI uses psi/ksi in US mode).
3. Calculation executes in code-required units.
4. Results are stored back in PEM canonical units with full traceability:
  - Project `UnitConfiguration`
  - Code-required intermediate units
  - Conversion factors applied

```text
PEM Quantity (canonical: 500 kip)
        ↓
CodeEngine input conversion (500 kip → 500,000 lb for ACI check)
        ↓
Code check execution
        ↓
Result stored (canonical: 8 ksi, dimension: STRESS)
        ↓
TraceabilityLink: conversion + code family + section
```

#### M.2.7 Unit System Change Behavior

When the user changes `UnitConfiguration`:

1. **Display/input units** update immediately (no change to canonical values).
2. System assesses whether change is **technically safe** (policy rule 5):
  - Display-only change: always safe.
  - Change affecting exported model units (ETABS, CAD): requires validation and may require user approval.
3. If change affects downstream integrations or stale converted results, trigger impact analysis similar to code configuration changes.
4. All conversions performed during the change are recorded in traceability log.

#### M.2.8 UI Requirements

The UI must:

- Display active unit system prominently (e.g., persistent header/badge: **"Units: US Customary (ft, kip, ksi)"**).
- Allow per-project unit system selection in project settings.
- Show units alongside every engineering quantity input and output.
- Never hide or obscure the active unit context.

### RISKS (Unit System)


| Risk                                                      | Impact                       | Mitigation                                                                 |
| --------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------------------- |
| Floating-point rounding in conversions                    | Accumulated error in designs | Loss-controlled conversion with explicit precision; store canonical values |
| CSI software unit mismatch (ETABS US vs SI)               | Incorrect analysis models    | Adapter-level unit mapping with validation gate before export              |
| Mixed units from ingested files (DXF in mm, loads in kip) | Silent dimensional errors    | Normalization pipeline with explicit conversion traceability               |
| Display unit change mistaken for value change             | User confusion or errors     | Canonical storage model; UI clearly separates display from stored value    |
| Code engine unit requirements differ from project units   | Wrong check results          | CodeEngine internal conversion layer (M.2.6)                               |


### RECOMMENDATIONS (Unit System)

- Phase 1: Include `UnitConfiguration` entity and enhanced `ParameterMetadata` (with `dimension`) in PEM schema.
- Phase 2: File ingestion normalization must route through `UnitConversionService` with traceability.
- Phase 4: Add unit tools (`get_unit_configuration`, `set_unit_configuration`, `convert_units`) to tool registry.
- Phase 6: CodeEngine must implement M.2.6 unit interaction pattern.
- Phase 7: CSI adapters must declare and validate model unit system before export/import.

---

## N. Validation and Traceability

### ValidationEngine (spec Section 22)

Independent validation across six categories:


| Category         | Examples                                                                                                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Input**        | Missing values, invalid values, unit conflicts, dimensional inconsistencies (kN vs lb, m vs ft, MPa vs ksi), **missing/incomplete CodeConfiguration**, **missing UnitConfiguration** |
| **Architecture** | Geometry gaps, dimension inconsistencies, level mismatches                                                                                                                           |
| **Structural**   | Connectivity, supports, material/section validity, load completeness, **code-standard conflicts**                                                                                    |
| **Analysis**     | Warnings, instability, non-convergence, suspicious results                                                                                                                           |
| **Design**       | Strength, serviceability, drift, deflection, code compliance, **stale results after code change**                                                                                    |
| **Output**       | Model/drawing consistency, missing annotations/schedules                                                                                                                             |


**Statuses:** `PASS`, `WARNING`, `ERROR`, `REQUIRES_ENGINEER_REVIEW`

**RECOMMENDATION:** Validation Agent should be invoked automatically after every agent tool execution that modifies PEM.

### Traceability (spec Section 18)

Every important result must maintain a provenance chain:

```text
TraceabilityLink
├── result_id: UUID (e.g., column design)
├── parent_id: UUID (e.g., design check)
├── link_type: enum [DERIVED_FROM, CHECKED_BY, LOADED_FROM, EXTRACTED_FROM, APPROVED_BY, GOVERNED_BY_CODE, UNIT_CONVERTED]
├── from_unit: string | null
├── to_unit: string | null
├── conversion_factor: number | null
├── code_family: string | null              ← e.g., ACI, AISC, Standard 2800
├── code_edition: string | null
├── code_section: string | null             ← section/clause when available
├── source_agent: string | null
├── source_file: string | null
└── timestamp: datetime
```

Example chain (extended per Design Code Policy):

```text
Final Column Design
  ← Design Check (AISC 360-22 §E3)
    ← CodeConfiguration (SOFTWARE_DEFAULT | US | IBC 2024 | ASCE 7-22 | AISC 360-22 | ACI CODE-318-25)
      ← Load Combination (1.2D + 1.6L per ASCE 7-22)
        ← Analysis Result (ETABS frame forces)
          ← ETABS Model (Frame F-102)
            ← Structural Member (Column C-12)
              ← Architectural Grid (B-4)
                ← Source Drawing (A-101.dwg)
```

**FACT (user-mandated):** Every important engineering decision must be traceable to code family, edition/version, section/clause (when available), inputs, assumptions, calculation/check, and resulting decision.

**RECOMMENDATION:** Store traceability as a directed acyclic graph (DAG) linked to PEM entity IDs. UI should allow drilling down from any result to its sources.

---

## O. Data Model

### Entity Relationship Overview

```text
Project 1──* FileRecord
Project 1──* PEMSnapshot (versioned)
Project 1──* MemoryEntry
Project 1──* Revision
Project 1──* ApprovalRequest
Project 1──* AgentActivityLog
Project 1──* TraceabilityLink
Project 1──1 CodeConfiguration (current, embedded in PEMSnapshot)
Project 1──1 UnitConfiguration (current, embedded in PEMSnapshot)
Project 1──* CodeConfigurationRevision (history via Revision records)

PEMSnapshot 1──1 ProjectEngineeringModel (JSON document, includes CodeConfiguration)
PEMSnapshot *──* ValidationResult
PEMSnapshot *──* FileRecord (source files)

ApprovalRequest *──1 AgentActivityLog
Revision *──1 PEMSnapshot (before)
Revision *──1 PEMSnapshot (after)
```

### Storage Strategy (AG-34 Aligned)


| Data Type                          | Storage                                      | Rationale                     |
| ---------------------------------- | -------------------------------------------- | ----------------------------- |
| Project metadata, users, approvals | **PostgreSQL** (AG-34)                       | ACID, queries, relationships  |
| PEM snapshots                      | JSONB in PostgreSQL                          | Flexible schema, versioned    |
| Uploaded files                     | Filesystem or object storage                 | Binary blobs                  |
| Agent activity logs                | PostgreSQL + time-series index               | Audit trail queries           |
| Memory / conversations             | Vector store + PostgreSQL metadata           | Semantic retrieval for agents |
| Traceability graph                 | PostgreSQL (adjacency list or closure table) | Graph traversal               |
| Code configuration history         | PostgreSQL, linked to Revision               | Audit and impact analysis     |
| Unit conversion traceability       | PostgreSQL, linked to TraceabilityLink       | Audit and dimensional audit   |


### Database: RESOLVED (AG-34)

**Decision:** PostgreSQL — user-approved (2026-08-11). Schemas, migrations, and database access **not yet implemented**.

---

## P. Security

Per spec Section 25.

### Required Security Controls


| Control                      | Description                                                             | Phase    |
| ---------------------------- | ----------------------------------------------------------------------- | -------- |
| **No LLM shell access**      | LLM never executes arbitrary OS commands                                | Phase 4+ |
| **Tool permission system**   | Each tool declares required permissions; enforced pre-execution         | Phase 4  |
| **Project file isolation**   | Projects cannot access each other's files                               | Phase 1  |
| **Credential management**    | API keys via environment variables or secrets manager; never hard-coded | Phase 1  |
| **Input validation**         | All tool inputs schema-validated before execution                       | Phase 4  |
| **Audit logging**            | All tool executions, approvals, and rejections logged                   | Phase 4  |
| **File upload sanitization** | Validate file types, size limits, scan for malicious content            | Phase 2  |


### RECOMMENDATIONS (Additional)

- Run CSI integration service with **least-privilege** Windows account.
- Sandbox file parsing ( malformed DWG/PDF should not crash the platform).
- Rate-limit LLM API calls to control cost and abuse.
- If multi-user: implement authentication (OAuth2/OIDC) and role-based access (engineer, reviewer, admin).

---

## Q. Deployment Architecture

### Deployment Options


| Model                                       | Pros                                    | Cons                               | Fit                                |
| ------------------------------------------- | --------------------------------------- | ---------------------------------- | ---------------------------------- |
| **Local desktop app**                       | Direct CSI/CAD access, data stays local | Harder to update, single-user      | Strong for CSI integration         |
| **Web app + local agent service**           | Modern UI, accessible                   | Requires local service for CSI/CAD | Good hybrid                        |
| **Full cloud**                              | Scalable, multi-user                    | CSI/CAD cannot run in cloud easily | Poor for CSI integration           |
| **Desktop (Flutter/Electron) + cloud sync** | Best of both                            | Complex                            | Recommended if multi-device needed |


### RECOMMENDATION

**Hybrid deployment:**

```text
┌──────────────────────┐     ┌─────────────────────────┐
│  Client (Flutter)    │────▶│  Backend API (Python)   │
│  Desktop or Web      │     │  Local or Cloud          │
└──────────────────────┘     └───────────┬─────────────┘
                                         │
                             ┌───────────▼─────────────┐
                             │  Integration Service     │
                             │  (C# .NET, Windows-only) │
                             │  ETABS | SAP2000 | SAFE  │
                             │  AutoCAD                 │
                             └─────────────────────────┘
```

- Backend and database can run locally (SQLite) for MVP or cloud (PostgreSQL) for production.
- Integration Service **must** run on a Windows machine with licensed CSI/CAD software.
- File storage local for MVP; object storage for production.

### Not Yet Decided

Deployment model is a **Decision Required From User** (Section T).

---

## R. Risks and Technical Constraints

### Critical Risks


| ID  | Risk                                                           | Likelihood | Impact   | Category                |
| --- | -------------------------------------------------------------- | ---------- | -------- | ----------------------- |
| R1  | **AI hallucination of engineering results**                    | High       | Critical | Engineering correctness |
| R2  | **DWG parsing/generation reliability**                         | High       | High     | CAD integration         |
| R3  | **CSI COM integration complexity**                             | High       | High     | Structural software     |
| R4  | **Scope creep across 12 phases**                               | High       | High     | Project management      |
| R5  | **Multi-jurisdiction code standard coverage gaps**             | Medium     | Critical | Engineering correctness |
| R11 | **Silent code conflict resolution by AI**                      | Medium     | Critical | Engineering correctness |
| R12 | **Incomplete invalidation after code configuration change**    | Medium     | High     | Data integrity          |
| R13 | **User selects incompatible cross-jurisdiction standards**     | Medium     | High     | Engineering correctness |
| R14 | **Dimensional unit mismatch across ingested files and models** | High       | Critical | Engineering correctness |
| R15 | **CSI adapter unit system mismatch (ETABS US vs SI)**          | Medium     | High     | Integration             |
| R6  | **Undetermined tech stack causing rework**                     | Medium     | High     | Architecture            |
| R7  | **Mock results presented as real**                             | Medium     | Critical | Trust/safety            |
| R8  | **Performance with large architectural files**                 | Medium     | Medium   | Performance             |
| R9  | **Multi-agent coordination bugs**                              | Medium     | High     | Agent architecture      |
| R10 | **Windows-only constraint for CSI/CAD**                        | Certain    | Medium   | Platform constraint     |


### Ambiguities in Specification


| ID  | Ambiguity                                                  | Impact                         | Resolution Needed                                                                                                                                                          |
| --- | ---------------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | ~~No technology stack specified~~                          | —                              | **RESOLVED** — Full stack approved (AG-32–AG-35); AI (AG-36–AG-37); deployment (AG-38–AG-39)                                                                               |
| A2  | ~~No target design codes/standards specified~~             | —                              | **RESOLVED** — Design Code Selection Policy (Section M.1): US default, project-scoped, user-controlled                                                                     |
| A3  | ~~No deployment model specified~~                          | —                              | **RESOLVED** — Hybrid/local-first (AG-38, AG-25)                                                                                                                            |
| A4  | ~~No multi-user vs. single-user specified~~                | —                              | **RESOLVED** — Single-user MVP initially; multi-user extensible (AG-39)                                                                                                     |
| A5  | ~~No LLM provider specified~~                              | —                              | **RESOLVED** — Provider-agnostic AI Gateway (AG-36); no single production model hard-coded                                                                                  |
| A6  | ~~No CSI software version targets specified~~              | —                              | **RESOLVED** — ETABS 23, SAP2000 27, SAFE 23 (AG-40, Section L.1)                                                                                                          |
| A7  | ~~No geographic/jurisdiction context~~                     | —                              | **RESOLVED** — Default jurisdiction US; user selects per project (AG-27)                                                                                                    |
| A7a | ~~Default US code editions not specified~~                 | —                              | **RESOLVED** — Software Default Code Profile (AG-30, Section M.3)                                                                                                            |
| A8  | No performance/scale requirements                          | Infrastructure sizing          | Deferred to Phase 1+ planning (U.23 U-A4)                                                                                                                                  |
| A9  | ~~`Project_Specification.md` referenced but absent~~       | —                              | **RESOLVED** — No additional spec beyond `MASTER PROMPT V2.md` (AG-51)                                                                                                      |
| A10 | ~~DWG vs. DXF acceptability for output~~                   | —                              | **RESOLVED** — Both DXF and DWG approved (AG-41, Section K.1)                                                                                                              |
| A11 | ~~AutoCAD license availability~~                           | —                              | **RESOLVED** — AutoCAD 2027 available (AG-41, Section K.1)                                                                                                                 |
| A12 | Whether scanned PDF drawings are in scope                  | Vision AI / OCR requirement    | User must clarify                                                                                                                                                          |


### Technical Constraints (FACTS)

1. CSI OAPI requires **Windows + licensed installed software**.
2. Editable DWG writing requires **commercial SDK or AutoCAD automation**.
3. Engineering code text is **copyright-protected** — system can reference sections, not reproduce full text.
4. LLM context windows are **finite** — large projects need selective memory retrieval, not full PEM injection.
5. COM automation is **single-threaded apartment (STA)** — requires careful process design.

---

## S. Recommended Implementation Phases

Aligned with master specification Sections 30–31. No modifications recommended to phase boundaries.


| Phase  | Name                    | Key Deliverables                                                                                                  | Dependencies          | Estimated Complexity |
| ------ | ----------------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------- | -------------------- |
| **0**  | Repository Analysis     | This document (FROZEN — AG-01–AG-75)                                                                              | —                     | ✅ Complete / Frozen  |
| **1**  | Foundation              | Project structure, PEM (incl. `CodeConfiguration`, `UnitConfiguration` schemas), persistence, config, logging     | Stack decision        | Medium               |
| **2**  | File Ingestion          | Upload, registry, parsers, extraction interfaces                                                                  | Phase 1               | Medium               |
| **3**  | Project Memory          | Memory store, indexing, retrieval                                                                                 | Phase 1, 2            | Medium               |
| **4**  | Agent Framework         | Orchestrator, tools, permissions, approvals, logs                                                                 | Phase 1, 3            | High                 |
| **5**  | Architecture Agent      | Analysis, ambiguity detection, clarification, arch model                                                          | Phase 2, 4            | High                 |
| **6**  | Structural Agent        | Preliminary design, alternatives, structural model, mock adapters, **pre-design code gate**, CodeEngine interface | Phase 4, 5            | High                 |
| **7**  | ETABS/SAP2000/SAFE      | Real or mock CSI adapters, integration service                                                                    | Phase 6, CSI software | Very High            |
| **8**  | CAD                     | CAD abstraction, DXF/DWG output, structural drawings                                                              | Phase 6               | Very High            |
| **9**  | Optimization            | OptimizationEngine, objectives, constraints, approval                                                             | Phase 6, 7            | High                 |
| **10** | Reports & Documentation | DOCX/PDF/XLSX reports, schedules, indexes                                                                         | Phase 6+              | Medium               |
| **11** | Full Integration        | End-to-end workflow connecting all modules                                                                        | All prior             | Very High            |
| **12** | Production Hardening    | Security, performance, backup, installer, regression tests                                                        | Phase 11              | High                 |


### Phase Gate Protocol

After each phase:

1. Generate `PHASE_<N>_REPORT.md` per spec Section 31.
2. Verify quality gates (spec Section 32): compile, tests, architecture, engineering, documentation.
3. **STOP** and wait for explicit user approval before next phase.

---

## T. Decisions Required From User

The following decisions **must be resolved** before Phase 1 implementation begins.

### T.1 Technology Stack


| #   | Decision                   | Status               | Approved Selection                                                          |
| --- | -------------------------- | -------------------- | --------------------------------------------------------------------------- |
| D1  | Backend language/framework | **RESOLVED (AG-32)** | **Python + FastAPI** — user-approved 2026-08-11                             |
| D2  | Frontend framework         | **RESOLVED (AG-33)** | **Next.js + React + TypeScript** — user-approved 2026-08-11                 |
| D3  | Database                   | **RESOLVED (AG-34)** | **PostgreSQL** — user-approved 2026-08-11                                   |
| D4  | Version control            | **RESOLVED (AG-35)** | **Git + GitHub** — user-approved 2026-08-11; repository not yet initialized |


**Implementation status:** All four decisions are **approved but not implemented**. See Section C for rationales and architectural consistency.

### T.2 AI / Agent Configuration


| #   | Decision                          | Status               | Approved Selection                                                                                                                                                                 |
| --- | --------------------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D5  | LLM provider and API strategy     | **RESOLVED (AG-36)** | **Provider-agnostic AI Gateway** with Provider Adapter Layer, configurable model routing, external API + local/self-hosted support, fallback capability — user-approved 2026-08-11 |
| D6  | Agent orchestration               | **RESOLVED (AG-37)** | **Hybrid orchestration** — deterministic workflow/state machine for engineering-critical workflows + controlled AI planning/routing — user-approved 2026-08-11                     |
| D7  | Vision model for drawing analysis | **RESOLVED (AG-36)** | Routed via AI Gateway task-type model routing — freeze 2026-08-12 |


**Implementation status:** AG-36 and AG-37 are **approved but not implemented**. See Section G.1 and G.2 for architecture details. No AI Gateway, provider adapters, agents, or orchestration code until Phase 1+ authorization.

### T.3 Deployment and Users

| # | Decision | Status | Approved Selection |
|---|----------|--------|-------------------|
| D8 | Deployment model | **RESOLVED (AG-38)** | Hybrid web frontend + local Integration Service; local-first for CSI/CAD — freeze 2026-08-12 |
| D9 | User model | **RESOLVED (AG-39)** | Single-user MVP initially; multi-user extensible later — freeze 2026-08-12 |
| D10 | Data residency | **RESOLVED (AG-25)** | Local-first; hybrid optional — freeze 2026-08-12 |


### T.4 Engineering Domain


| #    | Decision                          | Status       | Options / Notes                                                                                                                                                  |
| ---- | --------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D11  | Design code jurisdiction default  | **RESOLVED** | US default per Design Code Selection Policy (Section M.1)                                                                                                        |
| D11a | Default US code editions          | **RESOLVED** | IBC 2024, ASCE 7-22, ACI CODE-318-25, AISC 360-22 (Section M.3.1)                                                                                                |
| D11b | Priority standard plugins for MVP | **RESOLVED** | Priority 1: IBC, ASCE 7, ACI 318, AISC 360; Priority 2: AISC 341/303, extended ASCE/materials; Priority 3: Iranian NBR, Standard 2800, Eurocodes (Section M.3.4) |
| D12  | Default unit system               | **RESOLVED** | US Customary default; SI/Metric fully supported; project-scoped, user-controlled (Section M.2)                                                                   |
| D13  | Jurisdiction / region             | **RESOLVED** | US default; user selects per project; Iran and Eurocode jurisdictions supported                                                                                  |


### T.5 External Software


| #   | Decision               | Status               | Approved Selection                                                   |
| --- | ---------------------- | -------------------- | -------------------------------------------------------------------- |
| D14 | CSI products available | **RESOLVED (AG-40)** | **ETABS 23**, **SAP2000 27**, **SAFE 23** — user-approved 2026-08-11 |
| D15 | AutoCAD availability   | **RESOLVED (AG-41)** | **AutoCAD 2027** — user-approved 2026-08-11                          |
| D16 | CAD output format      | **RESOLVED (AG-41)** | **DXF** and **DWG** — user-approved 2026-08-11                       |


**Implementation status:** AG-40 and AG-41 are **approved but not implemented**. See Section L.1 (CSI) and Section K.1 (CAD). No adapters, SDKs, or export code until Phase 7+ authorization.

### T.7 Agent & Platform Architecture

| # | Decision | Status | Approved Selection |
|---|----------|--------|-------------------|
| D20 | Agent extensibility | **RESOLVED (AG-42)** | Two agents now; extensible via Registry/Contract/Orchestrator — user-approved 2026-08-12 |
| D21 | Agent domain isolation | **RESOLVED (AG-43)** | Clear domain boundaries; no super-agent — user-approved 2026-08-12 |
| D22 | Agent Registry | **RESOLVED (AG-44)** | Registry/contract-based discovery — user-approved 2026-08-12 |
| D23 | Agent Contract | **RESOLVED (AG-45)** | Stable domain-neutral interface — user-approved 2026-08-12 |
| D24 | Agent orchestration/collaboration | **RESOLVED (AG-46)** | Extends AG-37; PEM-mediated; no direct agent calls — user-approved 2026-08-12 |
| D25 | Shared platform services | **RESOLVED (AG-47)** | Defined service boundaries for agent access — user-approved 2026-08-12 |
| D26 | UnitConversionService | **RESOLVED (AG-48)** | Independent deterministic platform service — user-approved 2026-08-12 |
| D27 | CompatibilityEngine + CodeConfiguration | **RESOLVED (AG-49)** | Independent compatibility service; expanded extensible schema — user-approved 2026-08-12 |

**Implementation status:** AG-42 through AG-49 are **approved but not implemented**. See Section G.6–G.14.

### T.6 Scope and Priority


| #   | Decision                                | Options                                             |
| --- | --------------------------------------- | --------------------------------------------------- |
| D17 | MVP workflow priority | **RESOLVED (AG-26)** | Architecture-first per master specification — freeze 2026-08-12 |
| D18 | Scanned PDF support in MVP              | Yes (requires vision AI), No (CAD PDFs only), Defer |
| D19 | Is `Project_Specification.md` expected? | **RESOLVED (AG-51)** | No — `MASTER PROMPT V2.md` only |


---

## U. Phase 0 Platform Architecture Freeze (AG-54–AG-75)

**Status:** FROZEN — user-approved (2026-08-12). **Documentation only — not implemented.**

### U.1 Platform Vision (AG-54 — RESOLVED)

The platform is an **Engineering AI Platform**. **Structural Engineering** is the **initial engineering domain**. The architecture **MUST NOT** become Structural-only.

Future engineering domains (extension points only — not implemented): Mechanical, Electrical, Computer, Industrial, and other engineering disciplines. The **Core architecture must remain domain-independent**.

### U.2 Multi-Agent Scale and Registries (AG-55, AG-56 — RESOLVED)

| Scope | Target |
|-------|--------|
| **Current active agents** | **2 agents only** (initial implementation) |
| **Future scale** | Up to **~20 agents or more** without core rewrite |

Architectural concepts (not implemented): **Agent Registry**, **Capability Registry**, **Domain Registry**, **Workflow Registry**, **Domain Plugin Architecture**, **Hybrid Agent Orchestration** (AG-37), **Provider-agnostic AI Gateway** (AG-36).

Agents MUST NOT be hard-coded into platform core. Agents MUST NOT communicate directly with each other. Collaboration through **PEM** and **orchestration** only.

### U.3 Expanded Engineering Safety Principle (AG-57 — RESOLVED)

Strict separation required between: AI interpretation/planning | engineering calculations | analysis | design | verification | validation | approval.

**LLM may:** interpret, plan, route, explain, suggest.

**LLM MUST NOT silently:** invent critical engineering inputs; override validation; hide calculation failures; bypass approval gates; mark unverified results as final; replace deterministic engineering calculations.

*Extends G.5 and AG-37.*

### U.4 System Architecture Foundations (AG-58 — RESOLVED)

Preserves Section F: orchestrator, adapter isolation, tool-gated execution, PEM as collaboration hub, Integration Service boundary, modular engines. **Not implemented.**

### U.5 PEM, Integration, and Mock Policy (AG-59 — RESOLVED)

Preserves: **PEM as Single Source of Truth** (Section H); **Hybrid Integration Service** for CSI/CAD on Windows (Section L, Q); **mock adapter policy** — mocks labeled `MOCK`/`TEST ONLY`, never presented as real results (Section L); **modular CodeEngine** plugin architecture (Section M.1.3, M.3.4). **Not implemented.**

### U.6 Project Workspace (AG-60 — RESOLVED)

Every engineering project has an **isolated Project Workspace** containing or referencing:

Project metadata | members | configuration | code configuration | units | artifacts | requirements | PEM | execution graph | calculations | analysis | design | validation | quantities | BOQ | cost | reports | CAD outputs | revisions | audit history.

**Projects MUST remain isolated from each other.**

### U.7 Engineering Requirements (AG-61 — RESOLVED)

Requirements are **structured engineering data**. Origins: user input, uploaded files, existing models, codes, derived information.

Required attributes: **source**, **status**, **validation**, **revision**, **traceability**.

Status support: **UNKNOWN** | **PROPOSED** | **CONFIRMED** | **VALIDATED** | **APPROVED**.

Critical missing information MUST NOT be silently invented.

### U.8 Semantic Interpretation (AG-62 — RESOLVED)

Natural language and engineering files may be interpreted into a **Candidate Engineering Model**.

```text
Input → Semantic Interpretation → Candidate Engineering Model
     → Engineering Model Validation → PEM
```

Semantic interpretation is **NOT** engineering calculation.

### U.9 Engineering Geometry Core (AG-63 — RESOLVED)

**Domain-independent Engineering Geometry Core** supporting conceptually: parametric geometry, grids, levels, nodes, elements, sections, openings, connections, geometric constraints, 2D/3D representation, parameter change propagation.

Usable by: analysis, design, quantity takeoff, CAD.

### U.10 Materials and Components Catalog (AG-64 — RESOLVED)

Domain-independent catalogs for: materials, components, technical properties, units, applicability, provenance, revision, validity.

Catalog data does **NOT** replace engineering judgment. **DesignEngine** and **CodeEngine** remain responsible for engineering evaluation.

### U.11 Calculation Architecture (AG-65 — RESOLVED)

Engineering calculations must be **deterministic** where engineering computation is required.

Calculation definitions support: inputs, units, algorithms, dependencies, intermediate results, outputs, validation rules, code references, provenance, algorithm versioning.

**LLM is NOT the numerical authority.**

### U.12 Solver Architecture (AG-66 — RESOLVED)

Solver abstraction allowed. **Do NOT assume** the platform must rebuild existing specialized engineering solvers.

For Structural Engineering, **ETABS**, **SAP2000**, **SAFE** (AG-40) may provide specialized analysis/design solver capability via Integration Service adapters.

Internal solvers only where genuinely required. **Do NOT duplicate ETABS/SAP2000/SAFE unnecessarily.**

### U.13 Verification (AG-67 — RESOLVED)

External engineering software results must be **independently verifiable** where appropriate.

Verification may include: unit checks, dimensional checks, equilibrium checks, consistency checks, sanity/range checks, code consistency, completeness, independent simple calculations.

Verification is **NOT** a requirement to rebuild the external solver.

### U.14 Provenance (AG-68 — RESOLVED)

Engineering data must preserve provenance: source, source type, artifact, page/location (where applicable), extraction method, timestamp, revision, confidence, validation status, derived-from relationship, superseded-by relationship.

**IMPORTANT: Confidence is NOT Truth.**

### U.15 Assumptions and Uncertainty (AG-69 — RESOLVED)

Explicitly distinguish: **CONFIRMED** | **ASSUMED** | **UNKNOWN**.

Assumptions must be: visible, traceable, versioned, impact-aware, reviewable. No hidden engineering assumptions. Critical assumptions may require approval.

### U.16 Physical Quantities (AG-70 — RESOLVED)

Extends AG-48 / M.2. Physical quantities conceptually include: **magnitude**, **dimension**, **unit**, **metadata**.

Support: dimensional consistency, canonical representation, unit conversion, precision, display rounding separation. Incompatible dimensions must not be allowed in calculations.

### U.17 Domain Plugins and Workflows (AG-71 — RESOLVED)

Platform MUST support **domain plugins**. Core remains domain-independent.

Support: Domain Registry, Agent Registry, Capability Registry, Workflow Registry, domain-specific workflows/rules/calculations/validation/catalogs, extensible code profiles.

Adding a new engineering domain MUST NOT require rewriting core architecture.

### U.18 Code Intelligence (AG-72 — RESOLVED)

Code knowledge must be structured and traceable: code, edition, applicability, sections, rules, equations/requirements, provenance, versioning, retrieval, deterministic evaluation.

Do not hard-code all code logic in platform core. **CodeConfiguration** remains project-scoped.

### U.19 Optimization (AG-73 — RESOLVED)

Support: design alternatives, candidate generation, alternative comparison, multi-objective optimization, engineering constraints, cost/quantity/performance objectives, safety/code constraints, approval and selection.

Optimization does **NOT** replace analysis, design, or verification.

### U.20 Change Impact (AG-74 — RESOLVED)

Changes must propagate through dependencies. Support: dependency graph, change detection, impact analysis, stale-result detection, result invalidation, selective re-execution, revision integration.

Do not blindly rerun entire project when only a subset is affected. *Extends M.1.5 code change impact analysis.*

### U.21 Execution Safety (AG-75 — RESOLVED)

Engineering operations require appropriate preconditions. Support: safety gates, critical input classification, blocking conditions, explicit assumptions, validation gates, approval gates, external software compatibility gates, failure transparency, output release controls.

Invalid or incomplete critical inputs MUST block the affected engineering operation.

### U.22 Contradictions and Resolutions (Traceability)

| ID | Contradiction | Resolution |
|----|---------------|------------|
| C1 | AG-42–AG-49 approval-gate labels were redefined (2026-08-12) from earlier architecture-approval meanings | **Preserved:** Original content remains in Sections F, G, H, L, M. New AG-42–AG-49 labels are authoritative for agent/platform architecture. |
| C2 | AG-25 and AG-26 had no prior standalone definitions (numbering gap AG-24 → AG-27) | **Resolved at freeze:** AG-25 = data residency (local-first, hybrid optional); AG-26 = MVP workflow priority (architecture-first per master spec). |
| C3 | AG-53 previously described as requiring `"APPROVE PHASE 1"` message | **Resolved at freeze:** AG-53 = Phase 1 authorization gate **defined**; Phase 1 **NOT STARTED**. Future explicit implementation authorization still required before coding. |
| C4 | Project name "StructuralAIAgent" vs. platform vision "Engineering AI Platform" | **Resolved:** Structural Engineering is initial domain; core architecture is domain-independent (AG-54, AG-71). |
| C5 | D7 (vision model) listed OPEN in T.2 | **Resolved at freeze:** Vision routing via AI Gateway task-type model routing (AG-36); no separate provider decision. |

### U.23 Unresolved Architectural Ambiguities (Report Only — Do Not Invent)

| ID | Ambiguity | Status |
|----|-----------|--------|
| U-A1 | Specific identity/names of the **two initial agents** | Open — initial scope is two agents; exact agent roster selection deferred to Phase 4+ planning |
| U-A2 | **Deployment model** detail (AG-38): hybrid web + local service recommended but not user-explicitly specified before freeze | Resolved at freeze as hybrid/local-first aligned with CSI/CAD requirements; may be refined at Phase 1 planning |
| U-A3 | **Multi-user vs single-user** (AG-39) MVP scope | Resolved at freeze as single-user MVP initially, multi-user extensible later |
| U-A4 | D17 MVP workflow priority / D18 scanned PDF scope | Deferred to Phase 1+ planning — not blocking Phase 0 freeze |

---

# PHASE 0 APPROVAL GATE — FROZEN (AG-01 THROUGH AG-75)

**Freeze Date:** 2026-08-12  
**Phase:** PHASE 0 — **FROZEN / FREEZE CANDIDATE APPROVED**  
**Implementation:** **NOT STARTED** | **Phase 1:** **NOT STARTED**

All items **AG-01 through AG-75** are **RESOLVED**. Resolving an item records an architectural/documentation decision only — it does **NOT** authorize implementation, dependency installation, or Phase 1 work.

---

## Master Approval Index — ALL RESOLVED

| AG | Topic | Section | Status |
|----|-------|---------|--------|
| AG-01 | Greenfield status | B | RESOLVED |
| AG-02 | Phased development with stop gates | S | RESOLVED |
| AG-03 | Phase 0 deliverable document | — | RESOLVED |
| AG-04 | Design Code Selection Policy | M.1 | RESOLVED |
| AG-05 | CodeConfiguration PEM entity | H, M.1 | RESOLVED |
| AG-06 | Standard relationship model | M.1.3 | RESOLVED |
| AG-07 | Minimum supported standard families | M.1.2 | RESOLVED |
| AG-08 | Code conflict handling | M.1.6 | RESOLVED |
| AG-09 | Pre-design code disclosure gate | M.1.4 | RESOLVED |
| AG-10 | Code change impact analysis | M.1.5 | RESOLVED |
| AG-11 | AI code constraint behavior | M.1, G | RESOLVED |
| AG-12 | Unit System Policy | M.2 | RESOLVED |
| AG-13 | UnitConfiguration PEM entity | H, M.2 | RESOLVED |
| AG-14 | Canonical value storage | M.2.3 | RESOLVED |
| AG-15 | Deterministic unit conversion service | M.2.5, G.12 | RESOLVED |
| AG-16 | Dimensional consistency enforcement | M.2.4 | RESOLVED |
| AG-17 | CodeEngine unit interaction | M.2.6 | RESOLVED |
| AG-18 | UI unit system display | M.2.8 | RESOLVED |
| AG-19 | Default US Code Profile Policy | M.3 | RESOLVED |
| AG-20 | Five code profile types | M.3.2 | RESOLVED |
| AG-21 | Edition mismatch handling | M.3.5 | RESOLVED |
| AG-22 | Latest vs governing edition | M.3.6 | RESOLVED |
| AG-23 | NEWER_EDITION_AVAILABLE flag | M.3.7 | RESOLVED |
| AG-24 | Future editions as versioned packages | M.3.7 | RESOLVED |
| AG-25 | Data residency (local-first, hybrid optional) | T.3 D10, U.22 C2 | RESOLVED |
| AG-26 | MVP workflow priority (architecture-first) | T.6 D17, U.22 C2 | RESOLVED |
| AG-27 | Default jurisdiction US | M.1 | RESOLVED |
| AG-28 | Project-scoped code configuration | M.1 | RESOLVED |
| AG-29 | Default unit system US Customary | M.2 | RESOLVED |
| AG-30 | Default US code editions | M.3.1 | RESOLVED |
| AG-31 | MVP CodeEngine plugin priority | M.3.4 | RESOLVED |
| AG-32 | Backend Python + FastAPI | C, T.1 | RESOLVED |
| AG-33 | Frontend Next.js + React + TypeScript | C, T.1 | RESOLVED |
| AG-34 | Database PostgreSQL | C, O | RESOLVED |
| AG-35 | Version control Git + GitHub | C, T.1 | RESOLVED |
| AG-36 | AI Gateway provider-agnostic | G.1 | RESOLVED |
| AG-37 | Hybrid agent orchestration | G.2 | RESOLVED |
| AG-38 | Deployment model (hybrid/local-first) | Q, T.3, U.22 | RESOLVED |
| AG-39 | User model (single-user MVP, multi-user extensible) | T.3, U.22 | RESOLVED |
| AG-40 | CSI ETABS 23 / SAP2000 27 / SAFE 23 | L.1 | RESOLVED |
| AG-41 | AutoCAD 2027; DXF + DWG | K.1 | RESOLVED |
| AG-42 | Agent extensibility (2 now, extensible later) | G.6 | RESOLVED |
| AG-43 | Agent domain isolation | G.7 | RESOLVED |
| AG-44 | Agent Registry | G.8 | RESOLVED |
| AG-45 | Agent Contract / Interface | G.9 | RESOLVED |
| AG-46 | Orchestration and collaboration | G.10 | RESOLVED |
| AG-47 | Shared platform services access | G.11 | RESOLVED |
| AG-48 | UnitConversionService | G.12, M.2.5 | RESOLVED |
| AG-49 | CompatibilityEngine + CodeConfiguration | G.13 | RESOLVED |
| AG-50 | Phase 1 scope definition | S | RESOLVED |
| AG-51 | Specification scope (MASTER PROMPT V2 only) | B | RESOLVED |
| AG-52 | Phase 0 assessment approved / frozen | — | RESOLVED |
| AG-53 | Phase 1 authorization gate defined; Phase 1 NOT started | U.22 C3 | RESOLVED |
| AG-54 | Platform vision — Engineering AI Platform | U.1 | RESOLVED |
| AG-55 | Multi-agent scale and registries | U.2 | RESOLVED |
| AG-56 | Domain-independent core | U.1, U.2 | RESOLVED |
| AG-57 | Expanded engineering safety principle | U.3 | RESOLVED |
| AG-58 | System architecture foundations | U.4, F | RESOLVED |
| AG-59 | PEM SSOT; Integration Service; mock policy; CodeEngine | U.5, H, L, M | RESOLVED |
| AG-60 | Project Workspace isolation | U.6 | RESOLVED |
| AG-61 | Engineering Requirements model | U.7 | RESOLVED |
| AG-62 | Semantic Interpretation pipeline | U.8 | RESOLVED |
| AG-63 | Engineering Geometry Core | U.9 | RESOLVED |
| AG-64 | Materials and Components catalog | U.10 | RESOLVED |
| AG-65 | Calculation Architecture | U.11 | RESOLVED |
| AG-66 | Solver Architecture | U.12 | RESOLVED |
| AG-67 | Verification architecture | U.13 | RESOLVED |
| AG-68 | Provenance architecture | U.14 | RESOLVED |
| AG-69 | Assumptions and uncertainty | U.15 | RESOLVED |
| AG-70 | Physical quantities model | U.16 | RESOLVED |
| AG-71 | Domain Plugins and Workflows | U.17 | RESOLVED |
| AG-72 | Code Intelligence | U.18 | RESOLVED |
| AG-73 | Optimization architecture | U.19 | RESOLVED |
| AG-74 | Change Impact architecture | U.20 | RESOLVED |
| AG-75 | Execution Safety architecture | U.21 | RESOLVED |

---

### Repository and Process — RESOLVED

- [x] **AG-01:** Greenfield status — build from scratch per master specification.
- [x] **AG-02:** Phased development with stop gates — no automatic phase progression.
- [x] **AG-03:** `PHASE_0_ARCHITECTURE_ASSESSMENT.md` is the Phase 0 deliverable.

### Design Code Selection Policy — RESOLVED

- [x] **AG-04** through **AG-11:** Design Code Selection Policy (Section M.1) — all rules approved.

### Unit System Policy — RESOLVED

- [x] **AG-12** through **AG-18:** Unit System Policy (Section M.2) — all rules approved.

### Default US Code Profile Policy — RESOLVED

- [x] **AG-19** through **AG-24:** Default US Code Profile (Section M.3) — all rules approved.

### Data Residency and MVP Priority — RESOLVED

- [x] **AG-25:** Data residency — local-first; hybrid optional (aligned with CSI/CAD local Integration Service).
- [x] **AG-26:** MVP workflow priority — architecture-first per master specification phased roadmap.

### Engineering Domain Defaults — RESOLVED

- [x] **AG-27:** Default jurisdiction **US**.
- [x] **AG-28:** Code configuration project-scoped, user-controlled.
- [x] **AG-29:** Default unit system **US Customary**; SI/Metric fully supported.
- [x] **AG-30:** Default US Code Profile — IBC 2024, ASCE 7-22, ACI CODE-318-25, AISC 360-22.
- [x] **AG-31:** MVP CodeEngine plugin priority (M.3.4).

### Technology Decisions — RESOLVED

- [x] **AG-32:** Python + FastAPI | **AG-33:** Next.js + React + TypeScript | **AG-34:** PostgreSQL | **AG-35:** Git + GitHub — not implemented; Git not initialized.

### AI Configuration — RESOLVED

- [x] **AG-36:** Provider-agnostic AI Gateway | **AG-37:** Hybrid agent orchestration — not implemented.

### Deployment and Users — RESOLVED

- [x] **AG-38:** Deployment — hybrid web + local Integration Service (local-first for CSI/CAD).
- [x] **AG-39:** User model — single-user MVP initially; multi-user extensible later.

### External Software Integration — RESOLVED

- [x] **AG-40:** ETABS 23, SAP2000 27, SAFE 23 — not implemented.
- [x] **AG-41:** AutoCAD 2027; DXF + DWG — not implemented.

### Agent & Platform Architecture — RESOLVED

- [x] **AG-42** through **AG-49:** Agent extensibility, isolation, registry, contract, orchestration, shared services, UnitConversionService, CompatibilityEngine — not implemented.

### Scope and Phase Authorization — RESOLVED

- [x] **AG-50:** Phase 1 scope defined (schemas, project structure, persistence foundation — services deferred).
- [x] **AG-51:** No additional specification beyond `MASTER PROMPT V2.md`.
- [x] **AG-52:** Phase 0 assessment **approved and FROZEN**.
- [x] **AG-53:** Phase 1 authorization gate **defined** — **Phase 1 NOT STARTED**; future explicit implementation authorization required.

### Platform Architecture Freeze — RESOLVED

- [x] **AG-54:** Engineering AI Platform vision; Structural initial domain.
- [x] **AG-55:** Multi-agent architecture — 2 active now, ~20+ future; registries.
- [x] **AG-56:** Domain-independent core architecture.
- [x] **AG-57:** Expanded engineering safety principle.
- [x] **AG-58:** System architecture foundations (Section F).
- [x] **AG-59:** PEM SSOT; Integration Service; mock adapters; modular CodeEngine.
- [x] **AG-60:** Project Workspace isolation.
- [x] **AG-61:** Engineering Requirements structured data model.
- [x] **AG-62:** Semantic Interpretation → Candidate Model → PEM pipeline.
- [x] **AG-63:** Domain-independent Engineering Geometry Core.
- [x] **AG-64:** Materials and Components catalog architecture.
- [x] **AG-65:** Deterministic Calculation Architecture.
- [x] **AG-66:** Solver abstraction; external CSI solvers; no unnecessary duplication.
- [x] **AG-67:** Independent verification of external software results.
- [x] **AG-68:** Provenance architecture; confidence is not truth.
- [x] **AG-69:** Assumptions — CONFIRMED / ASSUMED / UNKNOWN.
- [x] **AG-70:** Physical quantities — magnitude, dimension, unit, metadata.
- [x] **AG-71:** Domain Plugins; Domain/Capability/Workflow Registries.
- [x] **AG-72:** Code Intelligence — structured, traceable, deterministic evaluation.
- [x] **AG-73:** Optimization architecture — does not replace analysis/design/verification.
- [x] **AG-74:** Change Impact — dependency graph, selective re-execution.
- [x] **AG-75:** Execution Safety — preconditions, gates, blocking on invalid critical inputs.

---

## Phase 0 Freeze Status Summary

| Item | Status |
|------|--------|
| **Phase** | PHASE 0 |
| **Phase 0 Status** | **FROZEN / FREEZE CANDIDATE APPROVED** |
| **AG-01 through AG-75** | **ALL RESOLVED** |
| **Implementation** | **NOT STARTED** |
| **Source Code** | **NOT CREATED OR MODIFIED** |
| **Dependencies** | **NOT INSTALLED** |
| **Agents** | **NOT IMPLEMENTED** |
| **Services** | **NOT IMPLEMENTED** |
| **Integrations** | **NOT IMPLEMENTED** |
| **Git** | **NOT INITIALIZED** |
| **Phase 1** | **NOT STARTED** |

---

**END OF PHASE 0 ASSESSMENT**

*Phase 0 Architecture Freeze complete (2026-08-12). AG-01 through AG-75: ALL RESOLVED. Only `PHASE_0_ARCHITECTURE_ASSESSMENT.md` modified. No source code created, modified, or deleted. No dependencies installed. No agents, services, or integrations implemented. Git not initialized. Project remains in PHASE 0. Phase 1 NOT STARTED.*