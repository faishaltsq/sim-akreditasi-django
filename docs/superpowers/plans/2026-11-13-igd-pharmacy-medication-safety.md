# IGD Pharmacy and Medication Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task. Track checkboxes and RED → GREEN → REFACTOR. This document does not authorize implementation, production data imports or release.

**Status:** CORE LOCAL IMPLEMENTATION VERIFIED. See `../specs/2026-11-13-igd-clinical-expansion-delivery.md` for implemented scope, proof and unresolved pricing/clinical-approval boundaries; historical authoring checkboxes are not bulk-ticked.
**Goal:** Add reviewed four-level medication selection, structured prescriptions, medication risk/PPRA review and replay-safe pharmacy dispensing to the existing IGD episode.
**Architecture:** Reuse `ResepElektronik`, `ResepDetail` and `BillingItem`. Put reviewed medication identities/formularies in `klinis`, prescription/risk lifecycle in focused `pasien` services, and expose a small IGD composer plus existing pharmacy worklist; never maintain a parallel recipe or charge ledger.
**Tech Stack:** Existing Django, Bootstrap, vanilla JavaScript, Decimal and transactional PostgreSQL gates. No new LLM SDK, stock engine or external data provider is required.
**Spec:** `../specs/2026-11-13-igd-diagnosis-pharmacy-ancillary-analysis.md`, RX01–RX03 and source document 1 lines 18–535.
**Dependency:** Diagnosis/action plan contracts; ancillary order IDs for optional culture references. The roadmap serializes shared-file edits.

## Global Constraints

- All roadmap constraints apply. Existing prescription rows and prices remain historical facts; never classify them by fuzzy name or rewrite them in bulk.
- The source's generics/brands/strengths/risk categories are examples, not certified master data. Source version, reviewer and approval precede activation.
- Four-level selection: type → therapy group → generic/strength/form → product. Racikan selects multiple eligible component products and a compound recipe; BMHP uses supply group → specification → product rather than fake drug classes.
- Dose, dose unit, concentration, dispensing unit and pack size are different concepts. Do not calculate tablet quantity from mg without an explicit conversion.
- LASA, High Alert, OOT, controlled-substance class and antimicrobial restriction are independent flags. Multiple flags may coexist.
- Fornas membership is version/effective-period/restriction data, not a guarantee of claim approval or stock availability.
- Only authenticated permitted clinicians prescribe; pharmacists review/dispense in assigned service/depo scope. Admin, assessor and arbitrary posted profession cannot substitute for these predicates.
- Draft/save/send/dispense/complete/cancel are distinct operations; no bill on draft/save/send. Completion creates linked charges once according to approved recognition policy.
- Allergy/duplicate/PPRA evaluation is local, deterministic and policy-versioned; no live AI decides a prescription, override or approval.

## Review Focus

1. Half-tablet, mL versus bottle, PRN and variable-dose courses — Task 2 pins dimension-aware calculation and explicit unknown/override, never guessed totals.
2. Two brands with shared active ingredient and a third drug in the same therapy class — Task 3 distinguishes exact ingredient duplication from class-overlap review.
3. Unknown/blank historical allergy versus confirmed none — Task 3 pins unresolved screening and manual pharmacist review without a false negative.
4. Culture reference or PPRA approval belongs to another visit, is stale or self-approved — Task 4 pins actor/visit/version/content binding.
5. Two pharmacy requests finish the same prescription — Task 5 pins unique detail-to-billing linkage, locks and durable replay.

## File inventory

**Create:** `klinis/data/medication_catalogue.json`, `klinis/services/medication_catalogue.py`, `klinis/management/commands/import_medication_catalogue.py`, `klinis/tests/test_medication_catalogue.py`; `pasien/forms_medication.py`, `pasien/services/prescriptions.py`, `pasien/services/medication_safety.py`, `pasien/services/ppra_review.py`, `pasien/pharmacy_views.py`, `pasien/tests_medication_catalogue_ui.py`, `pasien/tests_prescription_workflow.py`, `pasien/tests_medication_safety.py`, `pasien/tests_pharmacy_authorization.py`, `templates/pasien/_igd_medication_composer.html`, `static/js/igd-medications.js`.
**Modify:** `klinis/models.py`, `klinis/admin.py`, generated `klinis/migrations/`; `pasien/models.py`, `pasien/admin.py`, generated `pasien/migrations/`; `pasien/views.py`, `pasien/urls.py`, `pasien/igd_workflow_views.py`, `pasien/forms_igd_operations.py`, `pasien/services/igd_actions.py`, `pasien/services/igd_finalization.py`; `templates/pasien/igd_workflow.html`, `templates/pasien/_igd_workflow_operations.html`, `templates/pasien/igd_workflow_resume.html`, `templates/pasien/farmasi_antrean.html`, `templates/pasien/kunjungan_detail.html` for its existing prescription entry; `static/js/igd-clinical-controls.js` only for shared operation serialization integration.
**Existing regression references:** `pasien/tests_object_authz.py`, `pasien/tests_route_rbac.py`, `pasien/tests_security_owasp.py`, `pasien/tests_igd_workflow_finalization.py`, `pasien/tests_igd_workflow_integration.py`.

All new symbols below are proposed. Generate migration names from the current leaf, not assumed numbering.

## Task 1: Reviewable medication identities, branches and formulary

**Files:** clinical catalogue models/data/importer/service/admin/tests.
**Produces proposed models:**

| Model | Fields/invariants |
|---|---|
| `KelasTerapiObat` | Stable code/name, reviewed source/version, active state; separate supply grouping for BMHP |
| `GenerikObat` | Canonical generic + strength + strength unit + dosage form; structured concentration/dispensing unit; therapy group; review status |
| `ProdukFarmasi` | Stable local product ID, generic FK nullable only for BMHP, supply group/specification for BMHP, brand/form/pack, optional verified KFA code and code-system version, independent risk flags, Tall Man display label, active/review state |
| `KomposisiProdukFarmasi` | Product→active ingredient relation with Decimal strength/unit; combination products have multiple rows; support ingredient-based duplicate/allergy evaluation |
| `KeanggotaanFormularium` | Product/generic target, FORNAS/RS, source/edition, valid-from/to, restrictions and reviewed scope; no inferred coverage from payer alone |

**Interface:** proposed `medication_choices(actor, *, visit, kind, parent_id=None, query='', page=1) -> dict`; same paginated `results/page/has_more` convention as ancillary lookup. Catalogue lookup does not expose clinical patient fields.

- [ ] RED: normal drug hierarchy, multiple risk flags, combination ingredients, inactive ancestor, wrong-type parent, expired formulary, forged KFA code and idempotent importer. Missing source or reviewer prevents active status.
- [ ] GREEN: implement models and clean/constraint validation; restrict writes to catalogue managers. Keep product identity independent from display names. Prefer explicit enum fields/through records over concatenated flags in a label.
- [ ] Extract all eight source therapy groups and retain source row text. Split strengths/forms/brands into reviewed product candidates; do not create unverified strength-brand pairings. Include all three prescription categories even when a branch initially has no reviewed items.
- [ ] For racikan: catalogue offers eligible components; the prescription recipe carries final form (puyer/kapsul/salep), preparation instructions and number of divided units. A compound is not a fabricated KFA branded product.
- [ ] For BMHP: capture product specification and dispensing unit; no mandatory oral route/signa. Display the same four-level interaction with accurate branch labels.
- [ ] Import command supports dry-run and explicit apply, source hash/version, reviewed-row conflict report and no destructive deletion. No import on app startup or migration from raw DOCX.
- [ ] Run `manage.py test klinis.tests.test_medication_catalogue --keepdb --noinput`; review additive migrations and source coverage artifact.

## Task 2: Structured draft prescription and quantity calculation

**Files:** `ResepElektronik`, `ResepDetail`, proposed forms/prescriptions service/tests and migration.
**Produces:** nullable product FK and frozen product/ingredient/formulary/flag snapshot on details; structured `regimen` JSON version 1, Decimal prescribed quantity separate from legacy integer compatibility; proposed `KomponenRacikan` child referencing prescription detail and product/component amount/unit. Keep old `nama_obat`, `dosis`, `aturan_pakai` readable and derive them on new saves.
**Header:** explicit DRAFT default for new composer flow, record version/author/time; do not automatically turn existing DIKIRIM rows into drafts. New prescribing policy/totals reference is explicit; legacy default-zero prices are not reinterpreted as known free medicine.
**Interfaces:** proposed pure `calculate_quantity(regimen, product_units) -> dict` and `save_prescription(visit, workflow, actor, data) -> dict` called as operation `prescription_save` through existing dispatcher. Return prescription ID and canonical rendered lines; no sent pharmacy task or bill.

- [ ] Add new test module with the real fixture idiom and a calculator RED test:

```python
from decimal import Decimal
from django.test import SimpleTestCase

class MedicationQuantityTest(SimpleTestCase):
    def test_half_tablet_fixed_regimen(self):
        from pasien.services.prescriptions import calculate_quantity
        result = calculate_quantity(
            {'schema_version': 1, 'frequency': 'FIXED', 'times_per_day': '2',
             'dose': '0.5', 'dose_unit': 'tablet', 'duration_days': '3'},
            {'dispense_unit': 'tablet', 'dose_unit': 'tablet'},
        )
        self.assertEqual(result['quantity'], Decimal('3'))
        self.assertEqual(result['unit'], 'tablet')
        self.assertFalse(result['requires_manual_quantity'])
```

- [ ] Run `manage.py test pasien.tests_prescription_workflow --keepdb --noinput`; before service creation RED should fail at the proposed import. Add tests with `IgdWorkflowTest` for database operations.
- [ ] GREEN: parse bounded Decimal values; support fixed times/day, every-N-hours and PRN, dose/unit, route, timing, duration and manual quantity+reason. Distinguish concentration dose conversion from pack rounding. Missing conversion returns `quantity=None` and `requires_manual_quantity=True`, not zero or a guessed amount.
- [ ] PRN requires indication, interval/max frequency when clinically configured and explicit maximum/quantity review. Variable/tapering courses and multicomponent compounds require manual verified quantity in this first version; the UI must say why automatic calculation is unavailable.
- [ ] Validate route against product form, quantity >0, supported units, finite values, maximum line count 100, per-note length 2,000 and required compound recipe. Reject negative/NaN/infinity, unsupported schema and extra keys. BMHP does not need drug-only fields.
- [ ] Persist all rows atomically; partial line failure rolls back header/details. Server resolves prices/references; unknown price stays unresolved, while an explicit approved zero price is distinguishable. Never use posted total or float parsing.
- [ ] Implement safe unique numbering using an allocator under lock/DB uniqueness with bounded retry, not `count()+1`. Bind draft save to current workflow/version/replay. Editing a sent prescription uses an explicit revision/cancel/reissue, not silent mutation.
- [ ] Test reload retains compound components, manual quantity reason and canonical signa; old integer `jumlah` consumers must read a deliberate compatibility projection without truncating fractional prescribed quantity. Do not change existing financial quantity meaning accidentally.

## Task 3: Medication risk engine with traceable acknowledgement

**Files:** proposed `medication_safety.py`, safety models/forms, tests and prescription service.
**Produces:** proposed `MedicationSafetyReview` record with prescription/content digest, policy version, risk rule ID, severity, evidence references, evaluated time, reviewer/acknowledgement/reason. Proposed structured `AlergiPasienTerstruktur` is patient-scoped, with substance/ingredient/class mapping, reaction/status and provenance; preserves raw `Pasien.alergi_obat`/visit text unchanged.
**Interface:** proposed `evaluate_prescription(prescription, policy) -> list[dict]`, pure evaluator over loaded data; persisted evaluation is created in the submission transaction.

- [ ] RED: exact ingredient in two brands, overlapping class without identical ingredient, multi-ingredient product allergy, unmapped historical allergy, confirmed none, LASA/High Alert multi flags, stale assessment and waived restriction. No string substring alone establishes a definitive allergy match.
- [ ] GREEN: use structured ingredient/class IDs and reviewed cross-reactivity tables. Mark unstructured history as unresolved review, not no allergy; keep original raw text visible. Explicit recording of no-known-allergy is an attributed clinical action.
- [ ] Separate outcomes: product risk information; duplicate ingredient review; therapeutic-class overlap review; confirmed allergy policy block; unresolved-allergy review; restricted antibiotic PPRA hold. Policies decide which may be overridden and by whom; do not invent a universal blanket ban.
- [ ] Persist acknowledgements with actor/reason and content digest; edit to ingredients/dose/route invalidates old review/approval. Re-evaluate at submit and before dispensing if relevant allergies/policy changed. An old evaluation must not authorize a changed prescription.
- [ ] Clinical alert UI includes text/icon and reviewed Tall Man label, not color alone. Master flag does not automatically mark accreditation EP fulfilled. Resolve EP links only against active framework after clinical review.
- [ ] Run `manage.py test pasien.tests_medication_safety pasien.tests_prescription_workflow --keepdb --noinput`; negative authorization and unresolved-data cases must pass.

## Task 4: Submission, PPRA review and pharmacy-authorized transitions

**Files:** `ppra_review.py`, `prescriptions.py`, proposed `pharmacy_views.py`, URLs, old recipe/status views, review records/forms/tests.
**Produces:** proposed `PpraReviewRequest` with prescription/content hash, explicit policy/source, requested-by/time, culture order/attachment references when applicable, decision PENDING/APPROVED/REJECTED, decision actor/time/reason/expiry. Do not invent antimicrobial line classification from the document's example list.
**Interfaces:** proposed `submit_prescription(visit, workflow, actor, data) -> dict`, `review_ppra(actor, request_id, decision, reason, expected_digest) -> dict`, `transition_prescription(actor, prescription_id, action, expected_version, request_id) -> dict`.

- [ ] RED: non-doctor submit; nurse/admin direct POST; pharmacist without assigned depo; PPRA requester self-approving; culture/result/attachment from another visit; approval for old content; rejected or expired approval; out-of-order pharmacy status; changed payload with reused request ID.
- [ ] GREEN: derive separate predicates for prescribe, review/dispense and PPRA approval. Pharmacy worklist scope is assigned serving depo/service and legitimate hospital-wide oversight grants, not simply “same requesting unit”; also not unrestricted global patient access.
- [ ] Keep header DRAFT while PPRA review is pending; submission response exposes a hold/review request without claiming DIKIRIM. If the approved policy permits culture-only release, verify the linked completed culture and version explicitly; otherwise culture is evidence, not approval.
- [ ] Persist requests and decisions atomically with event/audit; lock in roadmap order. Do not grant reviewer authority merely because a user is ADMIN_RS. Pending/rejected policy failures return actionable UI while retaining draft.
- [ ] After required reviews and valid quantities/indications, explicit submit moves DRAFT→DIKIRIM and starts pharmacy visibility. DIKIRIM→DISPENSING→SELESAI are permitted pharmacy transitions; cancellation before handover requires reason. After handover use retained reversal/return records, not deletion or retroactive BATAL that hides charges.
- [ ] Adapt `views.resep_buat` and `views.resep_update_status` to shared services. Direct routes cannot bypass profession, scope, schema, risk engine, state/version or workflow guards. Protect adopted/final IGD content without breaking legitimate later operational dispensing.
- [ ] Pharmacy transitions use their own durable prescription request ledger/version so authorized pharmacists do not require the doctor/nurse-only IGD dispatcher. Proposed `PrescriptionOperation` stores actor/request UUID/payload digest/result; authorize before replay lookup. Persist it in the same transaction as state/billing.
- [ ] Test non-IGD legacy entry compatibility explicitly; no silent prescription routing change for RAJAL/RANAP. Run new pharmacy authorization/workflow tests plus current route/module tests.

## Task 5: Exactly-once charge ownership and frozen evidence

**Files:** prescription service, detail/billing links and migration, tests, final snapshot/resume/worklist.
**Produces:** nullable unique one-to-one `ResepDetail.billing_item` for new system-owned charges and a frozen submitted prescription snapshot. Include product/signa/quantity/unit/price provenance and review references in new IGD final snapshots.

- [ ] RED: repeated completion with same/different request key, two simultaneous completions, empty prescription, unknown-price line, explicit zero price and same drug in two distinct prescriptions. Completion must charge each billable detail at most once, not deduplicate by drug name across prescriptions.
- [ ] GREEN: lock header/details, verify valid state/review, create/link charges in the same transaction and return existing linked results on replay. Existing unlinked legacy charges are not adopted by guessed name. Flag ambiguous historical billing for reviewed reconciliation without deleting it.
- [ ] Unknown-price lines remain visibly unresolved and cannot be represented as zero-cost successful reconciliation. Whether handover can complete with unresolved billing is an explicit approved financial policy; the default blocks financial-complete status while preserving an attributable clinical handover record.
- [ ] Record before/after quantity/price/override/source and actor/reason. Preserve manual non-pharmacy billing and action billing. No charge at prescription save or send.
- [ ] Snapshot final documentation at signing; later dispensing updates appear in operational view only. An old revision without prescriptions shows absence, not today's live prescription. A new prescription after finalization requires its own authorized episode policy/addendum rather than modifying the original signed plan.
- [ ] PostgreSQL two-connection completion test must prove one charge per detail and no deadlocks. Keep this separate from SQLite test proof.

## Task 6: Four-level composer, review surfaces and gate

**Files:** medication partial/JS, catalogue view in proposed pharmacy views, step-8 integration, pharmacy worklist, old detail entry and UI tests.
**Produces:** proposed visit-scoped medication catalogue GET `igd_medication_catalogue`; render composer inside Tindakan/Obat panel after nursing planning. Lookup route uses visit authorization without bypassing pharmacy action predicates.

- [ ] RED: unauthorized lookup/mutation, broken parent path, expired formularium, stale async response, mode switch clearing unsaved recipe and duplicate named fields.
- [ ] GREEN: implement type→group→generic-strength→product with all three branches, clear only descendants on parent change, reject stale fetches and retain added prescription rows. Show unavailable/unreviewed catalogue states rather than fabricated stock.
- [ ] Form captures structured signa/frequency/dose-unit/route/timing/duration, quantity suggestion and editable reasoned override; product/formulary/risks and unresolved-price state remain visible per row.
- [ ] Racikan supports multiple ingredient rows and final preparation details; BMHP hides drug-only requirements. Avoid sending repeated controls through the existing scalar-only FormData collector: build a typed JSON lines/components array.
- [ ] Add risk acknowledgements, pending PPRA/decision evidence, pharmacist review/dispense/cancel reason and retry feedback. Direct buttons cannot imply a blocked prescription was sent. DOM updates use textContent/escaped templates.
- [ ] Browser synthetic journeys at 375/768/1366 include non-racikan, racikan, BMHP, duplicate ingredient, unresolved allergy, PPRA pending/approved, draft reload, send retry and finish retry; verify persisted values/charges and printed frozen evidence.
- [ ] Run focused command below; full regression, PostgreSQL, catalogue approval, migration and release gates remain in roadmap.

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test klinis.tests.test_medication_catalogue pasien.tests_medication_catalogue_ui pasien.tests_prescription_workflow pasien.tests_medication_safety pasien.tests_pharmacy_authorization pasien.tests_route_rbac pasien.tests_object_authz pasien.tests_igd_workflow_finalization --keepdb --noinput
node --check static/js/igd-medications.js
git diff --check
```

Expected: runner `OK`, zero failures, exit 0; record actual count. Do not claim national catalogue completeness, current Fornas correctness, stock availability, full drug-drug interaction checking or SATUSEHAT MedicationRequest integration from these tests. Those are separate data/integration capabilities, not hidden substitutes for the required local functionality.
