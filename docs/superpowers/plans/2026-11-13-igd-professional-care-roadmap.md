# IGD Professional Care Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` or `subagent-driven-development` task-by-task after approval. Track real evidence with checkboxes; this plan does not authorize implementation, operational migrations, commits or deployment.

**Status:** PLANNED.
**Goal:** Connect IGD step 9 to reviewed professional privileges/grades, component tariffs, multiprofessional CPPT and one auditable billing ledger.
**Architecture:** Extend existing HC, visit, action, CPPT and billing owners. Implement the three component plans in dependency order; reuse the versioned action dispatcher and preserve immutable snapshots rather than adding a second clinical workflow.
**Tech Stack:** Existing Django, Bootstrap, vanilla JS, Decimal, SQLite tests and PostgreSQL concurrency/release gates.
**Spec:** `../specs/2026-11-13-igd-professional-care-cppt-analysis.md` (PC01–PC14).
**Source:** `pelaksanaan dan cppt.docx`, SHA-256 `0c8ab23a74b58b13872292909fc867a637f216e7157d922782593179b3233551`.

## Global Constraints

- This is the authoritative delta for professional care/CPPT step 9, not permission to rerun the original eleven-step workflow or replace the existing clinical-expansion roadmap.
- Current main workspace contains another active workstream editing models, actions, forms, views and migrations. Confirm its handoff before implementation; an old execution note or quiet git status does not prove ownership release. Do not overwrite or stage its work.
- Reopen current source and migrate graph at execution. Do not preassign the next migration number or claim the dirty source is exactly HEAD `112a7b3`.
- Patient-module/object scope remains mandatory. A selectable profession/grade, role ADMIN_RS, catalogue row or account name is never clinical authority.
- Reuse `Pegawai.akun/profesi_master/jenjang_master`; validate grade belongs to profession. Do not add another employee grade field or equate all bidan grades with nursing PK grades.
- New feature gate `IGD_PROFESSIONAL_CARE_ENABLED` defaults false. Do not globally enable it while production has no issued SPK/privileges or reviewed prices. Old records remain readable, not automatically reclassified.
- Do not widen the four-profession dispatcher globally. Grant newly supported PPA only their own action operations and scope; nutrition/rohani writing a note does not enable prescription, medical diagnosis or episode finalization.
- Planning is not performance; dispensing is not medication administration; sending an order is not performing/billing it again. Each domain retains financial ownership.
- Prices/quantities are Decimal. Unknown price is not zero; an explicit approved zero is valid. Document examples are fixtures, not operational tariffs or employment records.
- Automatic CPPT is a draft event log, not a signed SOAP/ADIME assessment. DPJP verification requires an explicit account-bound current-content signature.
- Performed records/posted charges are never hard-deleted. Only unused drafts cancel; eligible performed error correction creates an audited void/reversal whose net totals are consistent across readers.
- No fake grades, privileges, signatures, medical records, accreditation compliance or live provider calls. No production writes in planning/testing.

## Review Focus

1. Staff's SPK/grade changes between dropdown preview and submit — A/C revalidate under transaction and retain performed-time snapshots.
2. Two grade/profession mappings match or none matches — A fails explicitly; never choose first row or lowest/highest tariff.
3. Actor posts another employee/supervisor or a nutrition user calls a prescription operation — A/B/C pin operation-scoped denial, including direct JSON/legacy routes.
4. Replayed execution, direct treatment and dispensing point at the same financial event — C pins unique ownership and one net charge, not merely HTTP 200.
5. Note revision, tariff amendment, void or transfer follows DPJP verification/finalization — B/C preserve signed content and classify new changes separately.

## Component order and shared ownership

| Phase | Component plan | Prerequisite / independently testable output |
|---|---|---|
| 0 | This roadmap | Confirmed source handoff, current baseline and policy/source inventory |
| A | `2026-11-13-igd-professional-tariffs-privileges.md` | Reused HC actor/privilege context, reviewed service mapping, versioned price quote and administration |
| B | `2026-11-13-igd-multiprofessional-cppt.md` | A; SOAP/ADIME/spiritual lifecycle, explicit DPJP assignment/signature and read-only history |
| C | `2026-11-13-igd-care-execution-billing.md` | A+B and established pharmacy/ancillary handoff; atomic execution, billing/void, step-9 UI and integration |

Shared files `pasien/models.py`, `klinis/models.py`, `pasien/forms_igd_operations.py`, `igd_actions.py`, `igd_finalization.py`, workflow views/templates, `accounts/models.py`, routes and static manifest are single-writer. Each phase extends the previous phase rather than replacing captured full files. New helpers/models are proposed by their owner plan, not existing APIs.

### Boundaries with work already in progress

- Diagnosis/actions plan owns step-8 diagnosis/procedure planning, source modes and occurred-at metadata. This delta consumes its `TindakanAsesmen` IDs; it does not implement those features again.
- Pharmacy plan owns prescriptions, safety/PPRA, review/dispensing and drug/BMHP billing. Step 9 reads its statuses/ledger references. Bedside MAR and claim reconciliation remain excluded.
- Ancillary plan owns order basket, dispatch/result and diagnostic charge policy. Step 9 does not create another LAB/RADIOLOGI bill for the same order.
- Physical-examination plan owns step 6. Preserve its source/evidence, snapshots, JS and static artifacts.
- This roadmap does not change those plans' completion statuses. Their documents and source diverged during inspection; get the actual owner's current handoff.

## Phase 0: Freeze facts and record policy defaults

- [ ] Obtain explicit implementation approval and shared-file ownership. Recheck status, merge state, file fingerprints and current migrations before any code edits.
- [ ] Re-run the targeted baseline on a stable approved checkout and record actual counts. Measured planning close run: **18 tests, OK, exit 0**, 6.407 seconds, with watched source hashes unchanged across that run; not a full suite or future acceptance count. Scratch evidence: `step9-plan-close-baseline.log` and `step9-plan-close-source.json`.

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python manage.py test pasien.tests_igd_workflow_integration klinis.tests.test_tarif_service --keepdb --noinput
```

- [ ] Read-only reconcile actual HC/price coverage: 23 professions, 118 grades, 499 catalogue items; only 9 of 24 employee rows have a grade; zero issued SPK/privilege snapshots/individual privilege lines and zero `KasusTindakan` prices at planning time. This is not verified staffing or authorization data.
- [ ] Adopt recommended defaults unless the owner explicitly changes them: self-performance only; required approved supervisor for supervised privilege; no inferred tier mapping; clinical tariffs managed by separately granted price admins; explicit free service versus unknown; author signs note before explicit DPJP countersignature; full void of an erroneous unpaid charge only, paid refunds/partial credit require a separate finance workflow.
- [ ] Record approved catalogue/price/effective-date sources. Import only reviewed rows with preview/dry-run and provenance; absent source stays unavailable. Do not seed source-document example names/amounts or grant accounts fictional privileges.

## Combined acceptance gate

- [ ] Run all new component test modules and current `pasien`, `klinis`, `accounts`, plus affected `sdm` access tests. Capture runner counts and all failures. Repeating an old green count is not proof for the moving dirty source.
- [ ] Synthetic journey: review action planned in step 8 → preview eligible profession/grade/self performer and quote → execute → one draft CPPT + one charge → complete SOAP/ADIME/spiritual → author sign → assigned DPJP verify → final snapshot → historical read.
- [ ] Direct-care journey uses the same execution service without creating a separate patient visit or duplicate event. Zero-price and unpriced services have distinct visible financial outcomes.
- [ ] Medication and ancillary summaries use owner records: dispensed does not say administered; price/risk eligibility and original billing IDs are retained; repeated viewing/execution cannot generate second charges.
- [ ] PostgreSQL synthetic races: same request key, two keys for one planned action, competing tariff revisions, privilege withdrawal during execution, concurrent DPJP verification/correction, two void requests. Assert persisted counts and lock order visit → workflow → employee/SPK/context → service/price version → action → note → billing/void, not SQLite-only assumptions.
- [ ] Browser 375/768/1366: cascading profession/grade/staff/service with stale-response protection, empty-configuration guidance, unknown/free prices, direct/planned selection, note format switching without losing entered content, row-targeted verification/void, double-click/retry and keyboard focus; measure overflow and no page errors.
- [ ] Frozen snapshot proof after master name/grade/price/assignment/note changes; old final snapshots never use live new fields. Legacy boolean verification is labelled as historical/unattributed when identity/digest is missing.

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python manage.py check
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python manage.py makemigrations --check --dry-run
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python manage.py test pasien klinis accounts --keepdb --noinput
git diff --check
```

Expected: no unplanned migration, no test failures, exit 0. New test modules must actually be collected; do not predict a future passing count.

## Conditional release

- [ ] Release requires separate approval. Freeze an allowlisted commit, verify exact checkout, review additive migrations and backup/restore readiness, then apply on the correct DB manually; Vercel does not run Django migrations automatically.
- [ ] New sensitive tables require RLS/direct-client privilege review. Read back constraints/migration records and approved reference sources before feature activation.
- [ ] Generate/verify tracked static assets, push exact SHA, verify provider SHA and canonical alias READY. Do not deploy a dirty moving workspace.
- [ ] Keep feature disabled until staff/source mappings and approved prices are populated and authenticated QA passes. Rollback app/flag first; retain issued clinical/financial evidence and additive schema.

## Definition of done

Report implementation, reference-data readiness, local tests, browser, PostgreSQL race proof, authorized deployment and human policy approval separately. A dropdown with zero eligible staff or a draft-generated CPPT is not evidence of completed care or valid DPJP verification.
