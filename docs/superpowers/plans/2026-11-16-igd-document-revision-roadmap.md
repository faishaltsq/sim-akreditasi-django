# IGD Document Revision Completion Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** IMPLEMENTATION IN PROGRESS — the user approved execution using subagents. Commit, push, deployment, operational migration/import and clinical activation remain outside this authorization.
**Goal:** Apply the revised Step 8 replacement requirements and complete remaining medication/ancillary integration gaps on top of ARima's existing clinical expansion.
**Architecture:** Keep the Django monolith, eleven-step workflow, canonical visit/diagnosis/action/prescription/order/billing models, profession authorization and immutable final snapshots. Implement three completion workstreams in order with explicit shared-file ownership; no parallel replacement system or new mapping table.
**Tech Stack:** Existing Python/Django project venv, Bootstrap, vanilla JavaScript, Decimal, SQLite targeted tests and isolated PostgreSQL migration/concurrency gates. Reuse the existing backend AI transport; no new SDK or frontend framework.
**Spec:** `../specs/2026-11-16-igd-document-revision-gap-analysis.md`.
**Inspected baseline:** `master` at `f2583ea936dc1d00669ae16b5228880d0e6b5a29`.

## Global Constraints

- Planning artifacts only until the user approves the written scope and execution approach. No commit, push, deployment, operational migration, import or clinical activation is implied by implementation approval.
- Revised source instructions are replacement, not addition: remove the editable resuscitation/stabilization and IGD pharmacotherapy controls from the new Step 8, placing action/medication plans after medical diagnosis.
- Preserve database columns/history, all signed/performed/dispensed/billed evidence and existing professional-care/CPPT privileges and billing contracts. Current Step 6 physical-examination functionality is outside this delta.
- Plan approval does not certify example master data. Retain original catalogue source hashes, stable IDs/reviewers/destinations and inactive/unavailable state where not configured.
- Reuse existing `perform_action()` UUID/digest/version replay, `get_visit()`/authorization, explicit transitions and snapshot owners. Lock mutations in visit → workflow → header/domain row → child rows → billing order. No provider call inside a clinical write transaction.
- Keep ICD-10, ICD-9-CM and KFA distinct. Master-based suggestions are deterministic; AI remains separately gated, validated and explicitly accepted. Do not fabricate live-provider/API results.
- Missing tariff/conversion/quantity is unknown, not zero or rounded into a financial transaction. Draft planning and catalogue selection do not post charges.
- Retain the five pre-existing untracked professional QA/settings files; do not stage, clean up or modify them merely to satisfy this plan.

## Review Focus

1. Layout replacement can silently remove fields from snapshot/resume/signature digest because they are derived from `STEPS`: Step 8 Task 1 owns preservation and the regression.
2. One form's successful action can reload another unsaved form: component browser gates must cover retained drafts when switching panels and actual persistence before navigation.
3. The source's already-implemented features can be incorrectly rebuilt from an older plan: use the delta matrix, not unchecked historical authoring boxes, to assign tasks.
4. Test DB schema/data is not the operational target: verify environment, migration ledger, installed catalogues and deployed behavior separately.
5. Cross-profession actors and late results after finalization need their existing broader read/narrow mutation contracts: include doctor, nurse/bidan, pharmacist/TTK, assigned lab/radiology, nonclinical admin and assessor controls.

## Authoritative Plans and Supersession

| Order | Component plan | Concrete output |
|---|---|---|
| 0 | This roadmap | Current-tree baseline, source continuity and isolated execution target |
| 1 | `2026-11-16-igd-step8-replacement-completion.md` | Replacement UI/history, diagnosis-linked ICD-9, meaningful assessment recommendations, independent 3S |
| 2 | `2026-11-16-igd-medication-composer-completion.md` | Persisted general/PRN instructions, selected-product risk display and authoritative quantity preview |
| 3 | `2026-11-16-igd-ancillary-integration-completion.md` | Item metadata, deterministic cascade/pagination reset, explicit manual fallback and coverage/journey |
| 4 | This roadmap | Integrated browser, regression, PostgreSQL and conditional release evidence |

This is the authoritative roadmap for the **revised** attachment. The `2026-11-13-igd-clinical-expansion-*` and diagnosis/pharmacy/ancillary plans are historical baseline/design context. Their NEW-model/NEW-file creation instructions are superseded for requirements already present. Their accepted safety/state/history contracts remain in force. Separate professional-care and physical-examination plans are not restarted or replaced.

## Shared-File Ownership

- **Step 8 owns first:** `pasien/forms_igd_workflow.py`, `pasien/igd_workflow_views.py`, `pasien/services/igd_finalization.py`, `templates/pasien/igd_workflow.html`, Step 8/diagnosis/nursing templates, `static/js/igd-assessment-workflow.js`, `igd-clinical-controls.js`, `igd-diagnosis-plan.js`, and first changes to `igd-clinical-expansion.js`/workflow operations/resume.
- **Medication owns second:** medication template, prescribing service, preview view/route, pharmacy/resume instruction consumers and its subsequent changes to `igd-clinical-expansion.js`/`pasien/urls.py`.
- **Ancillary owns third:** ancillary template/catalogue/order service and subsequent workflow operations/view/controller edits.
- **One QA owner:** serial updates to `qa/clinical_expansion_browser.py` and race probe. Keep existing synthetic state contract and append new assertions; do not overwrite another component's journey.
- **Final release owner only:** generated tracked `staticfiles/` files and `staticfiles.json`, after approved `collectstatic`; no component independently regenerates them while others edit scripts.

Models/migrations are expected to remain unchanged for the scoped integration delta. Any implementation finding that genuinely needs schema change must be reviewed as an explicit additive change, with a freshly discovered migration leaf; do not reserve numbers or replay old create-model tasks.

## Phase 0: Reconfirm Evidence and Select the Execution Environment

### Task 0.1: Preserve current scope and source identity

- [ ] Run the read-only commands below. Record branch/HEAD/untracked files, any conflicts and the selected component baseline. Stop for unresolved conflicts; do not repair unrelated work during planning/execution setup.

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git diff --check
```

- [ ] Re-hash both DOCX sources and compare to the analysis register. The ancillary source is unchanged; medication staging still cites the older source. If sources changed again, re-diff the Word text/tables before executing tasks.
- [ ] Reopen the exact shared files at the start of each component. Read prior delivery ledgers as historical evidence, not declarations that the revised requirements are complete.
- [ ] Confirm interpreter/dependencies without exposing configuration secrets. The inspected venv is Python 3.12.10/Django 6.1.1; repository pins Django 6.1.2. Choose a consistent isolated test environment against the manifest before release; do not silently install packages into an unrelated global interpreter.

### Task 0.2: Reproduce the measured test baseline

```bash
DATABASE_URL='' DJANGO_DEBUG=true PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test pasien.tests_igd_diagnosis_lines pasien.tests_igd_target_ai pasien.tests_clinical_expansion pasien.tests_clinical_expansion_safety pasien.tests_penunjang_results pasien.tests_igd_workflow_ui --keepdb --noinput
```

**Measured in this planning turn:** 101 tests, `OK`, 14.162 seconds, exit 0; the repeated pre-handoff run also returned **101 tests, `OK`, 13.095 seconds, exit 0**. The existing naive-datetime fixture warning remains documented. This is a baseline of existing tests only. At the unchanged baseline a different result requires investigation; once tests are added, record the runner's actual count and failures instead of enforcing a guessed new total. Inheritance/import collection does not equal new scenario coverage.

- [ ] Establish and save the full `pasien klinis accounts` baseline before application changes if full-regression attribution is required. Do not label unrelated failures pre-existing without this comparison.
- [ ] Keep one test runner per shared test database at a time. Store raw logs under `C:/Users/cubeb/AppData/Local/hermes/cache/scratch`, not the repository. Start long runs once as tracked jobs; inspect their terminal outcome before retrying.

### Task 0.3: Separate local schema lag from feature work

- [ ] Explicitly select an isolated development/test DB and assert its identity before writes. Do not use a guessed `DATABASE_URL` or expose connection credentials in logs.
- [ ] Reconcile the read-only SQLite finding: local ledger `pasien.0020`, `klinis.0002`, `accounts.0008`, `sdm.0066` versus repository leaves `pasien.0032`, `klinis.0006`, `accounts.0009`, `sdm.0067`. New workflow/catalogue tables are absent locally. A test DB's successful migration does not change this ledger.
- [ ] Before any authorized operational/local-target migration, take and verify a target-specific backup, inspect `showmigrations` and `migrate --plan`, then apply the normal graph. No `--fake`, skipped seeds, edited migration history or automatic production migration to force readiness.
- [ ] For browser/PG tests, use generated synthetic records, reviewed synthetic catalogue representatives and isolated sessions. Existing probes need real generated state JSON; an absent fixture/bootstrap is a setup task, not permission to invent a passing report.
- [ ] Record decisions for nurse order delegation, catalogue reviewers/sources, destination/depo configuration, Fornas/PPRA policy and any unresolved financial policy. Default to observed permissions and inactive/unavailable reference data until explicitly changed.

## Phase 4: Integrated Acceptance and Verification

### Task 4.1: Source-specific acceptance map

- [ ] Maintain the spec's IDs RV01/RV02/DG01/DG02/AC01/AC02/NS01/RX01–RX04/PX01–PX03/IX01/EN01 with **implementation evidence and verification evidence in separate columns**.
- [ ] Do not count disabled/unconfigured clinical activation or live-AI quality as delivered merely because a synthetic journey passes.
- [ ] No obsolete editor in the new Step 8; intended DOM order and historical notes verified. Existing records retain all clinical/financial evidence. Legacy non-workflow behavior remains compatible.
- [ ] Diagnosis-conditioned master suggestions actually use an active episode diagnosis and existing case relation. Manual/unmapped diagnosis retains global/manual alternatives.
- [ ] Recommendations consume bounded provenance-labelled clinical evidence and preserve negative/numeric distinctions. Wrong target/code/actor/visit/stale ticket is rejected; AI-off/timeout leaves Manual/Master usable.
- [ ] Medication instructions persist for FIXED/INTERVAL/PRN, preview is exact when supported and explicitly manual otherwise, and selected risks/formulary availability are accurately rendered.
- [ ] Ancillary metadata required by selected items is enterable, validated and persisted; stale parent/pagination responses cannot repopulate children, while completed basket rows remain.

### Task 4.2: Actual clinical and role journeys

- [ ] Synthetic journey: send CITO before full assessment → assigned service records result → choose primary/secondary diagnosis → obtain diagnosis-linked master procedure → save plan → independently save 3S → prepare ordinary/racikan/BMHP prescription → review/PPRA if configured → dispense → professional execution/CPPT/DPJP verification where required → billing recap → final snapshot → late result/addendum.
- [ ] Verify DB IDs/counts/values after each action and after reload; selecting/candidate acceptance/quantity preview/planning must not create performed care or charges. Replaying the same committed request must not duplicate rows or bills.
- [ ] Negative roles: wrong-unit physician; nurse changing medical diagnosis/submitting prescription/order under current policy; physician changing nurse-owned 3S; unrelated depo pharmacist; PPRA self-approval; nonclinical admin mutation; assessor mutation. Broad administrative read-only oversight remains available where currently authorized.
- [ ] Browser at 375/768/1366 px: keyboard-operable segmented/cascading controls, real sequential note typing, two saves/reloads, draft retention on panel switching, focusable errors, no nested forms/duplicate IDs/horizontal overflow/page errors, no patient data in local/session storage.
- [ ] Restart the isolated browser server after backend/template edits before accepting evidence. Capture actual HTTP responses unchanged; no fixture response substitution to mask failures.
- [ ] Verify original signed snapshot/print remains frozen after live catalogue label/flag/price changes. Preserve old revision fallback behavior and invalidate stale signatures for genuine clinical changes, not merely a field-enumeration refactor.

### Task 4.3: Regression, migration shape and concurrency

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py check
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien klinis accounts --keepdb --noinput
node --check static/js/igd-assessment-workflow.js
node --check static/js/igd-clinical-controls.js
node --check static/js/igd-clinical-expansion.js
node --check static/js/igd-diagnosis-plan.js
git diff --check
```

Expected after implementation: system checks exit 0, no unexplained model/migration drift, test runner `OK`, JS syntax/whitespace exit 0. The broad command collects the newly proposed component test modules because they live in `pasien`; it also includes the existing `klinis` tests extended by the recommendation task. No guessed future test count is an acceptance gate.

- [ ] Run separate professional regression as needed: `pasien.tests_professional_http`, `pasien.tests_professional_execution`, `pasien.tests_professional_billing`, `pasien.tests_professional_snapshots` and existing applicable privilege/SDM tests. Do not change their assertions solely to accommodate an accidental regression.
- [ ] On isolated PostgreSQL apply the **normal full migration graph**, then exercise competing primary diagnosis, same-key order batch, plan-to-professional execution, concurrent prescription submit/dispense/complete, stale versions and final snapshot/late result. SQLite cannot establish row-lock correctness.
- [ ] Existing `qa/clinical_expansion_concurrency.py` asserts DB name `clinical_verify`; pre-existing professional QA settings assert a different database/port. Do not mix these harnesses by name or point either at operational data. Generate state against its selected isolated fixture and report actual setup/scenario results.
- [ ] Inspect final diff/status and confirm only approved application/tests/docs/assets were changed during implementation. Planning turn itself must leave application code and pre-existing untracked files untouched.

## Conditional Release, Activation and Rollback

These are separate approval gates, not actions to run during analysis or automatically after tests.

- [ ] Obtain explicit target and release authorization; record deployment/source ID, backup/restore proof, manifest-aligned dependencies and source/review provenance.
- [ ] Rehearse migration and data readiness on the selected engine. Apply Django migrations manually on the exact approved target; Vercel deployment does not auto-apply them. Read back migration records and required tables.
- [ ] Keep import dry-run first. Only apply reviewed/authorized reference records after comparing provenance and preserving existing reviewed IDs/transactions. Never activate all DOCX examples to produce nonempty menus. For development demo activation, require its own explicit environment scope and visible DEMO/provenance conventions.
- [ ] Run `collectstatic --noinput` after approved code completion; keep tracked `staticfiles/` and `staticfiles.json`, verify source/collected/hashed JS bytes and served manifest entries. Stage specific files only if a commit is requested.
- [ ] After release, GET exact deployed routes, exercise an authorized synthetic workflow and read back its records in the target. Provider/tool success is not deployed verification. AI remains off unless separately enabled and tested with approved synthetic input.
- [ ] Roll back application/feature gates first, leaving clinical/financial/historical data intact. No deletion or schema reversal without a reviewed data-dependency analysis. Existing additive schema/data must remain readable by the rollback path.

## Handoff and Definition of Done

The user reviews the analysis and component plans before implementation. Recommended method: **subagent-driven with serialized shared-file work and an independent final reviewer**, because layout/snapshot changes and existing professional/financial boundaries need independent checks. Native execution remains a valid explicit choice; neither choice implies deployment.

The implementation handoff must contain the revised requirements, actual changed paths, exact test commands/results, browser and PostgreSQL evidence, unresolved activation decisions and deployed status as separate facts. This planning deliverable is complete when those tasks and their source-to-code rationale have been reviewed and statically checked; application acceptance remains future work, not a planning success claim.
