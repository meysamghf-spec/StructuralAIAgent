# SAAI Demo

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

## 3D frame analysis (Phase 1)

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

### ETABS / SAFE / AutoCAD export (Phase 4)

After any 3D frame analysis, the result card shows download buttons for **`model.e2k`** (ETABS text model: stories, grids, materials, rectangular RC sections with cracked modifiers, points/lines per story, fixed base, rigid diaphragm D1, Dead/Live line loads, EX/EY *User Coefficient* with the C and k used by the analysis, mass source 1.0D + 0.2L, linear-static + modal cases, all strength combos), **`foundation.f2k`** (SAFE tables: column points with DEAD/LIVE/EX/EY loads = − base reactions, strength + service combos, a clearly labelled *placeholder* mat 1 m beyond the grid, t = 0.6 m, ks = 20000 kN/m³), **`plans.dxf`** (one plan per storey with grids/bubbles, COLUMNS/BEAMS layers, section labels and — after a Mabhas 9 design — rebar text) and **`frame3d.dxf`** (3D wireframe: LINEs with Z + 3D polylines per column stack). Files are generated on demand by `POST /api/v1/frame3d/export` from the card's model inputs; no CSI API, no new dependencies.

Follow-up prompts in the same project re-run the last frame and highlight the requested files: `خروجی ایتبس بده`, `فایل سیف برای فونداسیون بده`, `خروجی اتوکد قاب را بده`, `export to ETABS/SAFE/AutoCAD`.

Syntax status: e2k/f2k lines are copied from public files exported by ETABS 2016/21 and ETABS→SAFE 2014, and round-trip through our own parsers in `tests/test_csi_text_export.py`, **but no import into licensed ETABS/SAFE has been done yet**. Known gaps: EX/EY are written without the ±5 % eccentricity (set "X + Ecc. Y" in ETABS), the f2k mat tables are a placeholder written from memory of SAFE 12 (delete them if SAFE rejects them), and slabs are not shells (floor loads are already on the beams). DXF files are R12 ASCII and open in ezdxf with 0 errors.


The card adds group-wise design tables (beams: storey × direction × edge/interior; columns: storey × corner/edge/interior) with required As, suggested bars, stirrups/ties, D/C ratios, strong-column/weak-beam ratios per level, CSV downloads, and the lists of implemented vs simplified clauses. For the example: all member groups pass (max D/C 1.00; columns 8Φ16–12Φ16–8Φ22, ρ 1.0–1.9 %), SCWB min ratio 1.12 at level 2 → status CHECK.
Implemented: φc = 0.65, φs = 0.85, εcu = 0.0035, α1/β1 block; beam flexure with As,min / ρ ≤ 0.025 / yielding check / M⁺ ≥ M⁻/3; beam shear Vc = 0.2φc√f'c·bd with spacing and end-zone limits; column P–M strain compatibility, Pr,max = 0.8Pr0, 1–6 % steel, tie spacing; ΣMnc ≥ 1.2ΣMnb. Simplified/not checked: linear biaxial load contour, shear from analysis (no capacity design), centre-line moments, column shear, slenderness, joint shear, Ash confinement, development lengths. Forces come from the equivalent static cases.
