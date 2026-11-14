# IGD Care Execution and Billing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` or `subagent-driven-development` after approval and A/B handoff. Execute RED → GREEN; no operational charge/void or shared-file overwrite is authorized by this plan alone.

**Status:** PLANNED — component C, depends on A+B and the pharmacy/ancillary ownership contracts.
**Goal:** Execute reviewed planned/direct professional care once, create a factual draft CPPT and one attributable charge, then render consistent actual-versus-estimated billing with auditable unpaid-charge voids.
**Architecture:** Extend `TindakanAsesmen`, `BillingItem` and the existing action dispatcher. Consume A's verified actor/quote and B's draft-note writer in the original transaction. Medication and diagnostic charges remain owned by their existing domains, not a second ledger.
**Tech Stack:** Django, Decimal, PostgreSQL row locks/constraints, existing Bootstrap/JS.
**Spec:** `../specs/2026-11-13-igd-professional-care-cppt-analysis.md`, PC01, PC03–PC07, PC12–PC14.
**Orchestration:** `2026-11-13-igd-professional-care-roadmap.md`.

## Global Constraints

- All roadmap/A/B constraints apply. No bill on planning, preview, navigation or CPPT narrative save.
- Self-performance default; delegated recorder and supervisor require explicit scoped grants and separate identity snapshots.
- Reuse existing caller-held workflow version and UUID request/digest. All mutations validate authorization before replay response.
- Revalidate current performer/privilege/payor/price context against the displayed quote; never trust posted nominal, grade, display name or an already-stale eligibility dropdown.
- Preserve source action, CPPT and billing links. The single planned action may be performed only once; repeated services require distinct reviewed plans/events, not secretly replaying the same plan.
- Unpriced care is not free. Record actual care with FINANCIAL_PENDING if policy permits, no fabricated zero charge; approved zero creates a linked zero-amount ledger item with explicit free provenance.
- New professional scope cannot execute/void MANUAL, pharmacy or ancillary charge ownership through this handler.
- Performed-care history is not deleted by the UI's source-document “Hapus”. Void is an explicit full correction of an eligible unpaid charge; payment refund and partial credit remain outside this component.

## Review Focus

1. Two different request IDs execute the same planned action — one performance/CPPT/charge, enforced under the shared visit lock and ownership constraints.
2. Price/grade/payor changed after preview — explicit 409/refresh, never silently charge a different amount.
3. Manual tariff/missing price/approved free — three distinct states; admin price permission is not a clinical performance permission.
4. Pharmacy/order row already billed — summary can read it but never creates another charge or claims medication administration.
5. Void changes one screen but not discharge/PDF/recap totals — every consumer must use the same net/gross contract before the void feature is enabled.

## File inventory

**Create:** `pasien/services/professional_execution.py`, `pasien/services/professional_billing.py`, `pasien/tests_professional_execution.py`, `pasien/tests_professional_billing.py`, `templates/pasien/_igd_professional_execution.html`, `static/js/igd-professional-execution.js`.
**Extend after B handoff:** `pasien/professional_care_models.py`; `TindakanAsesmen` and `BillingItem` additions registered through `pasien/models.py`; action forms/dispatcher, workflow context/routes and `_igd_workflow_operations.html`/`igd_workflow.html`/resume.
**Financial reader owners:** `pasien/models.py` discharge totals/subtotal, `pasien/views.py` detail/discharge/rekap/SQL aggregates, `pasien/pdf_utils.py`, `pasien/services/igd_finalization.py`, workflow context and associated billing/print templates found by the bounded search below.
**Regression:** existing workflow integration/hardening/finalization/outcomes, clinical tariff tests, and pharmacy/ancillary suites from their actual handoff.

## Task C1: One atomic execution path

**Produces:** `execute_professional(visit, workflow, actor, data) -> dict` called only inside `perform_action`, and the initial pure `charge_state(unit_total, is_free)` in `professional_billing.py` used by this task. Create both declared test modules before running their labels; C2 extends the billing module rather than creating an unresolved dependency for C1.

Input contract: exactly `source` PLANNED/DIRECT, optional `action_id`, service ID, Decimal quantity, actual occurred-at and retrospective reason, client-held quote fingerprint, optional performer/supervisor only when granted. PLANNED uses the existing plan's code/quantity rather than accepting a different hidden service. DIRECT creates its reviewed action line inside the same transaction; neither mode creates another patient visit.

Add protected service reference and `professional_snapshot`, `price_snapshot`, `financial_status` POSTED/FREE/PENDING to action data; reuse `performed_by`, `performed_at`, `recorded_at`, `execution_cppt` and billing FK. Preserve original legacy fields/source status and do not backfill role/grade on historical performed rows.

- [ ] RED: extend the existing integration fixture with reviewed A/B test configuration, then assert the same semantic execution returns stable links even under a different request ID. Keep the existing `IgdWorkflowTest` setup idiom; add actual HC/service/price grants from A, not an invented role string.

```python
from decimal import Decimal
from django.test import SimpleTestCase

class ExecutionArithmeticTest(SimpleTestCase):
    def test_unknown_and_free_are_distinct(self):
        from pasien.services.professional_billing import charge_state
        self.assertEqual(charge_state(None, False), 'PENDING')
        self.assertEqual(charge_state(Decimal('0'), True), 'FREE')
        self.assertEqual(charge_state(Decimal('200000'), False), 'POSTED')
```

Run `manage.py test pasien.tests_professional_execution pasien.tests_professional_billing --keepdb --noinput`; first RED must expose the missing proposed behavior, then GREEN must assert database links/counts as well as arithmetic.
- [ ] Implement actual-time validation: reject future time, explicit reason for retrospective recording, retain server recorded-at. Parse timezone-aware timestamps, display datetime-local as WIB (Asia/Jakarta) and keep the server's canonical time; test a business-date boundary across UTC/WIB. Resolve A's performer/privilege context for actual time and recording policy; require locked source rows for the mutation.
- [ ] Reconcile final lock order with A/B: visit → workflow → employee/SPK/context → service/price version → action → CPPT → billing/void. Tariff approval locks the same service/price key; source privilege revocation must serialize with the rows used for eligibility. Do not call network/provider inside this transaction.
- [ ] Compare caller's quote fingerprint/version against freshly validated context. Changed payor, service, grade, source authority or tariff returns conflict before writes. Nonclinical admins cannot bypass the performer check by posting their own approved price.
- [ ] Persist action execution → call B's `create_care_note` for a DRAFT event log → create/link a single professional BillingItem if priced/free → store persistent action result. Any failure rolls back the entire local transaction. Unpriced policy records PENDING and no numeric zero item, with explicit reconciliation state.
- [ ] Extend the existing `execute` and new direct operation to share the responsible execution owner when this feature applies; do not leave a permissive legacy handler bypass. Existing unadopted legacy behavior is preserved while the new feature is disabled, without claiming it enforces RKK.
- [ ] Add tests for same key, altered payload, second key/same plan, concurrent attempts, cancelled plan, price drift, wrong performer/grade/supervisor/unit, unauthorized direct service, late timestamp, CPPT/billing rollback, unknown price, explicit free and signature invalidation. Require one source action/one draft/one owned charge after replay.

## Task C2: Component snapshot, one ledger and full unpaid void

**Produces:** `charge_state(unit_total, is_free)`, `professional_billing_summary(visit) -> dict`, `void_professional_charge(actor, billing_id, expected_version, request_id, reason) -> dict` in `professional_billing.py`; immutable `PembatalanTagihan` in the shared model module.

Summary contract: separate planned estimate, actual gross, approved full void, net, unpriced counts and explicit free counts; categories MEDICAL/NURSING/OTHER_PPA/DRUG_BMHP plus labelled LEGACY_UNMAPPED for ambiguous history. BillingItem is authoritative for posted amounts. Store sarana/pelayanan and grade/source/price version snapshots at execution; do not recompute old bills from today's master.

- [ ] RED: synthetic posted professional rows, unpriced actions, approved free, cancelled plans, existing MANUAL and already-billed pharmacy/order items yield correct distinct buckets with no writes during summary GET.
- [ ] Add `BillingItem.is_void` default false as a projection, preserving original quantity/unit price/amount; `PembatalanTagihan` keeps protected unique original item, full original amount, actor/time, reason, idempotency and action/context references. No deletion of original billing or performed care.
- [ ] Only a separate scoped VOID_UNPAID_CHARGE capability may void an owned professional item. Recheck it belongs to the actor's scope and eligible unpaid, non-final episode; paid/closed cases, partial credit, other ownership and altered original amount are rejected. Clinical note correction remains B's reasoned operation, not a side effect of voiding a financial item.
- [ ] Expose proposed `igd_professional_void` as a CSRF-protected POST financial operation with exact charge, reason, caller-held workflow version and request key. Its permission path is narrowly financial: an authorized nonclinical finance actor may correct the eligible charge but cannot call clinical execution/signing/CPPT operations. Preserve object/unit scope, final-state denial, replay, workflow version/invalidation and audit; do not widen the dispatcher into a blanket admin clinical bypass.
- [ ] Under locks, create one immutable void record and set the is_void projection once. Repeated key or competing request cannot produce two reversals. Retain original price and record readback before reporting success; do not equate a requested void with a completed refund.
- [ ] Update `BillingItem.subtotal` to net zero for voided rows and provide original amount in the shared summary. Update SQL sums to exclude voided rows, not only the Python property. Pre-existing discharge snapshots stay historical; new discharge/net totals use the canonical summary.
- [ ] Before enabling void, inspect every financial reader with this exact source search and list the changes in the execution ledger:

```bash
git grep -n -E 'billing__harga_satuan|billing\.all\(|sum\(.*subtotal|kuantitas.*harga_satuan|harga_satuan.*kuantitas' -- '*.py' 'templates/*'
```

Known inspected call sites include `models.py` discharge, `views.py` detail/discharge and two aggregate readers, `pdf_utils.py`, `igd_finalization.py` and workflow context. Include newly added untracked services in the search with `search_files`; `git grep` alone omits them. Do not enable the void control if any total reader still counts an item differently.
- [ ] Verify detail/PDF/rekap/clearance/new discharge totals agree after full void, while original record and final historical content remain available. Add query-budget assertions/prefetch where relevant rather than an N+1 lookup of void records for every row.
- [ ] Price management creates effective versions; an exceptional pre-performance override requires MANAGE_TARIFF with reason and before/after audit. The source action's clinician cannot simply supply sarana/pelayanan in JSON as authority. Post-performance corrections do not edit original price snapshots.

## Task C3: Step-9 UI and neighbouring-domain adapters

**Consumes:** A lookup/quote endpoints and context, B note partial/operations, current planned actions and ledger, pharmacy/ancillary handoff.
**Produces:** `_igd_professional_execution.html` and `igd-professional-execution.js`, integrated only in step 9 under the default-off gate.

- [ ] Render separate cards: estimates versus actual net categories; planned/direct source; profession/grade/eligible staff/service cascade; component quote with unknown/free state; actual-time/quantity input; executed table; B's CPPT form/list and assigned-DPJP verification.
- [ ] Picker filters are navigation aids only; default performer is current linked employee. Show clear source-data gaps for unconfigured grade/SPK/tariff instead of a working-looking empty dropdown. Unsupported religion/discipline/grade labels are not silently converted to masters.
- [ ] Reset dependent selections after parent changes; cancel or ignore stale async responses. Store the preview's quote fingerprint in the submitted intent and refresh on drift. Do not compare two newly loaded quotes and call that a stale-price check.
- [ ] Preserve one stable request key during network retry; changing submitted intent starts a new key. Disable controls during pending save; show row-specific conflict and keep typed input. Rehydrate the server's action/CPPT/billing IDs and workflow version, not a client-total guess.
- [ ] Expose cancellation for unused plans; a performed row never has hard-delete. Eligible finance actors get the explicitly named unpaid-charge void action with reason/confirmation and original/net amounts visible; other users see status only.
- [ ] Add read-only medication/order panels from owner records. Label planned/prescribed/dispensed accurately; do not say “obat diberikan” based only on dispensing or re-create drug/LAB/RADIOLOGI billing. Medication administration/MAR is a separate future scope if explicitly requested.
- [ ] Shared profession/format widgets must not accidentally duplicate named fields in the parent draft form. Do not let the main step-9 navigation POST an execution as a documentation save.
- [ ] Test real browser cascade parent reset, missing setup, stale quote, double-click/retry, correct PPA format, actor restrictions, cancellation/void confirmation, keyboard, error focus and 375/768/1366 geometry. Verify persisted counts through the approved synthetic fixture.

## Task C4: Snapshot and integration gates

- [ ] Freeze actor/profession/grade/service/authority/supervisor, component prices, CPPT revision/verifier identities and execution/financial status into newly signed episode snapshots. Stored old snapshots never resolve to current tariff or staff-master data.
- [ ] Retain the physical-exam and diagnosis/pharmacy/ancillary snapshot extensions already in the handed-off source. Use additive versioned readers, not a full-file replacement of `clinical_snapshot`.
- [ ] Run both new modules plus current workflow integration/hardening/finalization/outcomes, tariff, pharmacy and ancillary tests, then the roadmap cross-app gate. Record actual counts. Read every additive migration and preserve default-off compatibility.
- [ ] Execute PostgreSQL races and full UI journeys from the roadmap. Report missing source configuration, live credentials or third-party acceptance separately; do not manufacture clinical/financial rows in production to close a demo gate.
- [ ] After separate release approval, regenerate tracked static assets from the frozen source, verify hash/gzip/manifest, apply approved additive migrations manually and prove exact provider SHA/alias. This component alone does not authorize rollout.
