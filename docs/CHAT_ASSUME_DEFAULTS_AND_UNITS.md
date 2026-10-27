# «Assume defaults and optimize» + project units

## Behaviour (after PR #49)
- «پیش‌فرض‌ها را فرض کن و بهینه کن», "assume defaults and optimize", Finglish "pishfarz ha ro farz kon va behine kon":
  one message is an optimize request *and* an assume request -> `frame_optimizer.build_optimization_from_chat`
  fills missing geometry with `frame3d_followup.DEFAULTS` (4 storeys, 3x3 bays of 5 m, 3.2 m, columns 50x50,
  beams 40x50, 2800 + Mabhas 9), lists the assumptions and runs the optimization. No prerequisites list is returned.
- «پیش‌فرض‌ها را فرض کن» alone right after the prerequisites checklist is merged with the pending optimize request
  (`frame_optimizer.merge_assume_with_checklist`).
- `is_optimize_request` also recognises Finglish «behine / behineh / behine sazi» and Arabic-yeh «بهينه».

## Units
- New Iranian-code projects are created with SI (kN, m, MPa).
- Existing projects may still store the old never-confirmed US_CUSTOMARY *default*. `effective_unit_configuration`
  (pure, idempotent) resolves it to SI at **read time** for Iranian codes (model API, project context -> chat workflow
  assumptions, drawing-sheet title block). Stored rows are not rewritten; user-confirmed units and US-code projects are
  unchanged. No data migration is required.
- NOT changed on purpose: `structural_solver_integration_service` (CSI target units) and PEM snapshots written by
  analysis/design engines still copy the stored value; changing them would alter solver payloads of existing projects.
  If a data migration is ever wanted: `UPDATE` pem rows where unit status = DEFAULT and system = US_CUSTOMARY and
  jurisdiction = IRAN to the SI configuration (idempotent, back up first).
