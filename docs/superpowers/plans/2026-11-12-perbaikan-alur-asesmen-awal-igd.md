# IGD Assessment-to-Disposition Workflow Implementation Plan

> **For agentic workers:** Use `executing-plans` or `subagent-driven-development` to execute this plan task-by-task. Use RED → GREEN → REFACTOR for each behavioral change. Do not implement or deploy merely because this plan exists.

**Status:** IMPLEMENTATION COMPLETE — local workflow, regression, browser and PostgreSQL gates verified. Production release and live AI activation were not requested. Final delivery status is in §8; §7 is historical first-batch evidence.
**Date:** 2026-11-12.
**Baseline:** `master` at `36aa2900c1d0d3d174acfdabede1c09a6b7174b1`.
**Source:** `C:/Users/cubeb/Downloads/Perbaikan Alur asesmen awal di igd.docx`, extracted lines 4–14.
**Analysis:** `../specs/2026-11-12-perbaikan-alur-asesmen-awal-igd-analysis.md`.

**Goal:** Deliver one visit-scoped, eleven-step IGD workflow covering assessment, care planning, actual care, evaluation, and disposition, without losing historical observations or duplicating orders and charges.

**Architecture:** Keep `KunjunganPasien`, `Pasien`, `OrderPenunjang`, `CPPT`, `TindakanAsesmen`, `BillingItem`, and `DischargeRecord` as canonical domain records. Add narrowly scoped workflow metadata, observation history, immutable final revisions, and durable action idempotency. Use Django forms and application services behind a dedicated IGD page; do not duplicate business rules in JavaScript or call old HTTP views from new views.

**Tech stack:** Existing Django installation, Bootstrap, vanilla JavaScript, SQLite for local tests and PostgreSQL for production/concurrency verification. Existing `requests` and backend AI transport suffice; do not add a frontend framework or an LLM SDK.

## 1. Requirements and implementation boundaries

### Source traceability

| ID | Source line | Required outcome |
|---|---:|---|
| R01 | 4 | Identity and guarantor visible before clinical steps; price source is explicit. |
| R02 | 5 | Arrival, triage system/category, operational color and ABCDE available together. |
| R03 | 6 | Current complaint, present/past/family history, medicines and allergy screening. |
| R04 | 7 | Initial BP, pulse, RR, temperature, SpO2, GCS and pain with units/time. |
| R05 | 8 | Psychological/social/spiritual assessment, education barriers, MST and fall screening. |
| R06 | 9 | Head-to-toe/local examination and persistent anatomical markers. |
| R07 | 10 | Order and result panel for lab, ECG, imaging/CT and other investigations. |
| R08 | 11 | Medical and nursing diagnosis/plan through Manual, Master and actual AI assistance modes. |
| R09 | 12 | Integrated CPPT and performed medical/nursing actions with correct billing linkage. |
| R10 | 13 | End-of-IGD condition, repeat observations and response to therapy. |
| R11 | 14 | Pulang, inpatient transfer, specialist pathway, external referral, death, and final resume. |

**In scope:** R01–R11, draft persistence, authorization, finalization/addendum, compatibility with existing forms, rekap/print integration, migration and release evidence.

**Not in scope:** autonomous diagnosis or treatment, automatic insurance-claim approval, a new tariff catalogue, replacing hospital-wide RBAC, redesigning RAJAL/RANAP, automatic live SISRUTE/LIS/SATUSEHAT integration, kiosk changes, purchasing AI quota, or retrospective mass rewriting of clinical records. Existing PAPS and SBAR must remain available even though the source does not enumerate them separately.

### Pre-implementation decisions

Record the approved answer before implementing the affected behavior. These do not prevent completing the analysis/plan.

- [x] **D01 — Triage:** user approved proceeding with recommended defaults. Require explicit system selection for a new numerical category; operational colors remain separately selected. No hospital-specific conversion policy is invented and historical ambiguity remains unchanged.
- [x] **D02 — Specialist pathway:** implemented consultation without transferring IGD ownership, separate service transfer, and origin-scoped historical reads.
- [x] **D03 — Clinical signatures:** implemented account/profession-bound approvals, content digests, invalidation on clinical edits, final snapshots and reason-required addenda. Administrator role alone does not confer clinical signing authority.
- [x] **D04 — AI activation:** implemented the default-off module gate, existing backend transport, bounded terminology/vital payload, catalogue validation and signed acceptance tickets. Live provider activation remains excluded; no live outbound patient-data call was made.

## 2. Target workflow and user experience

1. Identitas & Penjamin.
2. Triase & Cara Datang + Primary Survey ABCDE.
3. Anamnesis & Riwayat.
4. Tanda-Tanda Vital.
5. Biopsikososial, Spiritual & Skrining.
6. Pemeriksaan Fisik Lengkap + Lokalis + Penanda Anatomi.
7. Pemeriksaan Penunjang — Order & Hasil.
8. Penetapan Diagnosis & Rencana — Medis & 3S.
9. Pelaksanaan Asuhan — CPPT, Tindakan & Billing.
10. Evaluasi Akhir IGD.
11. Disposisi & Resume Keluar.

Use a persistent patient/visit identity and allergy header. Show the current step, draft/final status and last successful save. Each step has `Sebelumnya`, `Simpan Draft`, and `Simpan & Selanjutnya`; step 11 offers a review of missing/excepted sections followed by `Selesai & Simpan Permanen` with explicit disposition confirmation.

Clinical urgency overrides documentation order: allow direct navigation and partial drafts. Do not require steps 1–8 to be complete before sending an urgent investigation or documenting actual care. Validate the submitted step, not hidden unrelated controls. Do not default undocumented clinical findings to normal, zero, no allergy, or no risk. Completion badges describe documentation, not clinical stability or verified accreditation compliance.

No localStorage/sessionStorage containing patient data. On failed save keep entered values in memory and show retry; leaving with unsaved edits requires an explicit decision. Render only one visit's workflow, not eleven forms per patient on a dashboard roster. Test mobile navigation without eleven cramped horizontal tabs.

## 3. Ownership, persistence and contracts

### Existing records to reuse

- `Pasien`: identity and longitudinal allergy text. New structured allergy-screening status must not turn blank legacy text into “no allergies”. Updating patient-level allergies requires an explicit action and audit.
- `KunjunganPasien`: admission/guarantor, ABCDE, histories, psychosocial/spiritual fields, screening, examination, medical/nursing diagnosis and plans, disposition fields.
- Existing examination JSON fields overlap. Establish a field-by-field adapter: the new UI writes one canonical location per finding, reads legacy-only values without dropping them, and tests all existing print consumers. Do not bulk copy conflicting JSON values.
- `OrderPenunjang`: actual sent investigations and results. Extend its choices for ECG/other only after tracing filters, labels and result-entry consumers. Selecting a planned investigation is not sending an order.
- `TindakanAsesmen`: clinical action rows and existing master/manual tariff overrides/EP associations. Extend with explicit planned/performed/cancelled semantics and execution metadata as needed.
- `BillingItem`: financial source of truth, linked by the existing `TindakanAsesmen.billing_item`; never calculate permanent amounts with JS floats.
- `CPPT`: professional progress records. Add a nullable authenticated author reference where needed; preserve legacy name/profession text. A POST profession string cannot confer doctor authority.

### Proposed additions — not existing symbols

Generate additive migrations using the next available migration numbers; do not assume a number from this plan.

| Proposed model/field | Purpose and invariants |
|---|---|
| `IgdAssessmentWorkflow` | One-to-one visit; origin IGD unit, `DRAFT/FINAL`, integer version, last step, update actor/time, final actor/time and schema version. New visits only create it on an intentional write, never on GET. |
| `IgdVitalObservation` | Append-only visit observations with INITIAL/EVALUATION phase, observed time, authenticated recorder, BP/pulse/RR/temperature/SpO2/GCS/pain. Null means unmeasured; zero remains valid where applicable. Corrections append and reference the corrected observation. |
| `IgdAssessmentRevision` | Unique `(workflow, revision)`; original final snapshot plus append-only addenda with actor, timestamps, reason and clinical signatures. Snapshot includes identity/guarantor at signing, relevant clinical data, observation/action/order references and disposition. Historical snapshots do not resolve to mutable current patient values. |
| `IgdWorkflowAction` | Durable unique `(workflow, request_id)` plus operation type, request digest, actor and resulting record references. Same request/key returns the original result; different payload with reused key is rejected. Authentication/authorization precede replay lookup. |
| Minimal clinical extensions | Explicit triage system; allergy-screening status; education barriers; local examination and validated anatomical-marker JSON; end-of-IGD response narrative/time. Reuse existing fields whenever they already represent the requirement. |

Keep current visit TTV fields as the latest-observation projection for existing dashboards. Step 4 and step 10 read their own observation records. Saving an earlier-timestamp observation must not replace a later projection. Import existing TTV into a legacy initial observation only when provenance/time is known; otherwise show it as legacy, not a new measurement.

Historical visits have no invented final status, triage system, signature, action execution or measurement timestamp. Legacy billed actions keep their money and are marked as legacy/uncertain execution until explicitly reviewed. Do not delete/reprice them to conform to the new planned/performed model.

### Proposed endpoints — not live URLs

All below are prefixed by `/pasien/kunjungan/<pk>/asesmen-igd/` and implemented in a **new** `pasien/igd_workflow_views.py`.

| Relative route | Method | Contract |
|---|---|---|
| root | GET | Authorized workflow or legacy projection; no writes. |
| `langkah/<step>/draft/` | POST | Step-owned patch plus expected version. Omitted fields remain unchanged; permitted explicit clears are represented separately. |
| `aksi/` | POST | Typed explicit operation: send investigation, append CPPT, execute action, sign section, or apply disposition. Stable request ID required; dispatch to domain services, not arbitrary function names. |
| `saran-ai/` | POST | Clinical AI suggestions only; no persistent clinical mutation. Auth, unit scope, rate limit and module gate apply. |
| `finalisasi/` | POST | Validate current version/signatures, snapshot and explicitly requested disposition transactionally. Replay-safe. |
| `addendum/` | POST | Authorized, reason-required new signed revision; original final record remains intact. |

New mutation requests require CSRF and return canonical updated values/version. Validation errors are field-addressable; stale version is `409`; no writes on validation/authorization failure. HTML form fallback can return the same errors with entered values. Successful navigation uses server-generated URLs.

Every new mutator locks the visit/workflow in a consistent order inside `transaction.atomic()`. Existing competing writers touching the same signed fields must use the same guard/version mechanism, otherwise optimistic locking in the new page is ineffective. Durable request IDs survive restarts; cache-only de-duplication is insufficient.

## 4. Implementation tasks

The checkboxes in this section preserve the original implementation/TDD working notes, including first-batch checkpoints; they are not the final completion ledger. The authoritative task-by-task implementation and verification disposition is §8. No unchecked historical RED instruction should be read as a new request to repeat already-verified implementation work.

The proposed new files below are intentionally new artifacts, not claims that they already exist. Keep one task active. Do not commit/push automatically; review diffs and follow the user's release authorization.

### Task 1 — Characterization, clinical policy and triage correction

**Modify:** `pasien/models.py`, `pasien/views.py`, `templates/pasien/igd_dashboard.html` where triage labels are rendered.
**Create:** `pasien/tests_igd_workflow.py` for new behavior; additive migration for the explicit triage-system field when required.
**Reference:** `pasien/tests_revisi_asesmen_medis_igd.py`, `pasien/tests_igd_lifecycle.py`, analysis §3.

- [ ] Resolve D01; list every reader/writer of `triage` and `triase_kategori`, including print templates and copy-previous.
- [x] RED: category 5 must not imply DOA; invalid category/system is rejected; unknown historical scale is preserved; triage changes do not set death/discharge status.
- [x] GREEN: replace substring-based conversion with explicit validated policy. Separate scale/category/color and death semantics. Update labels without silently rewriting historical values.
- [ ] RED/GREEN: characterize existing TTV, tariff override, EP, attachments, current billing and disposition behavior so the new UI can preserve it.
- [x] Run focused new tests and `pasien.tests_revisi_asesmen_medis_igd`; review the diff.

**Acceptance:** corrected semantics are consistent across save/read/print; no record is declared dead from category selection.

### Task 2 — Draft/final data foundation, observation history and guarded writes

**Modify:** `pasien/models.py`, `pasien/views.py`, `pasien/asesmen_tindakan.py`, `pasien/unit_scope.py` only if an explicit historical read policy requires it.
**Create:** `pasien/forms_igd_workflow.py`, `pasien/services/igd_assessment_workflow.py`, generated `pasien/migrations/` files.
**Test:** `pasien/tests_igd_workflow.py`.

- [x] RED: workflow uniqueness; read-only GET; step patch preserves unrelated sections; explicit clearing differs from omitted fields; a stale version fails without writes.
- [x] RED: observation append preserves initial values, null versus zero and timestamps; two simultaneous edits cannot silently overwrite each other.
- [ ] GREEN: add the proposed workflow/observation/revision/action records and minimal clinical fields, with model constraints, schema validation and fixed write ownership.
- [ ] Implement service/form boundaries, `transaction.atomic()`, consistent locking and a field ownership map for all eleven steps.
- [ ] Add shared guards to legacy writers: generic and IGD assessment saves, copy-previous, reset/delete, relevant TTV/visit edits, action-row writes and attachment deletion. Protect signed snapshot material without blocking unrelated later RANAP care or legitimate appended lab results.
- [ ] Preserve all legacy values; signed records use addenda, not destructive reset. New-only rollout logic must not silently change RAJAL behavior.
- [ ] Validate migrations forward on local SQLite and isolated PostgreSQL; `makemigrations --check --dry-run` must report no pending model changes after generation.

**Acceptance:** no partial-step deletion, lost initial TTV, final-record bypass through a legacy URL, or retroactively fabricated history.

### Task 3 — One dedicated eleven-step IGD page

**Modify:** `pasien/urls.py`, `templates/pasien/igd_dashboard.html`.
**Create:** `pasien/igd_workflow_views.py`, `templates/pasien/igd_workflow.html`, `static/js/igd-assessment-workflow.js`.
**Test:** new `pasien/tests_igd_workflow_ui.py`.

- [ ] RED: authorized route resolves, exactly eleven ordered steps render, existing records prefill, unauthorized/other-unit/non-IGD-new-workflow requests fail. Page rendering, save/readback, CSRF and service-level cross-unit denial are proven; comprehensive HTTP negative cases remain open.
- [x] GREEN: build header, stepper, individual form boundaries, explicit draft/save-next behavior, version handling and field error focus.
- [ ] Initial creation requires an IGD visit. Existing IGD workflow/snapshot remains addressable after inpatient transfer mutates `jenis_kunjungan`; use a deliberate origin-unit historical read policy, not a global scope bypass.
- [x] Keep shared `_asesmen_awal_wizard.html` working for legacy consumers. The enabled dashboard now routes its primary assessment, CPPT, investigation/lab and disposition shortcuts into the corresponding workflow steps; disabled rollout retains the legacy UI without removing managed-record guards.
- [x] Add loading/error/retry/unsaved states, keyboard navigation and mobile-friendly progress. Never store patient data in browser persistent storage.

**Acceptance:** one visit-specific workflow, no nested forms, no full-record reset on step save, and no RAJAL layout regression.

### Task 4 — Clinical steps 1–6 and anatomical markers

**Modify:** new workflow forms/service/page/JS; canonical `Pasien`/`KunjunganPasien` adapters.
**Test:** `pasien/tests_igd_workflow.py`, `pasien/tests_igd_workflow_ui.py`; existing Morse tests.

- [ ] RED: identity is not writable via clinical mass assignment; guarantor changes follow permission/audit and explicit tariff review; missing insurer tariffs remain unknown.
- [ ] RED/GREEN: arrival/ABCDE, histories, structured allergy-screening state and existing allergy text; no automatic “normal” defaults.
- [ ] RED/GREEN: TTV bounds/precision, GCS component validation, legitimate zero pain, unmeasured values, timestamp and recorder; preserve earlier measurements.
- [ ] RED/GREEN: psychosocial/spiritual/education barriers, MST and Morse; unsupported screening tools show their own method and are not calculated as Morse.
- [ ] RED/GREEN: organ-field adapter, local examination and marker JSON with allowed side/region/type, normalized coordinates, labels and text alternative. Marker add/edit/delete survives reload and renders in print; no raw user HTML/SVG execution.

**Acceptance:** six steps round-trip all values, including legacy-only findings, without contradictory duplicates or automatic clinical assertions.

### Task 5 — Investigation orders and results in step 7

**Modify:** `OrderPenunjang` choices and affected filters/templates, existing order services extracted from `pasien/views.py` as needed, workflow service/page, generated migration.
**Test:** new `pasien/tests_igd_workflow_integration.py`.

- [ ] RED: choosing/saving a proposed investigation does not send an order; explicit send creates one order on repeated or concurrent requests.
- [ ] RED: wrong-visit result/attachment access is forbidden; pending, in-progress, completed and critical results remain distinct.
- [ ] GREEN: reuse LAB/RADIOLOGI workflows, add explicit ECG/other support and displayed result sources; CT remains an imaging examination, not a fabricated external integration.
- [ ] Reuse protected attachment handling; show actual order/result records and allow further assessment while results are pending.
- [ ] Ensure final snapshots retain the results known at signing; late results append to the live episode/addendum rather than modifying an already signed snapshot.

**Acceptance:** real, attributable orders/results rather than checkboxes pretending that investigations were ordered or completed.

### Task 6 — Medical/3S planning with Manual, Master and AI modes

**Modify:** workflow forms/service/page, `akreditasi/ai_service.py` through a narrow public wrapper if needed, `akreditasi/system_models.py` for a default-off `ai_enable_igd` gate and its generated migration.
**Create:** `klinis/services/ai_igd.py`, `pasien/tests_igd_workflow_ai.py`.
**Reuse:** `klinis/services/saran.py`, `klinis/services/tarif.py`, existing ICD/3S services and backend AI configuration.

- [ ] RED/GREEN: Manual and Master independently produce editable diagnosis/plan data; 3S uses actual SDKI→SLKI→SIKI mappings and preserves manual edits.
- [ ] Keep deterministic catalogue suggestions labeled `Saran Sistem`, not LLM. Actual AI remains a separate user-requested mode; no provider calls on page load or draft save. Extend action provenance with a distinct AI source and accepted-suggestion metadata where needed; do not overwrite the existing `SARAN` meaning or label catalogue suggestions as AI-generated.
- [ ] Resolve D04. Reuse backend-only transport and configuration; build a minimal clinical allowlist payload without identity fields, scrub free text and explicit patient identifiers, and validate output against a bounded schema/catalogue.
- [ ] RED: disabled/unconfigured AI, timeouts, invalid JSON, fabricated codes, cross-unit request, repeated clicks, rate limit and prompt-like free text do not mutate records or expose keys/prompts.
- [ ] GREEN: AI returns draft suggestions/provenance; accepting selected suggestions is a normal validated draft write. Unknown codes cannot create master records. No auto-selection of therapy, tariff or final signature.
- [ ] Use fake/synthetic cases and mocked HTTP for tests. A live provider test, if separately approved, uses non-patient data and records actual availability without fabricating a result.

**Acceptance:** all three specified modes exist as distinct behaviors; lack of AI service does not block Manual/Master or clinical work. Do not declare AI production-ready from mocked tests alone.

### Task 7 — Step 9 execution, CPPT and billing invariants

**Modify:** `pasien/models.py` for action execution metadata and CPPT author if required, `pasien/asesmen_tindakan.py`, `klinis/services/tarif.py`, existing CPPT/action handlers in `pasien/views.py`, workflow service/page.
**Test:** `pasien/tests_igd_workflow_integration.py`, existing tariff/EP tests.

- [ ] RED: saving planned actions does not create execution records or charge new workflow plans; executing one action links its clinical row, authenticated performer, CPPT and existing billing relation once.
- [ ] RED: save-next, refresh/retry, simultaneous submissions and repeated finalization do not duplicate orders, CPPT or charges. Reused request ID with a different payload fails.
- [ ] RED: partial saves never call the existing full-list replacement contract with an incomplete action collection. Missing rows cannot delete executed/legacy-billed items.
- [ ] GREEN: separate planning persistence from execution-triggered billing for workflow-managed visits. Keep legacy compatibility until explicit adoption; preserve existing charges and overrides without repricing/deletion.
- [ ] Use Decimal end-to-end, server-resolved tariff references and reasoned overrides; no invented SIKI/insurance amount or client-trusted totals. Recompute preview explicitly when guarantor changes and retain audited overrides.
- [ ] Bind CPPT author/profession to authenticated account capabilities. Medical verification requires the proper signer; sending `profesi=DOKTER` is not sufficient.
- [ ] Define repeated legitimate action semantics explicitly: separate execution IDs or explicit aggregate quantity, never silent loss of a second clinically distinct performance.

**Acceptance:** clinical plan, recorded performance, CPPT and financial charge remain attributable and consistent; manual non-assessment billing is untouched.

### Task 8 — Evaluation, final disposition, immutable resume and addendum

**Modify:** workflow forms/service/views/page, `pasien/views.py` disposition adapters, `templates/pasien/cetak_resume_igd.html`, `templates/pasien/cetak_asesmen_medis_igd.html`, rekap/detail consumers.
**Test:** `pasien/tests_igd_workflow_integration.py`, new `pasien/tests_igd_workflow_finalization.py`.

- [ ] RED/GREEN: step 10 records condition, response, author/time and repeat TTV observations; step 4 remains readable as initially recorded.
- [ ] Resolve D02/D03. Validate outcome-specific inputs: home instructions/control, available inpatient bed/DPJP, referral destination/reason, specialist consultation versus transfer, or death details. Preserve PAPS and SBAR behavior.
- [ ] Extract reusable disposition application logic, do not call views directly. Separate a saved disposition proposal from an applied transition. Finalizing documentation alone must not implicitly discharge a patient.
- [ ] RED: unavailable-bed races, stale version, missing signature, unauthorized signing and outcome validation failures roll back all associated local writes. Lock bed/state transitions and keep roster, queue and scope consistent.
- [ ] GREEN: finalization writes an immutable snapshot and signatures; when an explicit disposition is requested, coordinate it transactionally. Record IGD origin before a transfer mutates current service ownership. Do not perform unrequested external integrations or claim they succeeded.
- [ ] RED/GREEN: every old edit/copy/delete/attachment route is unable to overwrite signed material; read/print works after transfer for authorized historical readers without exposing other units.
- [ ] Add reason-required addenda as new signed revisions. Original signed snapshot remains retrievable; printing indicates revision, draft/final state and signer/time. No ordinary `delete` removes a signed assessment or already performed care.

**Acceptance:** all requested outcomes and retained PAPS behavior work; “Simpan Permanen” has a testable immutable-record meaning, not merely a success toast.

### Task 9 — Regression, browser evidence, PostgreSQL and controlled release

**Modify:** tests and release notes/this plan; collect static artifacts only for an approved release.

- [ ] Run all new workflow suites, then `klinis` and `pasien` regression suites. Include relevant `akreditasi` AI/navigation/control tests and expand to full app regression for shared model/RBAC/tariff changes.
- [ ] Run `manage.py check`, `makemigrations --check --dry-run`, and `git diff --check`; check changed JavaScript syntax. No claim of success until actual output is recorded.
- [ ] Test PostgreSQL with two independent connections: stale concurrent drafts, same idempotency key, duplicate finalization and same-bed transfer race. SQLite passing does not establish production lock behavior.
- [ ] Exercise the browser with synthetic visits at 375, 768 and 1366px: all eleven steps, reload/resume, missing fields, zero pain, marker operations, pending results, Manual/Master/AI unavailable, execution, repeat TTV, each disposition, final print and attempted legacy-route edits.
- [ ] Cover roles: authorized IGD doctor/nurse, same role outside the unit, viewer, admin without clinical signing capability, and anonymous user. Test direct URL access, not only hidden buttons.
- [ ] Add a default-off workflow rollout gate and compatibility guards. Rollback may hide the new UI but must not re-enable destructive legacy writes against already finalized records.
- [ ] On separately authorized release: snapshot/backup relevant production schema/data, apply and read back additive Supabase migrations manually, run `collectstatic` and include required tracked hashed `staticfiles/` artifacts, review exact staged paths, then push/deploy as requested.
- [ ] Verify exact deployed SHA, Vercel READY/alias, pending migrations and production read-only smoke. Use synthetic isolated test data for write-based QA; do not silently create real patient records. Store evidence without patient data/secrets.
- [ ] Rollback keeps additive tables/signed records intact. Disable affected writes if necessary; do not redeploy a pre-guard version that bypasses finalization protections. Restoring a backup is a separate explicitly authorized data operation.

**Acceptance:** behavioral, concurrency, authorization, browser and migration evidence exists; production readiness and live AI availability are reported separately.

## 5. Commands and evidence

### Baseline actually executed during planning

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python manage.py test \
  pasien.tests_revisi_asesmen_medis_igd \
  pasien.tests_asesmen_save_ep_tarif \
  pasien.tests_asesmen_rekap \
  pasien.tests_morse \
  pasien.tests_igd_lifecycle --keepdb --noinput
```

Observed: **29 tests, 30.972 seconds, OK, exit 0**. This is not full-suite or browser verification and does not validate any proposed new feature.

### During implementation, after the new test modules exist

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python manage.py test \
  pasien.tests_igd_workflow \
  pasien.tests_igd_workflow_ui \
  pasien.tests_igd_workflow_integration \
  pasien.tests_igd_workflow_ai \
  pasien.tests_igd_workflow_finalization --keepdb --noinput

PYTHONIOENCODING=utf-8 .venv/Scripts/python manage.py test klinis pasien --keepdb --noinput
PYTHONIOENCODING=utf-8 .venv/Scripts/python manage.py test akreditasi --keepdb --noinput
.venv/Scripts/python manage.py check
.venv/Scripts/python manage.py makemigrations --check --dry-run
git diff --check
```

Record actual commands, checkout SHA, database backend, test counts/duration, failures and evidence paths during execution. Do not copy historical test totals as current verification. Never put credentials, patient identifiers or entire medical payloads into release logs.

## 6. Completion checklist

- [x] R01–R11 demonstrated through domain tests and isolated browser journeys; see the verification report for each requirement.
- [x] Triage category 5 is not DOA; historical ambiguity is preserved.
- [x] Partial drafts, concurrent edits, repeated requests and guarded legacy writers verified.
- [x] Initial/repeat observations remain distinct, attributable and append-only; corrections reference prior observations.
- [x] Markers, order/results, Manual/Master/AI adapter, CPPT/action/billing and eight outcome choices verified. Positive AI transport is mocked, not a live-provider availability claim.
- [x] Manual/Master work without AI; signed tickets and explicit acceptance guard AI mutation.
- [x] Profession/unit permissions, clinical approvals, final snapshots and addendum revisions verified server-side.
- [x] Historical IGD resume remains readable after transfer without granting unrelated-unit access.
- [x] Relevant regressions, PostgreSQL races and browser scenarios passed with durable evidence.
- [ ] Production release condition not invoked: no migration/deployment/read-back/production rollback operation was authorized or performed.

**Execution order:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. Keep the final public cutover behind the rollout gate until the entire eleven-step path is verified. Do not describe the whole requirement as complete after delivering only the assessment UI.

## 7. Execution record — first implementation batch

### Done

- Triaging: added `triase_skala` with additive migration `0021_explicit_triage_scale`; removed automatic category-to-color mapping from the medical save handler. Rejected invalid categories before any mutation, preserved unknown historical systems, and corrected both the dashboard labels and the printed medical assessment. The existing medical-save regression fixture now submits its intended ATS system and KUNING color explicitly instead of assuming an automatic conversion.
- Persistence foundation: added `IgdAssessmentWorkflow`, `IgdVitalObservation`, `IgdAssessmentRevision` and `IgdWorkflowAction` via `0022_igd_workflow_foundation`. Observation payloads use server-validated JSON rather than duplicating all vital columns; Decimal serialization preserves precision. The revision/action tables are foundations, not evidence of implemented signing/addendum or action endpoints.
- Draft application service: visit/workflow locking, object/unit/profession checks, per-step field allowlists, model-form validation, version conflicts, omitted-versus-blank semantics, no draft billing reconciliation, append-only observations and out-of-order projection protection. Initial and evaluation forms read their own recorded phase rather than replacing the initial form with the latest vital projection.
- Compatibility guard: legacy assessment saves/copy/reset, relevant TTV and visit edit/cancel endpoints, attachment mutation and one-click execution routes reject writes to workflow-managed episodes. This protects the draft version boundary and FINAL metadata. Complete signing, late-result/addendum and disposition integration remain Task 8 work.
- Dedicated draft page: `/pasien/kunjungan/<pk>/asesmen-igd/`, eleven step labels, one scoped form per page, explicit save/save-next, CSRF, loading/error/retry/dirty-state handling, patient/allergy header and read-only viewer controls. Existing orders, CPPT, billing and observations are displayed from real records. This is a draft preview, not eleven completed clinical domain actions.
- Rollout: `IGD_WORKFLOW_ENABLED` defaults to false in `config/settings.py`; only an enabled environment gets the dashboard preview link. The existing shared wizard and normal dashboard entry points are not replaced before parity. No production environment flag was changed.
- Packaged the new JavaScript with `collectstatic`; retained existing hashed assets. Verified source bytes, collected unhashed bytes, manifest-selected hashed bytes and decompressed gzip are equal; `node --check`, Django system checks, migration drift checks and scoped `git diff --check` passed.
- Actual TDD evidence includes initial four triage failures, eight missing-foundation failures, missing-route failures, an initial-versus-evaluation readback regression, mobile navigation/print failures, viewer read-only failure and missing-explicit-system failure, followed by passing checks. Logs reside in `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/igd-*.log`.
- Full local regression after the last application edit: `manage.py test klinis pasien --keepdb --noinput` — **335 tests, 228.839 seconds, OK, exit 0**. An earlier 334-test full run also passed before the explicit-system regression was added. Do not sum these overlapping runs.
- Isolated browser evidence: real local WSGI/session/CSRF with synthetic fixtures; eleven pages at 375/768/1366 widths, 33 geometry checks, sequential keyboard access, draft save/reload, two-record isolation, zero pain, initial/repeat observations and stale-request rejection. A sticky action bar initially covered fields despite zero horizontal overflow; it was removed and the mobile step list replaced by a compact selector before the passing run. Evidence: `igd-browser-results.json` and `igd-workflow-375.png`, `igd-workflow-768.png`, `igd-workflow-1366.png` in scratch. The final passing probe ran after restarting the fixture server against the latest Python/templates; no page errors or action/field overlaps were detected. Fixture servers and the disposable PostgreSQL container were stopped after verification.
- Isolated PostgreSQL17 schema/concurrency probe: new schema migrations 0021/0022 executed; two separate connections raced the first draft with version 0, yielding one saved workflow/version 1 and one stale rejection, with no lost update. Evidence: `igd-postgresql-results.json`.

### Not done — implementation and live-environment gates

- Tasks 2/3 remain partially checked: minimal new clinical screening/examination fields, comprehensive historical-transfer read/print acceptance and full signing-path protections are not all implemented or proven. Do not mark these entire tasks complete from their passing draft tests.
- Tasks 4–8 are not delivered: structured allergy/education refinements, anatomy-marker editor, unified explicit investigation actions, full Manual/Master/AI mode UI/service, performed-action/CPPT/billing reconciliation, final evaluation narrative, outcome application, clinical signatures, immutable final resume and addendum endpoints. Existing records shown in the preview are not substitutes for these features.
- PostgreSQL **full migration-chain** verification failed at historical `akreditasi/0013` because `seed_starkes_16_bab` uses SQLite-style `cursor.lastrowid` after INSERT. The separate schema/concurrency probe explicitly skipped historical `RunPython` seed operations; it does NOT prove a clean full PostgreSQL bootstrap. No historical migration or production seed was weakened. See `igd-pg-probe.log` and the explicit exclusion in the JSON evidence.
- PostgreSQL finalization/action-idempotency/bed-race gates are pending their implementation. A passing draft race is not proof of those operations.
- Full `akreditasi` regression, live AI provider verification, authenticated production browser acceptance and all release/rollback checks remain pending. The local suite is `klinis` + `pasien`, not the entire repository.
- The primary local application DB and production DB have not been migrated by this batch; new migrations ran only in disposable test/QA databases. Release requires explicit production migration authorization and read-back.

### Skipped on purpose

- Commit, push, deployment, production migrations, activation of the workflow flag, AI quota purchases and external clinical integrations: user authorized implementation, not publication or production writes.
- Replacing old assessment entry points before parity, inferring old triage systems, silently repricing/removing existing billing, and claiming FINAL/signature support from database columns alone.
- Background helper delegation and installed CLI paths failed before modifying application files (provider entitlement/authentication and missing CLI installations). Implementation and verification were then performed directly; failed helpers provide no review evidence.

## 8. Final execution record — supersedes first-batch open items

### Done

| Task | Final implemented outcome | Verification |
|---|---|---|
| 1 — Characterization/triage | Explicit scale/category/color policy; unknown historical data preserved; no category-to-death inference; existing legacy behavior covered | Triage, medical-save, lifecycle, tariff/EP and recap regressions |
| 2 — Persistence/guards | Workflow, append-only observations/corrections, durable action replay, snapshots/revisions; step patches, version locking and legacy guards; scoped later-service append care | Foundation/hardening/finalization suites; full PostgreSQL migrations and races |
| 3 — Dedicated page | Eleven scoped steps, responsive navigation, drafts/retry/dirty state, history/print routes and gated dashboard shortcuts | UI tests; 48 browser geometry checks; dashboard smoke |
| 4 — Clinical steps | Histories/allergy, validated vitals/GCS, psychosocial/education fields, partial-safe Morse/MST, organ/local findings and anatomy editor | Clinical/hardening tests; browser save/reload and marker add/edit/delete |
| 5 — Investigations | Explicit orders, result/provenance entry, critical-result checks, scoped upload/download; late operational results cannot rewrite signed snapshots | Integration tests and browser order/result/attachment journey |
| 6 — Planning modes | Manual and Master/3S, independent default-off AI adapter/configuration, bounded output, actor/visit/version-bound tickets, explicit acceptance preserving unselected manual sections | AI/clinical tests with mocked provider; browser Manual/Master and disabled-AI fallback |
| 7 — Actual care/billing | Separate plan/execute/cancel, profession-bound CPPT, linked single charge, unknown tariff preserved, Decimal pricing and before/after tariff audit | Integration tests; browser medical/nursing performance; PostgreSQL execution replay |
| 8 — Evaluation/finalization | Separate evaluation history, current-content approvals, explicit outcome validation, atomic bed/queue/ownership transitions, immutable final resume and addendum | Outcome/finalization tests; all eight browser outcomes; bed/finalization races |
| 9 — Local release gates | Regression, checks, additive migration-shape review, PostgreSQL bootstrap/races, browser roles/journeys, packaged-asset byte equality and default-off rollback policy | Durable evidence and verification report below |

- Final regression: `manage.py test klinis pasien --keepdb --noinput` — **400 tests, 232.668 seconds, OK, exit 0**. The subsequent final run of eight workflow modules passed **96 tests, 9.753 seconds**, including the portable temporary-media fixture. These overlapping totals are not added.
- Earlier shared-app gate: `manage.py test klinis pasien akreditasi accounts --keepdb --noinput` — **1,383 tests, 874.286 seconds, OK, exit 0**. This preceded the two localized dashboard/tariff-audit additions; both are covered by the final clinical and workflow runs. No extrapolation to a never-run 1,385-test shared gate is made.
- Browser: real synthetic WSGI/session/CSRF, all eleven pages at 375/768/1366px, populated operation pages, **48 geometry checks**, keyboard/save/reload/network retry/stale conflict, marker lifecycle, clinical calculators, investigations/files, medical/nursing care, separate evaluation, approvals, immutable print/addendum and rejected legacy overwrites. All eight outcome choices passed functional desktop checks. Role controls cover non-superuser doctor/nurse, viewer, other-unit doctor, non-clinical admin and anonymous access. No page errors. Supplemental smoke verifies datetime-local WIB survives two saves and primary dashboard shortcuts use steps 7/9/11.
- PostgreSQL17: full migration chain applied with **no skipped RunPython operations**, then stale draft, same order request, same execution request, duplicate finalization and competing same-bed transfer verified on separate connections. Zero pending migrations. The historical seed inserted-ID incompatibility was fixed with PostgreSQL `RETURNING id` at all three affected seed sites, retaining SQLite `lastrowid`; this supersedes the first-batch schema-only exception.
- Build/checks: `collectstatic`, JavaScript syntax, Django check, migration drift and diff checks passed. Both JS source files equal their collected, manifest-selected hashed and decompressed gzip bytes. Local static collection was necessary to validate hashed storage; it did not publish a release.
- Delivery remains uncommitted on `master`. Base SHA is unchanged. Code fingerprint: `9677bd5950d43f6083132110038642f98f977b7ae87620458d216c1f3f1863da` (45 source files; detailed hashes in `verification.json`).
- Verification report: `../specs/2026-11-12-igd-workflow-verification.md`.
- Durable evidence: `../evidence/igd-workflow/verification.json`, `browser.json`, `postgresql.json`, three anatomy screenshots and `resume-synthetic.pdf`. No session fixture or credential-bearing seed log is copied into the repository.

### Not done — needs the live environment and separate release authorization

- Production backup/migration/read-back, commit/push/deploy, exact deployed SHA/alias confirmation, authenticated production acceptance and live rollback exercise. The implementation request does not authorize these external effects. Run the approved production migration/release procedure only after authorization; do not treat local PostgreSQL evidence as production migration state.
- Live AI provider/entitlement and clinical-data approval: positive transport is mocked. Manual/Master and disabled-provider behavior are verified; no claim of live AI production readiness is made.

### Skipped on purpose

- Activation of either rollout/AI flag in production; flags remain default-off in code.
- Autonomous treatment, automatic insurance-claim/financial clearance, external LIS/SISRUTE/SATUSEHAT execution, certificate-provider signing integration and physical-device/printer certification.
- Retrospective clinical rewrites, implicit guarantor correction/repricing, removal of existing billed care and inferring undocumented normal findings. Guarantor corrections are intentionally rejected by clinical drafts and require a separate administrative/financial review rather than a silent workflow edit.
- Repeating the original chronological RED instructions after the capability already exists. The original working checklist is retained as design history; final verified task status is the table above.
