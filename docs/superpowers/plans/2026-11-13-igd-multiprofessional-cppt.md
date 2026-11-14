# IGD Multiprofessional CPPT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` or `subagent-driven-development` after approval. Follow RED → GREEN and do not modify shared files until the preceding owner hands them off.

**Status:** PLANNED — component B, depends on A.
**Goal:** Provide authored SOAP, ADIME and spiritual notes with explicit draft/sign/correction and accountable DPJP verification.
**Architecture:** Extend `CPPT` with additive structured/lifecycle fields and immutable note revision/verification records; preserve existing SOAP fields and historical booleans. Reuse the visit/action transaction and the component-A professional context without granting every PPA medical episode-edit permissions.
**Tech Stack:** Django forms/services/templates, JSON, existing digest/signature infrastructure and vanilla JS.
**Spec:** `../specs/2026-11-13-igd-professional-care-cppt-analysis.md`, PC05, PC08–PC11, PC13–PC14.
**Orchestration:** `2026-11-13-igd-professional-care-roadmap.md`.

## Global Constraints

- All roadmap constraints and component-A permission contracts apply. SOAP identity derives from authenticated professional context, not a posted string.
- Automatic event log is DRAFT. Do not invent S/O/A, nutrition diagnosis, spiritual condition or successful treatment response from an execution click.
- CPPT signing and DPJP verification are distinct from episode MEDIS/KEPERAWATAN signatures. A nutritionist may sign their own ADIME but not finalize the medical IGD episode.
- `KunjunganPasien.dpjp` is legacy text. Do not authorize verification by matching a username/name to it.
- Existing `verifikasi_dpjp=True` without signer/time/digest remains labelled historical/unattributed; do not create retrospective electronic signatures or silently erase old values.
- Signed content and verified revisions are immutable. Changes create an authored, reasoned revision/addendum; old snapshots never resolve current live note content.
- Source spiritual/other-profession templates require reviewed service authorization; they do not inherit medical capabilities.

## Review Focus

1. Nutrition/spiritual user enters one note but reaches a medical write endpoint — operation-specific checks deny it.
2. Changing SOAP/ADIME tabs hides entered fields — keep per-format drafts and explicitly confirm any discard; no hidden submission of a different format.
3. Another doctor presses verify — require current assigned DPJP or a verified substitute grant, not any doctor.
4. A note changes after verification — verification binds the old revision; current revision is visibly unverified.
5. Empty auto-generated CPPT falsely satisfies final completeness — only eligible signed/completed notes count under the enabled policy.

## File inventory

**Create:** `pasien/professional_care_models.py` (shared model owner handed to C afterward), `pasien/services/professional_cppt.py`, `pasien/tests_professional_cppt.py`, `templates/pasien/_igd_professional_cppt.html`, `static/js/igd-professional-cppt.js`.
**Modify after handoff:** `pasien/models.py` for registration/CPPT fields, `pasien/forms_igd_operations.py`, `pasien/services/igd_actions.py`, `pasien/services/igd_assessment_workflow.py` only operation-scoped authorization adapters, `pasien/services/igd_finalization.py`, `pasien/igd_workflow_views.py`, `pasien/urls.py`, `templates/pasien/_igd_workflow_operations.html`, `templates/pasien/igd_workflow_resume.html` and exact legacy CPPT writers/readers discovered in `pasien/views.py`; generated additive migrations.

All new names below are proposed and must be created in this component.

## Task B1: Note schemas and explicit lifecycle

**Produces:** `validate_note(format_code, payload) -> dict` and `create_care_note(visit, workflow, actor, *, format_code, payload, context, source_action=None) -> CPPT` in `professional_cppt.py`.

Format contracts:
- SOAP: existing `subjektif`, `objektif`, `asesmen`, `plan`; retain them as SOAP's canonical columns, not two independently editable copies.
- ADIME JSON: `asesmen_gizi`, `diagnosis_gizi`, `intervensi`, `monitoring`, `evaluasi`.
- SPIRITUAL JSON: `kondisi_psikospiritual`, `pendampingan`, `respon_pasien`.
- Each string max 10,000 characters; no unknown keys; plain text; draft may be partial, but an intentional standalone draft requires some nonblank content. Event-created draft may carry only a factual `event_log` with source action, service, quantity, actual time and performer.
- Add `format_code`, `structured_content`, `professional_snapshot`, `status` DRAFT/SIGNED/LEGACY, `version`, recorded-versus-actual timestamps and optional protected source-action reference. Existing rows default LEGACY rather than becoming signed retrospectively. Exact source-action uniqueness must prevent duplicate auto-log creation.
- Add `CpptRevision` immutable signed payload/digest/author/time/reason per note version. Store professional labels at authoring, not live master names on print.

- [ ] RED: add pure schema tests before accepting the new formats.

```python
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

class MultiprofessionalNoteSchemaTest(SimpleTestCase):
    def test_adime_does_not_accept_disguised_soap_payload(self):
        from pasien.services.professional_cppt import validate_note
        with self.assertRaises(ValidationError):
            validate_note('ADIME', {'subjektif': 'Field SOAP bukan ADIME'})
```

Run `manage.py test pasien.tests_professional_cppt --keepdb --noinput`; require feature-specific RED, then GREEN after implementation.
- [ ] Implement additive fields/models and the validator. Map current `NUTRISIONIS` and reviewed HC DIET/NUTR to ADIME; approved spiritual service to SPIRITUAL; supported other clinical roles to SOAP. Format changes must respect profession/service context, not arbitrary client selection.
- [ ] Add tests for every format, unknown format/key, empty/whitespace-only standalone content, size bounds, HTML escaping, legacy SOAP read and source-action draft idempotency. Confirm draft event text says performed service only, not a fabricated full clinical assessment.
- [ ] Implement `save_care_note` with caller-held version, ownership/scope, permitted draft edits and audit. `sign_care_note` creates immutable revision after required clinical-format fields are reviewed; do not sign or verify automatically on create.
- [ ] Define sign completeness: SOAP requires meaningful A/P with explicit unavailable-reason support for S/O; ADIME requires the five fields or a per-field documented exception; spiritual requires its three fields or an explicit exception. Missingness must stay labelled, not filled with normal text. Policy is configurable/reviewed, never inferred from a profession label alone.

## Task B2: Assigned DPJP verification and note correction

**Produces:** `PenugasanDpjpEpisode`, `VerifikasiCppt`, `verify_cppt(actor, note_id, expected_version, request_id) -> dict` and `correct_care_note(..., reason) -> dict`.

- `PenugasanDpjpEpisode`: visit + verified doctor account, assignment type PRIMARY/SUBSTITUTE, unit/time validity, approved source and assignment actor/time. Preserve legacy DPJP text for display; do not bulk link by name. Resolve authorized substitutes explicitly.
- `VerifikasiCppt`: exact immutable note revision FK, verifier account, performed-at, content digest, assignment reference and idempotency binding. Keep each historical verification, never a boolean-only overwrite.
- [ ] RED: an arbitrary doctor with a valid clinical profile but no episode assignment must be denied. Add allow fixture for the correctly assigned doctor; also pin revoked/expired substitute, another-unit doctor, non-doctor, self-claimed assignment and stale note version.
- [ ] Implement verification only for a signed current note revision, under visit → workflow → note → revision/verification lock order. Same key/payload returns the original result; two requests cannot create duplicate verification. Altered content or stale version produces conflict without a signature.
- [ ] Do not infer legal TTE certification from the application signature. Label UI as authenticated application verification with signer/time/content identity.
- [ ] Signed correction creates a new immutable revision with reason and author. Previous verification stays attached to the previous revision; current note is unverified until an authorized DPJP acts again. No delete or mutable replacement of the original signed record.
- [ ] Keep legacy boolean projection for backward readers only when a new valid verification applies; do not migrate old True rows into new verified records. Expose historical/unattributed status separately from current verification state.

## Task B3: Operation-scoped access and usable CPPT UI

**Consumes:** A's `resolve_professional_context`, existing `perform_action`, visit/unit checks and default-off feature gate.
**Produces:** scoped `cppt_create`, `cppt_save`, `cppt_sign`, `cppt_verify`, `cppt_correct` operations through the same dispatcher; dedicated note read/edit/verify UI.

- [ ] RED: a scoped nutritionist can create/sign ADIME but cannot post a medical diagnosis, prescription, clinical action from another profession, MEDIS episode signature or finalization. Assessor remains read-only; admin without clinical qualifications cannot sign.
- [ ] Extend dispatcher authorization by operation allowlist and capability, not by globally adding all professions to `DOCTORS | NURSES` or setting the whole episode readonly false. Preserve existing action authorization for unrelated operations and replay-before-mutation invariants.
- [ ] Build partial with creator's real profession/grade, format-specific labelled fields, draft/signed/legacy and current-verification badges, save/sign/correct buttons and a per-row DPJP verification control. Body input never controls author identity.
- [ ] Switching format preserves separate unsaved drafts in memory and asks before discarding; no patient data in localStorage/sessionStorage. On save failure retain visible inputs; stale version points to explicit review/reload.
- [ ] Quote no authority from hidden or disabled controls: server denies forged operation/profession/employee/note IDs regardless of UI state. Autocomplete displays minimal in-scope staff information only if the delegated-recording policy is enabled.
- [ ] Guard legacy CPPT edit/delete/verify routes discovered by searching `CPPT.objects`, `verifikasi_dpjp` and CPPT forms across source. A new route must not be bypassable through an old writer. Do not block legitimate other-unit post-transfer care outside the adopted IGD document boundary.
- [ ] Add HTTP and browser journeys for SOAP/ADIME/spiritual, unsaved format switching, correct-row verification, another-author edits denied, stale correction, repeated click, keyboard and 375/768/1366 geometry. Syntax alone does not prove format switching works.

## Task B4: Snapshot/completeness compatibility and handoff

- [ ] Add CPPT status/format/content/professional context, signed revision and verification identity to the clinical snapshot at signing/finalization. Old snapshots missing these keys show unavailable historical metadata, never live rows or assumed verification.
- [ ] Update `missing_sections` so auto-created DRAFT notes cannot alone satisfy completed care under the new gate. Define legacy handling explicitly: display unchanged, require reviewed adoption/completion or existing reasoned exemption rather than forging a signed historical note.
- [ ] Test original snapshot/digest after changing current note/grade/DPJP assignment, reasoned correction preserving originals, and read-only historical care after transfer. Keep action-generated draft log distinct from author-signed clinical content in print.
- [ ] Run new module, current IGD integration/finalization/outcomes/hardening modules and affected CPPT legacy tests; later the roadmap's full cross-app gate. Generate/read additive migrations against the latest graph.
- [ ] Handoff `create_care_note` and its source-action uniqueness, note operations, format policy and snapshot contract to C. New features remain disabled/unconfigured until data and assignment approval; no release is implied.
