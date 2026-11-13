# IGD Clinical Expansion Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` to implement the component plans task-by-task. Track steps with checkboxes. This document does not authorize application changes, commits, pushes, or deployment.

**Status:** CORE LOCAL IMPLEMENTATION VERIFIED — 574 regression tests passed, with browser and real PostgreSQL evidence. Production clinical approval, activation and release remain gated. The delivery ledger records measured acceptance, deviations and unexecuted live steps: `../specs/2026-11-13-igd-clinical-expansion-delivery.md`. Authoring checkboxes are not bulk completion claims.
**Date:** 2026-11-13.
**Goal:** Extend existing IGD steps 7–9 with structured diagnosis/planning, medication prescribing and four-level ancillary ordering while retaining the eleven-step workflow and historical records.
**Architecture:** Reuse the Django monolith and canonical visit, action, prescription, investigation, billing and revision models. Introduce focused catalogue and application services, additive fields/models and small vanilla-JS controllers; integrate through existing versioned, authenticated actions instead of maintaining a second workflow.
**Tech Stack:** Project Django/Python environment, Bootstrap, vanilla JavaScript, Decimal, SQLite test database and PostgreSQL release/concurrency gates; existing backend AI transport only.
**Spec:** `../specs/2026-11-13-igd-diagnosis-pharmacy-ancillary-analysis.md`.
**Baseline:** `112a7b3357168ec53aac6cb4c6670b8bcab86f66`; 64 targeted tests passed. This is not a production baseline.

## Global Constraints

- Planning only until the user reviews these artifacts and authorizes execution. Never infer release permission from plan approval.
- Preserve unrelated untracked physical-examination files. That separate plan owns step 6. Re-read shared files at execution time.
- Preserve existing final revisions and raw legacy records; no mass classification/backfill or deletion to conform to new schemas.
- Reuse `get_visit`, `authorize_visit`, `perform_action`, optimistic workflow version, UUID request keys and actor-bound digest replay.
- Lock order is visit → workflow → domain header → child rows → billing rows; all competing writers use the same order. Do not hold a transaction open while waiting for an AI/network response.
- Store money and quantities using Decimal, never browser totals/float as authority. Missing price is unknown, not free.
- Actual AI remains separate from deterministic mapping; module gates remain default-off. No live provider/patient outbound calls in tests or this planning work.
- Code systems stay separate: ICD10, ICD9, KFA. Catalogue examples are review inputs, not certified national datasets.
- No product dependency install, new frontend framework, inventory/procurement system, bedside MAR, or live LIS/PACS/BPJS/SATUSEHAT integration.
- Every new/extended field that affects signed documentation must enter the snapshot and signature digest; old snapshots never fall back to live new fields.
- Do not commit, push, migrate an operational DB or deploy without explicit authorization. Do not fake migration ledger entries.

## Review Focus

1. Legacy writers bypassing a new validation or final guard — component service integration tasks must include direct legacy-route negative tests.
2. Different parent paths, stale async responses or inactive items selected through forged JSON — each catalogue task owns server and browser validation.
3. Cross-unit professional workflows — doctors/nurses/pharmacists/PPRA reviewers need separate action and visibility predicates, not a global admin bypass.
4. Retry after commit but before HTTP response — durable replay and unique billing ownership must prevent duplicate clinical/financial records.
5. Final snapshots after catalogue, price, dose, results or current episode ownership changes — each component owns its frozen representation and old-snapshot compatibility tests.

## Execution order and ownership

| Phase | Authoritative component | Output | Dependency |
|---|---|---|---|
| 0 | This roadmap | Current-tree baseline, schema/data provenance, policy decisions | User execution approval |
| 1 | `2026-11-13-igd-diagnosis-actions-3s.md` | Structured diagnoses, independent modes, action AI/metadata and compatible snapshots | Phase 0 |
| 2 | `2026-11-13-igd-ancillary-cascading-orders.md` | Catalogue/basket, indication/preparation and atomic order dispatch | Phase 1 diagnosis reference contract |
| 3 | `2026-11-13-igd-pharmacy-medication-safety.md` | Reviewed medication catalogue, prescriptions, risks/PPRA, safe dispensing billing | Phase 1; phase 2 for culture-order references where used |
| 4 | This roadmap | Cross-component journey, PostgreSQL and release-readiness evidence | All component gates |

Component plans are individually testable. Catalogue-only helpers may be explored independently after approval, but shared-file changes and migrations are serialized. Do not run the old workflow plan's NEW-file tasks; those files already exist. This roadmap is the authoritative orchestration for this delta, not a replacement for the separate step-6 plan.

### Shared-file owners

`pasien/models.py`, `pasien/urls.py`, `pasien/igd_workflow_views.py`, `pasien/forms_igd_operations.py`, `pasien/services/igd_actions.py`, `pasien/services/igd_finalization.py`, `templates/pasien/igd_workflow.html`, `_igd_workflow_operations.html` and static manifest are single-writer boundaries. Each phase reopens the latest files and extends the previous phase. Generate the next migration names at execution time; do not preassign conflicting migration numbers. Feature-specific catalogue/service/test files belong to their component. Only the final release task owns generated `staticfiles/` artifacts.

## Phase 0: Characterize the real execution environment

- [ ] Read `git status --short`, `git branch --show-current` and `git rev-parse HEAD`; preserve all unrelated work. Stop for unresolved conflict markers.
- [ ] Re-hash both DOCX attachments and compare with the spec before using a generated fixture or coverage list.
- [ ] Run the measured baseline command below; capture failing names/tracebacks rather than assuming a previous result is current.
- [ ] Read-only inspect the configured DB vendor and migration ledger. Local SQLite was at `pasien.0020` during planning; do not mistake the test DB's complete migration run for an applied operational schema.
- [ ] On a backed-up, explicitly selected local execution DB, inspect `showmigrations`/`migrate --plan`; apply existing required migrations only after authorization. PostgreSQL/production schema status is presently unverified.
- [ ] Record policy ownership for product sources, medication risk restrictions/overrides, pharmacy scope and billing recognition. Keep unavailable or unreviewed catalogues inactive.

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien.tests_igd_workflow_integration pasien.tests_igd_workflow_ai pasien.tests_3s_cascade pasien.tests_laboratorium klinis --keepdb --noinput
```

Expected at the recorded untouched baseline: 64 tests, `OK`, exit 0. Once features/tests are added, record the runner's measured count; never enforce 64 as a future total.

## Phase 4: Cross-component verification

- [ ] Run all component test modules plus current `pasien`, `klinis`, `accounts` suites. Include the existing AI/config/navigation tests affected by backend changes. Catalogue scripts must not silently alter production data during tests.
- [ ] Exercise a synthetic visit: CITO order before step completion → mixed manual/master diagnosis → separate nursing modes → action plan → execution → normal/racikan/BMHP prescription → pharmacy review → dispense → billing → signatures/final resume → late result → addendum. Verify persisted values and record counts, not only page strings.
- [ ] Negative journeys: physician from another unit, nurse trying medical diagnosis or prescription submit, admin with no clinical profession, assessor, pharmacist with unrelated depo, PPRA self-approval, stale workflow, forged child/catalogue code, replay key reused with different payload.
- [ ] Browser at 375/768/1366 px: keyboard-operable modes/dropdowns, child reset, basket retention, delayed response race, double click/retry, PRN and unit-conversion states, error focus, price/risk visibility, no horizontal overflow and no patient data in persistent browser storage.
- [ ] Isolated PostgreSQL: complete additive schema migration, same-key order batch, competing diagnosis-primary edits, two prescription submissions, two dispense-complete calls, stale version and consistent lock order. SQLite is insufficient proof of row-lock behavior.
- [ ] Verify snapshot digests and original final print remain unchanged after edits to catalogue names, flags, tariffs, live results and pharmacy status. Newly finalized records include complete component snapshots.

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py check
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien klinis accounts --keepdb --noinput
git diff --check
```

Expected: checks exit 0, no missing migrations, test runner `OK`, no whitespace errors. Compare failing tests to a current measured baseline; do not label them pre-existing without evidence. The separate untracked physical-examination tests belong to another workstream: report their state, do not change them merely to green this plan.

## Conditional release and rollback

- [ ] Release only after approval: review generated migrations for additive shape, backup/restore proof and active source/policy provenance; generate static assets with `collectstatic --noinput` and keep tracked hashed assets/`staticfiles.json`.
- [ ] Apply normal Django migrations manually on the correct production target in the approved order; Vercel deployment does not imply migration execution. Never fake data migrations to get a green ledger.
- [ ] Enable the new flows in stages; preserve read-only history when disabled. AI remains off unless separately approved and verified with synthetic input.
- [ ] Verify exact deployed routes and synthetic record readback; capture deployment identifier, migration status, source-catalogue version and result. Tool/API success alone is not deployment evidence.
- [ ] Rollback application/feature gates first, retain additive tables and clinical/financial records. Reverse deployed schema only after proving no dependent data; never delete charges or signed evidence as rollback.

## Deliverable and completion ledger

Implementation status, local tests, browser evidence, PostgreSQL migration/concurrency, catalogue/policy approval and deployed verification must be separate columns in the execution report. No component is complete because its UI merely renders, and no live integration is certified by mocks. Commit and release operations remain conditional; the plans deliberately contain no automatic commit step.
