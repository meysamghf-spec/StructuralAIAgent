# Gemini platform orchestrator («رئیس پلتفرم»)

Status: **MVP, behind a flag, default OFF.** Code: `backend/app/application/orchestrator/`.

Gemini acts like an experienced structural engineer who sits at the keyboard of SAIA: it reads free-form Persian, Finglish or English
(«یک قاب ۵ طبقه ۳ دهانه بساز، تحلیل کن و بهینه کن»), picks the platform operations needed, runs them, assumes sensible defaults
(SI units, Iranian codes: 2800 v4, Mabhas 6, Mabhas 9) and says so, asks only for what is essential, and explains the results.

**Gemini never edits source code, never runs a shell or SQL and never touches billing.** It can only call the typed tools below.
A failure it cannot handle is explained to the user and reported through the existing mechanism (`report_engine_failure` → Platform Helper auto-report).

## Architecture

```
chat message ─► ConversationService._generate_assistant_response
                  ├─ (no attachments) _maybe_orchestrate ──► engine.run_turn ──► Gemini (OpenAI-compat tool calling)
                  │                                              │  ▲                 │ tool_calls
                  │                                              ▼  └─ tool digests ◄─ ToolRegistry.execute ► ConversationPort ► existing engines
                  └─ otherwise / on any failure: the rule-based pipeline (unchanged; the fast path and the fallback)
```

* `config.py` – env settings (below). `registry.py` – `Tool`, JSON-schema validation, whitelist, audit. `tools.py` – the 11 tools.
  `context.py` – `PlatformPort` protocol + `TurnContext`. `service_port.py` – `ConversationPort`: ownership, quotas, plan features, persistence.
  `engine.py` – the bounded loop. `prompt.py` – engineer persona + generated platform knowledge. `summaries.py` – model-facing digests.
  `intent.py` – deterministic yes/no and gating. `llm.py` – `GeminiToolLLM` (timeouts, circuit breaker).
* The model sees compact **digests** of tool results (never raw payloads); numbers in the answer must come from the digests.
* Model-visible text from tools/projects/files is declared DATA, never instructions (prompt-injection guard in the persona).
* The assistant message from Gemini is echoed back verbatim so Gemini-3 `thought_signature`s stay valid; parallel tool calls are handled.

### Modes (`PLATFORM_ORCHESTRATOR_MODE`)

| mode | behaviour |
|---|---|
| `off` (default) | nothing changes; the model is never called |
| `auto` | only compound requests (≥ 2 action families) or frame requests with incomplete inputs go to Gemini; everything else stays on the instant rule path |
| `always` | everything except greetings/trivia, "how do I…" FAQ, attachments, approval commands and assistant switches goes to Gemini first |

## Tools

All tools are whitelisted, schema-validated (unknown tools/arguments are rejected), project-ownership-checked, quota/plan-checked and audited.

| tool | access | maps to | notes |
|---|---|---|---|
| `get_platform_state` | read | context | current project/model/limits |
| `platform_knowledge` | read | help | answers "how do I / what can it do" from the generated platform knowledge |
| `list_projects` | read | projects | only the user's accessible projects |
| `open_project` | write | projects | switches the chat to a project the user owns |
| `create_project` | write | projects | counts against the plan's project quota |
| `get_current_model` | read | frame3d | inputs of the current 3D frame model |
| `analyze_frame` | write | frame3d | build / edit + analyse a 3D frame (≤10 storeys, ≤6 bays); `assume_defaults` fills gaps and reports them; uses `analyses_per_month` quota |
| `optimize_frame` | write | optimizer | needs the plan's `optimization` feature; time-boxed |
| `export_files` | write | downloads | e2k / f2k / s2k / dxf / report / figures / ZIP via the existing download pipeline |
| `analyze_beam` | write | beam | single RC beam check from a description |
| `list_approvals` | read | approvals | read-only: **approving/rejecting stays a human action** |

Deliberately absent: delete project (no service exists), billing/payment/plan changes, approve/reject, code editing, shell, SQL, file system.

## Safety

* **Confirmations are decided by the platform, not the model.** There is no `confirmed` argument in any schema. A call that overwrites
  a complete model (`analyze_frame` mode=`new`) stops, asks in chat, stores `orchestrator.pending` in the assistant message metadata and is
  only executed after a bare yes («بله/آره/باشه/ok/yes…»); «نه/لغو/cancel» drops it without any model call.
* Bounded loop: `MAX_STEPS` rounds (the last round is forced to text with `tool_choice=none`), `MAX_TOOL_CALLS`, per-call timeout, per-turn deadline.
* Idempotency inside a message (tool + hash of canonical args) – a repeated identical call returns the previous result.
* Audit: logger `saia.orchestrator.audit` (one JSON line per tool call and per turn, secrets redacted) + `orchestrator.trace` in message metadata.
* Rate limit per account (per worker) + circuit breaker (20 s after an error, 60 s after HTTP 429) so the free tier is protected.
* Ownership: every project id goes through `_project_access.list_accessible_projects`.
* Step-0 model failure → the rule-based pipeline answers as before. Failure after tools ran → a deterministic summary of the real results (`degraded`).

## Configuration (server)

| env | value for rollout | default |
|---|---|---|
| `LLM_GEMINI_API_KEY` | already set on the server for the Platform Helper (secret; do not log) | – |
| `PLATFORM_ORCHESTRATOR_MODE` | `auto` first, later `always` | `off` |
| `PLATFORM_ORCHESTRATOR_LLM_PROVIDER` | `gemini` | `gemini` |
| `PLATFORM_ORCHESTRATOR_LLM_MODEL` | empty (= `gemini-3.5-flash`) | empty |
| `PLATFORM_ORCHESTRATOR_MAX_STEPS` | `6` | `6` |
| `PLATFORM_ORCHESTRATOR_MAX_TOOL_CALLS` | `8` | `8` |
| `PLATFORM_ORCHESTRATOR_CALL_TIMEOUT_SECONDS` | `25` | `25` |
| `PLATFORM_ORCHESTRATOR_TURN_DEADLINE_SECONDS` | `100` | `100` |
| `PLATFORM_ORCHESTRATOR_OPTIMIZE_BUDGET_SECONDS` | `30` (max 40) | `30` |
| `PLATFORM_ORCHESTRATOR_MAX_TURNS_PER_HOUR` | `40` | `40` |
| `PLATFORM_ORCHESTRATOR_MAX_TOKENS` | `1500` | `1500` |

An unknown `PLATFORM_ORCHESTRATOR_MODE` value is treated as `off`. Rollback = set the mode to `off` (or unset) and restart; no migration is involved.

## Rollout plan

1. Merge with `off` (no behaviour change). 2. Back up, then set `auto` on the server; try with a test account. 3. Watch `saia.orchestrator.audit`,
the 429/503 rate and latency for a few days. 4. Move to `always` if quality is good. 5. Consider a paid tier / second provider before wide use.

## Free-tier limits and fallback

Gemini's free tier has small per-minute/day quotas and returns HTTP 429/503 under load (seen in local tests). The orchestrator treats this
as normal: the user still gets an answer from the rule-based pipeline (or a deterministic summary if tools had already run), and the
breaker avoids hammering the API. Enabling billing for Gemini is a decision for Meysam and is **not** done by this change.

## Known limitations

* A compound turn carries only the **last** tool's `engineering_results`. The chat renders a result card for `frame3d_analysis` only (the optimizer result is listed on the Optimization page, as with the rule-based path), so «بساز، تحلیل کن و بهینه کن» shows the explanation in text and no analysis card.
* Cross-message idempotency (a retried identical message) is not covered; the rate limit is per worker.
* Optimizer sections are not applied back to the model automatically.
* The model may misquote numbers; mitigation: numbers only from tool digests, full figures stay in the result card.
* The orchestrator consumes `analyses_per_month`, plain rule-based chat analysis does not.
* Export files are not verified in real ETABS/SAFE/SAP2000.
* `auto` only catches frame requests the rule parser recognises.

## Adding a tool

Register it in `tools.py` with a JSON schema, `maps_to`, access level and (if destructive) a `confirm` callable; add it to the table above
(`tests/test_platform_knowledge.py` fails otherwise) and add a registry test.

## Tests

`tests/test_orchestrator_{registry,engine,llm,e2e}.py` (offline, scripted Gemini), `tests/test_orchestrator_live_smoke.py`
(real Gemini; local only, skipped when `/home/box/secrets/gemini_api_key.txt` is missing).

## Demo screenshots

`ui-shots/gemini-orchestrator/fa-chat-{1440,412}.png` (not committed): Persian chat, compound request then «e2k و گزارش PDF رو بده» (download buttons).
They were produced by a local server running the real app/tools with a **scripted replay of Gemini** (the free-tier quota returned 429 during
the session), so they show the UI and the tool pipeline, not live Gemini wording. A real-Gemini run passed `test_orchestrator_live_smoke.py`.
