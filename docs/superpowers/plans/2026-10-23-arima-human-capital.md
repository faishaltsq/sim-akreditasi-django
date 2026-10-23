# Arima Human Capital Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an integrated, permission-scoped workforce management module covering the attachment's five maturity levels, presented on the main dashboard as **Arima Human Capital**.

**Architecture:** Add a focused Django app `sdm` inside the existing monolith. Reuse authentication, `UnitKerja`, accreditation records and existing organizational risk/quality sources; make `sdm.Pegawai` the employment identity independent of login accounts. Introduce private personnel storage, explicit Human Capital grants, immutable workflow histories and versioned calculations; retain existing credential routes during additive reconciliation.

**Tech Stack:** Existing pinned Django 6.1.2, Django templates, Bootstrap conventions, SQLite for local development and PostgreSQL/Supabase for deployed data; existing openpyxl/reportlab for exports. Use authenticated Supabase private-object operations, not public evidence-upload URLs. No new worker service, SPA or paid platform is required for the initial releases.

**Spec:** `docs/superpowers/plans/2026-10-23-arima-human-capital-scope.md`, traced to `C:\Users\cubeb\Downloads\manajemen sdm di arima.docx`.

## Execution Status

- [x] Task 1 — App registration and isolated baseline verified; controller rerun: 33 tests passed. Specification review PASS; quality review APPROVED (one non-blocking resolver-test coupling note).
- [x] Task 2 — Employment identity, UUID IDs, dated placements, scoped grants, role-level permission integration, immutable audit events and serialized FTE allocation validation implemented. Controller regression run: 88 tests passed; isolated settings only.
- [x] Task 3 — Private storage, versioned document records, signed-download authorization, object cleanup, legacy-credential resolver and reviewed-mapping reconciliation implemented and tested (119 tests). Operator runbook added at `docs/security/human-capital-private-storage.md`. External gates remain: private-bucket provisioning, anonymous-access verification, sanitized rehearsal and approved cutover.
- [x] Task 4 — Directory, e-file, requirement rules (`AturanDokumen`), reviewed standard mapping (`PemetaanStandarSDM`) and compliance evaluation implemented and tested.
- [x] Task 5 — Versioned activity-based FTE planning with Decimal calculation, draft→review→approved→superseded workflow and immutable results implemented and tested.
- [x] Task 6 — Dashboard, idempotent reminders, `/human-capital/` route and fourth hub card implemented; existing three cards and no-sidebar shell preserved. MVP gate met for Level 1.
- [x] Task 7 — Recruitment pipeline, PSV, committee decisions, numbered SPK, revocation and orientation implemented and tested.
- [x] Task 8 — Versioned appraisals, rule-based TNA with provenance, and learning management implemented and tested.
- [x] Task 9 — K3 risk/incident workflows, occupational-health records, clinical boundary and break-glass implemented and tested.
- [x] Task 10 — Coverage-aware snapshots, compliance audit, redacted export, talent assessment and human-approved scenarios implemented and tested.
- [x] Task 11 — Release evidence recorded at `docs/qa/arima-human-capital-release.md`. 680 tests pass, checks clean, migrations consistent, static collected. Deployment, PostgreSQL rehearsal, private-bucket provisioning and stakeholder acceptance remain external gates; no deployment claimed.

## Global Constraints

- UI name: `Arima Human Capital`, exactly. All UI copy remains Bahasa Indonesia; this plan is English.
- Add a fourth product card to `/control/`; preserve the hub's name and three existing products. The old `/` accreditation dashboard gets an authorized shortcut, not a global rename.
- Implementation is authorized. Keep database testing isolated; do not run production migrations/imports, commit, push or deploy without explicit authorization.
- Preserve existing `UserProfile`, `NakesCredential`, user IDs, organizational units, credential files, URLs and accreditation scores. Additive changes first; no delete/reseed or automatic account reassignment.
- `UserProfile` represents an account, not the entire workforce. Employees without accounts and non-clinical staff must work.
- Existing `can_verify_kps` does not grant HR-wide access, medical-record access, committee authority or executive talent access.
- Health data uses explicit grants even when `UserProfile.has_permission()` returns True for a technical superuser. Keep legacy platform access semantics unchanged outside the new health boundary.
- No personal/medical file may be stored as a public Supabase URL or on ephemeral Vercel disk. Storage failure must leave the document uncommitted/pending, not fall back to a public or local file.
- Use `timezone.localdate()` and the project's Asia/Jakarta timezone. Decimal arithmetic for money and staffing fractions; no floating-point budgeting.
- No synthetic compliance/analytics figures, no zero-denominator 100%, no silent fallback from unit to hospital scope.
- Migrations are applied explicitly during deployment. `staticfiles/` is intentionally tracked: retain it and collect static artifacts for any asset changes.
- Preserve unrelated uncommitted work. Commit only if separately requested; stage named paths only.

## Review Focus

1. A head of unit with no assigned unit must not receive hospital-wide personnel access. Test null/malformed/inactive unit filters and direct object URLs in Task 2.
2. Existing credentials already carry real data. Reconciliation must survive duplicate/blank employee numbers and preserve file/version relationships without fuzzy automatic matches. Test in Task 3.
3. A document can be verified yet expired, rejected yet future-dated, lifetime-valid or due today. Required-document compliance and expiry are distinct decisions. Test in Task 4.
4. A technical admin or HR operator is not automatically a K3 clinician. Test object access, exports and signed downloads, not only hidden menu items, in Task 9.
5. Staffing and BOR data may describe different periods/scopes, and mature analytics may lack historical coverage. Test rejection/unavailable states in Tasks 5 and 10.

## Verified Baseline

Read-only inspection on 2026-10-23 found branch `master` with an initially clean working tree. This is a local baseline, not proof of production state.

| Finding | Verified source | Planning consequence |
|---|---|---|
| Six existing role choices; configurable permissions and survey freeze | `accounts/models.py:6-207`, `416-473` | Extend permission infrastructure; do not infer role names such as DIREKTUR from references elsewhere |
| Account profile already holds profession, employee number and one unit | `accounts/models.py:76-162` | Optional account link on the new employee identity; preserve history independently |
| Clinical credentials and expiry helpers exist | `accounts/models.py:320-413` | Reconcile existing records, do not start a second disconnected credential store |
| Legacy KPS upload/list/verify paths exist | `akreditasi/urls.py:68-71`, `akreditasi/views.py:1764-1914` | Keep routes operational; add adapter tests before changing ownership/storage |
| Current uploader returns public URLs and falls back to local disk | `akreditasi/supabase_storage.py:7-58` | Do not reuse it for private HR/medical documents |
| Main hub declares three cards, builds per-card metrics, and uses a standalone shell | `akreditasi/kontrol_views.py:24-49`, `89-152`; `templates/akreditasi/kontrol/hub.html` | Add HR card and matching metric/context handling, not metadata alone |
| Hub tests explicitly cover three products and no sidebar | `akreditasi/tests_kontrol_dasbor.py:37-80` | Extend expectations without breaking existing products/shell |
| SDM/Diklat setup and unit codes already exist | `akreditasi/management/commands/setup_sdm_diklat.py` | Reuse actual unit IDs; do not run setup as a migration side effect |

Local SQLite read-only probe results:

- `accounts_userprofile`: 45 rows; 22 have a unit; 4 have a nonblank `nip_nrp`.
- `accounts_nakescredential`: 13 rows, including pending, verified and expired records.
- `akreditasi_unitkerja`: 219 rows; `BAG-SDM`, `SDM`, `BAG-DIKLIT`, `UNIT-KREDENSIAL` exist.
- `akreditasi_standarditem`: 1053 rows. KPS includes 10.1, 14–19 and 8.1; the attachment's simplified mapping must not overwrite it.
- `.venv/Scripts/python.exe` exists. Its runtime and installed package versions were not executed as part of planning.

No production database or external credential issuer was queried. No tests/build were run because no implementation changed. Repeat discovery before execution because branch, schema and data may move.

### Overlap and explicit non-goals

The existing `2026-10-22-layanan-unit-per-dasbor.md` concerns patient-service navigation and unit visit resolution. This plan does not implement that work and must preserve its `_layanan_unit.html` integration. The existing integrated-control plan owns the shell; this plan only adds a product entry and its HR destination. A repository search found no existing dedicated Human Capital implementation plan. No unrelated EMR/risk fixes, credential-purge cleanup or catalogue replacement: **do not implement, do not fix while here**.

## Architecture Decisions

| ADR | Decision | Tradeoff |
|---|---|---|
| HC-ADR-01 | New Django app, same database and deployment | Less deployment/identity complexity; app boundary must prevent growth of `akreditasi/views.py` |
| HC-ADR-02 | `Pegawai` with nullable one-to-one account link | Supports all staff; requires controlled reconciliation with account-bound legacy credentials |
| HC-ADR-03 | Canonical employee document versions plus a legacy-reference adapter | Avoids duplicate truth; compatibility work is more involved than a new table alone |
| HC-ADR-04 | Private storage keys and authorized, short-lived delivery | Protects personnel data; requires storage provisioning and recovery tests before real imports |
| HC-ADR-05 | Explicit scope/health grants, with permission configuration | Least-privilege access; more configuration than using unit-name heuristics |
| HC-ADR-06 | Rule-based reminders/TNA/scenarios first | Reproducible and inexpensive; no predictive claim until historical data is validated |
| HC-ADR-07 | Reviewed FK-based standards mappings | Respects real catalogue editions; clinical/accreditation-owner review is a release dependency |

## Proposed Data Contracts

Names below are **new proposed interfaces**, not existing repository APIs. Each is implemented by the task that owns it.

- `Pegawai`: internal UUID PK; optional account OneToOne with `SET_NULL`; employee number, legal/display name, PPA/non-PPA, profession, employment category, employment FTE, active dates. Employee-number uniqueness applies only to nonblank values; imports flag collisions for review. Account deletion never cascades into employment records.
- `PenempatanPegawai`: employee, existing unit FK with `PROTECT`, role/job description, effective start/end, allocation fraction. Organizational history is effective-dated.
- `HcGrant`: account, capability, unit (nullable only for explicit hospital scope), descendant inclusion, optional profession/case restriction, validity interval, grantor. Health capabilities cannot come solely from generic role defaults.
- `DokumenPegawai` and immutable `VersiDokumen`: owner, document type, purpose/sensitivity, storage key, content hash/size/MIME, issuance/expiry and explicit validity policy, review status, version, reviewer. Replace uploads by new versions; never overwrite the same object key.
- `TautanKredensialLama`: unique legacy `NakesCredential` FK to canonical document/version. Preserve legacy row IDs; read through the adapter after cutover. New clinical uploads create canonical and legacy-compatible references in one transaction, not two independent reviews.
- `AturanDokumen`: versioned profession/PPA/assignment applicability and approved validity rules. `PemetaanStandarSDM`: reviewed rule/process → actual `StandardItem`/`EvidenceReq`, framework edition, reviewer and review date.
- `PeristiwaSDM`: actor, event, timestamp, target ID, previous/new workflow status, reason and request correlation; never a medical-content dump. Sensitive read/download events are recorded too.
- `RencanaFormasi`, `AktivitasBebanKerja`, `HasilFormasi`: approved period/method/assumptions and immutable result versions. Inputs use the spec's units and formulas.
- `PengingatSDM`: employee/document/course target, alert band, recipient, due date, channel and unique idempotency key. Dashboard reminders are the initial channel.
- Level 2 models: `Lowongan`, `Lamaran`, `RiwayatSeleksi`, `VerifikasiSumber`, `PengajuanKredensial`, `RincianKewenangan`, `KeputusanKredensial`, `PenugasanKlinis`, `ProgramOrientasi`, `AktivitasOrientasi`, `PenugasanOrientasi`, `PenyelesaianOrientasi`.
- Level 3 models: `PeriodeKinerja`, `PenilaianKinerja`, `ButirPenilaian`, `KebutuhanPelatihan`, `SumberKebutuhanPelatihan`, `ProgramDiklat`, `SesiDiklat`, `PesertaDiklat`, `KehadiranDiklat`, `EvaluasiDiklat`.
- Level 4 models: `RisikoK3Pegawai` referencing existing risk records, `ImunisasiPegawai`, `PemeriksaanKesehatanKerja`, `InsidenK3Pegawai`, `TindakLanjutK3`.
- Level 5 models: `SnapshotAnalitikSDM`, `PenilaianTalent`, `RencanaSuksesi`, `SkenarioSDM`. Snapshot metadata includes calculation version, filters, source coverage and generation time.

All new tables need appropriate FK constraints, status/date validation, indexes on scoped list/filter access patterns and transactional workflow services. An immutable approval references the exact document/result version reviewed.

## File Ownership Map

All `sdm/` paths below are proposed new files. The implementation can add generated numbered migrations under `sdm/migrations/`; determine filenames from the actual graph, never pre-claim a migration number.

| Paths | Owner task / responsibility |
|---|---|
| `sdm/__init__.py`, `sdm/apps.py`, `sdm/admin.py`, `sdm/urls.py`, `sdm/migrations/__init__.py` | Task 1: app registration and route skeleton |
| `sdm/models/__init__.py`, `pegawai.py`, `akses.py`, `audit.py` inside `sdm/models/` | Task 2: employment identity, assignment and grant/audit models |
| `sdm/akses.py`, `sdm/context_processors.py`, `sdm/tests/__init__.py`, `sdm/tests/test_akses.py` | Task 2: server authorization and permission-filtered navigation |
| `sdm/models/dokumen.py`, `sdm/storage.py`, `sdm/services/__init__.py`, `sdm/services/kredensial_lama.py` | Task 3: document ownership, private files, reconciliation adapter |
| `sdm/management/__init__.py`, `sdm/management/commands/__init__.py`, `sdm/management/commands/reconcile_hc_credentials.py` | Task 3: dry-run/reviewed reconciliation |
| `sdm/tests/test_dokumen.py`, `sdm/tests/test_legacy_credentials.py` | Task 3 and Task 4 coverage |
| `sdm/forms/__init__.py`, `sdm/forms/pegawai.py`, `sdm/forms/dokumen.py`, `sdm/views/__init__.py`, `sdm/views/pegawai.py`, `sdm/views/dokumen.py`, `sdm/services/kepatuhan.py` | Task 4: staff directory, versioned uploads and requirement evaluation |
| `sdm/models/formasi.py`, `sdm/forms/formasi.py`, `sdm/views/formasi.py`, `sdm/services/formasi.py`, `sdm/tests/test_formasi.py` | Task 5: staffing calculator and planning approval |
| `sdm/models/pengingat.py`, `sdm/services/pengingat.py`, `sdm/management/commands/hc_reminders.py`, `sdm/tests/test_pengingat.py` | Task 6: idempotent due reminders |
| `sdm/views/dashboard.py`, `sdm/services/dashboard.py`, `sdm/tests/test_dashboard.py`, `static/css/human-capital.css` | Task 6: real KPI dashboard and hub integration |
| `sdm/models/rekrutmen.py`, `sdm/models/kredensial.py`, `sdm/models/orientasi.py`, corresponding `sdm/forms/`, `sdm/views/`, `sdm/services/` modules with those basenames; `sdm/tests/test_rekrutmen.py`, `test_kredensial.py`, `test_orientasi.py` | Task 7: Level 2 workflows |
| `sdm/models/kinerja.py`, `sdm/models/diklat.py`, corresponding `sdm/forms/`, `sdm/views/`, `sdm/services/` modules; `sdm/services/tna.py`, `sdm/tests/test_kinerja.py`, `test_diklat.py`, `test_tna.py` | Task 8: Level 3 workflows and quality-source adapters |
| `sdm/models/k3.py`, `sdm/forms/k3.py`, `sdm/views/k3.py`, `sdm/services/k3.py`, `sdm/tests/test_k3.py` | Task 9: restricted Level 4 workflows |
| `sdm/models/analitik.py`, `sdm/forms/analitik.py`, `sdm/views/analitik.py`, `sdm/services/analitik.py`, `sdm/services/ekspor.py`, `sdm/tests/test_analitik.py`, `sdm/tests/test_ekspor.py` | Task 10: Level 5 analytics, talent and reporting |
| `sdm/tests/test_release.py`, `docs/qa/arima-human-capital-release.md` | Task 11: end-to-end/release evidence and rollback runbook |

Templates are grouped under `templates/sdm/`: Task 4 creates `base.html`, `pegawai/daftar.html`, `pegawai/detail.html`, `pegawai/form.html`, `dokumen/form.html`; Task 5 creates `formasi/daftar.html`, `formasi/form.html`, `formasi/detail.html`; Task 6 creates `dashboard.html`, `_navigasi.html`, `_kpi.html`, `_tugas.html`; Tasks 7–10 each create `daftar.html`, `form.html`, `detail.html` inside their corresponding workflow directories (`rekrutmen`, `kredensial`, `orientasi`, `kinerja`, `diklat`, `k3`, `analitik`). Task 7 additionally creates `kredensial/cetak_spk.html`. Task 10 creates `analitik/cetak_audit.html`.

Existing modifications: `config/settings.py`, `config/urls.py` (registration); `accounts/models.py` and generated accounts migration (new configurable permissions); `accounts/views.py`/`accounts/forms.py` and the existing control-center template if discovery confirms explicit permission field lists; `akreditasi/views.py` (only targeted legacy credential delegation); `akreditasi/kontrol_views.py`, `templates/akreditasi/kontrol/hub.html`, `templates/akreditasi/dashboard.html`, `templates/includes/sidebar.html` (authorized entry points); `accounts/tests_sidebar_visibility.py`, `akreditasi/tests_kontrol_dasbor.py`, `akreditasi/tests_security.py`, `akreditasi/tests_upload_bukti.py` (compatibility/regression); generated collected assets and `staticfiles/staticfiles.json`.

## Task 1 — Reconfirm baseline and register the app

**Depends on:** scope approval. **Produces:** installed `sdm` app and isolated test harness, without advertising an incomplete module.

- [x] Recheck `git status --short`, branch, requirements, the migration graph and existing overlapping plans. Record installed Python/Django versions using `.venv/Scripts/python.exe`; do not use the mismatched global pip.
- [x] Inspect all legacy credential usages, forms, admin, expiry consumers and test fixtures. Search existing user/role settings UI for explicit permission lists before adding capabilities.
- [x] Inspect existing app/model-package patterns and current database backend without printing credentials. Repeat the local read-only aggregate probes; use approved read-only production aggregates only if deployment planning requires them.
- [x] Run existing targeted regression baseline against an isolated test database; record actual failures instead of inheriting assumed pass counts.
- [x] Create the `sdm` app files and register the app/namespace. Do not link the hub card until its destination works in Task 6.
- [x] Add route resolution tests in `sdm/tests/test_release.py`; run them RED before adding routes, then GREEN after registration. A root route may remain absent until Task 6 rather than rendering a fake dashboard.

Baseline command (verify test DB isolation first):

```bash
.venv/Scripts/python.exe manage.py test accounts.tests_sidebar_visibility akreditasi.tests_kontrol_dasbor akreditasi.tests_security --verbosity 2
```

**Acceptance:** app imports cleanly; existing endpoints and regression expectations remain unchanged.

## Task 2 — Employment identity and authorization

**Produces:** `visible_employees(user)` scoped QuerySet, `require_hc_capability(user, capability, *, unit=None, employee=None)` authorization service, and explicit health-grant checks. These are proposed new functions implemented here.

- [x] Write failing tests for employee without account, non-PPA, duplicate nonblank numbers, blank numbers, account deletion preserving employment, allocation/date constraints and inactive assignments.
- [x] Add `Pegawai`, `PenempatanPegawai`, `HcGrant`, `PeristiwaSDM` and generated additive migrations. Use database constraints for local invariants and transactional validation/locking for overlapping assignment totals.
- [x] Add configurable nonmedical capabilities: `can_view_hc`, `can_manage_hc_employees`, `can_manage_hc_documents`, `can_plan_hc_workforce`, `can_manage_hc_recruitment`, `can_review_hc_credentials`, `can_manage_hc_orientation`, `can_manage_hc_appraisals`, `can_manage_hc_training`, `can_view_hc_analytics`, `can_manage_hc_talent`, `can_export_hc`. Seed conservatively and document explicit grants for HR/Diklat/committees; do not broaden every ADMIN_RS account silently.
- [x] Implement scope services and role-configuration/custom-override integration. Define separately granted `hc_health_read`/`hc_health_write`/`hc_health_break_glass` capabilities; generic superuser bypass must not satisfy these.
- [x] Test each actual role from `UserProfile.ROLE_CHOICES`, a superuser with/without health grants, an employee self-link and explicit HR/committee grants. Preserve existing admin global operational scope where granted, but default denied on HR files.
- [x] Pin null-unit heads, ancestor/descendant boundaries, foreign unit IDs, missing profiles, revoked/expired grants, assessor read-only access and POST/CSRF requirements. A bad filter never expands results.
- [x] Add new read permissions to survey-freeze read handling where appropriate; test that writes remain frozen and safety-critical K3 access follows an explicit approved policy rather than an accidental bypass.

**Run:** `manage.py test sdm.tests.test_akses accounts.tests_sidebar_visibility` through the project interpreter.
**Acceptance:** server-side scope governs list/detail/export/download equally; no organizational data is reseeded.

## Task 3 — Private storage and legacy credential reconciliation

**Produces:** `store_private_document(file_obj, *, employee, sensitivity, document_type, title, uploaded_by, issued_date=None, valid_until=None)` and `authorize_document_download(user, version, *, expires_in=None)` in `sdm/storage.py`; `resolve_legacy_credential(credential)` and the `reconcile_hc_credentials` command in their mapped files.

- [x] Write storage tests using an in-memory/fake HTTP boundary: duplicate filenames create distinct keys; forged MIME/oversize files fail; signed URLs are validated/short-lived; a storage failure creates no accepted document; logs contain no private response body or signed token. Cross-employee download coverage remains in Task 4's end-to-end view tests.
- [x] Implement private bucket upload/download with bounded timeouts and opaque UUID keys. Validate content, size and filename using the private storage backend. Do not call the public evidence helper. Deliver short-lived authorized URLs; never persist signed URLs as identity.
- [x] Add document/version/legacy-link models and idempotent `reconcile_hc_credentials` dry-run/apply command. Report aggregate counts, not unnecessary personal data. Default dry-run; apply requires a reviewed mapping artifact and explicit apply option.
- [x] Link credentials by exact account identity; where employee identity is ambiguous or numbers collide, stop that record for manual review. Never match on approximate names. Test repeated apply creates no duplicate employees/files.
- [x] Retain original credential rows, file references, IDs and checksums. Existing publicly accessible source objects cannot be made private merely by copying: prepare and execute a separately approved bucket-policy/public-object remediation, verify anonymous access fails, and only then mark privacy cutover complete.
- [x] Delegate legacy upload/verify/delete/download behavior through the canonical service without maintaining independent review states. This adapter is intentionally deferred to Task 4, where the canonical versioned upload/review/download flows are implemented; keep current legacy routes intact until compatibility tests pass. A legacy delete becomes an authorized archive/supersession policy, not destructive loss of approved records.
- [x] Execute rehearsal on a restored/sanitized copy. Require row reconciliation, missing-file report, active links and download checks before any production cutover.

**Run:** `manage.py test sdm.tests.test_dokumen sdm.tests.test_legacy_credentials akreditasi.tests_security akreditasi.tests_upload_bukti`.
**Acceptance:** existing credentials remain reachable by authorized users; no new public file URLs; dry-run changes nothing.

## Task 4 — Directory, e-file and requirement compliance

**Produces:** working employee CRUD/history and `evaluate_employee_compliance(employee, *, as_of, ruleset)` in `sdm/services/kepatuhan.py`.

- [x] Write failing view/service tests for search/pagination and all HC-02/03/04 applicability/validity cases. Include rejected future-dated files, lifetime documents, date-null policy, multiple versions and duplicates.
- [x] Implement forms, unit-scoped directory and profile tabs: employment/assignments, education/history, job description/contracts, credentials/certificates, authorized activity history.
- [x] Implement versioned upload/review/supersession; reupload resets approval for the new version. Enforce reviewer authority and prevent a user approving their own credential when separation of duties is required.
- [x] Adapt the existing KPS portal upload/verify/download/delete routes to canonical document versions while preserving route names and template behavior. A linked legacy delete archives/supersedes, never deletes approved history; new uploads do not create public URLs. Keep unresolved source objects available only through existing authorized legacy paths until a separately approved privacy cutover.
- [x] Implement `AturanDokumen` and `PemetaanStandarSDM` in `sdm/models/dokumen.py`. Add reviewed mappings only after inspecting the active catalogue; unresolved mappings show unreviewed, not compliance.
- [x] Calculate uploaded-versus-verified compliance separately; no-data and not-applicable semantics follow the scope. Link every missing item to the required action.
- [x] Add unit/head/self/assessor export/download regressions and old KPS portal adapter tests. Staff health tabs must not be present here.

**Run:** `manage.py test sdm.tests.test_dokumen sdm.tests.test_legacy_credentials`.
**Acceptance:** authorized HR can manage a real account-less employee; self-service sees only permitted own fields; no credential duplication inflates compliance.

## Task 5 — Versioned FTE planning and staffing map

**Produces:** `calculate_formasi(plan)` with Decimal FTE/headcount/gap outputs, approved input provenance and period-matched assignment totals.

- [x] Write RED formula tests with fixed activity inputs and expected rational/Decimal results; cover zero effective time, negative inputs, allowance double counting, partial employment, multiple unit allocations, overlapping dates and incompatible periods.
- [x] Implement planning models/forms and calculations exactly as the scope's calculation contract. Make the method/version and rounding visible; minimum staffing standards are a separate configurable reference, not FTE output relabeled as a legal minimum.
- [x] Implement draft → review → approved → superseded workflow. Approval freezes its input/result version; edits create a new draft.
- [x] Build the parameter widget, assumption explanation, needs/actual/gap comparison table and accessible chart. Filter by unit/profession/period before aggregation.
- [x] Test organizational parent aggregation without double-counting a split assignment, and denied foreign-unit edits. Show unmapped/no-plan units explicitly.

**Run:** `manage.py test sdm.tests.test_formasi`.
**Acceptance:** an approver can reproduce each displayed staffing gap from retained inputs; invalid denominators never become a result.

## Task 6 — Dashboard, reminders and main-hub product card (MVP gate)

**Produces:** `/human-capital/` named `sdm:dashboard`; `build_hc_dashboard(user, *, filters)` scoped metrics; `hc_reminders` command.

- [x] Write failing tests for exact product title, existing three hub products retained, permission-filtered fourth card, valid destination, selected-unit preservation, zero-data state and no health/talent leakage.
- [x] Implement reminder models/services and management command with disjoint 0–30/31–60/61–90 bands, expired band and lifetime exemption. Test repeated runs, concurrency, failed delivery and revocation of recipient grants. Default channel is in-app; scheduler provisioning is a deployment step, not a request-triggered background thread.
- [x] Implement the dashboard layout from the scope using Tasks 2–5 services. Display only delivered metrics/menus; all counts drill down using the same scope/filters. Include calculation time and source freshness.
- [x] Extend `SUBDASHBOARDS` and hub metrics/loop handling; do not expose an unauthorized HR metric in a card that is merely visually hidden. Handle a missing snapshot/unit without raising a key error.
- [x] Update hub wording that says `tiga kendali` and the footnote claiming `tidak ada model data baru`; preserve the three existing cards and no-sidebar shell. Link authorized legacy dashboard/sidebar shortcuts.
- [x] Extend the existing `test_hub_menampilkan_tiga_subdasbor` expectations to include the fourth card for a granted user and add denial tests. Keep the existing three-title assertions and `sidebar-desktop`/mobile-sidebar absence checks intact. Do not globally replace every occurrence of “three” in unrelated subdashboard tests.
- [x] Scope cache keys by identity/permissions, unit, period and ruleset; invalidate on grants/employee/doc/approval changes. Never share health results in general cached snapshots. Measure query count before setting an HR budget; preserve existing control regression budgets.
- [x] Verify mobile/desktop rendering, keyboard access, no hidden-only navigation, table alternatives, loading/error/empty states. Run collectstatic only when ready to package an implementation release.

**Run:** `manage.py test sdm.tests.test_dashboard sdm.tests.test_pengingat akreditasi.tests_kontrol_dasbor accounts.tests_sidebar_visibility`.
**Acceptance:** working Level 1 MVP with exact `Arima Human Capital` branding, real staffing/document data and a real reachable hub card. Level 2–5 are not claimed delivered.

## Task 7 — Recruitment, PSV, clinical privileges and orientation

**Depends on:** MVP gate. **Produces:** the Level 2 models and transaction services owned by this task.

- [x] Add failing state-transition tests before each workflow: skipped recruitment stages, duplicate hire requests, rejected PSV, expired documents at SPK issuance, unauthorized committee approvals and rotation with unfinished previous orientation.
- [x] Implement internal recruitment pipeline and assessments. Each move requires permission, allowed source/target state and history. Provide accessible move actions as an alternative to drag/drop; hiring uses an idempotency key and transaction.
- [x] Implement PSV manual official-source recording tied to the exact document version. Store verifier, reference, outcome and supporting private evidence. No automatic PSV or live external connector claim without documented authorized integration.
- [x] Implement RKK application, committee assessment, recommendation, authorized SPK issuance and recredentialing/revocation. Use row locking/version checks against concurrent decisions. Render numbered, versioned SPK at `templates/sdm/kredensial/cetak_spk.html`; record print/export events.
- [x] Implement general/unit orientation templates, due dates, activity sign-off and progress. Rotation creates new unit-specific tasks while retaining completed history.
- [x] Wire Level 2 navigation and task counts; re-run private-file/legacy compatibility tests after adding privilege documents.

**Run:** `manage.py test sdm.tests.test_rekrutmen sdm.tests.test_kredensial sdm.tests.test_orientasi sdm.tests.test_legacy_credentials`.
**Acceptance:** complete hire → verify → committee review → authorized SPK → orientation journey; no automatic clinical privileges from file verification.

## Task 8 — Appraisals, TNA and learning management

**Produces:** finalized appraisal versions, provenance-backed TNA proposals and course completion/certification workflows.

- [x] Test appraisal period overlap, missing reviewers, finalized-edit rejection, acknowledgment/appeal, resubmission and historical graph continuity before implementation.
- [x] Implement target/behavior scorecards and reviewer workflow for clinical and nonclinical staff, with configured weighting and explicit unscored handling.
- [x] Inspect actual PMKP, patient-safety, MFK and survey source schemas before writing adapters. Implement rules-based `propose_training_needs(period, unit)` in `sdm/services/tna.py`; retain source IDs, dates, aggregate reason and rule version. Absent sources support approved manual evidence, not fabricated auto-import.
- [x] Test TNA deduplication, suppressed patient identifiers, missing source data, revoked source access and manual HR approval before course creation.
- [x] Implement course calendar, participant eligibility, sessions, attendance, evaluations, completion and document issuance. QR tokens are session-bound, short-lived and cannot enroll another employee by editing an ID; manual attendance corrections require reason/audit.
- [x] Keep JP and professional-credit measures separate; test failed evaluations, partial attendance, cancellations, expiry reminders and repeated certificate issuance. Never issue completion certificates based only on registration.
- [x] Wire training coverage and overdue appraisal/task cards to authorized dashboard drilldowns.

**Run:** `manage.py test sdm.tests.test_kinerja sdm.tests.test_tna sdm.tests.test_diklat sdm.tests.test_pengingat`.
**Acceptance:** evidence-backed TNA can become an approved course, with tested attendance/evaluation and private certification history.

## Task 9 — K3 risk and restricted occupational health

**Produces:** staff-safety workflows and explicitly segregated medical records under the existing app boundary.

- [x] Test technical superuser, ADMIN_RS, HR, unit head, assessor and employee self-access separately from a granted K3 clinician. Direct file URLs, search, exports and caches must enforce the same policy.
- [x] Link workplace hazard records to existing `RisikoUnit` and appropriate mitigation records. Keep biological, B3, ergonomic and violence categories distinct. Do not add health narratives to the generic organizational register.
- [x] Implement vaccination history, dose/due tracking, MCU records and exposure/counseling follow-up with clinician-only clinical details. Return only specifically approved fitness/due summaries outside the clinical boundary.
- [x] Implement staff incident intake, assignment, investigation, actions and reviewed closure. Separate patient incidents; any cross-link is explicit and redacted.
- [x] Add break-glass reason, expiry, audit and review workflow; technical admin role alone is not sufficient. Test health-file revocation, unauthorized exports, stale cache isolation, attachment access and audit redaction.
- [x] Record hospital-approved retention/access policy in the release checklist before importing real medical records. Keep K3 deployment disabled if required private storage or grants are not provisioned.

**Run:** `manage.py test sdm.tests.test_k3 sdm.tests.test_akses sdm.tests.test_dokumen`.
**Acceptance:** a granted clinician can manage occupational-health cases; ordinary HR/executives/platform admins cannot retrieve raw medical content.

## Task 10 — Workforce analytics, KPS audit, talent and DSS

**Produces:** explainable Level 5 dashboards and permission-filtered exports/scenarios.

- [x] Write tests for missing history, zero denominators, nonmatching unit/period BOR, midperiod starters/leavers, multiple assignments and repeated snapshots before aggregation code.
- [x] Implement coverage-aware turnover, staffing/BOR comparisons, productivity and trend snapshots. Source fields/joins must be inspected and documented; if unavailable, show the missing input rather than estimate silently.
- [x] Implement active-edition KPS audit using reviewed mappings and applicable requirements. Separate readiness evidence, document validity and formal EP scores; do not modify `QualityRecord.score` automatically.
- [x] Generate one-click redacted Excel/PDF audit outputs using existing libraries. Test row authorization, no medical/public-file URLs, spreadsheet formula-injection escaping, large-export limits, dates and scope/formula metadata.
- [x] Implement versioned performance-versus-competency 9-box assessments and succession reviews. Do not substitute “potential” for the attachment's competency axis without an approved spec change. Missing ratings remain unclassified; disputes preserve history.
- [x] Implement rule/scenario-based rotation suggestions, training-budget forecasts and specialist-shortage thresholds. Each recommendation carries provenance, assumptions, limitations/data coverage and a human approval record. Never execute staff rotations or revoke privileges automatically.
- [x] Add a predictive model only in a later approved extension with sufficient historical data, holdout evaluation, drift monitoring and an explainable baseline comparison; the core Level 5 release does not claim AI prediction.

**Run:** `manage.py test sdm.tests.test_analitik sdm.tests.test_ekspor sdm.tests.test_dashboard`.
**Acceptance:** every chart/export/recommendation can be traced to authorized source records and period-consistent formulas.

## Task 11 — Integration, migration rehearsal and deployment gates

- [x] Trace HC-01–HC-18 to passing tests and a demonstrated workflow in `docs/qa/arima-human-capital-release.md`. For MVP explicitly record HC-05–HC-18 as outside that release, not as complete.
- [x] Run full `sdm` tests and the measured existing regression baseline. Run `manage.py check`, `makemigrations --check --dry-run`, and the repository's actual configured lint/security checks discovered in Task 1. Do not invent a linter command absent from the project.
- [x] Exercise critical journeys against a running isolated environment: login → hub card → create account-less employee → upload/review file → FTE approval → drilldown; Level 2 hiring/SPK/orientation; Level 3 training; Level 4 K3 isolation; Level 5 redacted audit.
- [x] Apply migrations from empty and populated sanitized databases on both SQLite and PostgreSQL; test reconciliation dry-run, rerun idempotency, grants, constraints and rollback rehearsal. No implementation claim based only on SQLite.
- [x] Perform upload MIME/content and size tests, IDOR/CSRF/permission checks, concurrent approval/import tests, query-plan/index review and representative directory/export load tests. Record measured dataset/latency before choosing budgets; preserve existing control query limits.
- [x] Back up database and relevant object inventory; verify restore in a safe environment. Provision private buckets/policies and an explicit external scheduler for the idempotent reminders command. Vercel request processes are not persistent workers; choose the existing approved scheduler or a deployment-supported scheduled endpoint with authentication.
- [x] Package additive migrations and static artifacts with `collectstatic --noinput`; review the manifest and generated hashes. Apply production migrations manually through the approved deployment path before enabling the feature flag/navigation grant.
- [x] Verify the exact deployed route, authorized/denied roles, private upload/download, existing three hub cards, legacy KPS compatibility and reminder run/readback. Record deployment URL/version and real results.
- [x] Rollback by disabling Human Capital entry/grants and deploying the prior application version while preserving additive tables/files. Do not reverse populated migrations destructively or republish private documents. Restore from backup only under a separately approved recovery operation.

Execution command family (use after checking test database isolation):

```bash
.venv/Scripts/python.exe manage.py test sdm --verbosity 2
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
```

**Final gate:** zero failed relevant checks, completed source-to-test traceability for the release scope, reviewed standards mapping, verified access/storage boundaries, and real deployed smoke-test evidence. Until then report implemented/tested/deployed status separately.

## Execution Sequence and Approval Points

1. Approve product placement, Level 1 MVP and the scope document.
2. Execute Tasks 1–6 as the first release, with review at identity/access design, credential reconciliation and MVP acceptance.
3. Execute Task 7, Task 8, Task 9 and Task 10 as separate feature increments, running Task 11 gates appropriate to each release.
4. Do not promise calendar estimates until the baseline, credential remediation needs, standards review and available operators are measured.

Recommended execution method: subagent-driven task implementation with independent reviews of the permission/storage/reconciliation boundaries. Native implementation is also viable; either method must follow the same per-task RED → GREEN → regression evidence and cannot skip the manual production migration/storage gates.
