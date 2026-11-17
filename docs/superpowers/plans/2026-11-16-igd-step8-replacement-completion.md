# IGD Step 8 Replacement and Recommendation Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** APPROVED FOR SUBAGENT EXECUTION — implementation in progress; no commit, push or release authorized.
**Goal:** Replace the obsolete Step 8 input surface with diagnosis → medical action/medication planning → nursing planning, and connect existing catalogues to assessment-based recommendations.
**Architecture:** Extend the existing eleven-step Django workflow, relational diagnosis rows and versioned action dispatcher. Retain historical fields and frozen revisions; reuse the existing ICD-10 → case → ICD-9 relationship instead of adding a second mapping table. Recommendations are candidates requiring explicit acceptance, never automatic clinical actions.
**Tech Stack:** Existing Django/Python, Bootstrap, vanilla JavaScript, existing AI transport and catalogue models.
**Spec:** `../specs/2026-11-16-igd-document-revision-gap-analysis.md`.
**Orchestration:** `2026-11-16-igd-document-revision-roadmap.md` owns baseline, shared-file sequencing and release gates.

## Global Constraints

- The revised source says “sebagai pengganti yang sudah ada. Gunakan yang ini saja”, “Hilangkan; resusitasi/stabilisasi dan terapi farmakologi IGD”, and places the treatment selector **after Diagnosis ICD10**. Replace those editable controls; do not append another parallel screen.
- Keep the `KunjunganPasien.tatalaksana_resusitasi` and `tatalaksana_terapi` database columns and existing values. No RemoveField, bulk clearing, historical recoding or rewriting signed revisions.
- Source operations already exist: `diagnosis_set`, `plan_action`, `prescription_save`, `prescription_submit`, independent `component_modes`, and target-specific AI. Do not recreate them.
- Keep `pasien:igd_workflow`, `igd_workflow_draft`, `igd_workflow_action`, `igd_workflow_ai` and `igd_workflow_catalogue` URLs and `pk`/`step` arguments stable.
- A plan is not performed care. Step 9 remains the owner of actual performer/time, CPPT, privileges and financial posting. With `IGD_PROFESSIONAL_CARE_ENABLED=True`, use professional operations, not the blocked legacy `execute`/`cppt` actions.
- AI remains controlled by `SystemConfig.ai_enabled` and `ai_enable_igd`; Manual/Master must work without a provider.
- ICD-10 diagnoses, ICD-9-CM procedures and KFA products are distinct code systems. No national-service activation is included.
- Proposed new symbols/files below are explicitly marked **proposed**. Existing symbols are cited at their inspected locations.

## Review Focus

1. Removing fields from `STEPS` also removes them from snapshots and generic resume sections: preserve historical rendering and signature inputs explicitly in Task 1.
2. Moving independent forms into a common visual section can create nested forms or lose nursing saves: Task 1 exercises the actual POST and reload boundaries.
3. A manual diagnosis or an ICD-10 without a local case mapping must not prevent catalogue search or urgent planning: Task 2 tests the empty mapping state.
4. Keyword intersections discard negative findings and numeric results; an order without a result is not diagnostic evidence: Task 3 pins source/status/absence semantics.
5. Nursing target switches and delayed AI responses must not overwrite another component or profession: Task 4 exercises independent modes and invalidated requests.

## File Ownership

**Modify:** `pasien/forms_igd_workflow.py`, `pasien/igd_workflow_views.py`, `pasien/services/igd_finalization.py`, `templates/pasien/igd_workflow.html`, `templates/pasien/_igd_step8_fields.html`, `templates/pasien/_igd_diagnosis_plan.html`, `templates/pasien/_igd_planning_components.html`, `templates/pasien/_igd_workflow_operations.html`, `templates/pasien/igd_workflow_resume.html`, `static/js/igd-assessment-workflow.js`, `static/js/igd-clinical-controls.js`, `static/js/igd-clinical-expansion.js`, `static/js/igd-diagnosis-plan.js`, `klinis/services/saran.py`, `klinis/services/ai_igd_targets.py`.
**Create:** `pasien/tests_igd_step8_replacement.py`, `klinis/services/igd_recommendation_context.py` (both proposed).
**Extend tests:** `pasien/tests_igd_target_ai.py`, `pasien/tests_igd_workflow_finalization.py`, `pasien/tests_clinical_expansion.py`, `klinis/tests/test_saran.py`, `qa/clinical_expansion_browser.py`.
No new model or migration is expected. Re-read the listed files at execution time; this inventory is a delta, not permission for broad rewrites.

## Task 1: Replace the active Step 8 surface without losing history

**Files:** The Step 8 forms/views/templates/controllers above; `pasien/services/igd_finalization.py`; `templates/pasien/igd_workflow_resume.html`; proposed `pasien/tests_igd_step8_replacement.py`; existing finalization tests.
**Consumes:** `STEPS` (`forms_igd_workflow.py:23–25`), `save_step()` (`igd_assessment_workflow.py:61–159`), `clinical_snapshot()` (`igd_finalization.py:19–38`), current include order (`igd_workflow.html:41–65`).
**Produces:** One ordered Step 8 presentation; historical-field preservation independent of editable fields; unchanged action and nursing persistence contracts.

- [ ] **RED:** Create the proposed test module using the real `IgdWorkflowTest` fixture. Include this complete characterization test; it should fail on the current editable fields:

```python
from django.test import override_settings
from django.urls import reverse
from pasien.tests_igd_workflow import IgdWorkflowTest


@override_settings(IGD_WORKFLOW_ENABLED=True)
class Step8ReplacementTest(IgdWorkflowTest):
    def test_replacement_has_no_obsolete_editors(self):
        self.visit.tatalaksana_resusitasi = 'Historical stabilization note'
        self.visit.tatalaksana_terapi = 'Historical medication note'
        self.visit.save(update_fields=['tatalaksana_resusitasi', 'tatalaksana_terapi'])
        response = self.client.get(
            reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=8'
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="tatalaksana_resusitasi"')
        self.assertNotContains(response, 'name="tatalaksana_terapi"')
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.tatalaksana_resusitasi, 'Historical stabilization note')
        self.assertEqual(self.visit.tatalaksana_terapi, 'Historical medication note')
```

- [ ] Run `DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien.tests_igd_step8_replacement --keepdb --noinput`; confirm the failure is the obsolete editor, not fixture authorization/import failure.
- [ ] Remove the two obsolete fields from **new workflow editable ownership**, not the model. Update `igd_workflow_views.py:65–67` so it no longer indexes absent form fields. Reject attempts to mutate retired fields through the new Step 8 draft endpoint; leave the separately guarded legacy non-workflow form contract intact.
- [ ] Decouple historical snapshot/print fields from editable ownership. A focused implementation pattern, to be introduced once and reused by snapshot/resume builders, is:

```python
LEGACY_STEP8_FIELDS = ('tatalaksana_resusitasi', 'tatalaksana_terapi')


def snapshot_visit_fields():
    return sorted({name for _, names in STEPS.values() for name in names}
                  | set(LEGACY_STEP8_FIELDS))
```

  Define these **proposed** symbols in `pasien/forms_igd_workflow.py`, where `STEPS` already lives. Import them explicitly into snapshot/resume owners. Keep the same existing values in new snapshot `visit` dictionaries, preserving the content digest for otherwise unchanged records. Old revisions render only their stored values, never live fallback. Render nonempty legacy notes in a labelled read-only historical block, not as new required inputs.
- [ ] Arrange the page DOM as `#igd-diagnoses` → “Kategori tata laksana” selector → action/medication panels → nursing block. Place nursing controls inside their own valid `#igd-step-form` **after** the independent action forms; retain the CSRF token, workflow version, save status and existing `main` element ID used by controllers. Never nest the diagnosis/medication/action forms inside it.
- [ ] Keep the single existing `#igd-action-panel` reachable by `data-care-tab="actions"`, and `#igd-medications` by `data-care-tab="medications"`. Switching panels retains unsaved input in memory and does not submit/create records. Do not move Step 9 professional execution into Step 8.
- [ ] Present Manual/Master/AI as labelled segmented controls that drive the existing canonical mode values. Maintain one submitted value per mode, keyboard focus and a working no-JS read-only/fallback explanation; update selectors only where necessary. No duplicate `name` inputs.
- [ ] Add route/render/persistence tests for DOM order, no nested forms, nursing save/reload, retired-field POST rejection with no mutation, signed snapshot preservation, old snapshots without these fields, and unchanged Step 9 professional controls. Scope assertions to `.igd-content`/responsible forms, not incidental navigation text.
- [ ] **GREEN:** Run the proposed module plus `pasien.tests_igd_workflow_ui`, `pasien.tests_igd_workflow_finalization`, `pasien.tests_professional_http`, `pasien.tests_professional_snapshots`; require `OK`, exit 0. Baseline actual counts are recorded in the roadmap, not invented here.

## Task 2: Connect ICD-10 selection to ICD-9 master suggestions

**Files:** `klinis/services/saran.py`, `klinis/tests/test_saran.py`, `pasien/igd_workflow_views.py`, proposed replacement tests, `templates/pasien/_igd_workflow_operations.html`, `static/js/igd-clinical-controls.js`, `static/js/igd-clinical-expansion.js`.
**Consumes:** `KasusTersering.icd10`, `KasusTindakan.icd9` (`klinis/models.py:77–136`), `_kelompok_for()` and `resolve_detail()` (`klinis/services/tarif.py:6–48`), persisted `visit.diagnoses`.
**Produces, proposed:** `tindakan_untuk_diagnosis(kunjungan, icd10_code, *, query='', limit=30) -> list[dict]`; visit-scoped catalogue response with `results`, `mapping_available`, and `source='KASUS_MASTER'` when `type=ICD9&diagnosis_id=<saved active diagnosis>` is supplied.

- [ ] **RED:** Add fixtures with the same procedure linked to different diagnoses and service groups. Assert exact ICD-10 FK matching, group scoping, deduplication and `None` for an unpriced tariff. Pin an unmapped code returning an empty list. Do not use only name-token similarity as proof of ICD-10 mapping.
- [ ] Implement the new helper in the existing `saran.py` owner. Select matching `KasusTindakan` through `kasus__icd10__kode` and `kasus__kelompok=_kelompok_for(kunjungan)`; order by case/action order then code, deduplicate by ICD-9 code, cap the result and resolve price through the existing resolver. Serialize Decimal as strings or null, never float/client-authoritative totals.
- [ ] Extend `igd_workflow_catalogue()` (`igd_workflow_views.py:284–299`) without changing default catalogue responses. Validate `diagnosis_id` as a positive integer; resolve it through `visit.diagnoses.filter(active=True)`. Reject another visit's/cancelled diagnosis. For a manual diagnosis with no code, return `mapping_available=False` and allow ordinary ICD-9 search separately.
- [ ] Add “Berdasarkan diagnosis” plus a selector of active structured diagnoses to the action panel. Default to the primary coded diagnosis only if it exists; permit secondary selection. Display reviewed catalogue suggestions as “Saran Master”, not AI. Choosing a suggestion fills code/canonical name and mode MASTER, but does not save, execute or bill until the operator uses the corresponding explicit action.
- [ ] On diagnosis or query changes, invalidate outstanding requests; a delayed result for the former diagnosis must not replace current suggestions. On no match, retain free-text Manual and global Master search and show “Belum ada pemetaan tindakan untuk diagnosis ini.” Never imply that a diagnosis mandates a procedure.
- [ ] Keep `plan_action()` as the validation/persistence owner, with canonical codes, quantity/location/notes and tariff-override reason. Actual performer and timestamp remain attributable to Step 9; show that distinction in the Step 8 recap.
- [ ] **GREEN:** Run `klinis.tests.test_saran`, the proposed replacement module, `pasien.tests_clinical_expansion`, `pasien.tests_professional_execution`, `pasien.tests_professional_billing`. Verify saving a plan creates no CPPT/billing, while approved execution retains the current one-execution/one-charge behavior.

## Task 3: Make recommendations consume meaningful evidence from steps 1–7

**Files:** proposed `klinis/services/igd_recommendation_context.py`, `klinis/services/ai_igd_targets.py`, `pasien/tests_igd_target_ai.py`.
**Consumes:** Actual fields enumerated in `forms_igd_workflow.py:13–22`, `IgdVitalObservation`, structured physical findings and completed `OrderPenunjang` results; current `generate_target()` transport/gates.
**Produces, proposed:** `build_igd_recommendation_context(visit) -> dict`, shared by medical/procedure/SDKI/SLKI/SIKI targets. It performs no external request and no database writes.

- [ ] **RED:** Capture the mocked transport argument and assert that documented abnormal/negative findings remain distinguishable, vital zero is not discarded, pending orders are labelled pending without claimed results, and clinical result numbers/units survive. Current word intersection (`ai_igd_targets.py:33–46`) is insufficient for these assertions.
- [ ] Implement a bounded allowlist context with schema version, source step, observation time, available/missing state and clinical values. Include age range and clinical sex only when needed; exclude name, MRN, address, NIK, phone and unfiltered notes. Preserve structured positive/negative findings and numeric results; do not infer normality from empty JSON or from a completed status without content.
- [ ] Treat legacy free-text results/findings as untrusted clinical text, not executable instructions. Only include sanitized bounded clinical summaries; if identity redaction or structure is uncertain, mark evidence unavailable for the model and keep it visible locally for the operator. Test synthetic identifiers and instruction-like content explicitly.
- [ ] Generate catalogue candidate sets using assessment/selected-diagnosis context, not exclusively `query + anamnesis_rps`. Preserve the existing catalogue membership check, target-specific profession authorization, maximum candidate count, default-off gates and actor/visit/version/target-bound signed tickets. Never hold a clinical write transaction while awaiting a model response.
- [ ] Show a local “Dasar saran” summary with source availability, including missing labs/unfinished assessment; acceptance stays explicit. Add this read-only context to the current Step 8 view/template if needed and include those changes in this task's diff, not a separate context-building system.
- [ ] **GREEN:** Run `pasien.tests_igd_target_ai` and `pasien.tests_igd_workflow_ai`. Test disabled AI (no transport call), timeout, malformed output, unknown code, wrong profession/target/visit, stale ticket, and valid explicit acceptance. Mock transport tests prove contract/gates, not live model quality; an authorized synthetic live-provider check is a separate release gate.

## Task 4: Finish independent assessment-aware 3S input and regression coverage

**Files:** `_igd_planning_components.html`, `static/js/igd-clinical-expansion.js`, `static/js/igd-assessment-workflow.js`, `pasien/tests_clinical_expansion.py`, `pasien/tests_igd_target_ai.py`, `qa/clinical_expansion_browser.py`.
**Consumes:** Existing `validate_components()` (`igd_planning_components.py:11–57`) and `Pemetaan3S`; Task 3 context; unchanged nursing field names.
**Produces:** Independently selectable modes with diagnosis → outcome → intervention suggestions and no silent cross-component overwrite.

- [ ] **RED:** Add a route-level save/reopen test for SDKI=MASTER, SLKI=MANUAL, SIKI=MASTER and a second save retaining modes/provenance; assert medical diagnosis is unchanged. Add AI context tests that require SDKI and selected SLKI before mapped SIKI suggestions.
- [ ] Retain the source's independent Manual/Master/AI behavior. Reuse the existing component validator and its mapping rejection; an out-of-map correction requires an explicit Manual choice, not rewriting master names. Preserve `I.01011 = Manajemen Jalan Napas` from the actual catalogue, not the document's conflicting label.
- [ ] Ensure the mapping helper intentionally changes the accepted component values **and** their mode state; do not fill a Master-looking code while retaining stale AI ticket/provenance. A delayed response after SDKI/SLKI changes is discarded; editing an accepted AI value explicitly resets it to Manual or requires a fresh acceptance.
- [ ] Extend the existing browser probe with the replacement DOM-order/absence assertions, real sequential typing, independent saves/reloads, keyboard mode selection, switching action/medication without draft loss, and Step 9 continuity. Keep doctor, nurse, assessor and nonclinical admin controls distinct; broader read visibility is not mutation permission.
- [ ] **GREEN:** Run the Step 8, diagnosis, 3S/AI, clinical expansion and professional HTTP suites named in the roadmap. Browser acceptance at 375/768/1366 px must show the intended order, zero page errors, no horizontal overflow, no duplicate IDs and correct persistence after two saves.

## Completion Evidence

Record requirement ID → changed path → exact test/journey → observed result. This plan is complete only after the source-specific replacement, linked master suggestions, assessment-context and independent 3S journeys pass; the presence of pre-existing services or the old delivery ledger is not completion proof. Do not commit, push or deploy as part of task execution without separate user authorization.
