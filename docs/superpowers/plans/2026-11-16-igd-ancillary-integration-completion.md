# IGD Ancillary Catalogue Integration Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** APPROVED FOR SUBAGENT EXECUTION — queued after medication integration; no operational migration, import or catalogue activation authorized.
**Goal:** Finish the existing four-level ancillary order journey, including preparation fields that the backend accepts but the rendered form cannot currently submit.
**Architecture:** Retain `KategoriPenunjang`, `ItemPenunjang`, `OrderPenunjang`, atomic `order_batch` and assigned-service result worklists. Extend the current basket form and metadata renderer rather than creating another order module or reimporting unchanged reference material.
**Tech Stack:** Existing Django, Bootstrap and vanilla JavaScript; Decimal/billing boundaries remain unchanged.
**Spec:** `../specs/2026-11-16-igd-document-revision-gap-analysis.md`.
**Dependency:** Serialize shared `igd_workflow_views.py`, `_igd_workflow_operations.html` and `igd-clinical-expansion.js` edits after the Step 8 plan and medication controller work. Read the newest files first.

## Global Constraints

- The supplied ancillary DOCX SHA-256 is unchanged: `a42f2b704625b6ff187bce787090909dd3bb0da1c6cfe7b9614c8a6c0433c69f`. Existing source fixture remains authoritative staging; no new parser or duplicate master required.
- Preserve both main categories and all source branches: clinical lab, PA, BDRS, external referral/other; imaging, electrophysiology, endoscopy and nuclear medicine.
- Existing basket supports cross-branch multiple selection and atomic submission. A panel is not automatically decomposed into multiple orders/charges, and selection/send does not mean performed or billed.
- Preserve CITO and manual working indication before all assessment steps are completed. Diagnosis code is selectable when available; do not make a finalized Step 8 diagnosis a prerequisite to Step 7 urgent orders.
- Source wording mentions doctor/nurse use, while current dispatch authorizes physicians to send. Keep the observed physician-submit policy unless explicitly changed; nurse delegation is a review decision, not an implicit permission expansion.
- Existing clinical-result authorization, after-final updates, reasoned corrections, private attachments, audit, version conflicts and request replay remain canonical.
- Do not activate unreviewed example products/services or invent service availability/external destination just to fill the dropdown.

## Review Focus

1. A catalogue requiring `specimen` or `external_destination` has no current UI input for those keys: Task 1 pins the rendered-to-persistence connection.
2. Generic metadata inputs can silently mix specimen site, imaging region and laterality: Task 1 uses canonical per-item field keys and validated choices.
3. Older responses and “next page” state can repopulate children after a parent reset: Task 2 tests controls as well as stale response suppression.
4. A second unlabelled manual form beside the new catalogue looks like two competing workflows: Task 2 makes the fallback explicit without deleting historical/manual order support.
5. Catalogue counts prove extraction, not clinical service readiness or production installation: Task 3 verifies provenance and labels environment-specific evidence separately.

## File Ownership

**Modify:** `templates/pasien/_igd_ancillary_order.html`, `templates/pasien/_igd_workflow_operations.html`, `static/js/igd-clinical-expansion.js`, `pasien/igd_workflow_views.py`, `klinis/services/penunjang_catalogue.py`, `pasien/services/penunjang_orders.py`, `qa/clinical_expansion_browser.py`, `qa/clinical_expansion_browser_race.py`.
**Create:** `pasien/tests_igd_ancillary_completion.py` (proposed).
**Extend tests:** `pasien/tests_clinical_expansion.py`, `pasien/tests_penunjang_results.py`.
**Reuse without recreating:** catalogue models/fixtures/import commands, `pasien/pharmacy_views.py:41–46` catalogue adapter, `pasien/ancillary_views.py`, `pasien/services/penunjang_results.py` and `pasien:igd_penunjang_catalogue` route.
No new model/migration is expected. `preparation` JSON and catalogue schemas already exist.

## Task 1: Connect item-specific preparation metadata end to end

**Files:** Ancillary template/controller, `penunjang_catalogue.py`, `penunjang_orders.py`, proposed test module.
**Consumes:** `item_snapshot()` includes `preparation_schema`/`variants` (`penunjang_catalogue.py:6–19`); `order_batch()` allows `fasting`, `pregnancy`, `contrast_allergy`, `specimen`, `site`, `region`, `side`, `contrast`, `external_destination` (`penunjang_orders.py:25–39`). Current form renders only three status fields, `site` and variants.
**Produces:** Inputs/serialization for the full current backend metadata contract, with required/visible state driven by the selected reviewed item.

- [ ] **RED:** Create the proposed module with the real fixture; include this route-level test before changing markup:

```python
from django.test import override_settings
from django.urls import reverse
from pasien import tests_clinical_expansion as expansion_tests


@override_settings(IGD_WORKFLOW_ENABLED=True)
class AncillaryCompletionTest(expansion_tests.AncillaryTest):
    def test_specimen_and_referral_inputs_are_reachable(self):
        response = self.client.get(
            reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=7'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="anc-specimen"')
        self.assertContains(response, 'id="anc-external-destination"')
```

- [ ] Run `DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien.tests_igd_ancillary_completion --keepdb --noinput`; verify the missing metadata inputs are the actual RED failures.
- [ ] Render specimen, specimen site, imaging region, side/contrast and external-destination controls using the existing canonical keys. Ordinary controls can be present but initially hidden/disabled until relevant to the selected item. Never manufacture arbitrary field names from untrusted JSON. Retain the current source terminology in labels and distinguish `site` from `region`.
- [ ] Add a bounded schema renderer for the known field allowlist. `variants` supplies allowed values; `preparation_schema.required` supplies presence requirements. Unknown keys, non-list required fields or invalid choices are configuration errors, not instructions to add arbitrary DOM or skip validation. Validate this at item resolution as well as submission.
- [ ] Serialize visible/relevant metadata from those controls into the basket row's own `preparation` dictionary. Copy values at add-to-basket time; changing the next item's preparation must not mutate an existing row. Reset stale variant controls before loading a different item/parent.
- [ ] Keep unknown/not assessed distinct from “NO”. An item can explicitly require a determinate response via its reviewed allowed choices; do not universally treat UNKNOWN as either negative or prohibited. Do not turn pregnancy/allergy flags into an undocumented universal hard block. Any additional decision rule needs reviewed policy and a dedicated test.
- [ ] Add positive HTTP/action tests with required specimen and external destination, and negative tests for omitted required metadata, wrong variant, >500-character values, foreign/cancelled diagnosis, inactive ancestor and invalid item type. One bad row rolls back the whole batch and creates no billing/workflow action evidence.
- [ ] **GREEN:** Run the proposed module and `pasien.tests_clinical_expansion`; require exact metadata on `OrderPenunjang.preparation` and the frozen catalogue snapshot, one saved order per selected item, zero charges on order submission.

## Task 2: Consolidate the visible order path and make resets deterministic

**Files:** Ancillary template, workflow operations template/controller and browser/race probes.
**Consumes:** Existing `#igd-ancillary`, `#anc-basket`, `#anc-next-page` and `data-anc-level`; current alternate manual `InvestigationForm` (`_igd_workflow_operations.html:1–4`).
**Produces:** One primary catalogue/basket path and an explicitly labelled manual fallback; stable navigation/pagination for every branch.

- [ ] **RED:** Add a browser case that selects a lower-level page, clears its parent, then attempts “Muat pilihan berikutnya”. Assert no obsolete child list reappears and no stale item can be added. The existing generation-token test alone does not exercise an enabled pagination button after reset.
- [ ] On any parent reset, invalidate in-flight requests, disable/empty all descendants, clear obsolete variant/metadata presentation and reset/hide the pagination owner. “Next page” must be bound to the currently selected parent/generation, not the prior `last` request. Preserve complete basket rows.
- [ ] Keep the four dropdown labels and cross-branch basket; this satisfies the source's multi-selection without replacing the basket with a second checkbox system. Add a visible selected-item path and metadata review/remove affordance, using escaped text.
- [ ] Make the existing free-text order form an explicit “Pemeriksaan manual di luar master” fallback, visually secondary, with the same mandatory clinical indication and authorization. It must not impersonate a reviewed catalogue item or silently inherit a destination. Preserve existing valid route/service behavior rather than deleting a writer as a presentation cleanup.
- [ ] Keep order/result recaps and assigned worklists linked to the existing `OrderPenunjang` records. Do not add another catalogue charge for an EKG also planned/performed via ICD-9; billing remains outside dropdown submission.
- [ ] Test keyboard selection, parent reset, cross-branch basket retention, no-active-item state, 50-item batch boundary, multi-page item access, delayed request, repeated send with the same request ID, and changed-payload/same-key rejection. Verify persisted order IDs and no duplicate orders.
- [ ] **GREEN:** Run the proposed module, `pasien.tests_penunjang_results`, `pasien.tests_laboratorium` and both synthetic browser probes after adapting their fixtures/selectors. Existing probes require generated synthetic auth state and an isolated migrated fixture DB; do not point them at the stale operational SQLite file or fabricate that state in the report.

## Task 3: Reconcile source coverage and prove order → result → diagnosis use

**Files:** Proposed completion tests, result tests, browser probe. The roadmap owns any authorized environment preparation/import.
**Consumes:** Existing `klinis/data/penunjang_catalogue.json` and clinical expansion import/result services; Step 8 recommendation-context contract.
**Produces:** A measured branch-coverage/readiness ledger plus a connected synthetic clinical journey.

- [ ] Parse the fixture in code and reconcile its source/hash and branch inventory. The current staging has 38 taxonomy nodes and 94 example items, not 94 clinically certified services or a final expanded-variant count. Preserve stable codes, existing destinations/reviewers and any transactions; import is not a replacement/upsert-all operation.
- [ ] Build a synthetic reviewable representative for each distinct branch and metadata shape, including external referral, BDRS components/crossmatch, PA specimen, contrast imaging and panels. Assert required metadata and one-panel/one-order semantics. Unavailable services stay visibly unavailable; do not create production rows to make the test pass.
- [ ] Verify CITO manual indication can be sent with no structured diagnosis before Step 8; later select a saved coded diagnosis for a different order. Test unrelated-unit denial and physician-submit policy. Document nurse delegation as unapproved rather than simulating an allowed nurse-send path.
- [ ] Exercise assigned service result recording, critical-value notes and reasoned correction through the existing result boundary. Assert requesting-clinician visibility, nonclinical admin read-only oversight, denial of unrelated service mutation and current after-final/addendum behavior.
- [ ] Return to Step 8: completed results appear in recommendation evidence with provenance; pending orders remain pending, not clinical findings. Finish the episode, mutate live catalogue metadata and verify the original frozen order/result snapshot does not change.
- [ ] Run the final targeted/cross-app gate in the roadmap. Require isolated PostgreSQL same-key batch and conflict scenarios before release, preserving the consistent visit → workflow → domain rows → billing lock order.

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien.tests_igd_ancillary_completion pasien.tests_clinical_expansion pasien.tests_penunjang_results pasien.tests_laboratorium --keepdb --noinput
node --check static/js/igd-clinical-expansion.js
```

## Explicitly Not Included

Do not implement, do not fix while here: LIS/PACS adapters, national procedure import, blood inventory/transfusion administration, external referral contracting, service capacity/scheduling, clinical permission delegation, operational activation, or a new ancillary billing policy. Preserve the existing professional-care/CPPT and physical-examination workstreams.
