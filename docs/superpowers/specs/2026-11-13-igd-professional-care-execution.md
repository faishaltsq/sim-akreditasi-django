# Professional care execution ledger

**Date:** 2026-11-13.
**Status:** DELIVERED & LOCALLY VERIFIED (production activation remains gated).
**Workspace:** `C:/Users/cubeb/OneDrive/Documents/coding/arima-igd-professional-care-isolated`.
**Base manifest:** `isolated-base-manifest.json`, 1767 source/static/reference paths captured from dirty base.
**Production authorization:** No commit/push/deploy or production DB writes.

---

## 1. Delivered components (A -> B -> C)

| Component | Delivered behavior | Proof / Gate |
|---|---|---|
| **A: Tariffs & Privileges** | Reused existing HC `Pegawai.jenjang_master`, `PrivilegeSnapshot`, `PenugasanKlinis`, and `RincianKewenangan`. Multi-grade `TarifLayananProfesi` (sarana + pelayanan, `ROUND_HALF_UP`, effective periods, explicit pending vs approved-free). Individual limits enforced via `BatasanKewenanganProfesional` digest against mandate text. Supervised trainee delegation requiring counter-signature. Same-day withdrawal via nullable `PrivilegeSnapshot.revoked_at`. | `tests_professional_tariffs.py`, `tests_professional_care_context.py`, `tests_professional_configuration.py`, PostgreSQL racing tariff approvals. |
| **B: Multiprofessional CPPT** | Structured SOAP, ADIME, and spiritual note schema. Draft saving, immutable author sign, reasoned corrections with parent revision lineage, and strict assigned-DPJP verification. Verification snapshot locks DPJP assignment metadata (`doctor_id`, `unit_id`, `valid_from`, `valid_until`, `source_version`). Read-only evidence admin, account-bound assignment admin. Legacy CPPT reads nonmutating snapshot. | `tests_professional_cppt.py`, `tests_professional_hardening.py`, `tests_professional_snapshots.py`, synthetic browser journey with format draft preservation. |
| **C: Care Execution & Billing** | Replay-safe execution dispatcher with atomic direct and planned conversion. One execution -> one performed action -> one draft CPPT -> one posted billing item. `BillingItem.sumber = 'PROFESI'` prevents legacy `sync_billing` deletion. Independent void authorization (`ProfessionalCareGrant.capability = 'VOID_UNPAID_CHARGE'`) creates immutable `PembatalanTagihan` audit record. Financial summary (gross, voided, net, category) and plan cancellation in Step 9 panel. | `tests_professional_execution.py`, `tests_professional_billing.py`, `tests_professional_http.py`, `tests_professional_concurrency.py`, browser network abort & replay test. |

---

## 2. Verification evidence

- **Full suite regression (`proc_455e908d7267`):**
  - Command: `DATABASE_URL='' DJANGO_DEBUG=true PYTHONIOENCODING=utf-8 manage.py test pasien klinis accounts sdm.tests.test_clinical_access --keepdb --noinput`
  - Result: **627 tests passed in 297.200s, OK (skipped=5), exit code 0**.
  - Log: `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/professional-full-regression.log`.
- **Source-attributed regression gate (`proc_0898679a5561`):**
  - Command: `python qa/professional_regression_gate.py`
  - Result: **940 monitored source files, 0 changed during run (`changed_during_run: []`), exit code 0**.
  - Manifest: `docs/superpowers/evidence/igd-professional-care/full-regression-source.json`.
- **True PostgreSQL 17 concurrency race suite:**
  - Tested on isolated Docker container `arima-professional-qa` (`postgres:17-alpine`, port 15482) via `config.professional_qa_settings`.
  - Scenarios:
    1. Double-execute with identical idempotency key -> second returns replayed true without duplicating action/charge/CPPT.
    2. Two competing idempotency keys claiming the same planned line -> exactly one succeeds, second fails with conflict.
    3. Competing concurrent first-tariff approvals -> database lock serializes; no duplicate active tariffs.
    4. Two concurrent void requests on same charge -> first marks void, second safely replays.
    5. Same-day privilege revocation concurrent with care execution -> execution rejected once revocation commits.
  - Result: **Exit code 0 (`professional-postgres-final.log`)**.
- **PostgreSQL Row Level Security (RLS):**
  - Migrations `klinis.0006_professional_configuration_rls` and `pasien.0032_professional_evidence_rls`.
  - Tables protected: `LayananProfesional`, `PemetaanKewenanganLayanan`, `ProfessionalCareGrant`, `TarifLayananProfesi`, `BatasanKewenanganProfesional`, `CpptRevision`, `PenugasanDpjpEpisode`, `VerifikasiCppt`, `PembatalanTagihan`.
  - Verified via `tests_professional_rls.py`: `relrowsecurity = true` on all tables, reader role cannot bypass signed CPPT notes.
- **End-to-end browser journey & layout verification:**
  - Synthetic test runner: `qa/professional_browser_probe.py` using Chromium via Playwright.
  - Viewports: **375px (mobile), 768px (tablet), 1366px (desktop)**.
  - Form layout: 0 horizontal overflow across all viewports.
  - Journey tested:
    1. Planned action preview in Step 8.
    2. Format draft switching (SOAP, ADIME) preserving memory drafts.
    3. Tariff preview for unpriced vs free-approved vs standard priced services.
    4. Delayed catalogue reset resilience.
    5. Action execution with network response abort -> client retries with identical key -> idempotent replay (200 OK, `replayed: true`).
    6. Complete and save CPPT draft -> sign CPPT -> DPJP counter-verification.
    7. Scoped void of unpaid professional billing item.
    8. Section signing and final assessment document generation.
  - Result: **0 page errors, all assertions passed, exit code 0**.
  - Evidence: `docs/superpowers/evidence/igd-professional-care/final-browser/browser.json` and 9 PNG screenshots.
- **Static assets verification:**
  - `static/js/igd-professional-execution.js` & `static/js/igd-professional-cppt.js`.
  - Byte equality verified across source, collected static, hashed static, and `.gz` decompressed.
  - Manifest recorded in `docs/superpowers/evidence/igd-professional-care/schema-and-assets.json`.
- **System checks:**
  - `manage.py check`: 0 issues (1 silenced).
  - `manage.py makemigrations --check --dry-run`: No changes detected.
  - Node JS syntax: `node --check static/js/igd-professional-execution.js` & `node --check static/js/igd-professional-cppt.js` passed.

---

## 3. Schema migrations generated

1. `accounts/0009_dental_professional_identity.py` (AlterField UserProfile.profesi adds DOKTER_GIGI)
2. `klinis/0004_professional_care.py` (CreateModel LayananProfesional, PemetaanKewenanganLayanan, ProfessionalCareGrant, TarifLayananProfesi)
3. `klinis/0005_reviewed_individual_limits.py` (CreateModel BatasanKewenanganProfesional)
4. `klinis/0006_professional_configuration_rls.py` (RunPython RLS enable & revoke public/anon/authenticated)
5. `pasien/0028_professional_cppt.py` (AddField CPPT metadata, CreateModel CpptRevision, PenugasanDpjpEpisode, VerifikasiCppt, AddConstraints)
6. `pasien/0029_professional_execution.py` (AddField BillingItem & TindakanAsesmen, CreateModel PembatalanTagihan)
7. `pasien/0030_professional_billing_source.py` (AlterField BillingItem.sumber adds PROFESI)
8. `pasien/0031_professional_verification_evidence.py` (AddField VerifikasiCppt.verifier_name & assignment_snapshot, AlterField CPPT.nama_ppa max_length=200)
9. `pasien/0032_professional_evidence_rls.py` (RunPython RLS enable & revoke public/anon/authenticated)
10. `sdm/0067_privilege_revocation_timestamp.py` (AddField PrivilegeSnapshot.revoked_at)

---

## 4. Integration readiness & changed path manifest

Source modifications are strictly confined to `arima-igd-professional-care-isolated`. All modified shared files apply cleanly on top of `sim-akreditasi-django`:

```
Changed existing files (16):
  accounts/models.py
  config/settings.py
  klinis/admin.py
  klinis/models.py
  pasien/admin.py
  pasien/igd_workflow_views.py
  pasien/models.py
  pasien/services/igd_actions.py
  pasien/services/igd_assessment_workflow.py
  pasien/services/igd_finalization.py
  pasien/urls.py
  pasien/views.py
  sdm/models/clinical_access.py
  sdm/services/clinical_access.py
  templates/pasien/igd_workflow.html
  templates/pasien/igd_workflow_resume.html

New modules & files:
  klinis/professional_care_models.py
  klinis/services/professional_tariffs.py
  klinis/professional_admin.py
  klinis/tests/test_professional_tariffs.py
  sdm/services/professional_care.py
  sdm/professional_policy.py
  pasien/professional_care_models.py
  pasien/services/professional_cppt.py
  pasien/services/professional_billing.py
  pasien/services/professional_execution.py
  pasien/services/professional_presentation.py
  pasien/professional_views.py
  pasien/professional_admin.py
  pasien/professional_test_support.py
  pasien/tests_professional_care_context.py
  pasien/tests_professional_cppt.py
  pasien/tests_professional_execution.py
  pasien/tests_professional_billing.py
  pasien/tests_professional_hardening.py
  pasien/tests_professional_http.py
  pasien/tests_professional_concurrency.py
  pasien/tests_professional_configuration.py
  pasien/tests_professional_rls.py
  pasien/tests_professional_snapshots.py
  templates/pasien/_igd_professional_execution.html
  templates/pasien/_igd_professional_cppt.html
  static/js/igd-professional-execution.js
  static/js/igd-professional-cppt.js
```
