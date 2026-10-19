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

### 3D frame analysis (Phase 1)

`Analyze a 3-storey RC moment frame, 2x2 bays of 5 m in X and Y, storey height 3.2 m, columns 40x40 cm, beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, live load 2 kN/m2, equivalent static seismic C=0.165 in X and Y.`

Expect a **3D frame analysis** card (internal 3D direct-stiffness solver, rigid diaphragms): 36 nodes / 27 columns / 36 beams, seismic weight ≈ 3920 kN, base shear V = C·W ≈ 646.8 kN (reactions check PASS), max storey drift 0.7R·Δ/h ≈ **2.13 %** (storey 2, X and Y), beam max M⁻ ≈ **179.5 kN·m**, column max P ≈ **1175 kN**, plus per-storey drift / force tables and a plan view. Persian prompts work too, e.g. `قاب بتنی ۳ طبقه با ۲x۲ دهانه ۵ متر، ضریب زلزله C=0.165 را تحلیل کن`.
Missing storeys/bays produce a clear "please specify" message; omitted values use listed defaults (slab 12 cm, walls 7 kN/m, parapet 2 kN/m, roof live 1.5 kN/m², R = 5). Seismic C is user-supplied (`seismic_code = ASSUMED_C`); **no Iranian Standard 2800 or Mabhas 9 checks are performed yet** (planned next phases).

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
