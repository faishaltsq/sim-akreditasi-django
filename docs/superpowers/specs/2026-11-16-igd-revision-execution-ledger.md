# IGD Revision Execution Ledger

**Status:** IN PROGRESS — implementation authorized by the user using subagents. No commit/push/deployment or operational DB mutation authorized.
**Baseline HEAD:** `f2583ea936dc1d00669ae16b5228880d0e6b5a29` (`master`).
**Roadmap:** `../plans/2026-11-16-igd-document-revision-roadmap.md`.

## Verified preflight

- Both supplied DOCX hashes match the analysis register.
- Existing untracked professional QA/settings files and five planning documents are preserved.
- Project interpreter: Python 3.12.10, Django 6.1.1; requirements pin 6.1.2. No product dependency change has been made. Dependency alignment remains an explicit release prerequisite.
- Controller and Step 8 worker settings were loaded and their database/test-database paths asserted under `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima_revision_20261116`; no repository `db.sqlite3` migration.
- Broad unchanged-source baseline: `manage.py test pasien klinis accounts --keepdb --noinput` with `DJANGO_SETTINGS_MODULE=revision_controller_settings`: **641 tests, OK (skipped=9), 73.334 seconds, exit 0**. Full normal migration graph retained.
- Baseline log: `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima_revision_20261116/broad-baseline.log`.
- Invocation-scoped worker route probe returned `ROUTE_OK`; no persistent delegation/model/provider settings changed.

## Task evidence

| Task | Implementation | Spec review | Quality review | Controller proof |
|---|---|---|---|---|
| Step 8 replacement/history | COMPLETE | PASS; tablet delta PASS | APPROVED; tablet delta APPROVED | Final 53 controller tests OK (7.477s); real browser 375/768/1366, no-JS/tab/keyboard/two nursing saves/readback. Tablet form corrected 194→464px; mobile347px/desktop784px unchanged. |
| Diagnosis-linked ICD-9 | Pending | Pending | Pending | Pending |
| Assessment context/3S | Pending | Pending | Pending | Pending |
| Medication instructions/risks | Pending | Pending | Pending | Pending |
| Quantity preview/lifecycle | Pending | Pending | Pending | Pending |
| Ancillary integration | Pending | Pending | Pending | Pending |
| Integrated browser/PostgreSQL | QA harness created; integrated feature bindings pending | Pending final integration review | Pending | Controller reran 10 fixture-boundary tests OK; direct synthetic readback and compilation passed. QA worker reports 4 existing browser journeys passed, 9 revision journeys pending; not full acceptance. PostgreSQL full schema readback: 201 migrations, none pending. |
| Final regression/integration | Pending | Pending | Pending | Pending |

## Environment and release boundaries

Docker was started successfully and a disposable `postgres:17-alpine` container `arima-revision-20261116` created with port bound only to `127.0.0.1:15486`. The full normal migration graph applied successfully to `clinical_verify`, without fake records or skipped historical seeds. Exact migration/schema readback is stored under scratch. Concurrency scenarios remain pending. The project venv lacks Playwright, but the controller interpreter has it; browser automation can drive a separate isolated Django server without adding application dependencies.

Catalogue clinical approval/activation, live AI quality, deployed routes, production backups/migrations/imports and release remain separate gates. Existing historical evidence is not counted as new execution proof.
