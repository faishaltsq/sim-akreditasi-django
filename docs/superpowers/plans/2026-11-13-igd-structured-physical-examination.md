# IGD Structured Physical Examination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This is a planning deliverable, not authorization to implement, commit, push, or deploy.

**Status:** IMPLEMENTED AND LOCALLY VERIFIED — uncommitted working tree; no push or production deployment. See execution status below for evidence, ordering deviations and conditional skips.
**Date:** 2026-11-13.
**Goal:** Extend IGD step 6 with the source document's eleven physical-examination groups, explicit structured findings, preserved legacy observations, safe normal shortcuts, and consistent draft/final/printed documentation.
**Architecture:** Reuse `KunjunganPasien`, `save_step`, existing workflow authorization/versioning, and immutable revisions. Store anatomical choices in `secondary_survey_detail.head_to_toe` with its own schema version, derive a server-owned narrative and compatible string projections, and reuse existing `keadaan_umum`/`kesadaran` fields for the first group. Introduce one focused Python catalogue/adapter module and one dedicated browser controller; no new clinical model, dependency, endpoint, or schema migration is expected.
**Tech Stack:** Existing Django, Python, Bootstrap, vanilla JavaScript, existing SQLite/PostgreSQL test paths and browser automation tools.
**Spec:** `../specs/2026-11-13-igd-structured-physical-examination-analysis.md`.
**Baseline:** `112a7b3357168ec53aac6cb4c6670b8bcab86f66`, clean tree before these documentation files. Source DOCX SHA-256: `9b440a3bf048e2fedda3a458ab4657729c2fc4c16dee8e9b73856de0205c8f7f`.

## Global Constraints

- Scope is the physical-examination delta PF01–PF15, not rebuilding the previous eleven-step workflow. The 2026-11-12 plan remains historical context; its create-file instructions are not to be executed again.
- Default means “Belum dikaji”, never normal. Normal is an explicit clinician selection. “Tidak diperiksa” is different from an examined normal finding.
- Preserve patient/visit identity, registration/guarantor, unit scope, profession checks, CSRF, lock order, optimistic version, billing, orders, CPPT, attachments, observation history, and immutable final revisions.
- Keep `fisik_head_to_toe` a dictionary of strings: `KunjunganPasien.has_asesmen_awal` calls `.strip()` on a legacy value. Never place list/dict selections inside those string values.
- Do not infer structured choices from legacy prose or legacy default-normal values. Show their original content/provenance and require explicit review for adoption.
- Do not copy combined historical head/neck or thorax prose into separate newly examined groups. Show the combined source once under a legacy panel.
- No patient-data browser storage, AI/provider calls, new EP mapping, production fixtures, historical bulk rewrite, or unrelated cleanup.
- No automatic GCS 15, E/V/M, observation timestamp, or lab interpretation from normal shortcuts or consciousness choices. GCS changes remain in step 4/10.
- Keep source clinical option coverage, but correct the source's incomplete six-group model example by implementing the full eleven-group narrative specification.
- Use `request.user`, existing visit authorization and the current transaction. New helpers must not create a workflow or alter records on GET.
- A schema change is not assumed necessary. `makemigrations --check --dry-run` must remain clean; stop and explain if an unforeseen model change is required.
- Commit/push/deploy commands below are conditional release instructions only: obtain explicit execution/release authorization before performing them.

## Review Focus

1. A secondary-only or legacy-alias record must display its real stored examination without silently creating normal findings or mutating the row — Tasks 1, 3, 4.
2. Reopening after save and a stale-version retry must preserve selected findings, notes, markers, localis and unrelated clinical/financial records — Tasks 2, 3.
3. “Semua Normal” must not overwrite abnormal findings, notes, unreviewed historical material, consciousness, GCS or an unperformed genital examination — Tasks 1, 3.
4. An old final snapshot missing the new general-state fields must never display today's live values; new structured findings must invalidate outdated approvals — Task 4.
5. Empty schema scaffolding, fake catalogue codes, normal-plus-abnormal, unsafe HTML and mismatched summary text must not become complete/trusted clinical documentation — Tasks 1, 2, 4, 5.

## Verified baseline and current evidence

- Current-turn local command: `.venv/Scripts/python manage.py test pasien.tests_igd_workflow_clinical pasien.tests_igd_workflow_ui pasien.tests_igd_workflow_finalization --keepdb --noinput`.
- Measured result: **35 tests passed**, exit 0, Django test time 4.701 seconds. Log: Hermes scratch `igd-physical-plan-baseline.log`. This is not the full suite or a production journey.
- Read-only production aggregate on 2026-11-13: 11 IGD visits, 1 with nonempty head-to-toe, 1 with nonempty secondary survey, **1 secondary-only**, no preexisting `head_to_toe` namespace, no non-object values in those two JSON columns, 1 workflow and 0 final workflows. This is not permission to rewrite those visits.
- The preceding release's 407-test result belongs to its frozen release, not to this unimplemented delta. Measure the future gate rather than inventing its test count.
- Inspect both plan directories: existing `.hermes/plans/` entries do not own this structured-examination requirement. This document is the authoritative step-6 delta; no previous plan is deleted or rewritten.

## File inventory and ownership

Execute sequentially: Tasks 2–4 share forms/views/tests and cannot be edited by independent workers concurrently.

**Create:**
- `pasien/physical_exam.py` — versioned catalogue, JSON validator, legacy reader, merge/projection, summary and presence semantics; no ORM writes.
- `templates/pasien/_igd_physical_exam_form.html` — complete step-6 field rendering, structured groups and narrative preview.
- `templates/pasien/_igd_physical_exam_readonly.html` — escaped structured/historical display shared by current/final print consumers.
- `static/js/igd-physical-exam.js` — hydration, selection state, conditional notes, preview, shortcut and draft-save rehydration.
- `pasien/tests_igd_physical_exam.py` — deterministic helper, HTTP persistence, lifecycle and rendering regression tests.

**Modify:**
- `pasien/forms_igd_workflow.py:12–29,40–118` — step ownership, legacy-tolerant general choices and structured validation.
- `pasien/services/igd_assessment_workflow.py:60–153` — persist server-derived fields in the same save/version/audit transaction.
- `pasien/igd_workflow_views.py:30–118,236–252` — context from correct live/snapshot source, readonly and compatible summary rendering.
- `pasien/services/igd_finalization.py:18–75` — actual-data presence and snapshot/signature compatibility, not JSON truthiness.
- `templates/pasien/igd_workflow.html:40–44,64` — select the dedicated step-6 partial and include the new script without duplicate named fields.
- `templates/pasien/_igd_clinical_widgets.html:9–16` — remove only old head-to-toe textarea row; retain anatomical-marker editor and step-5 widgets.
- `static/js/igd-clinical-controls.js:108–112` — remove only the superseded `.organ-finding` writer; retain operation, screening and marker behavior.
- `templates/pasien/igd_workflow_resume.html:9` — render physical data using stored snapshot and compatible partial instead of raw dictionary representation.
- `pasien/views.py` — extend only affected legacy print-context builders if needed; retain existing route decorators and final-record redirects.
- `templates/pasien/cetak_asesmen_medis_igd.html:147–169` — replace touched physical block with compatible renderer; absent observations must not render default-normal claims.
- `pasien/tests_igd_workflow_ui.py`, `pasien/tests_igd_workflow_clinical.py`, `pasien/tests_igd_workflow_finalization.py` — extend only affected assertions/contracts, do not weaken existing invariants.
- `staticfiles/` — generated assets/manifest from collectstatic, only after source implementation.

**Execution evidence, created during implementation only:** `docs/superpowers/evidence/igd-physical-exam/` for source-matched local/browser results; final production evidence outside the repo after the release push to avoid a documentation-only redeploy.

## Data contract and catalogue

### Canonical ownership

- Group 1 uses existing `keadaan_umum` and `kesadaran`; add them to step 6's allowlist and new snapshots. Do not duplicate them inside the anatomical JSON.
- The other ten groups use this document. The registry contains all eleven display groups and identifies group 1 as general-field bindings.

```json
{
  "head_to_toe": {
    "schema_version": 1,
    "sections": {
      "mata": {"status": "EXAMINED", "findings": ["anemis"], "note": "Konjungtiva pucat bilateral", "reason": ""},
      "genitalia_anus": {"status": "NOT_EXAMINED", "findings": [], "note": "", "reason": "Tidak ada indikasi saat asesmen"}
    }
  },
  "head_to_toe_summary": "Mata: Konjungtiva anemis — Konjungtiva pucat bilateral. Genitalia & Anus: Tidak diperiksa — Tidak ada indikasi saat asesmen."
}
```

The example is only the owned fragment of existing `secondary_survey_detail`; preserve its old `mata`, `thorax`, unknown metadata and manually documented values. Do not overwrite the full object with that fragment. Missing sections remain unassessed.

### Stable registry keys and options

| Display group/key | Option codes; labels and normal descriptions come from the spec |
|---|---|
| `keadaan_umum_kesadaran` | General fields, not anatomical findings: appearance `Baik / sakit ringan`, `Tampak sakit sedang`, `Tampak sakit berat`; consciousness `Kompos Mentis`, `Apatis`, `Somnolen`, `Sopor`, `Koma`. Existing other text remains visible as unchanged legacy data. |
| `kepala_wajah` | `normal`, `hematoma_vulnus`, `deformitas_fraktur_impresi`, `nyeri_tekan`, `lainnya` |
| `mata` | `normal`, `anemis`, `ikterik`, `anisokor`, `midriasis_miosis`, `edema_palpebra_hematoma`, `lainnya` |
| `tht` | `normal`, `otorrhea_rhinorrhea`, `epistaksis`, `deviasi_septum`, `faring_tonsil`, `lainnya` |
| `leher` | `normal`, `jvp_meningkat`, `deviasi_trakea`, `kgb_tiroid`, `kaku_kuduk_jejas`, `lainnya` |
| `paru` | `normal`, `asimetris_retraksi`, `vesikuler_menurun_hilang`, `rhonki`, `wheezing`, `perkusi_redup_hipersonor`, `lainnya` |
| `jantung` | `normal`, `ireguler`, `murmur`, `gallop`, `bunyi_menjauh`, `lainnya` |
| `abdomen` | `normal`, `distensi`, `nyeri_tekan`, `defans`, `bising_usus_abnormal`, `hepatosplenomegali`, `lainnya` |
| `genitalia_anus` | `normal`, `perdarahan`, `retensi_distensi_vesika`, `hemoroid_melena_hematochezia`, `lainnya`; catheter state is explicitly described in notes, never inferred. |
| `ekstremitas` | `normal`, `akral_dingin_pucat_sianosis`, `crt_memanjang`, `edema`, `deformitas_krepitasi_fraktur`, `paresis_plegia`, `lainnya` |
| `kulit` | `normal`, `turgor_menurun`, `sianosis_pucat_ikterik`, `ruam_petekie_ekimosis`, `luka_bakar_ulkus`, `lainnya` |

Grouped source alternatives retain their wording; notes specify site, side, pupil diameter, wound size, auscultation location, quadrant, strength or burn extent as applicable. Do not infer anatomic laterality or invent numeric measurements from a grouped option.

### Validator/merge invariants

- Exact integer schema version 1; reject unsupported versions and boolean-as-integer. Reject unknown new section/option codes, duplicates, non-string findings, unexpected owned keys, list-as-root and nested executable/HTML assumptions.
- Status enum: `UNASSESSED`, `EXAMINED`, `NOT_EXAMINED`. `UNASSESSED` contains no findings; `NOT_EXAMINED` has no findings and has a nonblank reason. `EXAMINED` has at least one known finding. Blank unrelated sections are valid partial drafts.
- `normal` is exclusive with every other finding for the same section. Abnormal findings can coexist. Do not globally reject findings that could occur at different sites based on unparsed notes.
- Notes/reasons are plain strings, at most 2,000 characters each; `lainnya` requires a nonblank note. Limit the new namespace to 64 KiB UTF-8; do not apply the new size rule retroactively to preserved legacy fields.
- Generate summary on the server in fixed registry order and labelled plain text; do not trust a client-submitted `head_to_toe_summary`. Keep preview and persisted canonical summary consistent.
- Merge submitted anatomical sections into existing owned sections, preserving omitted ones. Clearing requires explicitly submitting `UNASSESSED` for that section; omitted is not clear.
- Preserve old top-level keys and original unstructured findings. Legacy prose is never automatically checkbox-classified.
- Derive compatible string keys `mata`, `tht`, `abdomen`, `ekstremitas`, `kulit`, `kepala_leher` (labelled head+neck), `thorax` (labelled lung+heart), and aliases consumed by old surfaces: `toraks_dada`, `genitalia_anus`, `integumen_kulit`. Keep unrelated legacy keys. Preserve replaced source prose in the canonical owned document's server-only `legacy_before_adoption` map on first explicit adoption; do not repeatedly overwrite that retained original.
- `legacy_before_adoption` is generated from stored records, not accepted from an untrusted payload. `validate_exam` validates client fields; `prepare_exam` adds retained provenance only from trusted current values. Readers accept this server-owned stored extension.
- On subsequent edits, the hidden JSON may echo that server-owned provenance. `prepare_exam` accepts and removes an echo only when it equals the locked stored provenance, then reattaches the trusted original after validation; a newly supplied or altered provenance map is rejected. Omitting the echo preserves the stored map. This avoids making a legitimate second save fail the client-only validator.
- A legacy-only client that omits the new namespace must not erase it. If it attempts a conflicting flat-only edit after structured adoption, reject with a field-addressable instruction to use the structured form; do not report an ignored clinical edit as saved.

## Task 1: Catalogue, compatibility reader and deterministic serializer

**Files:** Create `pasien/physical_exam.py`, `pasien/tests_igd_physical_exam.py`.
**Interfaces (all proposed, created by this task):**
- `EXAM_SECTIONS`: ordered registry of eleven display groups with key, label, kind, option code/label/normal description and note hint.
- `validate_exam(document: dict) -> dict`: normalized client document; raises `django.core.exceptions.ValidationError`.
- `prepare_exam(current_secondary: dict, current_head: dict, incoming_secondary: dict, incoming_head: dict) -> tuple[dict, dict]`: validated merged secondary object and canonical string projection.
- `exam_context(head: dict, secondary: dict, general: dict) -> dict`: `sections` and `legacy` lists, summary and assessed-state metadata; pure, nonmutating.
- `exam_present(head: dict, secondary: dict, localis: str) -> bool`: meaningful examined findings/legacy text, not empty schema or unassessed-only scaffolding. All-not-examined does not assert a performed physical exam; existing reasoned episode exemption remains available.

- [x] Write helper regressions before introducing the module. Example initial tests:

```python
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

class PhysicalExamContractTest(SimpleTestCase):
    def test_normal_cannot_coexist_with_abnormal(self):
        from pasien.physical_exam import validate_exam
        document = {"schema_version": 1, "sections": {
            "mata": {"status": "EXAMINED", "findings": ["normal", "anemis"], "note": "", "reason": ""}
        }}
        with self.assertRaises(ValidationError):
            validate_exam(document)

    def test_secondary_only_is_visible_without_mutation(self):
        import copy
        from pasien.physical_exam import exam_context
        secondary = {"mata": {"konjungtiva": "Anemis bilateral"}}
        before = copy.deepcopy(secondary)
        context = exam_context({}, secondary, {})
        self.assertIn("Anemis bilateral", str(context["legacy"]))
        self.assertEqual(secondary, before)
```

- [x] Run `.venv/Scripts/python manage.py test pasien.tests_igd_physical_exam --keepdb --noinput`; require a RED attributable to the missing contract, not a fixture/import conflict elsewhere.
- [x] Implement the registry and interfaces above. Use standard-library copies/serialization and Django `ValidationError`; no database or new dependency. Keep old combined prose labelled in the legacy panel. Use empty placeholders only for display, not as persisted findings.
- [x] Add explicit tests for each group's source option coverage, duplicate codes, unsupported schema, bad shapes/oversize, normal exclusivity, plain-text escape boundary, preserved unknown legacy keys, adoption provenance, omitted-section merge, explicit clear and no semantic GCS/lab inference.
- [x] Run the module GREEN. Verify an empty scaffolding document is not considered `physical_exam` present, and valid legacy free text is still recognized.
- [ ] Review the diff. If commits have been authorized, stage only this task's paths and record a focused commit; otherwise leave changes uncommitted for review.

## Task 2: Transactional step-6 write and general-state bindings

**Files:** Modify `forms_igd_workflow.py`, `services/igd_assessment_workflow.py`; extend `tests_igd_physical_exam.py` and affected clinical tests.
**Consumes:** Task 1 interfaces and existing `save_step(pk, user, step, payload, version)`.
**Produces:** Existing draft endpoint remains unchanged; successful `values` includes canonical secondary/projection and general fields. No new route or model.

- [x] Add an HTTP regression using the real fixture idiom, not a parallel imaginary model:

```python
import json
from django.test import override_settings
from django.urls import reverse
from pasien import tests_igd_workflow as fixtures

@override_settings(IGD_WORKFLOW_ENABLED=True)
class PhysicalExamPersistenceTest(fixtures.IgdWorkflowTest):
    def test_saved_selection_projects_and_reopens(self):
        secondary = {"head_to_toe": {"schema_version": 1, "sections": {
            "mata": {"status": "EXAMINED", "findings": ["anemis"], "note": "Bilateral", "reason": ""}
        }}}
        response = self.client.post(
            reverse("pasien:igd_workflow_draft", args=[self.visit.pk, 6]),
            json.dumps({"version": 0, "fields": {"secondary_survey_detail": secondary}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.visit.refresh_from_db()
        self.assertIn("Bilateral", self.visit.fisik_head_to_toe["mata"])
        self.assertEqual(response.json()["values"]["fisik_head_to_toe"], self.visit.fisik_head_to_toe)
        page = self.client.get(reverse("pasien:igd_workflow", args=[self.visit.pk]) + "?step=6")
        self.assertContains(page, "Bilateral")
```

- [x] Run the persistence class RED. The existing server accepts generic JSON but does not derive/protect the string projection, so assert the missing invariant rather than mere HTTP 200.
- [x] Add only `keadaan_umum` and `kesadaran` to step 6. Build select choices using the registry and an unchanged historical stored value where needed. A historic `Lemah` or other unlisted text must survive editing an unrelated organ; new arbitrary general values are not accepted.
- [x] In `StepForm.clean`, invoke Task 1 validation/merge when step 6 fields are present. Convert failures to field-addressable `secondary_survey_detail` errors. Treat stored provenance as server-only. Derive narrative and projection from submitted selections, not client narrative.
- [x] Extend `save_step` so server-derived `secondary_survey_detail` and `fisik_head_to_toe` changes are included in `changed`/`update_fields` when structured data changes. Do not touch GCS/TTV, other clinical steps or financial relations. Record derived field names in the existing audit.
- [x] Keep the existing lock order: lock visit, resolve workflow, validate expected version, persist examination/projections, increment version and invalidate signatures once. Do not add a second transaction or independent writer.
- [x] Add tests: partial organ patch preserves other organs; repeat same facts is deterministic; stale version is 409 with unchanged data; invalid selection is 400 with no new workflow/version; unchanged legacy general values survive; empty structured metadata cannot satisfy completeness; flat-only conflicting update fails explicitly; CSRF/wrong-unit/ASESOR writes denied; markers/localis/order/billing unchanged.
- [x] Run new tests plus `pasien.tests_igd_workflow_clinical`, `pasien.tests_igd_workflow_ui`, `pasien.tests_igd_workflow_hardening`. Require exit 0; read actual collected test totals.
- [ ] Review/stage/commit only if authorized, preserving unrelated changes.

## Task 3: Eleven-group editor, normal shortcut and preview

**Files:** Create `_igd_physical_exam_form.html`, `igd-physical-exam.js`; modify workflow view, workflow template, clinical-widget partial and old organ JS block; extend new/UI tests.
**Consumes:** Task 1 registry/reader and Task 2 endpoint canonical readback.
**Produces:** Existing `#igd-step-form` submits one correctly named input per owned field and the same version/CSRF contract.

- [x] Write rendered-response tests that pin eleven groups, actual preselected saved options, secondary-only legacy visibility and all field names. Example additional assertion in a fixture-based UI method:

```python
page = self.client.get(reverse("pasien:igd_workflow", args=[self.visit.pk]) + "?step=6")
self.assertContains(page, 'id="igd-physical-exam"')
self.assertContains(page, 'data-exam-section="genitalia_anus"')
self.assertContains(page, 'id="igd-exam-summary"')
self.assertContains(page, 'id="igd-exam-normal"')
```

- [x] Run the owning test class RED; then build `physical_exam` view context with `exam_context` from the effective live/snapshot source, not arbitrary patient defaults.
- [x] In the main workflow template, render the dedicated form partial **instead of the generic field loop for step 6**. The partial renders general bound fields, the existing hidden JSON/marker fields and bound `fisik_lokalis` exactly once, plus the anatomical group widgets. Keep CSRF in the parent form. Preserve callable-default `initial-*` helpers and the existing serializer's exclusion of them.
- [x] Replace only the old head-to-toe textarea block in `_igd_clinical_widgets.html`. The marker fieldset and step-5 questionnaires remain. Remove its superseded `.organ-finding` listener, not the rest of `igd-clinical-controls.js`.
- [x] Emit registry data through Django `json_script`. Add the new script after existing workflow scripts. Declare all DOM/state references before initialization. Use `textContent` for notes/summary; never interpolate user text into `innerHTML`.
- [x] Required selectors: root `#igd-physical-exam`; one `[data-exam-section="<key>"]` per display group; anatomical status `[data-exam-status]`, finding checkboxes with `value` catalogue codes, note `[data-exam-note]`, reason `[data-exam-reason]`; `#igd-exam-normal`; readonly narrative `#igd-exam-summary` with no submitted name.
- [x] Anatomical widgets and GCS references have no submitted `name`; the owned hidden JSON fields and the two bound general fields carry the payload. Show GCS from existing timestamped initial/evaluation observations, or label legacy values as lacking observation provenance; no new measurements are written by this editor.
- [x] Hydrate saved checked state from canonical JSON. Abnormal/Lainnya reveals notes; NOT_EXAMINED reveals reason and clears draft findings only through explicit user interaction. Selecting Normal clears abnormal checks in that section, and selecting abnormal removes Normal. Server remains authoritative against crafted JSON.
- [x] When an individual status/Normal change would remove existing findings or hide a nonempty note, require an explicit review/confirmation; cancellation preserves the values. A retained note remains visible as an organ comment, not a hidden discarded field. Test this separately from the protected bulk normal shortcut.
- [x] “Semua Normal” is an explicit in-memory draft action. Fill only unassessed anatomical groups without existing notes or unreviewed legacy content. Skip group 1 and genitalia/anus; normal genital findings require individual explicit selection. Preserve all abnormal/annotated groups and list skipped groups in the status message. No POST, navigation, GCS/observation write or signature occurs merely from clicking the shortcut.
- [x] Preview changes immediately in deterministic registry order, with input debouncing if needed. Do not infer diagnosis, Hb, quantitative pupil/GCS values or missing laterality. On `igd:draft-saved`, hydrate the server's canonical values without firing input/dirty events again; clear dirty only after acknowledged save.
- [x] Readonly FINAL/ASESOR/transferred views disable every mutation control and hide normal shortcut; legacy material and stored findings remain readable. Do not remove the eleven-step navigation or anatomical editor.
- [x] Run Django rendered tests and `node --check static/js/igd-physical-exam.js`; syntax success is not browser acceptance. Exercise Task 5's real-browser journey before declaring this task visually/behaviorally verified.
- [ ] Review/stage/commit only if authorized.

## Task 4: Correct final, legacy print, completeness and signatures

**Files:** Create `_igd_physical_exam_readonly.html`; modify finalization service, workflow/resume views, resume template, relevant legacy print context/template; extend new/finalization tests.
**Consumes:** Canonical/legacy reader, current immutable revision mechanism and unchanged reasoned addendum operation.
**Produces:** Human-readable findings in current and stored-final documents, with blank/unperformed data represented honestly.

- [ ] Add a final-snapshot regression before modifying readers. Use a synthetic fixture and old snapshot dictionary, not production data. Example core of the method:

```python
from pasien.physical_exam import exam_context
stored = {"fisik_head_to_toe": {}, "secondary_survey_detail": {"mata": {"konjungtiva": "Temuan historis"}}}
context = exam_context(stored["fisik_head_to_toe"], stored["secondary_survey_detail"], {
    "keadaan_umum": stored.get("keadaan_umum"), "kesadaran": stored.get("kesadaran")
})
self.assertIn("Temuan historis", str(context["legacy"]))
self.assertNotIn("NORMAL_OTOMATIS", str(context))
```

- [x] Make the actual HTTP test finalize a synthetic workflow using the existing finalization fixture pattern, record snapshot/digest, mutate today's live examination/general fields, GET the stored final page/resume and assert the original observations remain while a unique new live-only string is absent. Also create an old-schema snapshot omitting the two new general fields and assert they render “Tidak dicatat pada snapshot”, never live values.
- [x] Keep the overall existing snapshot envelope backward-readable; the new structured document has its own schema version. New `STEPS` fields are included in new snapshots. Never recompute/overwrite an old revision to add the new fields.
- [x] Replace JSON truthiness for `physical_exam` in `missing_sections` with `exam_present`. Partial meaningful legacy/structured examination still follows the established policy; schema-only/unassessed-only does not. Entirely unperformed examination requires the existing explicit episode exemption, not a fabricated normal selection.
- [x] Bind readonly form initial values and catalogue legacy choices exclusively to `revision.snapshot.visit` for FINAL records, including absent new fields. New fields absent from old snapshots must not inherit their model-form live instance values.
- [x] Render the stored server narrative and versioned labels/rows with the readonly partial. Do not redefine the v1 catalogue labels silently in future changes; a later incompatible label/meaning change requires a new supported catalogue version. For legacy snapshots without a stored narrative, format their actual legacy content without mutation or normal defaults.
- [x] In touched legacy physical print blocks, use the same compatible reader and “Belum tercatat” fallback. Preserve the original URL/authorization/final redirect. Do not redesign other sections or legacy editors.
- [x] Explain stale clinical approval state in the UI when a signature's digest no longer matches the expanded current clinical snapshot. Existing draft approvals may need review/signing again after general-state fields join the snapshot; never forge/migrate signatures to a new digest. Stored FINAL snapshots/signatures remain immutable and readable.
- [x] Test final edit denial, old legacy-writer guards, signature invalidation on selection changes, reason-required addendum creating another revision without changing the original, current/snapshot isolation, escaped notes, genuine legacy normal text preserved and absent legacy data not rendered normal.
- [x] Run `pasien.tests_igd_physical_exam`, `pasien.tests_igd_workflow_finalization`, `pasien.tests_igd_workflow_hardening`, `pasien.tests_igd_workflow_outcomes` and affected print tests from the existing `pasien` suite. Discover exact print test names with repository search rather than inventing labels.
- [ ] Review/stage/commit only if authorized.

## Task 5: Browser evidence, regressions and conditional release handoff

**Files:** Extend affected tests; generate tracked `staticfiles/`; create local verification evidence under the declared evidence directory only during implementation.
**Consumes:** Tasks 1–4; synthetic local QA environment, never real patient data.
**Produces:** Evidence tied to the tested source/commit, with local and production gates reported separately.

- [x] Measure a fresh local baseline from the actual starting tree; if other source edits/merge markers appear, preserve them and isolate an approved checkout before testing.
- [x] Run the new module and the previously measured baseline modules. Newly introduced tests must actually be collected. Then run `.venv/Scripts/python manage.py test klinis pasien --keepdb --noinput`, Django check, migration drift, node syntax checks and `git diff --check`. Record exact totals/failures and command exits; do not assume the preceding release's count remains current.
- [x] Start an isolated QA server with scratch-only SQLite/media and synthetic visits covering empty, secondary-only, legacy-key aliases, structured abnormal, and FINAL cases. Reuse the existing fixture idiom (`IgdWorkflowTest`, `self.visit`, `self.user`, explicit local test session). Do not add cross-version site-packages or copy credentials to docs. Use the available browser automation environment rather than adding Playwright to application requirements just for this turn.
- [x] Drive the real emitted HTML/JS. This complete helper is an example for the external Playwright QA harness; `page` is an authenticated isolated-browser page and `workflow_url` comes from the registered route for a synthetic visit:

```python
async def verify_structured_exam(page, workflow_url):
    await page.goto(workflow_url + "?step=6")
    await page.wait_for_selector("#igd-physical-exam")
    assert await page.locator("[data-exam-section]").count() == 11
    mata = page.locator('[data-exam-section="mata"]')
    await mata.locator("[data-exam-status]").select_option("EXAMINED")
    await mata.locator('input[type="checkbox"][value="anemis"]').check()
    await mata.locator("[data-exam-note]").fill("Temuan sintetis bilateral")
    await page.locator("#igd-exam-normal").click()
    assert await mata.locator('input[value="anemis"]').is_checked()
    assert not await mata.locator('input[value="normal"]').is_checked()
    assert "Temuan sintetis bilateral" in await page.locator("#igd-exam-summary").input_value()
    async with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/langkah/6/draft/")) as pending:
        await page.get_by_role("button", name="Simpan Draft", exact=True).click()
    response = await pending.value
    assert response.status == 200
    result = await response.json()
    assert result["success"] is True
    assert "Temuan sintetis bilateral" in result["values"]["secondary_survey_detail"]["head_to_toe_summary"]
    await page.reload()
    mata = page.locator('[data-exam-section="mata"]')
    assert await mata.locator('input[value="anemis"]').is_checked()
    assert await mata.locator("[data-exam-note]").input_value() == "Temuan sintetis bilateral"
```

- [x] Add separate browser cases for save/reload twice, two-tab stale conflict preserving the unsaved draft, secondary-only GET with no writes, general-state choices, NOT_EXAMINED reason, Lainnya note, mixed findings, shortcut preservation/skipped groups, marker/localis stability, escaping, and FINAL readonly snapshot after transfer. Capture page errors and ensure no uncaught initialization/TDZ/null errors.
- [x] Measure rendered geometry at 375, 768 and 1366 pixels: root scroll width <= viewport width, controls reachable by keyboard, notes/summary not clipped, no duplicate named clinical inputs. Use print emulation for the new structured/legacy readonly report; compilation alone does not establish layout.
- [x] Run `collectstatic --noinput` after final source changes, then verify source/unhashed/hashed/manifest consistency and gzip integrity. Review generated-file scope and preserve unrelated tracked static assets.
- [x] Stop the isolated QA server, keep sanitized evidence with source hashes and limitations, and summarize which gates were actually exercised. Do not claim production login/provider journeys from local browser results.
- [ ] If the user authorizes release: freeze a reviewed commit, validate its clean detached checkout, push its exact SHA without force, verify GitHub remote SHA, wait for Git-triggered deployment before considering manual deployment, and match canonical `https://arima.web.id` to the provider's exact SHA/READY deployment. This plan requires no production data migration.
- [ ] After authorized deployment, verify hashed assets and read-only/CSRF controls. Use an approved authenticated QA session for post-login acceptance, or mark that gate explicitly blocked. Never create final medical records or overwrite the secondary-only production example merely to demonstrate the UI. Keep AI disabled and preserve private attachment behavior.

## Acceptance and traceability

| Requirement | Owning tasks | Required proof |
|---|---|---|
| PF01 general/consciousness and GCS separation | 1,2,3,4 | Persist/reopen two existing fields; no observation/GCS mutation; old final snapshot isolation |
| PF02–PF11 anatomical source coverage | 1,3,4 | Registry and rendered eleven-group assertions, multi-findings and readable final/cetak |
| PF12 notes/localis/markers | 1,2,3,5 | Conditional note and server validation; marker/localis unchanged through saves |
| PF13 normal shortcut | 1,3,5 | Explicit action, protected abnormal/notes/history, no GCS/genital/default-normal assertion |
| PF14 narrative | 1,2,3,4 | Immediate preview and server-recomputed saved summary agree; no fabricated observations |
| PF15 compatibility/lifecycle | 1,2,4,5 | Secondary-only read, alias fallback, partial merge, stale conflict, final immutability and reasoned addendum |

## Explicit exclusions and handoff

Do not implement/fix unrelated registration, other clinical steps, general RANAP/RAJAL redesign, tariff/CPPT/order changes, historical data conversion, global cleanup of other normal-default blocks, AI activation, signing certification, or the separate CLI probe project's deletion while executing this plan.

Recommended execution is sequential native work with one final independent review because all tasks share one step-owned persistence/snapshot boundary. If a different execution method was already agreed by the user, preserve it. First obtain review/approval of this plan; do not start application implementation from this planning request.

## Execution status — 2026-11-13

### Done

- Task 1: `pasien/physical_exam.py` implements the eleven-group registry, strict v1 validation, stable summary, compatible string projection, retained provenance and a nonmutating legacy reader. The independent deterministic catalogue probe passed **65 checks**, including every option, forged provenance, Unicode size bound and legacy aliases.
- Task 2: existing step-6 endpoint now persists general state, consciousness and derived JSON/string values in the original lock/version/audit transaction. Regression tests cover invalid selections, stale conflict, marker preservation, legacy general values, secondary-only GET and meaningful completeness.
- Task 3: structured multi-choice editor, conditional notes/reason, explicit protected normal shortcut and summary preview shipped locally. Browser confirmed eleven groups, unique clinical field names, typed spaces, multiple simultaneous findings, Lainnya validation, canonical server summary, two consecutive saves/reloads and marker/localis/general-state persistence.
- Task 4: current/final/legacy print views use compatible readers; immutable old snapshots do not inherit today's newly added fields. Stale approvals show a re-review message. Existing finalization/addendum/outcome and private-attachment regression modules remain in the full passing gate.
- Task 5: `manage.py test klinis pasien --keepdb --noinput` passed **429 tests**, exit 0, Django test time **277.169 seconds**. This is the affected-app suite, not every Django app. Check, migration drift, both touched JS syntax checks and diff check passed.
- Browser evidence: three cases (new/legacy/final) at 375, 768 and 1366 pixels produced **nine nonoverflow geometry checks**. Additional journeys verified two-tab 409 with unsaved values retained, cancellation of abnormal-to-normal replacement, XSS remaining text, keyboard focus, no GCS creation, and historical readonly access after transfer to RANAP. No page errors were captured.
- `collectstatic` completed. Three workflow JS assets have equal source/unhashed/hashed/decompressed bytes and correct manifest MD5 names. New static artifacts are left uncommitted with the source.
- QA was isolated to scratch SQLite/media and synthetic identities. Both fixture-server processes were stopped; port 18766 was verified closed.
- Evidence: `docs/superpowers/evidence/igd-physical-exam/verification.json`, `browser.json`, `catalogue.json`, and `verification.md`. Evidence binds **15 working-tree source files** by SHA-256; it is not a new Git commit or deployment proof. Source fingerprint: `682ac46fe572b7bc8f90049031792b9d5d4ec9db2c58c5e40cf380acf2817c8a`.

### Not done, needs the live environment

- Production release and authenticated post-release acceptance have not run. They require separate release authorization and an approved QA session; the production application is not changed by this local implementation. Close these only after exact-SHA deployment/alias readback and the real authenticated step-6 save/reopen journey. No clinical production fixture was created.
- A fresh external reviewer could not be reached: the delegated provider returned HTTP 403 before making edits. Implementation, direct diff review and actual verification were performed by the parent; no independent-agent approval is claimed.

### Skipped on purpose and deviations

- Commit/stage/push/deploy checkpoints remain unticked because the user's approval was implementation-only. No migration was generated because the existing fields suffice.
- The first old-snapshot regression was added after initial reader wiring, rather than before that wiring as the granular task requested. It went RED on the missing explicit absent-snapshot label and then GREEN; final tests also prove no live-field leakage. The original ordering checkbox remains unticked instead of claiming a stricter TDD sequence than occurred.
- The first browser harness attempts failed on its own assumptions: duplicate submit-button `intent` names were incorrectly treated as duplicate clinical fields, and exact legacy text matching ignored the field-label prefix. The harness was corrected without weakening clinical assertions; completed browser runs passed.
- Server-owned provenance was tested across repeated saves so generated projections are not mislabeled as historical data. This corrected a RED discovered during implementation before the final full gate.
- Separate clinical expansion plans that appeared in the shared workspace were not edited or staged. General RANAP/RAJAL rollout and the old CLI probe project cleanup remain outside this plan.
