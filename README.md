# Engineering AI Platform

AI-powered engineering platform with Structural Engineering as the initial domain. The core architecture is domain-independent and extensible for future engineering disciplines (Mechanical, Electrical, Computer, Industrial, and others).

**Current status:** Phase 1 — **Milestone 5** (File Ingestion Foundation — uncommitted)

Phase 0 architecture is frozen (`PHASE_0_ARCHITECTURE_ASSESSMENT.md`). AG-01 through AG-75 are resolved.

Milestone 1 delivered repository bootstrap. Milestone 2 adds PostgreSQL persistence for projects, versioned PEM snapshots (JSONB), and revisions. Milestone 3 exposes project/PEM/revision operations via `/api/v1`. Milestone 4 adds the platform-scoped Agent Foundation registry (definitions, versions, capabilities, prompt templates). Milestone 5 adds project-scoped file registration, local filesystem storage, synchronous ingestion, and a stub parser contract.

## Architecture Overview

```
engineering-ai-platform/
├── backend/          FastAPI API (Python)
├── frontend/         Next.js + React + TypeScript
├── engineering/      Calculation, units, validation, provenance boundaries
├── agents/           Agent contracts, runtime, orchestration boundaries
├── workers/          Background job processing boundary
├── integrations/     ETABS, SAP2000, SAFE, AutoCAD adapter boundaries
├── database/         PostgreSQL migrations
├── tests/            Golden, integration, e2e test placeholders
└── docs/             Project documentation
```

**Layered backend:** `api` → `application` → `domain` ← `infrastructure`

**Not implemented in M1–M5:** Meta-Agent runtime, Prompt Engineering Agent runtime, LLM execution, orchestration, CSI/CAD integrations, CodeEngine, CompatibilityEngine, UnitConversionService, authentication, production file parsers (DWG/PDF/OCR).

## Prerequisites

- Python 3.12+
- Node.js 20+ and npm (for frontend)
- PostgreSQL 15+ (for database; bootstrap migration optional in M1)

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Supported variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Application environment | `development` |
| `API_PORT` | Backend port | `8000` |
| `DATABASE_URL` | PostgreSQL connection string | see `.env.example` |
| `FILE_STORAGE_ROOT` | Local directory for uploaded files (outside repo) | sibling dir `structuralaiaagent_file_storage` |
| `MAX_UPLOAD_BYTES` | Maximum upload size in bytes | `10485760` (10 MiB) |

Do not commit `.env` or secrets.

## Start Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### M5 File API Examples

Upload a project file (multipart form field `file`):

```bash
curl -X POST http://localhost:8000/api/v1/projects/{project_id}/files \
  -H "X-Actor-Id: engineer-1" \
  -F "file=@notes.txt;type=text/plain"
```

List project files:

```bash
curl http://localhost:8000/api/v1/projects/{project_id}/files
```

Download stored content:

```bash
curl -OJ http://localhost:8000/api/v1/projects/{project_id}/files/{file_id}/content
```

### M4 Agent API Examples

Create an agent definition:

```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"key":"example-agent","name":"Example Agent"}'
```

Create and activate a version:

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/versions \
  -H "Content-Type: application/json" \
  -H "X-Actor-Id: engineer-1" \
  -d '{"instructions":"System instructions","capability_keys":["routing"]}'

curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/versions/1/activate
```

Create a versioned prompt template:

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/versions/1/prompts \
  -H "Content-Type: application/json" \
  -d '{"name":"system","template":"You are {{role}}","variables_schema":{"role":"string"}}'
```

### M3 API Examples

Create a project:

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "X-Actor-Id: engineer-1" \
  -d '{"name":"Tower A","description":"Test project"}'
```

Get current PEM:

```bash
curl http://localhost:8000/api/v1/projects/{project_id}/pem/current
```

Update PEM (creates new snapshot + revision):

```bash
curl -X PUT http://localhost:8000/api/v1/projects/{project_id}/pem \
  -H "Content-Type: application/json" \
  -d '{"pem":{...},"change_type":"PEM_UPDATE","summary":"Updated metadata"}'
```

## Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Run Tests

**Backend:**

```bash
cd backend
pip install -r requirements.txt
pytest
```

**Frontend:**

```bash
cd frontend
npm install
npm test
```

## Database (Migrations)

Milestone 2 adds `002_pem_foundation.sql` (projects, PEM snapshots, revisions). Milestone 4 adds `003_agent_foundation.sql` (agent registry). Milestone 5 adds `004_file_ingestion_foundation.sql` (project files). Apply when PostgreSQL is available:

```bash
psql "$DATABASE_URL" -f database/migrations/001_bootstrap.sql
psql "$DATABASE_URL" -f database/migrations/002_pem_foundation.sql
psql "$DATABASE_URL" -f database/migrations/003_agent_foundation.sql
psql "$DATABASE_URL" -f database/migrations/004_file_ingestion_foundation.sql
```

Persistence integration tests require a reachable PostgreSQL instance (`DATABASE_URL` or `TEST_DATABASE_URL`).

## Phase 1 Milestone 5 Scope (uncommitted)

This milestone delivers:

- Project-scoped file registry (`project_files` table)
- Local filesystem storage via `FILE_STORAGE_ROOT` (outside source tree)
- Synchronous upload → validate → store → detect type → stub parser → status update
- Domain contracts: `FileParserProtocol`, `FileStorageProtocol`
- Application services: `FileRegistryService`, `FileIngestionService`
- REST API under `/api/v1/projects/{project_id}/files`
- M5 allowlist: `.txt` / `text/plain` only (foundation testing)
- Backend version `0.5.0`

**Not implemented:** PEM mutation from files, production parsers, delete/archive, cloud storage, background workers, authentication.

## Phase 1 Milestone 4 Scope (complete)

## Phase 1 Milestone 3 Scope (complete)

This milestone delivers:

- REST API under `/api/v1` for projects, PEM (current/historical), and revisions
- Application services: `PemRevisionService`, `RevisionService` (PEM PUT creates snapshot + revision)
- API DTOs, consistent error envelope, optional `X-Actor-Id` header
- Development CORS for `http://localhost:3000`
- API integration tests against PostgreSQL
- OpenAPI documentation at `/docs`

## Phase 1 Milestone 2 Scope (complete)

This milestone delivered:

- PostgreSQL schema: `projects`, `pem_snapshots` (JSONB), `revisions`
- Domain models: `ProjectEngineeringModel`, `CodeConfiguration`, `UnitConfiguration`, `Revision`
- Repository/service boundaries (domain ← infrastructure)
- Software-default code profile and US Customary unit defaults in initial PEM
- Backend persistence tests (integration tests skip if PostgreSQL unavailable)

## License

Proprietary — internal development.
