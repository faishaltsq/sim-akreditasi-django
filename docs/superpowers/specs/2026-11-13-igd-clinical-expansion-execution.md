# IGD Clinical Expansion — Execution Checkpoint

> Historical tracer checkpoint only. Current implementation, verification and explicit release boundaries are documented in [the delivery ledger](2026-11-13-igd-clinical-expansion-delivery.md). Do not copy the older isolated workspace over the integrated main workspace.

**Date:** 2026-11-13.
**Status:** SUPERSEDED. The statements below describe the earlier isolated tracer, not current implementation status; see the delivery ledger above.

## Done

- Created an isolated source snapshot from the actual dirty workspace, preserving the separate physical-examination implementation as the base rather than resetting it.
- Preserved a durable working copy at `C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django-clinical-expansion`. It is an independent local git directory, not a branch or linked worktree of the original repository. No commits were created.
- `execution-base-manifest.json` records SHA-256 for each original copied file, allowing integration to compare against the exact dirty base and detect subsequent edits. Never copy whole shared files back without this comparison/three-way review.
- Implemented proposed `DiagnosisKunjungan`, additive migration `0026_diagnosis_lines`, active-primary unique constraint and doctor-only `diagnosis_set` action under the existing visit/version/request-key transaction.
- Implemented manual/master diagnoses, server-owned canonical master labels, active primary/secondary rows, explicit cancellation retaining history, primary switching through atomic API changes, omission preservation, replay and before/after audit.
- Implemented signed-AI-ticket validation for the existing medical ticket contract in the new action. New target-specific AI generation and a structured-list AI UI have NOT been implemented.
- Guarded old step-8 writes from overwriting adopted structured diagnosis, added structured diagnoses to clinical snapshots and final resume rendering without a live fallback for old snapshots.
- Added a step-8 add/cancel interface with manual/master modes, catalogue lookup, explicit primary selection, loading/retry handling and stable request keys. Existing global-mode fields are not yet replaced by independent modes.
- Wrote tests before the first implementation. Recorded missing-operation RED in `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima-diagnoses-red.log`; before/after-audit RED in `arima-diagnoses-audit-red.log`.
- Last combined isolated run: **132 tests, OK, exit 0**, Django test time **35.840 seconds**. Log: `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima-diagnoses-checkpoint.log`.
- `manage.py check`: no issues (one existing silenced check). `makemigrations --check --dry-run`: no changes detected. `node --check static/js/igd-diagnosis-plan.js`: exit 0.
- Reviewed generated migration: CreateModel only; no existing clinical/financial table deletion or rename. Test DB migration execution is not an operational DB migration.
- Generated static assets in the isolated snapshot for local template/manifest tests only. Nothing was collected into the main workspace by this execution.

## Not done, needs confirmed ownership or additional implementation

- Main-workspace integration: another worker's physical-examination changes touch the same models/views/services/templates. The focused ownership question timed out; no consent to overwrite or assumption that the other writer stopped was inferred. Ask whether that worker has stopped, then compare the main files against `execution-base-manifest.json` and merge only this delta.
- Remaining diagnosis plan tasks: independent component modes/profession-owned step fields; target-specific AI contexts/tickets; procedure AI and actor/time/location metadata; richer edit/primary-switch UI; full legacy-reader/finalization gates. Therefore Task 1 is a working tracer, not a claim of full phase-1 acceptance.
- Ancillary catalogue/basket and pharmacy/medication safety plans have NOT been implemented.
- Browser execution/layout/keyboard verification and PostgreSQL concurrency have NOT been exercised. HTTP/template tests do not prove browser behavior. These gates remain open.
- Production catalogue review, medication policies, database migration and live deployment are not verified. No patient/provider outbound call was used to test clinical features.

## Skipped on purpose

- Main development/production DB migration, seed activation, release, commits and pushes: no authorization for those operations.
- Editing the active physical-examination worker's main files: ownership remains unresolved.
- External coding-worker output: OpenCode launcher is broken; cached Codex launches but fails authentication; Claude smoke test timed out. No output from those attempts was treated as implementation. The diagnosis tracer was implemented directly and tested with the project's existing Python environment.

## Integration inventory

Modified relative to captured base:

- `pasien/models.py`
- `pasien/igd_workflow_views.py`
- `pasien/services/igd_actions.py`
- `pasien/services/igd_assessment_workflow.py`
- `pasien/services/igd_finalization.py`
- `templates/pasien/igd_workflow.html`
- `templates/pasien/igd_workflow_resume.html`

New source files:

- `pasien/migrations/0026_diagnosis_lines.py`
- `pasien/services/igd_diagnoses.py`
- `pasien/tests_igd_diagnosis_lines.py`
- `templates/pasien/_igd_diagnosis_plan.html`
- `static/js/igd-diagnosis-plan.js`

At integration time regenerate the migration number if another migration has landed. Preserve the actual dependency graph, not this historical filename.

## Known intentional boundaries and deviations

- Full diagnosis text is retained up to 2,000 characters on the structured row. The existing 300-character compatibility field receives an explicitly ellipsized projection if needed, avoiding an unrelated alteration of the existing database column. Structured list/resume uses the complete stored text.
- The initial UI supports add/cancel; a primary switch is atomic through the backend operation, while the current UI requires cancelling the prior primary then adding the replacement. Rich edit/switch UI remains pending, not accepted as finished.
- Snapshot currently adds a `diagnoses` key without a new versioned adapter for all downstream readers; the broad phase-1 snapshot/version review remains pending.

## Reproduction command

Run from the isolated durable workspace with the main project's existing interpreter:

```bash
DATABASE_URL='' DJANGO_DEBUG=true C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe manage.py test pasien.tests_igd_diagnosis_lines pasien.tests_igd_workflow_integration pasien.tests_igd_workflow_ai pasien.tests_igd_workflow_finalization pasien.tests_igd_workflow_ui pasien.tests_igd_physical_exam pasien.tests_3s_cascade pasien.tests_laboratorium klinis --keepdb --noinput
```

Expected: runner `OK`, exit 0; record the actual count on the current tree. The 132 count is the measured checkpoint, not a target to force after additional tests.
