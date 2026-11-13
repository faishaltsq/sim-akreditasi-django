# IGD Clinical Expansion — Delivery Ledger

**Date:** 2026-11-13.
**Status:** Core local implementation delivered and verified; production activation remains gated.
**Workspace:** `C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django`.
**Branch / unchanged HEAD:** `master` / `112a7b3357168ec53aac6cb4c6670b8bcab86f66`.

This supersedes the isolated-tracer checkpoint. Current code is integrated in the main workspace. The older `sim-akreditasi-django-clinical-expansion` copy is historical, not a source to overwrite current files. Existing physical-examination work and unrelated professional-care/CPPT plans are preserved.

## Done

| Component | Delivered behavior | Actual proof |
|---|---|---|
| Diagnosis | Relational primary/secondary rows, cancel/history, atomic primary switch, canonical labels, compatibility projection, actor/provenance and before/after audit | Diagnosis tests, three browser viewports, database readback, competing-primary PostgreSQL scenario |
| Nursing / AI / actions | Independent Manual/Master/AI modes, profession-owned fields, mapped SDKI/SLKI/SIKI, gated target-specific AI and signed acceptance tickets, action location/notes and actual/recorded timestamps | Component/AI tests, nursing browser save/reload, retrospective execution with CPPT/billing on PostgreSQL |
| Ancillary catalogue / orders | Reviewed four-level taxonomy, paginated lookup, retained basket, indication/preparation, atomic batch and replay; no charge on selection/send | Browser basket/parent-reset journeys, real delayed-response test and concurrent same-key PostgreSQL batch |
| Ancillary worklists / results | Assigned-service LAB/RADIOLOGI/EKG/LAINNYA worklists, pagination, shared validation across workflow and legacy writers, audited corrections | Result/RBAC tests, assigned lab browser journey, late-result/addendum scenario |
| Medication | Reviewed product/ingredient/formulary/policy records, structured ordinary medicine/racikan/BMHP, decimal regimen, route/PRN/manual quantity and component-unit validation | Catalogue/quantity/prescription/safety tests and prescription browser journey |
| Safety / pharmacy | Allergy/duplicate/class/risk checks, component-sensitive review digest, PPRA hold and independent approval, explicit depo grants, prescription versions and replay-safe charge ownership | PPRA browser journey, database readback and parallel submissions/dispensing/completion |
| History / print | Snapshot schema 2 includes new clinical context and frozen recipe/order/action metadata; absent historical fields do not use live master fallback | Final-resume browser journey, byte-identical print after live catalogue changes and immutable original revision after late result/addendum |
| Import / assets | Dry-run default, repeat-safe inactive DOCX staging, registered review/admin interfaces, read-only managed-prescription admin, regenerated static manifest | Import tests, source hashes, verified hashed asset bytes |

Existing visit/workflow, order, prescription, action, billing and AI boundaries remain canonical; there is no parallel episode or ledger. See the separate source-to-code analysis for requirements and source provenance.

## Measured verification

- Broad command: `DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien klinis accounts --keepdb --noinput` — **574 tests, OK, 307.945 seconds, exit 0**.
- That run includes the fix separating administrator read-only oversight from profession/service-bound result mutation. The existing superadmin route assertion was preserved; nonclinical mutation remains denied.
- After the broad run, one trailing space outside an HTML attribute was removed. The exact delivered template passed **14 result/RBAC tests, OK, 10.043 seconds**. No application behavior changed afterward.
- `manage.py check`: no issues, one existing silenced check. Schema drift: no changes detected. JavaScript syntax and whitespace checks: exit 0.
- Chromium: **375 / 768 / 1366 px**, matching document/viewport widths, eight recorded journeys and no captured page errors. A real delayed catalogue response is discarded after parent reset; keyboard selection works; no clinical data appears in local/session storage.
- Readback confirms two active diagnoses and one primary on each tested visit, matching compatibility projection, independent nursing modes, one pharmacy charge after completion replay and an independently approved PPRA request.
- Final print remains byte-identical after changing live catalogue name, price and risk flags in the isolated fixture DB. Those catalogue changes were rolled back afterward.
- **PostgreSQL 17.11**: the full migration chain applied in an isolated Docker DB without skipped historical data operations or fake migration records. The new migration records were read back explicitly.
- **Eight PostgreSQL scenarios passed:** competing primary edits, same-key order batch, retrospective execution, two submissions, concurrent dispensing, concurrent completion, billing/stale version and final snapshot/late result/addendum.

Evidence: `docs/superpowers/evidence/igd-clinical-expansion/verification.json`, `browser.json`, `browser-race.json`, `database-readback.json`, `postgres.json` and screenshots. Raw logs remain under Hermes scratch; repository evidence contains no session-cookie values.

## Decisions and deviations

- Component tests/controllers are consolidated rather than reproducing every proposed filename. Historical authoring checkboxes are not bulk-ticked: measured delivery does not assert that every original RED recipe or clinical reference example was independently exercised.
- Full diagnosis text stays on the structured row; its existing 300-character compatibility projection is explicitly ellipsized rather than widening an operational column.
- Migrations are `klinis.0003_clinical_expansion`, `pasien.0026_diagnosis_lines` and `pasien.0027_clinical_expansion`. Operations are CreateModel/AddField only; no destructive historical rewrite.
- Legacy unassigned LAB orders retain the canonical `LAB-BDRS` worklist. New catalogue orders use explicit destinations. Historical non-LAB destinations are not guessed from names.
- A validated complete result may go directly ORDERED-to-SELESAI for legacy compatibility, without a fabricated processing timestamp. Completed results cannot regress or be overwritten without a reasoned correction.
- Racikan components/amounts/units/instructions are frozen. A component price is not assumed to be the finished-compound price; finished racikan pricing remains unresolved until reviewed policy supplies it.
- The existing ledger stores two-decimal quantities. A four-decimal clinical quantity that cannot fit it remains exact and `financial_pending`, not silently rounded into a charge. Unknown prices are likewise unresolved, not free. Clinical handover is distinct from financial completion; no approval/reconciliation amount was invented.
- Canonical pharmacy profession `TTK` is recognized. Profession/depo checks still govern mutation even for administrators; administrative read access is not clinical authorization.
- Browser scenarios are representative synthetic journeys, not certification of every imported example.

## Not done, needs the live environment or explicit approval

- Clinical/pharmacy approval of strengths/forms, formulary validity/restrictions, panels, risk classifications, service availability and compound/financial policy. Staging contains **38 ancillary nodes / 94 items** and **9 medication classes / 59 generics / 59 products**: DOCX examples, not a certified production catalogue.
- Operational backup/restore, migration/import, activation and deployed-route verification. No operational DB was migrated. After release approval, inspect normal `showmigrations` / `migrate --plan`, back up the explicit target and run normal migrations. Import stays dry-run unless `--apply` is authorized.
- Live AI/provider quality verification. Local tests prove gates, candidate validation and signed acceptance, not live model quality. No patient/provider outbound call was used.
- LIS/PACS, inventory/procurement, bedside MAR and national-service integration remain outside this delta.

## Skipped on purpose

- No commit, push, merge, production migration, catalogue activation or deployment.
- No historical deletion, invented national codes, zero-price substitution for unknown costs or fabricated provider/API output.
- No edits to unrelated professional-care/CPPT plans merely because they coexist in this workspace.

## Reproduction

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien klinis accounts --keepdb --noinput
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py check
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
node --check static/js/igd-clinical-expansion.js
node --check static/js/igd-diagnosis-plan.js
git diff --check
```

Synthetic probes: `qa/clinical_expansion_browser.py`, `qa/clinical_expansion_browser_race.py`, `qa/clinical_expansion_concurrency.py`. They require generated synthetic fixture state, not real credentials. Verification DBs/settings/sessions were isolated under Hermes scratch and a loopback-only Docker container.
