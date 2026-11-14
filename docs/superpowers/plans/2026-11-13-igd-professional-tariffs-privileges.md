# IGD Professional Tariffs and Privileges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` or `subagent-driven-development` after approval. Execute RED → GREEN with checkbox tracking; do not mutate production reference data or shared files without handoff.

**Status:** PLANNED — component A.
**Goal:** Resolve a genuinely eligible professional performer and an approved, effective component price for an IGD service.
**Architecture:** Reuse HC profession/grade/employee/SPK data; add reviewed service-to-RKK mappings and versioned tariffs rather than another staff directory. Implement a purpose-scoped clinical adapter so patient-care access does not require unrestricted HR-directory permissions.
**Tech Stack:** Existing Django, Decimal and database constraints; no provider/SDK dependency.
**Spec:** `../specs/2026-11-13-igd-professional-care-cppt-analysis.md`, PC02–PC04, PC13.
**Orchestration:** `2026-11-13-igd-professional-care-roadmap.md` owns global constraints, handoff, sequencing and release.

## Global Constraints

- All roadmap constraints apply. `Pegawai.jenjang_master` already exists in source and production; do not add a replacement grade column.
- Grades bind to their actual profession, not an approximate source-document label or numeric ranking across professions.
- Individual effective SPK/privilege is required for clinical services; a default catalogue supervision label is not an issued grant. Revalidate active source decision, unit, time and exact mapped service.
- Self-performance is the default. Other-performer recording and tariff management are separate scoped grants; neither gives clinical privileges.
- Missing mapping, multiple eligible prices or unknown grade is a visible configuration error. Do not pick `.first()` as a financial or clinical policy.
- Quoting does not execute a service, bill or grant authority. Exact context/version must be revalidated at execution.
- Zero is valid only when explicitly approved as free. Never populate prices from the example DOCX; amounts in tests are synthetic fixtures.

## Review Focus

1. Same procedure code has two grade/unit/payor prices — quote binds exact context and preserves future/expired versions.
2. HC profession and account profile disagree or employee grade is missing — no invented fallback authority.
3. Supervisor lacks the specific independent privilege — matching senior title alone does not authorize supervision.
4. A revoked/expired source SPK still has a snapshot row — eligibility checks the live source and effective date.
5. No configuration exists in production — UI/API explain missing setup without exposing HR identifiers or enabling a bypass.

## File inventory

**Create:** `klinis/professional_care_models.py`, `klinis/services/professional_tariffs.py`, `sdm/services/professional_care.py`, `pasien/tests_professional_care_context.py`, `klinis/tests/test_professional_tariffs.py`.
**Modify after handoff:** `klinis/models.py` (registration imports), `klinis/admin.py` or existing app admin registration owner, `pasien/igd_workflow_views.py`, `pasien/urls.py`, `config/settings.py`; additive migrations generated at execution.
**Reuse without redesign:** `sdm/models/pegawai.py`, `sdm/models/katalog_rkk.py`, `sdm/models/kredensial.py`, `sdm/models/clinical_access.py`, `sdm/services/clinical_access.py`.

All names below are **proposed**, not existing symbols.

## Task A1: Reviewed service mapping and price versions

**Produces:**
- `LayananProfesional`: immutable stable local `code`, reviewed `name`, `group` (MEDICAL/NURSING/OTHER_PPA), `authority_kind` (CLINICAL/SUPPORT), optional protected ICD9 or SIKI reference, `source_version`, `reviewed_by`, `reviewed_at`, and `is_active`. No fabricated ICD9 for counselling/spiritual services.
- `PemetaanKewenanganLayanan`: protected service FK + existing `KatalogTindakan` FK, reviewed source/reviewer/time and active state; unique service/catalogue binding. An RKK code is not an ICD code.
- `TarifLayananProfesi`: protected service, unit, profession and grade; payor; effective dates; Decimal(12,2) `jasa_sarana` and `jasa_pelayanan`; explicit `is_free`; review state/version/source. Validate grade's profession and nonnegative finite amounts. Zero total requires explicit reviewed free status.
- `ProfessionalCareGrant`: user/unit/capability binding for MANAGE_TARIFF, RECORD_FOR_OTHER, VOID_UNPAID_CHARGE and approved SUPPORT_SERVICE, with validity and grant audit. Default grants empty, no automatic clinical role escalation.
- Pure `price_breakdown(sarana, pelayanan, quantity) -> dict` returning Decimal unit and total values; quantity respects existing Decimal(8,2) constraints and derived totals fit financial fields.

- [ ] RED: add arithmetic and invalid-value tests before model/service implementation.

```python
from decimal import Decimal
from django.test import SimpleTestCase

class ProfessionalPriceTest(SimpleTestCase):
    def test_source_example_is_a_component_sum(self):
        from klinis.services.professional_tariffs import price_breakdown
        result = price_breakdown(Decimal('50000'), Decimal('150000'), Decimal('1'))
        self.assertEqual(result['unit_total'], Decimal('200000'))
        self.assertEqual(result['subtotal'], Decimal('200000'))
```

Run `manage.py test klinis.tests.test_professional_tariffs --keepdb --noinput`; require RED on the missing proposed contract, then GREEN after implementation.
- [ ] Implement model validation and additive constraints; reject profession/grade mismatch, negative/NaN/Infinity, invalid date windows and out-of-range quantities. Under a locked service/unit/payor/profession/grade key reject overlapping approved effective intervals; a database strategy must also handle concurrent approval, not validation alone.
- [ ] Serialize tariff approval by locking the common reviewed service row, including when no price row exists yet; add a unique context/version key and database nonnegative/date constraints. Quote/execute locks the same service before the selected price. Test concurrent first approvals rather than relying on an unlocked `.exists()` check. Resolve date-effective prices/privileges using the business date in Asia/Jakarta, not a UTC date obtained by slicing an ISO string.
- [ ] Add tests for explicit free versus unpriced, date-boundary inclusivity, overlapping concurrent versions, inactive sources and price precision/overflow. Record exact collected counts, not estimated totals.
- [ ] Register purpose-scoped admin/import preview for reviewed configuration. Creating/approving prices requires MANAGE_TARIFF in the unit; editing an approved version creates a new version, never rewrites a price already referenced by care.
- [ ] Generate/read migrations after the active workstream's migration graph is settled. Do not assign a migration number in this plan or seed operational rows automatically.

## Task A2: Eligible performer and supervision adapter

**Produces:** `resolve_professional_context(actor, visit, service, *, at, performer=None, supervisor=None, for_update=False) -> dict` in `sdm/services/professional_care.py`; `eligible_performers(actor, visit, service, *, at) -> list[dict]` for minimal scoped autocomplete. `for_update=True` requires the caller's existing transaction and locks the authority rows used for mutation; GET previews use false and create nothing.

Context contains actor/performer employee+account references, profession/grade labels and IDs, mapped service/RKK code, unit, supervision condition, source SPK/privilege IDs/validity, recorded-versus-performed intent and source version. Do not return private HR documents, identifiers or unrestricted employee listings.

- [ ] RED: use existing `IgdWorkflowTest` fixture for an account without HC linkage. That test user is clinically labelled but has no issued SPK, which must not pass strict professional execution.

```python
from django.core.exceptions import PermissionDenied
from pasien.tests_igd_workflow import IgdWorkflowTest

class ProfessionalContextTest(IgdWorkflowTest):
    def test_profile_title_does_not_replace_verified_employee(self):
        from sdm.services.professional_care import resolve_professional_context
        from klinis.models import LayananProfesional
        from django.utils import timezone
        service = LayananProfesional.objects.create(
            code='QA.NO-HC', name='Layanan fixture', group='MEDICAL', authority_kind='CLINICAL',
            is_active=True, source_version='qa-fixture', reviewed_by=self.user, reviewed_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            resolve_professional_context(self.user, self.visit, service, at=timezone.now())
```

Run `manage.py test pasien.tests_professional_care_context --keepdb --noinput`; RED must reflect missing eligibility enforcement/API, not fixture misconfiguration.
- [ ] Add positive fixtures using actual `Pegawai`, `MasterProfesiPegawai`, `MasterJenjangProfesi`, `KatalogTindakan`, `PengajuanKredensial`, `KeputusanKredensial`, `PenugasanKlinis`, individual privilege lines and reviewed mappings. Use source `MANUAL` with synthetic test identity, valid unit/dates and explicit approved per-procedure status; do not invent credentials in production.
- [ ] Validate active account/employee, grade/profession lineage, episode unit/time, reviewed source and individual mandate. Generic `ClinicalActionCode` permission is necessary where used but not sufficient for every procedure. Do not call `require_clinical_action` unchanged if it would force a nutritionist to gain HR-directory access.
- [ ] For M/S/MT: accept independent only with the actual grant; require explicit eligible nonself supervisor for supervision; enforce documented limits for MT. Reject catalogue T/denied, expired or revoked source, unsupported/ambiguous mapping and trainee self-supervision.
- [ ] Bind posted performer to actor by default; RECORD_FOR_OTHER only permits audited delegated recording, not falsified authority. Revalidate performer and supervisor, save both identities separately, and test another-unit or inactive employee IDs supplied directly through JSON.
- [ ] SUPPORT services such as rohani use a reviewed service assignment/competency policy, not automatic medical privileges. If the source master/policy is absent, return configured unavailable state. Do not classify religion as a clinical grade.
- [ ] Add deny/allow matrix for dentists, nurses/bidan, nutrition, pharmacy, rehab, diagnostic PPA and support roles according to reviewed mapping; unsupported source labels remain unmapped. Do not widen unrelated prescribe/finalize rights.

## Task A3: Quote and scoped lookup contract

**Produces:** `quote_professional_service(visit, context, service, *, at, quantity=Decimal('1'), for_update=False) -> dict` with service/price IDs, price version, quantity, payor/unit/profession/grade, sarana/pelayanan/unit/subtotal, explicit free/unpriced status and fingerprint. Import Decimal at module level. Mutation mode locks the common service/price key in the caller's transaction; preview mode is read-only. Preserve `resolve_detail(kunjungan, icd9_kode)` as a legacy contract, not a competing new-price resolver.

- [ ] RED: a mocked/fixture context selecting a different grade, expired price or changed payor must not receive the previous quote. More than one matching approved row is an error. Tariff rows absent return UNPRICED, not numeric zero.
- [ ] GREEN: query exact effective context, return bounded minimal catalogue/employee lookup results and quote. Quote fingerprint binds request context and source versions; execution must compare the client-held fingerprint with a freshly locked/revalidated context, not two freshly loaded identical values.
- [ ] Add GET-only scoped lookup/quote views after source handoff. Route names: proposed `igd_professional_catalogue` and `igd_professional_quote`, under the existing visit prefix; required query arguments are service, profession/grade filters and intended actual time, with performer/supervisor only when policy permits. GET creates no workflow or assignments.
- [ ] Add `IGD_PROFESSIONAL_CARE_ENABLED` default false and explicit unavailable response/UI context. Gate off must retain historical reads and existing clinical behavior; no claim that old mode enforces new RKK policy.
- [ ] Test scope, stale/forged dependencies, no writes on GET, search pagination, empty coverage guidance, actor self restriction and permission-separated tariff administration.

## Acceptance and handoff

- [ ] Run both new modules, `klinis.tests.test_tarif_service`, affected HC privilege tests and existing IGD integration tests. New lookup paths need HTTP assertions, not helper-only coverage.
- [ ] PostgreSQL: competing tariff approval and SPK revocation versus execution use a documented consistent lock/revalidation strategy; do not certify with SQLite.
- [ ] Handoff model/permission/lookup/quote interfaces and explicit unconfigured states to B/C. No operational data or feature activation is part of completing this component's source implementation.
