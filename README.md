# StructuralAIAgent

Chat-first structural engineering assistant. The current local product is a runnable Demo: register/login, projects, chat, file upload, project memory, agents/Agent Builder, and a graphical RC beam analysis result.

Phase 0 architecture remains frozen (`PHASE_0_ARCHITECTURE_ASSESSMENT.md`). Later engineering, auth, orchestration, CAD/CSI adapters, and payments are already in this repository. CSI/ETABS/SAP2000/SAFE/AutoCAD are labeled adapters — the Demo does not pretend they are executing unless connected.

**Investor/user Demo walkthrough:** [docs/DEMO.md](docs/DEMO.md)

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

## Prerequisites

- Python 3.12+
- Node.js 20+ and npm (for frontend)
- PostgreSQL 15+ (required for the Demo)

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Set `DATABASE_URL`, `FILE_STORAGE_ROOT`, and local auth secrets in `.env`. Do not commit `.env` or secrets.

Frontend API base (optional; defaults to `http://127.0.0.1:8000`):

```bash
set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## Start Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Apply PostgreSQL migrations through `020_conversations_foundation.sql` (or let the app apply them if `RUN_MIGRATIONS_ON_STARTUP` is enabled). Chat requires the conversations tables.

Health check:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Start Frontend

```bash
cd frontend
npm install
set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Demo prompt

After creating a project, in Chat:

`Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m.`

Expect a graphical result card: span 6.00 m, UDL 20.00 kN/m, **Mmax = 90.00 kN·m**, **Vmax = 60.00 kN**, labeled as a demonstration calculation.

## Run Tests

**Backend:**

```bash
cd backend
pip install -r requirements.txt
python -m pytest
```

Do not run backend tests in parallel against the shared test database.

**Frontend:**

```bash
cd frontend
npm install
npm test
npm run build
```

## Historical Phase 1 notes

Early milestones (M1–M5) established health, PEM persistence, the project API, the agent registry, and file ingestion. Those APIs remain. Later work added authentication, orchestration, chat, document extraction, the RC beam Demo visualization, structured agent-run progress, and incremental SSE for live agent execution.

See `PHASE_1_IMPLEMENTATION.md` for M1–M5 history. See [docs/DEMO.md](docs/DEMO.md) for the current Demo. Agent lifecycle and capability boundaries: [docs/AGENT_WORKSPACE.md](docs/AGENT_WORKSPACE.md).

## License

Proprietary — internal development.
