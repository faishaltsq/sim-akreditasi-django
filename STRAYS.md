# Stray test artifacts

Reported against the OWASP suite added in `.github/workflows/security-tests.yml`.
Scan date: 2026-10-30.

## 1. Test-runner configs

**None.** No `pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini`, or `conftest.py`
anywhere in the repo. `requirements.txt` has no `pytest`; the only `pytest` mention in
tracked files is a comment in `security-tests.yml` explaining why pytest is *not* used.
Django's own `manage.py test` is the sole runner.

One artifact remains from a past pytest invocation and is untracked/ignored:

- `.pytest_cache/` — `README.md`, `CACHEDIR.TAG`, `.gitignore`, empty `v/cache/nodeids`,
  `v/cache/stepwise` = `[]`. No `lastfailed`. Not git-tracked (self-ignoring). Harmless
  but stale — a leftover marker that pytest was run at some point. Left in place: it is
  ignored, unreachable by CI, and outside this workstream's scope.

## 2. Stray test files

### 2a. `var/` — abandoned test files, superseded by `sdm/tests/` (untracked, ignored)

`.gitignore:23` has `var/`, so these are untracked local scratch. `var/` has no
`__init__.py`, so Django's discovery (`test*.py`, recursing only into packages) does not
reach them — but they are near-verbatim duplicates of committed tests, which is exactly
the kind of drift that causes "why did my edit not take effect".

| Path | Lines | Relationship to committed test |
|---|---|---|
| `var/t4_tests.py` | 224 | `IntakeUploadTests` — 70% similar to `sdm/tests/test_intake_uploads.py` (412 lines) |
| `var/t5_tests.py` | 70 | Bare `def test_*` methods (no class header) — copies of `test_intake.py:202,232,262` |
| `var/t8_route_tests.py` | 134 | `StaffImportRouteTests` — 98% similar to `sdm/tests/test_staff_import_routes.py` |
| `var/t8_svc_tests.py` | 31 | Bare `def test_*` fragment of the same import-service tests |
| `var/t9_activation_tests.py` | 158 | `StaffActivationViewTests` — no committed counterpart; orphan |
| `var/t9_expiry.py` | 14 | Bare fragment: no class, no imports — a single `def test_expired_invitation_is_refused(self)` method lifted out of a `TestCase` body; relies on `self.employee`, `UndanganAkunPegawai`, `accept_staff_invitation`, `ValidationError`, `timezone` from an enclosing scope that is not present in the file |

Also in `var/` (non-test scratch, same abandoned batch): `t4_fetch.py`, `t4_model.py`,
`t4_service.py`, `finalize_block.py`, `helpers_block.py`, `blk_1276.js`,
`starkes-2024-mapping.json`, `starkes-2024-mapping-prod.json`, `rehearsal-mapping.json`,
`backup/akreditasi-20261023-210258.json` (652 KB DB dump), `probe/probe_*.py` (4 files
that boot `DiscoverRunner` against `config.control_test_settings`).

### 2b. `config/tests_allowed_hosts.py` — host-hardening tests that never ran in CI (tracked) — **FIXED**

`config/` is a package (`__init__.py`), so `manage.py test` discovery *does* find it.
Contains `ExtraAllowedHostsTests(TestCase)` — 4 tests pinning the `ALLOWED_HOSTS` /
`CSRF_TRUSTED_ORIGINS` contract:

- `test_extra_hosts_are_parsed_from_env`
- `test_no_wildcard_host_is_ever_added` — host-header injection hardening
- `test_production_hosts_are_always_present`
- `test_csrf_origins_use_https_scheme`

This was a **real coverage gap, not merely a file outside the suite**. The module is
discovered only by a bare `manage.py test`, and `security-tests.yml` runs an explicit
module list — so these 4 tests never executed in CI, leaving A05 (Security
Misconfiguration) / A01 (Broken Access Control) host-surface assertions unguarded.

**Fix applied:** `config.tests_allowed_hosts` added to the module list in
`.github/workflows/security-tests.yml`, after `akreditasi.tests_security`. A header
comment now records that it covers A05/A01 host hardening.

### 2c. `config/control_test_settings.py` — alternate test settings module (tracked)

`DJANGO_SETTINGS_MODULE=config.control_test_settings`: in-memory SQLite,
`MIGRATION_MODULES` all `None`, locmem cache, `MD5PasswordHasher`. Referenced only by
the untracked `var/probe/*.py`. A second test-settings convention alongside the default
`config.settings` that `security-tests.yml` uses.

## 3. Stray test output / logs

| Path | Tracked | Notes |
|---|---|---|
| `.qa_akses.log` (24 KB) | no (ignored by `*.log`) | Django `manage.py test` output — "Found 26 test(s)", full migration log |
| `.qa_combo.log` (24 KB) | no (ignored) | same, "Found 20 test(s)" |
| `.qa_dash.log` (21 KB) | no (ignored) | same, "Found 9 test(s)" |
| `.qa_uid.log` (21 KB) | no (ignored) | same, "Found 8 test(s)" |
| `.qa_tmp/rkk_err.txt` (0 B) | **yes** | empty error capture, committed |
| `.qa_tmp/{alur,katalog,orientasi,rkk}_text.json` | **yes** | STARKES design-text dumps, committed |
| `qa/reports/*.md`, `qa/reports/*.json` | yes (`.md`) / no (`.json`) | QA-fleet reports from a 1,295-account run, not test output |

The four `.qa_*.log` files are the actual `manage.py test` transcripts. They are
git-ignored so CI cannot pick them up, but they sit in the repo root and are easy to
mistake for a test report. `.qa_tmp/` *is* committed and holds no test data.

## 4. Stray CI workflows

Only two workflow files exist under `.github/workflows/`:

- `security-tests.yml` — the OWASP suite. Runs an explicit module list
  (`accounts.tests_security_owasp`, `akreditasi.tests_security_owasp`,
  `pasien.tests_security_owasp`, `sdm.tests.security_owasp`, `tests_session_security`,
  `tests_priv_escalation`, `tests_admin_gate`, `tests_object_authz`, `tests_security`,
  `accounts.tests_unit_rbac`, `sdm.tests.test_akses`, `sdm.tests.test_private_documents`).
  Deliberately red on 32 documented P0 findings; no `continue-on-error`.
- `hc-reminders.yml` — scheduled `manage.py hc_reminders` cron. Runs **no tests**.

There is **no** generic CI workflow that runs the full suite (`manage.py test` with no
arguments), so nothing silently re-runs or duplicates the OWASP job. `nixpacks.toml`,
`render.yaml`, `build.sh`, `build_vercel.sh`, and `Procfile` contain no test steps.

## Summary of interference risk

- **No runner conflict.** No pytest config exists; Django is the only runner.
- **No CI duplication.** No workflow runs the full suite.
- **Coverage gap closed:** `config/tests_allowed_hosts.py` (4 host-hardening tests) was
  discovered by a bare `manage.py test` but absent from the workflow's explicit module
  list, so it never ran in CI. Added to `security-tests.yml`.
- **Real clutter:** `var/` holds six abandoned test files that duplicate committed
  `sdm/tests/` coverage, plus a 652 KB DB dump and four probe scripts. Left in place —
  untracked, git-ignored, user's local scratch.
- **Committed noise:** `.qa_tmp/` (5 files, incl. a 0-byte `.txt`) is tracked but holds
  no test data.
- **Ignored noise:** `.qa_*.log` (4 files, ~91 KB) and `.pytest_cache/` are untracked
  leftovers; left alone.

## Final module list in `security-tests.yml`

```
accounts.tests_security_owasp
akreditasi.tests_security_owasp
pasien.tests_security_owasp
sdm.tests.security_owasp
akreditasi.tests_session_security
accounts.tests_priv_escalation
akreditasi.tests_admin_gate
pasien.tests_object_authz
akreditasi.tests_security
config.tests_allowed_hosts      <-- added
accounts.tests_unit_rbac
sdm.tests.test_akses
sdm.tests.test_private_documents
```
