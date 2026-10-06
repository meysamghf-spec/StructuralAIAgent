# Cursor-like Agent Workspace

StructuralAIAgent remains a **chat-first** structural engineering product. The workspace now surfaces real agent execution as structured progress, tools, context, and approval — without becoming a generic IDE and without replacing the existing orchestration stack.

## Architecture

```
Frontend chat
  → POST /api/v1/chat
  → ConversationService
  → AgentOrchestrationService / AgentRuntimeService
  → AgentCapabilityCatalog + AgentAccess / entitlements
  → deterministic engineering handlers / validation
  → Human Approval Gate when required
  → chat message metadata.agent_run
```

`agent_run` is a **view** of the existing `AgentExecutionRecord`. It is not a second run table, capability registry, or orchestration pipeline.

## Agent lifecycle

Derived from the existing execution progress (`queued`, `in_progress`, `awaiting_approval`, `blocked`, `completed`, `failed`, …):

| Lifecycle | Meaning |
|-----------|---------|
| planning | Request accepted, workflow not running yet |
| executing | Authorized capability is running |
| waiting_for_approval | Human Approval Gate is blocking completion |
| completed | Terminal success |
| failed | Failed, rejected, or cancelled |
| blocked | Missing inputs / additional information required |

Progress steps shown in chat (`Understanding request`, `Loading project context`, `Reading documents`, capability execution, `Validating results`, approval, `Final response`) are mapped from that record. Document steps appear only when attachments exist. There is no frontend timer that invents extra “thinking” steps.

## Incremental streaming (SSE)

`POST /api/v1/chat` remains the JSON fallback.

`POST /api/v1/chat/stream` uses Server-Sent Events. The route only authenticates, resolves the conversation, and opens the stream. `ConversationService.iter_send_events` runs the existing `send_message` path and forwards progress from `AgentOrchestrationService`. There is no second orchestrator and no timer-based fake progress.

Frontend: `streamChatMessage` in `chat-api.ts` parses events, `useChat` updates the in-flight assistant `agent_run`, and `AgentProgress` / tool / context / error cards re-render from that view. If the stream fails, `useChat` falls back to `POST /api/v1/chat`.

### Event types

| Event | When it is emitted |
|-------|--------------------|
| `agent_run.started` | User message persisted |
| `agent_run.step` | A real lifecycle step starts or finishes |
| `agent_run.context` | Project context assembled |
| `agent_run.tool` | A catalog capability or document action is in use. Optional fields carry real file, count, artifact, and error metadata |
| `agent_run.validation` | Deterministic validation status is known |
| `agent_run.approval_required` | Human Approval Gate created, or chat persisted an awaiting-approval result |
| `agent_run.completed` | Assistant message persisted after a successful run |
| `agent_run.failed` | Blocked, failed, rejected, cancelled, or a safe application error |

Steps that did not happen are not emitted. A fast handler may complete in the same stream burst as `started`.

The connection closes after the worker finishes. Client disconnect sets a cancellation flag so further events are not queued; execution still completes so the conversation record stays consistent.

`STREAMING_CAPABILITIES` is `{ supported: true, transport: "sse" }`.

### Rich tool events

`agent_run.tool` stays the same event type. Payloads are built by `agent_run_tool_payloads.py` from attachment context and the existing `AgentResult`. The frontend aggregates events that share a tool `id` into one `ToolExecutionCard`.

Optional fields (omit anything unknown):

| Field | Meaning |
|-------|---------|
| `operation` / `operations` | Real stage such as `DOCUMENT_DISCOVERED`, `DOCUMENT_INDEXED`, `DOCUMENT_SEARCHED`, `DOCUMENT_READ`, `ENGINEERING_ANALYSIS`, `CAD_GENERATION`, `REPORT_GENERATION`, `RESULT_VALIDATION` |
| `details` | `{ key, label, state }` rows. `key` lets later events update the same row |
| `files` | Authorized filename, type, availability, and `page_count` only when a parser provided an integer |
| `counts` | Real integers already known (`members`, `load_combinations`, `relevant_sections`) |
| `artifacts` | Existing artifact identifiers/names/types. No filesystem paths |
| `actions` | Existing workspace links (`View context`, `View analysis`) |
| `error` | Safe title/reason |

Document metadata is emitted only when attachment context already has it. Indexing events are not sent for stored-only files. Page counts are never invented. Engineering counts come from `model_summary` / load summaries already produced by deterministic handlers. Demo RC beam tool events say that deterministic analysis completed; numerical results stay on `EngineeringResultCard`.

Security: tool events must not include API keys, tokens, credentials, server paths, connection strings, stack traces, or raw document text.

### Event aggregation

SSE may emit several `agent_run.tool` events for one execution (`DOCUMENT_DISCOVERED` then `DOCUMENT_INDEXED` then `DOCUMENT_SEARCHED`). `applyAgentRunEvent` merges them by tool `id` and detail `key`. Older events that only have `id`, `name`, `status`, and `details` remain renderable. Unknown optional fields are ignored.

### How a future capability should emit events

Do not add a frontend event list or a second runtime. At a real handler/orchestration transition, call `emit_progress(sink, EVENT_TOOL, {"tool": capability_tool_payload(...)})` or extend `capability_tool_payload` with facts the handler already knows. Reuse the same tool `id` so the UI aggregates. Never emit a field the implementation did not compute. The chat stream and `build_agent_run_view` share these builders.

## Capabilities

Capability selection still goes through:

- `AgentCapabilityCatalog` / `get_agent_capability_profile`
- existing intent routing (`agent_intent_routing.py`) when mode is **Auto** or **Design**
- entitlement / access checks inside `AgentOrchestrationService`

The lightweight composer modes are hints, not a second registry:

| Mode | Effect |
|------|--------|
| Auto (default) | Existing routing selects the agent type |
| Analyze | `ANALYSIS_AGENT` |
| Design | No forced type — routing chooses concrete vs steel |
| CAD | `CAD_AGENT` |
| Documents | `DOCUMENT_INTERPRETATION_AGENT` |
| Reports | `REPORTING_AGENT` |

Unauthorized or entitled-but-unavailable capabilities still fail in the existing access layer. The UI shows the resulting failed run; it does not execute the capability.

## Progress events

Assistant message metadata includes:

- `progress` / `execution_status` — existing user-facing status
- `status_events` — backward-compatible strings
- `agent_run.steps` — structured `{ key, label, state }`
- `agent_run.tools` — structured capability/document actions, including optional file, count, artifact, and error metadata when those facts already exist
- `agent_run.context` — conversation, project, files, indexed document count
- `agent_run.error` — safe title/reason (no stack traces)

Frontend components: `AgentProgress`, `ToolExecutionCard`, `AgentContextStrip`, `AgentErrorCard`.

## Human approval

Consequential agent types still require the existing Human Approval Gate. Chat shows:

- `requires_approval` / `approval_request_id`
- an in-thread `ApprovalReviewPanel`
- an approval step in `agent_run` when a request exists

The client cannot approve by setting a flag. Approval remains an explicit engineer action.

## Project File Tree

The sidebar Files section is a **view** over existing project files. It does not create a second document store, file repository, indexer, or runtime.

```
Existing Project Files
        ↓
GET /api/v1/projects/{project_id}/files
        ↓
Project File Tree
        ↓
Chat / Context / File actions
```

Source of truth: `project_files` via `FileRegistryService` and `GET /api/v1/projects/{project_id}/files`. The router already requires `get_accessible_project`. A file is listed only when it belongs to that project; another project's `file_id` returns 404. Server `storage_path` is never returned.

Folders are not a backend concept (`filename` is flat and path separators are rejected). The tree is a flat authorized list. Do not invent a hierarchy.

Safe metadata shown: `file_id`, `filename`, `file_type`, `parsing_status`, `extraction_status`, dates, and `byte_length` when ingestion already recorded it. Indexing status is omitted because the list API does not persist an indexing field — do not infer it from filename or type.

Actions (only existing APIs):

- **Use in chat** — reuses the existing `file_id` as a composer attachment. No second upload.
- **Download** — `GET /api/v1/projects/{project_id}/files/{file_id}/content`.
- **Upload file** (empty state) — existing `POST /api/v1/projects/{project_id}/files`, then refresh the list.

Selecting a file opens the existing context panel with filename, type label, availability from parsing/extraction status, and the current project name. Raw document contents are not loaded to render the tree.

The tree clears immediately when the project changes, then loads that project's files. Composer uploads refresh the same list. Loading / empty / error + Retry states never use mock files. Desktop keeps the sidebar; tablet/mobile still use the existing drawer.

## Chat and files

Chat remains the primary surface. Users attach ETABS/SAFE/SAP2000/DWG/DXF/PDF/DOCX/XLSX/images in the composer, or attach an existing project file from the tree. Attachments become conversation message chips and `attachment_context` on the execution using the existing `file_id`.

## Security boundaries

Unchanged:

- Authentication required for `/api/v1/chat`
- Conversation ownership checks
- `ProjectAccessService` for every project-scoped file and execution
- Capability entitlements before handler execution
- Server-side approval policy (client `requires_approval` is not trusted)
- Tool events never include secrets, server filesystem paths, raw document text, or stack traces

## Engineering calculation boundary

LLMs may interpret intent, plan, select a catalog capability, and summarize. Numerical analysis, code checks, and Demo RC beam results still come from deterministic services. The completed graphical RC Beam Demo (`EngineeringResultCard` → `RCDemoVisualization`) is unchanged.

## ACI 318 RC beam check (live capability)

This is the first **non-demo** structural calculation exposed through chat. It is not a CSI/ETABS/SAP2000/SAFE/AutoCAD integration.

```
User
  → Chat (POST /api/v1/chat or /chat/stream)
  → AgentOrchestrationService
  → AgentCapabilityCatalog (CONCRETE_DESIGN_AGENT / design.concrete.beam.aci318)
  → ConcreteDesignAgentHandler
  → aci_rc_beam_check.run_aci_rc_beam_check
  → CodeEngineService (ACI318-25 plugin) + UnitConversionService
  → AgentResult kind aci_rc_beam
  → SSE tool/validation events
  → AciRcBeamResultCard
```

### What it does

Simplified **ACI CODE-318-25** rectangular RC beam:

- Flexure: Whitney rectangular stress block with the **provided** tension steel `As` (`φ = 0.90` assumed tension-controlled)
- Shear: concrete only, `φVc = 0.75 · 2√f'c · b · d` (no stirrups / `Vs`)

Demands are either user-supplied `Mu` and `Vu`, or computed from user-supplied span and UDL as `M = wL²/8`, `V = wL/2`. Those formulas are used only when the user provided `w` and `L`. The service does not invent loads, `As`, or section sizes.

### Required inputs

| Input | Type | Unit (chat) | Range | Required |
|-------|------|-------------|-------|----------|
| Width `b` | float | mm | 100–2000 | yes |
| Height `h` | float | mm | 150–3000 | yes |
| Effective depth `d` | float | mm | 50–2800 and `< h` | yes |
| `f'c` | float | MPa | 15–80 | yes |
| `fy` | float | MPa | 280–600 | yes |
| `As` | float | mm² | 50–20000 | yes |
| Demands | pair | `Mu`+`Vu` (kN·m, kN) **or** span (m) + UDL (kN/m) | see service ranges | yes |
| Design code | project `CodeConfiguration` | — | ACI CODE-318-25 | yes |

Missing inputs produce `MISSING_REQUIRED_INPUT` and a request for the missing values. Invalid ranges produce `INVALID_INPUT`. Neither path invents defaults or creates a Human Approval request.

### Units

- **Input (chat):** SI — mm, MPa, kN, kN·m, mm²
- **Internal:** US customary for the existing ACI plugin — in, psi, kip, kip-ft, in² via `UnitConversionService` (`mm` / `mm2` already on that service)
- **Output:** both SI and US customary on the structured payload

Do not mix SI and US values in one field. Do not add a second converter.

### Code / configuration

Uses the project's existing `CodeConfiguration`. Software default is `ACI CODE-318-25` → plugin `ACI318-25`. Other ACI editions and Eurocode return `UNSUPPORTED_CODE`. The product does not pretend those checks ran.

`CodeEngineService.validate_configuration` is recorded on completed results. Member checks go through `CodeEngineService.run_check` (`CONCRETE_BEAM_FLEXURE`, `CONCRETE_BEAM_SHEAR`).

### Agent integration

- Catalog: `CONCRETE_DESIGN_AGENT` capability `design.concrete.beam.aci318`
- Routing: design + beam / ACI / RC terms. "Analyze a simply supported…" still hits the **Demo** analysis path, not this check
- Authorization: existing project access, entitlements, and capability profile
- Approval: completed PASS/FAIL checks require the Human Approval Gate. Missing/invalid/unsupported do not
- Files: project attachments are **not** parsed for demands. The agent says so if files are present

### Tool / SSE events

`capability_tool_payload` emits `ENGINEERING_CODE_CHECK` and real flexure/shear outcomes when `aci_rc_beam` is present. No invented member counts, durations, or load-combination totals.

`POST /api/v1/chat/stream` is unchanged. Non-streaming `POST /api/v1/chat` remains the JSON fallback.

### UI

`AciRcBeamResultCard` shows inputs, results, validation, assumptions, units, and warnings. The Demo card / `RCDemoVisualization` is not used for this payload (`kind: aci_rc_beam`).

### Not supported

- Stirrup design / `Vs` / `Av`
- Strain-based φ transition (φ flexure is fixed at 0.90)
- ρmin / ρmax as a hard code rejection
- Slabs, columns, walls, foundations
- ACI 318-19 or earlier, Eurocode 2, CSA, or other concrete codes
- Reading Mu/Vu from ETABS, SAP2000, SAFE, DWG, PDF, or spreadsheets
- Internal frame analysis / CSI solvers
- Construction documents

Example: `Check this RC beam per ACI 318: span 6 m, 20 kN/m, b=300 mm, h=500 mm, d=450 mm, fc=25 MPa, fy=400 MPa, As=1500 mm2.`

## How to add a capability

1. Add or extend an `EngineeringAgentType` profile in `agent_capability_catalog.py`.
2. Implement or reuse a handler in `engineering_agent_handlers.py`.
3. Route keywords in `agent_intent_routing.py` if Auto should select it.
4. Register entitlements / approval policy if the operation is consequential.
5. Let `build_agent_run_view` derive progress/tools from the existing execution record.

Do not add a parallel capability list in the frontend.
