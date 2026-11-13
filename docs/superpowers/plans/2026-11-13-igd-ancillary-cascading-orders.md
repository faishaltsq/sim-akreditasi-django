# IGD Ancillary Cascading Orders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task. Steps use checkboxes and RED → GREEN → REFACTOR. No implementation/release is authorized by this document.

**Status:** CORE LOCAL IMPLEMENTATION VERIFIED. See `../specs/2026-11-13-igd-clinical-expansion-delivery.md` for implemented scope, proof and live-only boundaries; historical authoring checkboxes are not bulk-ticked.
**Goal:** Deliver four-level ancillary selection with a retained multi-item basket, clinical indication/preparation and replay-safe actual orders/results in IGD step 7.
**Architecture:** Add a reviewed catalogue in `klinis` and extend existing `OrderPenunjang`, not a new order/result subsystem. Use one order row per selected catalogue item, group submissions by batch UUID, retain legacy rows and route all result writers through shared validation.
**Tech Stack:** Existing Django, Bootstrap, vanilla JavaScript and PostgreSQL concurrency gates.
**Spec:** `../specs/2026-11-13-igd-diagnosis-pharmacy-ancillary-analysis.md`, PX01–PX02; full second source DOCX.
**Dependency:** Diagnosis stable-row/reference contract from `2026-11-13-igd-diagnosis-actions-3s.md`; the roadmap owns sequencing and release.

## Global Constraints

- All roadmap constraints apply; do not rebuild existing order, upload, worklist, critical-result or revision mechanisms.
- Four levels are catalogue taxonomy, not authorization. Clinical service availability and order destination permissions are independent checks.
- Root categories are Laboratorium and Penunjang Diagnostik. Preserve existing operational `jenis` values LAB/RADIOLOGI/EKG/LAINNYA; do not conflate root labels with worklist routing.
- Selecting or saving a basket is not an order; explicit Kirim creates orders. No automatic charge from catalogue selection.
- Indication text is mandatory on send; an accepted master diagnosis resolves to a visit-owned diagnosis/code, while a temporary manual indication supports urgent work without requiring completed step 8.
- Source headings/panels/variants are not certified item totals, procedure codes or tariffs. Do not invent LOINC/ICD9 codes.
- All new context copied into an order is frozen at send; later catalogue edits do not rewrite sent orders or final snapshots.
- Authorized historical/result access after transfer must remain scoped to the responsible performing service and episode origin; no broad all-patient bypass.

## Review Focus

1. Root/subcategory changes after asynchronous search — Task 2 pins stale-response rejection and server ancestry validation.
2. Basket includes a valid and an unavailable/invalid item — Task 3 pins all-or-nothing send, no partial worklist.
3. CBC panel plus its component selected independently — Task 1 pins explicit panel/component definitions; Task 3 requires deliberate duplicate confirmation, not automatic extra charges.
4. Lab/farmasi/IGD team has different legitimate cross-unit access — Task 4 pins service-assigned result permissions separately from requesting-clinician permissions.
5. Late results arrive after finalization — Task 5 pins operational append versus unchanged signed snapshot.

## File inventory

**Create:** `klinis/data/penunjang_catalogue.json`, `klinis/management/commands/import_penunjang_catalogue.py`, `klinis/services/penunjang_catalogue.py`, `klinis/tests/test_penunjang_catalogue.py`, `pasien/services/penunjang_orders.py`, `pasien/tests_penunjang_cascade.py`, `templates/pasien/_igd_ancillary_order.html`, `static/js/igd-ancillary-orders.js`.
**Modify:** `klinis/models.py`, `klinis/admin.py`, generated `klinis/migrations/`; `pasien/models.py`, generated `pasien/migrations/`; `pasien/forms_igd_operations.py`, `pasien/services/igd_actions.py`, `pasien/igd_workflow_views.py`, `pasien/services/igd_finalization.py`, `pasien/urls.py`, `pasien/views.py`, `templates/pasien/_igd_workflow_operations.html`, `templates/pasien/igd_workflow.html`, `templates/pasien/igd_workflow_resume.html`, `templates/pasien/laboratorium_dashboard.html`, `templates/pasien/cetak_permintaan_lab.html`, `static/js/igd-clinical-controls.js` only where shared repeated-field serialization must change.
**Existing tests:** `pasien/tests_laboratorium.py`, `pasien/tests_revisi_asesmen_medis_igd.py`, `pasien/tests_igd_workflow_integration.py`, `pasien/tests_object_authz.py`, `pasien/tests_igd_workflow_finalization.py`.

All new symbols/endpoints below are proposed.

## Task 1: Reviewable hierarchy and item identity

**Files:** catalogue model/data/importer/service/admin/tests, generated migrations.
**Produces:** proposed `KategoriPenunjang` node (`level` 1–3, parent FK, immutable code, label, order, active state), `ItemPenunjang` leaf (group FK, immutable code, label, `jenis_order`, destination service, panel/variant metadata, preparation schema, review/source version and active state).
**Interfaces:** `list_choices(user, *, parent_id=None, query='', page=1) -> dict` returns `results`, `page`, `has_more`; `resolve_items(user, item_ids) -> list[ItemPenunjang]` validates leaf activity, complete ancestry and available destination.

- [ ] RED: test root→installation→group→item shape, wrong-level parent, cycle attempt, duplicate codes, inactive ancestor, unavailable destination and panel/variant identity. Importing twice must not duplicate rows or overwrite a reviewed local customization silently.
- [ ] GREEN: model constraints and service validation require root level 1, installation level 2, group level 3; no child under an item. Authorize catalogue administration separately from clinical lookup. Bind every leaf to one explicit operational type and service.
- [ ] Extract all source branches into the data artifact with source heading/path and reviewed classification. Enumerate coverage: clinical lab's nine groups; PA histopathology/cytopathology/IHC; BDRS compatibility and component requests; external referral and configurable others; imaging X-ray/USG/CT/MRI/special imaging; electrophysiology cardiology/neurology/pulmonology-THT; endoscopy GI/airway-THT/urinary-gynecology; nuclear organ scans/PET.
- [ ] Normalize Bank Darah as an installation; retain a source-note for its inconsistent placement in Word. External referrals require destination notes and must not masquerade as a local available machine/service.
- [ ] Split variants only where clinically reviewed; keep panel definitions explicit. CBC is one orderable panel; components are results, not automatically new orders. Store regional/laterality/contrast choices as validated variant definitions, not arbitrary suffixes.
- [ ] Implement importer dry-run, source hash/version, explicit apply and deactivate-only-when-requested behavior; default new examples to inactive/unreviewed. Unknown national codes stay blank, not fabricated.
- [ ] Run `manage.py test klinis.tests.test_penunjang_catalogue --keepdb --noinput`; review generated migrations.

## Task 2: Scoped lookup and four-level basket interface

**Files:** workflow views/URLs, proposed partial/JS, operation partial/page and cascade tests.
**Produces:** proposed visit-scoped GET `/pasien/kunjungan/<pk>/asesmen-igd/katalog-penunjang/`, route `igd_penunjang_catalogue`, backed by existing `get_visit`. No clinical writes on GET.

- [ ] RED: anonymous, unauthorized module/unit, malformed parent/query/page, inactive parent and forged hierarchy fail; permitted clinician can browse paginated relevant leaves. Enforce max query length 200, page size 50, parent integers and explicit result metadata.
- [ ] GREEN: build server lookup using Task 1; never trust client `jenis` or destination. No all-patient data in catalogue response.
- [ ] Implement four labelled selects and item search/checklist. On parent change clear only uncommitted descendant choices, abort old fetches and check response generation before rendering. Keep already-added basket entries with full breadcrumb visible; require explicit removal.
- [ ] Basket row carries stable item/variant ID, indication diagnosis or manual text, priority and preparation. Use JSON item arrays, not generic FormData last-value wins: the current operation adapter assigns `fields[name] = value` and would otherwise drop multiselect entries.
- [ ] Show loading/empty/error/retry and unavailable-service states, keyboard accessible selection, a clear Review/Kirim boundary and no persistent browser storage of clinical data. Do not auto-check the first returned item.
- [ ] Render tests confirm selectors/names occur once and readonly final view has no send controls. Browser tests cover rapid parent switching, stale response, multi-group basket, error retention and reload after successful send.

## Task 3: Atomic batch send, indication and preparations

**Files:** `OrderPenunjang`, proposed `penunjang_orders.py`, operation form/dispatcher, migration and cascade tests.
**Produces:** proposed fields `catalogue_item` nullable protected FK, `catalogue_snapshot` JSON, `batch_id` UUID, diagnosis reference/code snapshot, `preparation` schema JSON and authenticated `ordered_by`. Preserve `nama_pemeriksaan`, `catatan_klinis`, priority, parameter_list and old operational choices.
**Interface:** proposed `order_batch(visit, workflow, user, data) -> {'order_ids': list[int], 'batch_id': str}` under existing `perform_action`, operation `order_batch`.

- [ ] Add executable failing test to `pasien/tests_penunjang_cascade.py` using the real fixture base:

```python
from uuid import uuid4
from pasien.tests_igd_workflow import IgdWorkflowTest
from pasien.models import OrderPenunjang

class AncillaryBatchTest(IgdWorkflowTest):
    def test_invalid_batch_never_creates_partial_orders(self):
        from pasien.services.igd_actions import perform_action, HANDLERS
        self.assertIn('order_batch', HANDLERS)
        payload = {'items': [
            {'item_id': 99999999, 'prioritas': 'CITO', 'indication': 'Indikasi uji', 'preparation': {}},
        ]}
        with self.assertRaises(ValueError):
            perform_action(self.visit.pk, self.user, 'order_batch', payload, 0, str(uuid4()))
        self.assertFalse(OrderPenunjang.objects.filter(kunjungan=self.visit).exists())
```

- [ ] Run `manage.py test pasien.tests_penunjang_cascade --keepdb --noinput`; before the operation exists, RED must expose the missing contract rather than an unrelated fixture error. Then add valid synthetic catalogue fixtures to the same class for success/replay tests.
- [ ] GREEN: validate 1–50 basket entries; reject duplicate exact item/variant within one batch unless distinct specimen/site and explicit reviewed repeat semantics. Resolve every item, diagnosis ownership, indication, destination and preparation before creating any row. One invalid row rolls back all.
- [ ] Preparation captures independent enums/nullable states: fasting YES/NO/UNKNOWN/NA; pregnancy YES/NO/UNKNOWN/NA where relevant; contrast allergy YES/NO/UNKNOWN/NA; specimen type/site; region/side/contrast variants. Required metadata follows item schema; unknown is never silently NO.
- [ ] A clinical order may be entered before complete assessment; do not require filled step 8. Diagnosis references from another visit are rejected; manual indication remains supported. Doctor sends by default; delegate ordering only through an approved predicate, never by posted profession.
- [ ] Create rows atomically, return stable IDs through dispatcher replay, invalidate signatures and update version once per batch. A timeout retry with the same key returns the same IDs; a different payload with reused key fails.
- [ ] Legacy free-text order routes for adopted IGD visits use an explicitly labelled manual item path through the same indication/preparation validation; keep historical orders readable without automatic mapping by name.
- [ ] Add tests for mixed valid-invalid batch, per-row priority, two legitimate repeat samples, unknown fields, payload bounds, cross-visit diagnosis, final-state denial and unchanged billing count.

## Task 4: Worklists and result-entry authorization

**Files:** shared order service, existing workflow result handler, legacy views, lab dashboard/print, cascade and existing lab/auth tests.
**Consumes:** sent order identity, destination and current operational state.
**Produces:** proposed `record_result(order, actor, values, expected_state)` service called by both workflow and legacy result writers; no second result field store.

- [ ] RED: result from an unrelated performing service, forged order ID, invalid status, completion without result, critical flag without note and out-of-order transition all fail. Requesting clinician and responsible performing-service permissions are tested separately.
- [ ] GREEN: preserve ORDERED→PROSES→SELESAI. Corrections to already completed results retain before/after actor/time/reason; do not silently overwrite signed result evidence. Use existing workflow version where the action changes its signed content.
- [ ] Reuse current `result_recorded_by/at`, critical flag/note and protected attachments; preserve unknown legacy author/time. Lab worklist displays LAB only, imaging/ECG/other route to assigned service views without forcing them into LAB.
- [ ] Keep pagination instead of a first-100-only operational view with inaccessible remaining work. Scope counts to the same query/permissions as displayed rows. This is limited to the touched order worklist, not all dashboards.
- [ ] Update request print with frozen selected item path, indication, priority, preparations and ordering actor. Verify every printed datum comes from this order/visit, not a similarly named latest order.
- [ ] Run existing lab/integration/authorization tests plus cascade tests. Demonstrate a performing-service user can legitimately see its assigned cross-requesting-unit orders without global patient access.

## Task 5: Frozen records and acceptance

**Files:** finalization snapshot, workflow resume/context, tests and conditional static artifacts via roadmap.

- [ ] RED/GREEN: extend snapshot order entries to include catalogue code/path, item label/variant, indication/diagnosis, preparations and order actor/time. Preserve original revision after late results; live list labels current operational results separately.
- [ ] Old snapshots and free-text orders still render their stored names/results; absence of new keys is historical unknown, not live master lookup.
- [ ] Browser journey at 375/768/1366: select Lab→Klinik→Hematologi→CBC and diagnostic→Imaging→CT→reviewed variant, submit basket once, check exact worklist rows, record result, print request and signed resume. No charge appears merely for sending; prevent duplicate EKG billing ownership across future integrations.
- [ ] Run focused gate below, schema drift and JS syntax checks. Record actual counts and screenshots/DOM assertions without patient data.

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test klinis.tests.test_penunjang_catalogue pasien.tests_penunjang_cascade pasien.tests_laboratorium pasien.tests_revisi_asesmen_medis_igd pasien.tests_igd_workflow_integration pasien.tests_igd_workflow_finalization --keepdb --noinput
node --check static/js/igd-ancillary-orders.js
git diff --check
```

Expected: `OK`, zero failures and exit 0. Roadmap separately requires PostgreSQL same-key batch concurrency, full regression and approved migration/release readback. No live LIS/PACS integration or new automatic ancillary charging is included.
