# IGD Diagnosis, Actions and 3S Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task. Use checkboxes and RED → GREEN → REFACTOR. This is a proposed plan, not execution/release authorization.

**Status:** CORE LOCAL IMPLEMENTATION VERIFIED. See `../specs/2026-11-13-igd-clinical-expansion-delivery.md` for implemented scope, proof and live-only boundaries; historical authoring checkboxes are not bulk-ticked.
**Goal:** Support primary/secondary medical diagnoses, independent Manual/Master/AI medical/nursing components, and attributable medical procedures in existing IGD steps 8–9.
**Architecture:** Add relational diagnosis lines while retaining server-owned legacy projections. Extend existing planning validation, action dispatcher, AI ticket protocol and immutable snapshots; do not create another assessment or billing ledger.
**Tech Stack:** Existing Django, Bootstrap, vanilla JavaScript, Decimal and backend AI transport.
**Spec:** `../specs/2026-11-13-igd-diagnosis-pharmacy-ancillary-analysis.md`, DG01–DG02, AC01, NS01.
**Orchestration:** `2026-11-13-igd-clinical-expansion-roadmap.md` owns shared-file sequencing and release.

## Global Constraints

- All roadmap constraints apply. Keep the separate step-6 plan untouched.
- Existing `diagnosa_masuk`, nursing strings, `diagnosis_mode` and `diagnosis_provenance` are legacy contracts, not new sources to parse into invented clinical records.
- At most one active primary diagnosis per visit. Empty/partial draft may have none; completing medical diagnosis requires a primary or an explicit existing exemption.
- Manual mode preserves free text; master/AI codes must resolve locally. Do not rename master `I.01011` to the source document's mismatched label.
- Diagnosis and medical procedure planning require doctor profession; nursing component writes require PERAWAT/BIDAN according to current clinical policy. Admin/assessor roles do not confer a profession. Preserve unrelated values when submitting one's own section.
- AI proposals do not send orders, mark actions performed, assign tariffs or sign records. Accepting a proposal is an ordinary validated write.
- Plan save never bills; actual execution reuses the existing idempotent execution/CPPT/billing path.

## Review Focus

1. Two tabs assign different primary diagnoses — Task 1 pins conflict/unique handling and no partial projections.
2. Nurse changes one 3S component while medical data has a legacy manual diagnosis — Task 2 pins independent validation and unchanged medical fields.
3. AI ticket accepted for another target, actor, version or code — Task 3 pins signed target/candidate binding.
4. Clinician records earlier actual care after the fact — Task 4 pins occurred-at versus recorded-at and authenticated attribution without backdating audit.
5. Old final snapshot missing new data — Task 5 pins absence rather than live fallback.

## File inventory

**Create:** `pasien/services/igd_diagnoses.py`, `pasien/tests_igd_diagnosis_lines.py`, `pasien/tests_igd_planning_components.py`, `pasien/tests_igd_procedure_assistance.py`, `templates/pasien/_igd_diagnosis_plan.html`, `static/js/igd-diagnosis-plan.js`.
**Modify:** `pasien/models.py`, `pasien/forms_igd_workflow.py`, `pasien/forms_igd_operations.py`, `pasien/services/igd_planning.py`, `pasien/services/igd_assessment_workflow.py`, `pasien/services/igd_actions.py`, `pasien/services/igd_finalization.py`, `pasien/igd_workflow_views.py`, `klinis/services/ai_igd.py`, `templates/pasien/igd_workflow.html`, `templates/pasien/_igd_workflow_operations.html`, `templates/pasien/igd_workflow_resume.html`, `static/js/igd-clinical-controls.js`, `pasien/urls.py` only if a view contract needs a new route, generated additive `pasien/migrations/`.
**Regression references:** `pasien/tests_igd_workflow_ai.py`, `pasien/tests_igd_workflow_integration.py`, `pasien/tests_3s_cascade.py`, `pasien/tests_revisi_diagnosa_picker.py`, `klinis/tests/test_tarif_service.py`.

All new symbols below are **proposed**, not claims about existing APIs.

## Task 1: Structured diagnosis persistence and compatible projection

**Files:** models, proposed `igd_diagnoses.py`/`tests_igd_diagnosis_lines.py`, operations form, action dispatcher, generated migration.
**Consumes:** existing `perform_action(pk, user, operation, payload, version, request_id)` and visit/workflow locks.
**Produces:** proposed `DiagnosisKunjungan` and `diagnosis_set` action; `set_diagnoses(visit, workflow, user, data) -> dict`, called only inside `perform_action`.

### Data/operation contract

`DiagnosisKunjungan`: visit FK; nullable protected `MasterIcd10` FK; text/name/code snapshots; `is_primary`; active/cancelled state; Manual/Master/AI source; provenance JSON; actor/time; stable row ID. Add conditional unique active-primary constraint. Use plain text max 2,000 characters and at most 30 active rows per submitted visit.

`diagnosis_set` fields: `changes` list of explicit upserts/cancellations with row IDs (or unique temporary IDs for new rows) and an explicit `is_primary` boolean on each upsert; no implicit deletion for omitted rows. Validate ownership and final state before mutations. Build the resulting active set in memory, reject duplicate/unknown IDs or more than one primary, persist under lock, then project primary label to `diagnosa_masuk`. Do not concatenate secondary diagnoses into that primary field. An explicit primary cancellation must also choose a replacement or leave an incomplete draft. Unknown code never creates a master.

- [ ] RED: add tests using `IgdWorkflowTest` from `pasien.tests_igd_workflow`; use actual `UserProfile` professions and force-login conventions. Include a concrete action test:

```python
from uuid import uuid4
from pasien.tests_igd_workflow import IgdWorkflowTest

class DiagnosisLinesTest(IgdWorkflowTest):
    def test_two_primary_rows_roll_back(self):
        from pasien.services.igd_actions import perform_action
        from pasien.models import DiagnosisKunjungan
        payload = {'changes': [
            {'op': 'upsert', 'temp_id': 'a', 'mode': 'MANUAL', 'text': 'Diagnosis kerja A', 'is_primary': True},
            {'op': 'upsert', 'temp_id': 'b', 'mode': 'MANUAL', 'text': 'Diagnosis kerja B', 'is_primary': True},
        ]}
        with self.assertRaises(ValueError):
            perform_action(self.visit.pk, self.user, 'diagnosis_set', payload, 0, str(uuid4()))
        self.assertFalse(DiagnosisKunjungan.objects.filter(kunjungan=self.visit).exists())
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk, '')
```

- [ ] Run `manage.py test pasien.tests_igd_diagnosis_lines --keepdb --noinput` with the roadmap's SQLite environment. RED must fail on proposed model/operation, not fixture import.
- [ ] GREEN: implement the model, form and service with explicit change validation, actor authorization, same transaction/version and primary projection. Store replay results with resulting stable row IDs.
- [ ] Add tests: primary+secondary round trip; primary switch; omission preservation; inactive master; forged row from another visit; wrong profession/unit; stale version; same-key replay and altered-key payload rejection; final episode rejection; primary cancellation semantics.
- [ ] Handle legacy-only diagnosis as a labelled read-only legacy projection until explicit adoption; never auto-classify old prose. Legacy diagnosis writers cannot overwrite structured managed diagnoses.
- [ ] Generate/read additive migration; run focused tests and migration checks. Read the next migration number rather than assigning one in advance.

## Task 2: Independent component modes and profession-owned validation

**Files:** `igd_planning.py`, `igd_assessment_workflow.py`, `forms_igd_workflow.py`, proposed tests/UI partial.
**Consumes:** existing step-8 `save_step` and master mapping.
**Produces:** proposed step-8 special payload `component_modes`, accepted only for `medical`, `sdki`, `slki`, `siki`; server-owned provenance version 2 under existing `diagnosis_provenance['components']`. Each entry includes mode, authenticated accepted-by/time and optional verified suggestion identity. `diagnosis_mode` remains a legacy adapter; do not add two contradictory mode authorities.

- [ ] RED: parameterized component tests prove `sdki=MASTER`, `slki=MANUAL`, `siki=MASTER` can coexist; an unchanged legacy medical string is not revalidated as ICD10. A nurse cannot update medical fields and a doctor cannot silently rewrite nursing planning.
- [ ] RED: fake SDKI/SLKI/SIKI code, mismatched mapping, changed SDKI with stale descendants, manual target without text, provenance forged in payload, and unchanged master field all have explicit outcomes. Mapping suggestions must not erase edited manual text.
- [ ] GREEN: extract per-component validators. Always canonicalize real master labels. An out-of-map master choice needs a separate deliberate Manual conversion with a reason, not a forged mapped relationship. Omitted values remain unchanged.
- [ ] Extend `save_step`'s strict special-key allowlist and form adapter without passing nonmodel keys into ModelForm/update_fields. Persist server-derived provenance/projections in the actual transaction and invalidate signatures on accepted changes.
- [ ] Preserve existing v1 AI/global-mode tickets through an explicit compatibility reader; new independent-mode writes produce v2 metadata. No GET adoption/write.
- [ ] Run `manage.py test pasien.tests_igd_planning_components pasien.tests_igd_workflow_ai pasien.tests_3s_cascade --keepdb --noinput`.

**Acceptance:** mode selection is independent at persistence and UI layers, not just separate tabs over the same global field.

## Task 3: Target-specific AI assistance and validated acceptance

**Files:** `klinis/services/ai_igd.py`, `pasien/igd_workflow_views.py`, `igd_planning.py`, `igd_actions.py`, proposed procedure-assistance tests.
**Consumes:** current backend `_call_deepseek`, SystemConfig gates, catalogue models and workflow version.
**Produces:** proposed optional AI request `target` enum `medical|sdki|slki|siki|procedure`; default legacy target retains current response compatibility. New tickets contain target, actor, visit, expected version, candidate codes and expiry. Add optional `mode` and `ai_ticket` to action-plan input for procedure acceptance.

- [ ] RED: mocked provider returns a fabricated code, a valid code for the wrong target, an expired ticket, a ticket issued to another actor/visit/version, or a class-compatible but unmapped nursing item; all rejected without clinical mutation.
- [ ] RED: disabled module, timeout, malformed response and empty candidates leave Manual/Master usable; no request on page load, master search or draft save. Verify no identity, MRN/NIK, full dates, provider keys or unrestricted free text in transport/log payloads.
- [ ] GREEN: build a bounded context adapter from complaint/history terminology, triage/vitals, reviewed physical findings and known investigation summaries. Label source and missingness. Read both current physical-exam storage shapes through verified adapters; do not implement the separate step-6 feature here. Do not treat missing finding/result as normal.
- [ ] Candidate retrieval must be target-specific and not silently truncate unsearched catalogues to an alphabetical first-N set. Query by reviewed clinical terms and paginate/retrieve a bounded relevant candidate set. Validate every response against that exact set.
- [ ] Extend prompt/schema for procedure candidates; existing prompt explicitly says no therapy, so do not pretend current medical suggestions cover procedures. Return no drug dosages or autonomous prescriptions in this workstream.
- [ ] Validate SLKI against selected SDKI and SIKI against selected SDKI/SLKI relation. Tie target/context to current server version; an AI response fetched before a draft change must be re-requested.
- [ ] Run new tests plus `pasien.tests_igd_workflow_ai`; mock network only. Record live activation as excluded, not passed.

## Task 4: Action metadata and usable step-8 interface

**Files:** operations form, `TindakanAsesmen`, action services, proposed partial/JS, workflow page, existing controls and operation partial.
**Consumes:** existing plan/execute, Decimal tariffs, authenticated user and UUID replay.
**Produces:** proposed `lokasi_anatomis`, `catatan_klinis` action fields; execution input `occurred_at` plus reason for retrospective entry. Existing `performed_by` remains authenticated performer; separate recorded-at/recorded-by preserves audit. Do not accept an arbitrary posted user ID as proof of performance.

- [ ] RED: earlier allowed occurred-at persists distinctly from recorded-at; future/invalid datetime and unsupported actor ID reject atomically. Scope any clinician selector to verified eligible staff and require an explicit delegated-recording policy before enabling it.
- [ ] GREEN: extend action plan/execute forms with field-level validation: location max 200, clinical note max 2,000, positive Decimal quantity, time in declared timezone. Retain reason-required tariff override and unknown-price semantics.
- [ ] Build separate medical and nursing cards, each component's segmented Manual/Master/AI controls, diagnosis row list with primary control, and a Tindakan/Obat selector. The pharmacy phase supplies the medication partial; until then show an explicit unavailable state rather than a working-looking empty form.
- [ ] Exclude only replaced step-8 fields from the generic form loop; render each named input once. Remove/disable only superseded diagnosis/AI bindings in `igd-clinical-controls.js`; retain marker, questionnaires, upload, execution and version handling.
- [ ] Show individual medical/nursing subtotals, unknown tariff counts and unified recap. Switching tabs does not submit a hidden form or erase edits. Role-readonly controls mirror server permissions.
- [ ] Add HTTP render/persist tests and browser cases: independent modes, primary+secondary, mapping with manual notes, AI accept, procedure plan then execute, retry and quantity. Verify version updates across operation and main draft form.
- [ ] Run `node --check static/js/igd-diagnosis-plan.js` and existing controls syntax check; targeted diagnosis/action tests must pass.

## Task 5: Snapshot/readers and integration gate

**Files:** `igd_finalization.py`, workflow context/resume, legacy read adapters, proposed tests and relevant existing finalization tests.
**Consumes:** structured diagnoses/components/action metadata from Tasks 1–4.
**Produces:** bumped snapshot schema carrying diagnosis lines, per-component provenance and action clinical metadata with frozen labels and actor/time.

- [ ] RED: sign/finalize a synthetic visit; mutate catalogue name and live diagnosis/action metadata through an allowed later path; original revision digest and printed original remain identical. Old snapshot with no new keys displays unavailable historical detail, never current live rows.
- [ ] GREEN: snapshot complete data on signing/finalization and use the exact snapshot for final print; current operational views remain labelled separately. Update completeness to primary diagnosis or a documented exemption.
- [ ] Trace legacy medical print, detail/rekap, copy-previous and editable diagnosis routes. Add field-aware guards/adapters; keep RAJAL/RANAP behavior unchanged outside adopted IGD records.
- [ ] Run targeted command below, full roadmap regression later, plus `makemigrations --check --dry-run` and `git diff --check`.

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien.tests_igd_diagnosis_lines pasien.tests_igd_planning_components pasien.tests_igd_procedure_assistance pasien.tests_igd_workflow_ai pasien.tests_igd_workflow_integration pasien.tests_igd_workflow_finalization pasien.tests_3s_cascade klinis --keepdb --noinput
```

Expected: runner `OK`, zero failures, exit 0; record measured count. Browser and PostgreSQL race gates remain separate in the roadmap. Handoff to ancillary/pharmacy with diagnosis stable row IDs and unchanged primary projection contract; no commit/deploy without authorization.
