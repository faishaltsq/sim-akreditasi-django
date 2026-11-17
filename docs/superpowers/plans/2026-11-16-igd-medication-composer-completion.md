# IGD Medication Composer Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** APPROVED FOR SUBAGENT EXECUTION — queued after Step 8; no operational prescribing, master activation or release authorized.
**Goal:** Complete the revised document's medication planning UX by exposing risk flags at selection, previewing supported quantities and persisting all typed instructions through the existing prescribing lifecycle.
**Architecture:** Reuse `ProdukFarmasi`, `GenerikObat`, formularies, structured prescription lines, safety/PPRA reviews and pharmacy grants. Add one read-only calculation endpoint around the existing Decimal calculator; retain server recalculation on save and the existing draft → submit → dispensing → completion boundary. Do not rebuild pharmacy or create another ledger.
**Tech Stack:** Existing Django, Bootstrap, vanilla JavaScript and Decimal.
**Spec:** `../specs/2026-11-16-igd-document-revision-gap-analysis.md`.
**Dependency:** The Step 8 plan owns container placement and shared controller edits first; this plan then extends the medication branch.

## Global Constraints

- Source hierarchy remains: Obat Jadi / Racikan / BMHP → kelas terapi/kelompok → generik-kekuatan-sediaan/spesifikasi → produk/merek and risk flags.
- Existing medication catalogue, independent product flags, Fornas date/restrictions, quantities, racikan components, safety evaluation, PPRA independent approval and replay-safe dispensing already exist. Preserve them.
- Current staged medication fixture is derived from the **older** DOCX. The revised document changes workflow placement and emphasis, not the medication list. Keep original fixture source/hash; add revision provenance to analysis, not a fake claim that the new file generated the fixture.
- No guessed KFA code, Fornas membership, stock availability, drug-strength/brand pairing or approved policy from illustrative Word rows. No automatic clinical activation or seed replay into an operational DB.
- Known price is Decimal, missing price is unresolved. Preserve `financial_pending` when clinical quantity/price cannot be represented in the financial ledger. No silent rounding or zero-cost substitution.
- Maintain the existing physician, assigned pharmacist/TTK and independent PPRA boundaries. Nonclinical administrative read access is not authorization to prescribe/dispense.

## Review Focus

1. The “PRN / additional instructions” field currently persists only for PRN: Task 1 tests FIXED/INTERVAL instructions from the browser through storage.
2. A quantity preview based on stale product, dose or units can look authoritative: Task 2 invalidates pending responses and recalculates on save.
3. PRN, VARIABLE, racikan and BMHP cannot share the simple tablet formula: Task 2 keeps these explicit manual-quantity branches.
4. A red paragraph is not a usable multidimensional risk display: Task 1 renders labelled badges and Tall Man text without weakening server checks.
5. Empty/unreviewed catalogues or expired Fornas membership must not be “fixed” by activating examples: Task 3 supplies actionable unavailable states and verifies current source/review provenance.

## File Ownership

**Modify:** `templates/pasien/_igd_medication_composer.html`, `templates/pasien/farmasi_antrean.html`, `templates/pasien/igd_workflow_resume.html`, `static/js/igd-clinical-expansion.js`, `pasien/pharmacy_views.py`, `pasien/urls.py`, `pasien/services/prescriptions.py`, `qa/clinical_expansion_browser.py`.
**Create:** `pasien/tests_igd_medication_completion.py` (proposed).
**Extend tests:** `pasien/tests_clinical_expansion.py`, `pasien/tests_clinical_expansion_safety.py`.
**Read/reuse, no planned structural rewrite:** `klinis/expansion_models.py`, `klinis/services/medication_catalogue.py`, `pasien/services/medication_safety.py`, `pasien/services/ppra_review.py`, `klinis/data/medication_catalogue.json`, `klinis/services/catalogue_import.py`.
No new model/migration is required for the planned completion. The roadmap owns conditional migration/import/release, not this component.

## Task 1: Persist complete instructions and expose risk metadata at selection

**Files:** Medication template/controller; proposed tests; browser probe.
**Consumes:** `calculate_quantity()` and structured `regimen` (`prescriptions.py:28–54,98–115`), `product_snapshot()` (`medication_catalogue.py:6–15`), current `rx-prn` input (`_igd_medication_composer.html:22`) and serializer (`igd-clinical-expansion.js:137–148`).
**Produces:** A distinct instruction field persisted under `regimen.instructions`, independent of PRN indication, plus visible risk components before saving.

- [ ] **RED:** Create the proposed module using the existing fixture via a module alias, avoiding accidental direct imports of discoverable test classes:

```python
from django.test import override_settings
from django.urls import reverse
from pasien import tests_clinical_expansion as expansion_tests


@override_settings(IGD_WORKFLOW_ENABLED=True)
class MedicationComposerCompletionTest(expansion_tests.PrescriptionTest):
    def test_composer_has_independent_instruction_control(self):
        response = self.client.get(
            reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=8'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="rx-instructions"')
        self.assertContains(response, 'id="rx-prn"')
```

- [ ] Run `DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien.tests_igd_medication_completion --keepdb --noinput`; pin the missing independent input as the RED result. Inherited methods increase collected totals; do not report them as newly authored behaviors.
- [ ] Add `rx-instructions` with a 2000-character limit for instructions for all medication regimens. Relabel `rx-prn` specifically as PRN indication; serialize the two fields separately. Existing regimen allowlists already accept `instructions`, so do not invent a second note store or silently truncate it into `aturan_pakai` alone.
- [ ] Include full instructions in draft line review and persisted recap. Extend `templates/pasien/_igd_medication_composer.html:35–43`, `templates/pasien/farmasi_antrean.html:31,280–286` and `templates/pasien/igd_workflow_resume.html:17` to render the stored `regimen.instructions` separately from generated/truncated legacy `aturan_pakai`. Pin the medication, PPRA/pharmacy and frozen-print consumers with render tests. Never read live master instructions into a signed snapshot.
- [ ] Replace the single `rx-product-info` concatenated sentence with scoped text plus risk badge elements for LASA, HIGH_ALERT, OOT, NARKOTIKA, PSIKOTROPIKA and PPRA. Render `tall_man_label` when supplied. Use `textContent`/Django escaping, not product HTML. No-flags copy means “Tidak ada flag terdaftar”, not a universal safety verdict.
- [ ] On product/kind/formulary change, clear displayed prior risk/routes/price before awaiting the new response; do not clear an already-added prescription basket. For racikan, retain each component's frozen data and the existing combined risk behavior.
- [ ] Extend the real browser journey: enter FIXED and INTERVAL instructions using sequential typing, add/save, reload and verify `regimen.instructions` via a synthetic readback; repeat a second save. Test PRN storing both indication and instructions. Retain BMHP's no-drug-signa behavior.
- [ ] **GREEN:** Run the proposed module and both existing expansion modules, then the browser cases. Require correct readback and unchanged no-billing-on-draft behavior, not only input presence.

## Task 2: Add a server-authoritative quantity preview

**Files:** `prescriptions.py`, `pharmacy_views.py`, `urls.py`, medication template/controller and proposed tests.
**Consumes:** `decimal_value()`, `calculate_quantity()` and `product_snapshot()`. Final authority remains `save_prescription()`.
**Produces, proposed:** `preview_prescription_quantity(actor, visit, line) -> dict`; route `pasien:igd_medication_quantity`, path `kunjungan/<int:pk>/asesmen-igd/resep/pratinjau-jumlah/`, POST JSON. It is read-only in business state despite using POST to avoid putting regimen content in URLs/logs.

- [ ] **RED:** Add HTTP tests for a verified tablet product with two doses/day × half tablet × three days returning exact string `3` and its dispense unit; record recipe/workflow/billing/audit counts before/after and assert no writes. Confirm route registration plus this successful case before negative tests, so a missing handler cannot falsely pass.
- [ ] Add negative tests: nurse/assessor/nonclinical admin, cross-unit visit, inactive/unreviewed product, invalid parent kind, NaN/Infinity/bool/negative/zero values, overflow and unsupported precision. Verify 403/400 according to the responsible boundary and no mutation. Test absent conversion separately as a successful response requiring manual quantity, not a guessed estimate or validation error. Keep out-of-scope visibility unchanged.
- [ ] Implement the helper through the existing calculator and active reviewed product snapshot. Validate a narrow payload (`product_id`, `kind`, `regimen`) and product-kind compatibility; require prescriber plus authorized episode access in the view, `@login_required`, `@require_POST`, `@never_cache`, CSRF and the existing bounded JSON parser. Do not trust browser unit/conversion/price data. Format supported Decimal quantities as fixed-point strings with insignificant trailing zeros removed, never scientific notation, so the exact response example below is reproducible.
- [ ] Preserve the response contract as strings/null with explicit manual state, for example:

```json
{
  "success": true,
  "estimated_quantity": "3",
  "unit": "tablet",
  "requires_manual_quantity": false,
  "reason": "Kalkulasi berdasarkan aturan pakai dan konversi master."
}
```

  For PRN/VARIABLE/racikan/BMHP/unknown conversion, return null estimate with `requires_manual_quantity=true` and a specific explanation. Racikan quantity uses its final unit (`bungkus`/`kapsul`/`pot`); never label the parent component tablet estimate as the finished preparation.
- [ ] Add a debounced preview on relevant changes and explicit status label “Estimasi jumlah — dihitung ulang saat simpan”. Bind results to a generation token including product, kind and regimen. Ignore delayed responses after edits. Never overwrite an entered manual quantity; show reference estimate beside it and continue requiring a reason for adjustment.
- [ ] Do not change final validation to trust this endpoint: `save_prescription()` recalculates using fresh master data inside the existing dispatcher. Test a conversion change after preview; stale display does not bypass actual save validation.
- [ ] **GREEN:** Run the proposed module, `QuantityTest`, `PrescriptionTest` and `ExpansionSafetyTest` through the concrete modules listed below; verify `OK`, exit 0 and no extra charge on preview/save/retry.

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien.tests_igd_medication_completion pasien.tests_clinical_expansion pasien.tests_clinical_expansion_safety --keepdb --noinput
node --check static/js/igd-clinical-expansion.js
```

## Task 3: Reconcile catalogue readiness and prove the whole retained lifecycle

**Files:** Medication template/controller, proposed/expansion safety tests and browser probe. No catalogue JSON rewrite is assumed.
**Consumes:** Existing inactive DOCX staging, reviewed-product queries, Fornas membership, `PharmacyServiceGrant`, `review_risks()` and `transition_prescription()`.
**Produces:** Accurate configured/unavailable states and new UX evidence connected to existing prescription and financial records.

- [ ] Test no active product, no matching Fornas product and no configured dispensing depo. Display the responsible unavailable state without offering a free-text bypass that sends an unreviewed medication. Manual diagnosis/action remains usable. Use existing authorized admin review/configuration screens, not invented provisioning links.
- [ ] Characterize reviewed normal/racikan/BMHP fixtures and expired Fornas membership; preserve strict rejection at save, not just filtering. Do not classify every antibiotic or a document's illustrative flag as an approved hospital rule.
- [ ] Verify prescription draft → safety review → PPRA hold where configured → independent approved decision → explicit resubmit → assigned pharmacy dispensing → completion. Changing ingredient/strength/flags/allergy/policy invalidates old reviews. Assert exactly one owned charge after replay and `financial_pending` for unpriced/nonrepresentable quantities.
- [ ] Verify new instructions and risk text in the frozen final snapshot/print after changing live product labels/flags; old revisions without them display unavailable historic metadata, never current values. Keep patient identities out of evidence exports.
- [ ] Browser at 375/768/1366 px: keyboard cascading, parent reset, stale response suppression, Tall Man/badges before save, exact preview/manual override, FIXED/PRN instructions, draft reload and reachable Step 9. Assert no horizontal overflow/page errors or clinical information in local/session storage.
- [ ] Run the complete cross-app gate in the roadmap and the authorized isolated PostgreSQL scenarios before a release claim. Current tests prove local contracts; current staging count and historical evidence are not proof of clinical activation/deployed configuration.

## Explicitly Not Included

Do not implement, do not fix while here: inventory/stock/procurement, medication administration records, a national-drug importer without a reviewed source, changing Fornas/PPRA policy, unrestricted pharmacy access, financial reconciliation policy for compounds, outbound SATUSEHAT/BPJS/LIS integrations, or operational catalogue activation. Any requested development/demo activation needs its own explicit environment authorization and readback.
