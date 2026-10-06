# ACI 318 RC beam check

Deterministic rectangular RC beam flexure + concrete-shear check. This is a live engineering capability, not the graphical RC Beam Demo.

See [AGENT_WORKSPACE.md](AGENT_WORKSPACE.md) for agent, SSE, and UI integration. The Demo workflow remains in [DEMO.md](DEMO.md).

## Boundary

| Layer | Responsibility |
|-------|----------------|
| LLM / chat | Understand the request, extract parameters, ask for missing inputs, explain the result |
| `aci_rc_beam_check` | Validate inputs, convert units, compute or accept demands |
| `CodeEngineService` / `ACI318-25` | Numerical φMn and φVc |
| `UnitConversionService` | mm↔in, MPa↔psi, kN↔kip, kN·m↔kip-ft, mm²↔in² |
| `ValidationEngine` / orchestration `_validate_result` | Map capability/check status to agent validation events |

Calculations are not performed in React, FastAPI routes, LLM prompts, or SSE formatters.

## Worked example (hand-verifiable)

Inputs: `b = 300 mm`, `h = 500 mm`, `d = 450 mm`, `f'c = 25 MPa`, `fy = 400 MPa`, `As = 1500 mm²`, span `6 m`, `w = 20 kN/m`.

Demands: `Mu = wL²/8 = 90 kN·m`, `Vu = wL/2 = 60 kN`.

Whitney:

- `a = As fy / (0.85 f'c b) = 94.12 mm`
- `Mn = As fy (d − a/2) = 241.76 kN·m`
- `φMn = 0.90 Mn ≈ 217.59 kN·m`
- Flexure utilization `90 / 217.59 ≈ 0.414` → PASS

Shear uses the existing ACI plugin formula in US customary units, then converts `φVc` back to kN.

## Limitations

Listed in `AGENT_WORKSPACE.md`. Do not treat a PASS as a construction-ready design.
