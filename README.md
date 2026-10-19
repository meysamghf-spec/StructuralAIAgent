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

### Standard 2800 seismic loads + modal / response spectrum (Phase 2)

`Analyze a 3-storey RC intermediate moment frame, 2x2 bays of 5 m in X and Y, storey height 3.2 m, columns 40x40 cm, beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, live load 2 kN/m2, Standard 2800, high seismic hazard, soil type II, I=1.`

Persian: `قاب خمشی بتنی متوسط ۳ طبقه با ۲x۲ دهانه ۵ متر، خطر نسبی زیاد، نوع خاک ۲، ضریب اهمیت ۱ را طبق ۲۸۰۰ تحلیل کن`

Expect (Arak-type case): T = 0.05·H^0.75 = 0.273 s, B1 = 2.5, N = 1, **C = A·B·I/R = 0.30·2.5·1/5 = 0.150** (Cmin 0.036), V = 588.0 kN, max drift Cd·Δ/(I·h) = **2.49 %** ≤ 2.5 % (PASS); modal T1 ≈ **0.83 s** (83 % mass), response-spectrum V_dyn ≈ 325 kN = 55 % of static → scaled ×1.54 to 85 %.
Implemented: zone A, soil I–IV spectrum (T0, Ts, S, S0), B1·N, empirical period, I, R/Cd for RC/steel moment frames, Cmin = 0.12AI, k-exponent vertical distribution (4th ed.), 5 % accidental eccentricity, Cd/I drift with 2.5 %/2.0 % limits, modal analysis on diaphragm DOFs, CQC response spectrum and 85 %/90 % scaling. Simplified: empirical period only for C, drift from design forces, no accidental torsion in dynamic cases, no 100 %+30 % orthogonal combination, no irregularity checks.

### Mabhas 9 RC design (Phase 3)

Add `design per Mabhas 9` to the Phase 2 prompt, e.g.
`Analyze and design per Mabhas 9 a 3-storey RC intermediate moment frame, 2x2 bays of 5 m in X and Y, storey height 3.2 m, columns 40x40 cm, beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, live load 2 kN/m2, Standard 2800, high seismic hazard, soil type II, I=1.`
(Persian: `... طبق ۲۸۰۰ تحلیل و طبق مبحث نهم طراحی کن`).

The card adds group-wise design tables (beams: storey × direction × edge/interior; columns: storey × corner/edge/interior) with required As, suggested bars, stirrups/ties, D/C ratios, strong-column/weak-beam ratios per level, CSV downloads, and the lists of implemented vs simplified clauses. For the example: all member groups pass (max D/C 1.00; columns 8Φ16–12Φ16–8Φ22, ρ 1.0–1.9 %), SCWB min ratio 1.12 at level 2 → status CHECK.
Implemented: φc = 0.65, φs = 0.85, εcu = 0.0035, α1/β1 block; beam flexure with As,min / ρ ≤ 0.025 / yielding check / M⁺ ≥ M⁻/3; beam shear Vc = 0.2φc√f'c·bd with spacing and end-zone limits; column P–M strain compatibility, Pr,max = 0.8Pr0, 1–6 % steel, tie spacing; ΣMnc ≥ 1.2ΣMnb. Simplified/not checked: linear biaxial load contour, shear from analysis (no capacity design), centre-line moments, column shear, slenderness, joint shear, Ash confinement, development lengths. Forces come from the equivalent static cases.

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
