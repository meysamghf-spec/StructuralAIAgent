# StructuralAIAgent Demo

Chat-first structural engineering workspace for local demonstration.

This Demo uses deterministic calculations and labeled adapters. It does not execute ETABS, SAP2000, SAFE, or AutoCAD.

## Backend

1. Copy `.env.example` to `.env` and set `DATABASE_URL`, `FILE_STORAGE_ROOT`, and `AUTH_JWT_SECRET` locally. Do not commit secrets.
2. Apply migrations, including `database/migrations/020_conversations_foundation.sql`.
3. Start the API:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

## Frontend

```bash
cd frontend
npm install
set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Demo workflow

1. Register a new account.
2. Sign in.
3. Open **Projects** and create a project, for example `RC Beam Demo`.
4. Return to Chat and select that project.
5. Ask:

   `Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m.`

6. Confirm the chat result shows the graphical RC beam Demo:
   - simply supported beam / UDL diagram (6.00 m, 20.00 kN/m)
   - bending moment diagram (Mmax = 90.00 kN·m at midspan)
   - shear force diagram (V = +60 kN → 0 → −60 kN)
   - synchronized hover readout for x, M(x), and V(x)
   - RC cross-section (300 × 500 mm, d = 450 mm)
   - parameters (fc = 25 MPa, fy = 400 MPa) and result summary
   - completed workflow/status strip
7. Upload an engineering document (PDF, DOCX, XLSX, CSV, DXF, or image) and ask a follow-up question about it.
8. Inspect **Project memory** in the right context panel or `/workspace/memory`.
9. Open **Agents** and **Agent Builder**.
10. Sign out.

## Graphical RC beam Demo

The visualization is embedded in the chat assistant result (`EngineeringResultCard` → `RCDemoVisualization`). It is not a separate dashboard.

Diagrams are derived from the existing `engineering_results` payload:

- `M(x) = Rx − wx²/2`
- `V(x) = R − wx`
- `R = wL/2`

If span, load, or result values are missing, the UI falls back to the textual field grid and does not invent diagrams.

This is a deterministic demonstration calculation, not a substitute for engineer review or project-specific code compliance.

For a live ACI 318 flexure/shear check that uses provided `As` and does not invent parameters, see [ACI_RC_BEAM_CHECK.md](ACI_RC_BEAM_CHECK.md). Do not confuse the two: the Demo reports `M` and `V` only; the ACI check reports `φMn`, `φVc`, and utilizations.

The RC beam numbers are a labeled demonstration: `M = wL²/8`, `V = wL/2`. Final engineering decisions require a qualified engineer.
