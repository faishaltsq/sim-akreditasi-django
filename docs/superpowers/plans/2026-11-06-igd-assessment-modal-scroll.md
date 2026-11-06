# IGD Assessment Modal Scroll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the complete seven-tab IGD assessment scrollable, including its final physical-examination fields and save controls.

**Architecture:** Retain the existing modal, seven tabs, save endpoint and JSON persistence. Move the form boundary onto `.modal-content` so Bootstrap's existing scrollable-dialog flex layout owns height and overflow; do not introduce a second scroll controller or replace this form with the four-tab assessment page.

**Tech Stack:** Django templates, Bootstrap 5.3, existing Django tests, browser DOM measurements.

**Spec:** `C:/Users/cubeb/Downloads/Perbaikan dan urutan menunya pemeriksaan fisik lengkap.docx` (text and all three embedded screenshots inspected).

## Global Constraints

- Preserve all existing dirty/untracked work; no commit, push, deployment or database changes without separate authorization.
- Keep the existing seven-tab order. The attachment names no replacement order.
- Preserve `pasien:igd_asesmen_medis_save`, POST names, CSRF, patient-specific modal IDs, secondary-survey JSON and printed-document behavior.
- This extends decision D4 of `2026-11-05-asesmen-awal-igd-layanan-unit-dan-kunjungan.md`; it does not supersede or recreate the four-tab full-page implementation.
- No new dependency, model, migration, service or shared-modal redesign.

## Verified Evidence and Root Cause

The attachment shows `/pasien/igd/`, the seven-tab modal and tab 6 clipped below its first examination cards. Local source matches that surface: `templates/pasien/igd_dashboard.html:1255-1266` has `.modal-dialog.modal-dialog-scrollable > .modal-content > form > .modal-body`. The header is outside the form; the footer is inside it at lines 2280-2284. The intermediate unbounded form interrupts Bootstrap's constrained flex chain. Structural cause is established from code; live browser reproduction is still required before implementation.

The data already exists: `pasien/models.py:475` stores `secondary_survey_detail`; `pasien/views.py:2235` owns the save endpoint and its secondary-survey assignments. Existing persistence tests live in `pasien/tests_revisi_diagnosa_picker.py` and `pasien/tests_revisi_asesmen_medis_igd.py`.

## Review Focus

- Short viewport: last secondary-survey field and save button remain reachable.
- Different patients: opening one modal does not affect another patient's fields.
- Tabs wrapping: all seven remain visible/reachable without horizontal page overflow.
- Keyboard: dialog focus, tab navigation, close and save remain operable.
- Persistence: unchanged field names reach the existing endpoint and reload correctly.

## Task 1: Restore Bootstrap's scroll ownership

**Files:** Modify `templates/pasien/igd_dashboard.html` only for the seven-tab assessment modal; extend `pasien/tests_asesmen_awal_ux.py` using its existing authenticated IGD fixtures.

**Interfaces:** Existing `modalAsesmenAwal{{ k.pk }}`, `asesmenTab{{ k.pk }}`, `tabSecondary{{ k.pk }}`, `pasien:igd_asesmen_medis_save` remain unchanged.

- [ ] Reproduce on an authorized local/test environment at 1366x768 and 1920x1080. Open the actual Asesmen button, activate tab 6, record modal/body/footer bounding rectangles and body scrollHeight/clientHeight. Do not create production patients or submit live clinical changes.
- [ ] Add a regression test rendering the dashboard with the existing fixture. Parse the specific modal using Python's `html.parser.HTMLParser` (stdlib): assert exactly one form, its class includes `modal-content`, and header/body/footer are direct children of that form. Assert CSRF and existing action URL, seven tab targets and submit button remain present. Run the new test and establish failure on the current nesting.
- [ ] Replace the assessment modal's opening `.modal-content` div with the form below, remove the old inner form opening, and move the CSRF token immediately inside the outer form. Keep header/body/footer markup and content in place; replace the old two closing form/content tags with one closing form.

```html
<form class="modal-content" method="post" action="{% url 'pasien:igd_asesmen_medis_save' k.pk %}">
    {% csrf_token %}
```

- [ ] Add a patient-specific title ID and `aria-labelledby` on this dialog; give its close button `aria-label="Tutup"`. Preserve Bootstrap dismissal and focus behavior. Add regression assertions for these relationships.
- [ ] Run the existing secondary-survey persistence suites and the updated UX suite. Do not change expectations about clinical data to make a layout fix pass.

```bash
.venv/Scripts/python.exe manage.py test pasien.tests_asesmen_awal_ux pasien.tests_revisi_diagnosa_picker pasien.tests_revisi_asesmen_medis_igd --keepdb -v 1
```

Expected: exit code 0, no failed tests.

## Task 2: Verify the rendered journey

**Files:** No application file required unless Task 1's measured behavior fails; keep temporary browser probes in Hermes scratch.

- [ ] At both target viewport sizes, open Asesmen via dashboard, activate tab 6 and scroll its body to the end. Assert the final field is visible, footer lies inside viewport, dialog does not exceed viewport and document has no horizontal overflow.
- [ ] Switch through all seven tabs and reopen a second patient's modal. Verify identity and patient-specific values do not cross over.
- [ ] Verify keyboard entry/close/focus return and reachable save control; check browser console for new errors.
- [ ] In an isolated test database only, save distinctive secondary-survey values and confirm the correct patient's values reload. Do not issue real clinical writes.
- [ ] Check the previous full-page four-tab assessment still has reachable footer and working tab navigation.
- [ ] Record viewport measurements, commands and results in this document. If browser authentication is unavailable, report that blocker explicitly instead of declaring UI acceptance complete.

## Explicitly NOT in This Plan

Do not implement, do not fix while here: reordering clinical tabs without a supplied sequence; merging four- and seven-tab forms; rewriting other modal structures; unrelated authorization or clinical-validation redesign; full regression failures handled by the separate regression-completion plan.

## Acceptance and Rollback

Done requires passing targeted tests and measured browser evidence for both viewports, keyboard and isolated persistence. Rollback is a targeted reversal of this modal's markup and its new tests; no schema/data rollback is required. Preserve all unrelated working-tree changes.
