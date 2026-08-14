# Engineering AI Platform

AI-powered engineering platform with Structural Engineering as the initial domain. The core architecture is domain-independent and extensible for future engineering disciplines (Mechanical, Electrical, Computer, Industrial, and others).

**Current status:** Phase 1 — **Milestone 2** (Persistence + ProjectEngineeringModel Foundation)

Phase 0 architecture is frozen (`PHASE_0_ARCHITECTURE_ASSESSMENT.md`). AG-01 through AG-75 are resolved.

Milestone 1 delivered repository bootstrap. Milestone 2 adds PostgreSQL persistence for projects, versioned PEM snapshots (JSONB), and revisions.

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

**Not implemented in M1–M2:** agents, LLM, CSI/CAD integrations, CodeEngine, CompatibilityEngine, UnitConversionService, REST project API.

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

Milestone 2 adds `002_pem_foundation.sql` (projects, PEM snapshots, revisions). Apply when PostgreSQL is available:

```bash
psql "$DATABASE_URL" -f database/migrations/001_bootstrap.sql
psql "$DATABASE_URL" -f database/migrations/002_pem_foundation.sql
```

Persistence integration tests require a reachable PostgreSQL instance (`DATABASE_URL` or `TEST_DATABASE_URL`).

## Phase 1 Milestone 2 Scope

This milestone delivers:

- PostgreSQL schema: `projects`, `pem_snapshots` (JSONB), `revisions`
- Domain models: `ProjectEngineeringModel`, `CodeConfiguration`, `UnitConfiguration`, `Revision`
- Repository/service boundaries (domain ← infrastructure)
- Software-default code profile and US Customary unit defaults in initial PEM
- Backend persistence tests (integration tests skip if PostgreSQL unavailable)

**Milestone 3 has NOT started.**

## License

Proprietary — internal development.
