# Assessment and Control Regression Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two measured regression failures without weakening SEP behavior, unit authorization or the dashboard query budget.

**Architecture:** Keep the existing JSON SEP integration and align its legacy assertion with the intentional contract change. Diagnose the warm-dashboard query capture before editing production code, then remove redundant work in its owning layer rather than raising the budget or introducing a speculative cache.

**Tech Stack:** Django TestCase, CaptureQueriesContext, existing template/ORM/cache infrastructure.

**Spec:** Completion of `docs/superpowers/plans/2026-11-05-asesmen-awal-igd-layanan-unit-dan-kunjungan.md`; execution evidence in `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima-plan-regression.log`.

## Global Constraints

- Preserve dirty/untracked work. No commits, deployment, data cleanup or migration.
- Do not rerun completed source-creation tasks from the original plan.
- No relaxing `BUDGET = 12`, removing authorization queries without equivalent enforcement, or hiding failures with broad mocks.
- Keep SEP POST, CSRF, BPJS-only visibility, contextual Detail links and inline accessible feedback.
- This plan owns regression completion only. Modal layout changes belong to `2026-11-06-igd-assessment-modal-scroll.md`; those tasks do not edit these files.

## Measured Baseline

Latest complete run: 1029 tests in 745.064s, two failures, no reported errors. The 75 targeted tests previously passed. Reproduce the two failing suites on the current tree before changing code; historical totals are evidence, not a required future count.

Failures:
1. `akreditasi.tests_kontrol_admission_desk.AdmissionDeskDashboardTest.test_sep_action_is_post_only_for_bpjs_rows`: line 69 expects the old action without JSON query parameter.
2. `akreditasi.tests_kontrol_dasbor.KontrolQueryBudgetTest.test_subdasbor_setelah_cache_hangat`: 16 queries against a budget of 12. Root cause is unverified; do not attribute it to the resolver change without captured SQL.

## Review Focus

- BPJS row exposes only the intended JSON POST action; UMUM row exposes no SEP action.
- SEP success/failure never overwrites clinical visit status.
- Warm-cache optimization preserves role/unit boundaries and cold-request correctness.
- Query growth across multiple rows is not concealed by the empty-fixture budget.
- Full-suite test isolation: avoid real AI network requests during unit tests; inspect existing mocks before proposing a separate isolation fix.

## Task 1: Align the SEP regression contract

**Files:** Modify `akreditasi/tests_kontrol_admission_desk.py:59-82`; production template remains `templates/akreditasi/kontrol/layanan.html` unless the tests expose a real defect.

**Interfaces:** Existing `pasien:bpjs_buat_sep`, `?format=json`, `.layanan-sep-form`, `method="post"`.

- [ ] Reproduce the failing test and read both BPJS/non-BPJS neighboring tests.
- [ ] Replace this exact assertion:

```python
self.assertIn(f'action="{sep_url}"', body)
```

with:

```python
self.assertIn(f'action="{sep_url}?format=json"', body)
```

- [ ] Keep neighboring POST and Detail assertions. Strengthen row-scoped assertions for BPJS and UMUM using the existing fixtures; do not assert only that a script string or sidebar URL occurs somewhere on the page.
- [ ] Verify CSRF remains inside the form and JSON success/failure displays inline without changing the clinical status cell. Exercise success, business failure and malformed/HTTP failure with browser request interception, not a real SEP issuance.

```bash
.venv/Scripts/python.exe manage.py test akreditasi.tests_kontrol_admission_desk akreditasi.tests_layanan_block --keepdb -v 1
```

Expected: exit code 0, no failures.

## Task 2: Trace and fix the warm-dashboard query excess

**Files:** Inspect `akreditasi/tests_kontrol_dasbor.py:137-155`, dashboard URL/view, context processors and snapshot builder; modify only the production owner identified by SQL evidence. Retain the existing budget test; extend its fixtures in the same module if a repeated-query cause is found.

**Interfaces:** `KontrolQueryBudgetTest._queries(url)` warms the URL then captures the second response. `test_subdasbor_setelah_cache_hangat` calls `reverse('akreditasi:kontrol_emr')`.

- [ ] Run the failing suite independently. Capture SQL plus repeated normalized statements for the second request using the existing CaptureQueriesContext setup, storing diagnostic output in scratch. If the failure occurs only after other suites, locate state/cache leakage before optimizing application code.
- [ ] Trace every repeated query to its actual caller. Inspect role/profile relations, unit tree resolution, template context and cached snapshot boundaries. Document the identified owner and why the work repeats; do not change a guessed file.
- [ ] Add a regression test that reproduces the discovered pattern and a contrasting role/unit case. Use real setup helpers in `tests_kontrol_dasbor.py`, not invented roles or bypassed middleware.
- [ ] Implement the smallest responsible-layer fix: reuse a request-local resolved object/queryset, use select_related/prefetch_related on the actual repeated relation, or correct an existing cache key/lifecycle only if the trace proves that owner. Do not add a new cache architecture.
- [ ] Re-run the budget suite and unit-scope tests. Require warm dashboard at most 12 queries with correct response and scope; confirm cold rendering remains correct.

```bash
.venv/Scripts/python.exe manage.py test akreditasi.tests_kontrol_dasbor akreditasi.tests_kontrol_admission_desk akreditasi.tests_layanan_unit akreditasi.tests_layanan_block --keepdb -v 1
```

Expected: exit code 0; existing budget unchanged. If a legitimate required query makes this impossible, stop and report measured SQL and the tradeoff rather than silently changing the budget.

## Task 3: Close the original plan's quality gate

- [ ] Run the targeted assessment and control suites after both tasks; include the new modal suite if that separate plan was executed.
- [ ] Run full regression once using a tracked background process with completion notification; write logs to Hermes scratch, not repository or system temp. Do not create duplicate full-suite processes against the same test database.

```bash
.venv/Scripts/python.exe manage.py test pasien akreditasi --keepdb -v 1
```

- [ ] Require exit code 0 and a real final test summary. Report network-dependent failures separately; never fabricate a successful result or weaken unrelated tests.
- [ ] Verify the original four-tab form at 1366x768 and 1920x1080: no horizontal overflow, reachable final fields/footer and keyboard navigation. Use isolated data for save/copy journeys.
- [ ] Run `git diff --check` and `git status --short`, preserve unrelated work, update the original plan with exact completed/unverified gates, and report outcomes. No commit/push/deploy.

## Explicitly NOT in This Plan

Do not implement, do not fix while here: clinical tab reordering, seven-tab/four-tab consolidation, unrelated failing tests, real BPJS/AI integration configuration, schema changes, production data repair or broad control-dashboard redesign.

## Rollback

Revert only the exact new query optimization and contract-test changes if needed. Keep the existing SEP JSON implementation, four-tab form and unrelated working-tree edits intact. No persistent data change is planned.
