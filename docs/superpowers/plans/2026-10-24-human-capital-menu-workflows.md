# Human Capital Menu and Operational Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing `Arima Human Capital` module match the ten functional groups in `struktur menu ideal Human capital.docx`, with trustworthy data, complete operator/self-service journeys and approved accreditation outputs.

**Architecture:** Extend the existing Django app and reuse its employee, placement, document, staffing, recruitment, credential, orientation, training, K3 and analytics models/services. Replace the five maturity-level presentation with role-filtered functional navigation without removing existing capabilities. Deliver core personnel/compliance workflows first; isolate the newly requested shift/presence/leave and RME-privilege integration behind separate release gates.

**Tech Stack:** Existing Django/templates/Bootstrap, SQLite and PostgreSQL, Supabase private storage, openpyxl/reportlab. Rules and explicit source data precede optional predictive analytics or third-party integrations.

**Spec:** `C:/Users/cubeb/Downloads/struktur menu ideal Human capital.docx`; shared `2026-10-24-arima-improvement-baseline.md`; identity/document contracts in `2026-10-24-staff-intake-efile.md`; edition/evidence contracts in `2026-10-24-starkes-transition-hardening.md`, all plans in this directory.

## Global Constraints

- Proposed work only; no implementation, personnel import, catalogue cutover, grant provisioning, commit or deployment is authorized by producing this plan.
- Preserve `Arima Human Capital`, `/human-capital/`, all existing `sdm` route names, the four-product control hub and the existing accreditation/clinical workflows.
- Keep 425 seeded employee identities and 219 organizational units intact; use B1's reviewed provenance for operational denominators, not a number-prefix heuristic at request time.
- Do not seed an HR rules catalogue until B3 fixes precise document matching. Do not publish numbered KPS claims until track C verifies the actual active instrument and reviewed mappings.
- All UI copy is Bahasa Indonesia. Empty configuration is `Belum dikonfigurasi`; insufficient historical data is `Belum dapat dihitung`; no applicable requirement is `Tidak berlaku`, not 100%.
- Use real capability plus scope checks on server list/detail/write/download/export boundaries. Absence of unit or employee link never means global access.
- Existing roles are `SUPER_ADMIN`, `ADMIN_RS`, `KOORDINATOR_POKJA`, `KEPALA_UNIT`, `STAF_NAKES`, `ASESOR`. Committee, Diklat, K3 clinician and director are scoped capabilities/appointments, not invented global role values.
- Preserve explicit occupational-health grants and break-glass; ordinary HR/admin status does not reveal MCU, vaccination or exposure clinical content.
- Decimal arithmetic and explicit same-period/same-unit calculation contracts; hours, JP and SKP credits are separate units.
- Retain existing public accreditation-evidence workflow, but never publish an HR private key/URL or unredacted health record into it.
- No payroll calculation, biometric hardware integration, paid geofence service, certified-signature-provider claim or predictive staffing automation is included.

## Review Focus

1. Hospital-wide grants, own-profile-only staff and authorized read-only K3 reviewers must see the right navigation without broadening their write scope.
2. More than 200 employees, mixed demo/real data, incomplete rule configuration and duplicate document versions must not distort dashboard or audit denominators.
3. Unit-specific BOR, dated staffing and annual training totals must reject missing/incompatible source coverage rather than reuse a hospital/current snapshot.
4. A credential may be valid only for one profession, site, action and interval; direct EMR POST, expiry/revocation and trainee countersignature must respect those boundaries.
5. Overnight shifts, duplicate attendance, declined location access, concurrent leave approval and staff without accounts must work without duplicating hours or losing history.

## Current capability and gap matrix

| Requested group | Existing implementation | Actual remaining work |
|---|---|---|
| Dashboard & Analytics | `build_hc_dashboard`, KPI/reminder UI, cached dashboard | Real-data provenance; full denominator; employment categories; 7-day urgency; correct annual training and historical metrics |
| Planning & staffing | `RencanaFormasi`, `AktivitasBebanKerja`, `HasilFormasi`, activity FTE and approval | Approved workload inputs/coverage, unit/profession period selection, employment capacity, reviewed WISN method |
| Database & e-file | UUID staff, dated placements, private versions/rules | Track B's complete intake/import, exact document kinds, education/employment/license data and trainees |
| Attendance & shift operations | No roster/geofence workflow in `sdm/urls.py` or current models | New optional bounded workforce-operations increment, not duplicate training attendance |
| Credentialing & privileges | PSV, requests, free-text privileges, immutable decision, numbered printable SPK | Staff submission, committee/profession separation, action catalogue, issuance UI/recredentialing, version validation and live privilege checks |
| Performance & orientation | Period/appraisal/TNA/training services, orientation assignment/completion routes | Complete creation/edit/assessment journeys; explicit OPPE/FPPE cases; annual hours and individual acknowledgments |
| Job descriptions & RME access | Job text and generic document storage; patient module decorator | Versioned job descriptions/acceptance; approved action mapping and server-side clinical enforcement |
| Staff health & safety | Existing K3 hazards/MCU/immunization/incidents/break-glass models/services | Usable scoped record/review/follow-up UI; redacted status reminders; operational data and role acceptance |
| Self-service | Own credential path in storage; personal reminders | Own-profile portal without broad HR grant; reviewed corrections, training requests and leave workflow |
| Reports | Existing aggregate XLSX/PDF audit and coverage-aware snapshots | Exact active-edition mappings, sample file packs, annual training, local SIP/STR status and redacted evidence publication |

### Root causes to fix before adding more cards

- `sdm/services/dashboard.py:83` evaluates `employees[:200]`; a dashboard over a larger population silently reports a sample as the overall result. Its metric is percent of fully complete staff, not the separate ratio of satisfied requirements. Both must be explicitly named.
- Training coverage (`dashboard.py:60-72`) accepts any `LULUS` participation across past sessions, without annual period or required-course applicability. This does not implement twenty training hours/year.
- `sdm/services/analitik.py:27-52` labels current inactive/active counts as turnover while ignoring the supplied date window; the employment history needed for period departures/average headcount is missing.
- `compute_bor` accepts `unit` but queries all RANAP beds/admissions (`analitik.py:55-105`); its capacity denominator is current bed status, not historical available bed-days. `staffing_bor_comparison` accepts contained subperiods, not exact period equality (`136-170`). Do not surface these as unit-period analytics until corrected.
- HC navigation (`sdm/context_processors.py:16-24`) excludes null-unit hospital grants even though `sdm/akses.py:43-47` explicitly supports them. It exposes K3 only for write capability. A menu refactor must unify the resolver, not copy that mismatch.
- `compliance_audit` ties mapping selection to `standard_item__record__unit` (`analitik.py:183-187`). A reviewed requirement mapping should not disappear merely because an EP has no `QualityRecord`, and the current query does not enforce the active framework.
- Printable SPK and generic appraisal services are not a certified electronic signature, OPPE or FPPE. `pasien/views.py` clinical writes such as `cppt_tambah:393` and `resep_buat:536` have no HC privilege dependency.

### Overlap and exclusions

The earlier `2026-10-23-arima-human-capital.md` delivered the app's foundation. **This plan does not implement that plan again.** It closes functional gaps and expands the newly supplied menu requirements. Track B owns canonical identity, typed documents, five-step intake/import and activation. Track C owns edition/archiving/remapping. This plan consumes their interfaces and does not create a second staff master, rule engine or accreditation catalogue.

Unrelated patient billing, drug-number generation, risk visualization, existing QA-fleet data creation and broad source-file refactors: **do not implement, do not fix while here**. Patient authorization changes below are limited to the explicit clinical-privilege boundary and its existing module/object guards.

## Target navigation — proposed UI, not a claim of current routes

```text
Arima Human Capital
├─ Dasbor & Analitik
│  ├─ Ringkasan, EWS & Tugas
│  └─ Analitik, Talent & Skenario [existing advanced features retained]
├─ Perencanaan & Formasi
│  ├─ Beban Kerja, Kalkulator FTE, Peta & Gap
│  └─ Usulan Formasi, Rekrutmen & Seleksi
├─ Database & e-File
│  ├─ Direktori, Tambah Staf, Impor Excel
│  ├─ Profil, Legalitas, Pendidikan & Riwayat
│  └─ Mahasiswa / Residen / Magang
├─ Presensi & Operasional Shift [optional release]
│  ├─ Jadwal Dinas, Presensi & Koreksi
│  └─ Jam Efektif & Ekspor Remunerasi
├─ Kredensial & Kewenangan Klinis
│  ├─ Pengajuan Saya, Verifikasi & Komite
│  └─ RKK, Penerbitan/Rekredensial SPK & Peta Kewenangan
├─ Kinerja, Orientasi & Pengembangan
│  ├─ Orientasi, KPI/SKP, OPPE & FPPE
│  └─ TNA, Kalender Diklat, Kehadiran & Sertifikasi
├─ Uraian Tugas & Akses RME
│  ├─ Master/Versi Jobdesc & Penerimaan Staf
│  └─ Kebijakan Akses Klinis & Riwayat Keputusan
├─ Kesehatan & Keselamatan Staf
│  ├─ Risiko K3, Insiden & Tindak Lanjut
│  └─ MCU / Imunisasi [explicit clinical grants]
├─ Portal Mandiri
│  ├─ Profil Saya, Dokumen & Notifikasi
│  └─ Usulan Pelatihan & Cuti [leave is optional release]
└─ Laporan & Bukti Akreditasi
   ├─ Audit e-File, STR/SIP & Jam Pelatihan Tahunan
   └─ Paket Sampel KPS & Publikasi Bukti Teredaksi
```

Render only authorized delivered destinations; an optional group may show a non-clickable `Belum diaktifkan` status to authorized planners, not a working-looking fake page. Retain orientation, training, recruitment and advanced analytics from the previous five-level layout.

## Proposed new interfaces and file ownership

Existing services stay in their actual files, including workflow implementations in `sdm/services/rekrutmen.py` and analytics exporters in `sdm/services/analitik.py`. Read any similarly named thin modules before changing ownership.

| Task | Modify existing | Create NEW |
|---|---|---|
| A1 | `sdm/services/dashboard.py`, `analitik.py`; `sdm/models/formasi.py`; `sdm/signals.py`; `test_dashboard.py`, `test_analitik.py`, `test_ekspor.py`, `test_formasi.py` | `sdm/services/metric_scope.py`, `sdm/tests/test_metric_scope.py` |
| A2 | `sdm/context_processors.py`, `sdm/views.py`, `sdm/akses.py`, `templates/sdm/_navigasi.html`, `dashboard.html`, `templates/includes/sidebar.html`; existing sidebar/dashboard/route tests | `sdm/navigation.py`, `sdm/tests/test_navigation.py` |
| A3 | `sdm/models/pengingat.py`, `sdm/management/commands/hc_reminders.py`, document/dashboard views and tests | `sdm/services/legalitas.py`, `sdm/tests/test_legalitas.py` |
| A4 | `sdm/models/formasi.py`, `sdm/services/formasi.py`, staffing forms/templates/tests, recruitment creation link | `sdm/models/beban_kerja.py`, `sdm/services/wisn.py`, `sdm/tests/test_wisn.py` |
| A5 | `sdm/models/kredensial.py`, `sdm/services/rekrutmen.py`, credential forms/views/URLs/templates; `test_rekrutmen.py`, `test_level_actions.py` | `sdm/tests/test_clinical_privilege_workflow.py` |
| A6 | `sdm/models/__init__.py`, `sdm/akses.py`, `pasien/decorators.py`, targeted writes in `pasien/views.py` and clinical templates | `sdm/models/uraian_tugas.py`, `sdm/services/clinical_access.py`, `sdm/jobdesc_views.py`, `templates/sdm/uraian_tugas/{list,detail,form}.html`, `sdm/tests/test_jobdesc.py`, `pasien/tests_clinical_privileges.py` |
| A7 | `sdm/models/kinerja.py`, `diklat.py`, training/appraisal/orientation services/forms/views/templates; existing performance tests | `sdm/models/evaluasi_klinis.py`, `sdm/services/evaluasi_klinis.py`, `sdm/tests/test_oppe_fppe.py`, `sdm/tests/test_annual_training.py` |
| A8 | `sdm/models/k3.py`, `sdm/services/k3.py`, health forms/views/URLs/templates, `sdm/tests/test_k3.py` | `sdm/tests/test_k3_journeys.py` |
| A9 | `sdm/akses.py`, `sdm/urls.py`, reminder and profile navigation | `sdm/portal_views.py`, `sdm/models/layanan_mandiri.py`, `sdm/services/layanan_mandiri.py`, `templates/sdm/portal/{index,pengajuan}.html`, `sdm/tests/test_staff_portal.py`, `sdm/tests/test_leave.py` |
| A10 | HC capability configuration across `accounts/models.py`, existing grant choices/scope validation and navigation; staffing adapters | `sdm/models/presensi.py`, `sdm/services/presensi.py`, `sdm/presensi_views.py`, `templates/sdm/presensi/{jadwal,presensi,koreksi}.html`, `sdm/tests/test_presensi.py` |
| A11 | `sdm/services/analitik.py`, `sdm/services/ekspor.py`, `sdm/views.py`, `sdm/urls.py`, report templates/tests; reuse `PemetaanStandarSDM` | `sdm/services/publikasi_bukti.py`, `sdm/tests/test_kps_evidence_pack.py` |
| A12 | Existing HC release/private-storage runbooks | `docs/qa/hc-improvement-release.md`; generated migrations and collected static artifacts |

All new models must be exported through `sdm/models/__init__.py`; all URL registrations stay under `sdm/urls.py`, with the patient clinical routes retaining their existing namespace. Every task owns the migrations for its model changes; regenerate dependency numbering from the actual graph. Update `sdm/admin.py` only for models the task adds, with clinical/private objects restricted. Shared capability additions must update both profile permission forms/configuration and `HcGrant` choices; a boolean alone does not grant scope.

New interfaces implemented by their owner tasks:

- A1: `resolve_metric_population(user, *, unit, as_of, origin_policy) -> QuerySet[Pegawai]` and explicit metric metadata `{value, numerator, denominator, scope, period, coverage, is_available, reason}`. Historical scope is evaluated at the requested dates, not only today's placements.
- A3: `legal_status(employee, *, as_of, practice_site) -> list[dict]`; it consumes B2/B3 typed permits/document versions and existing SPK, never filename matching.
- A4: `calculate_wisn(plan) -> dict` with approved available working time, standard workloads, category/individual allowances and versioned method. Existing `calculate_formasi` continues to mean activity FTE.
- A5: `effective_privileges(employee, *, unit, at) -> set[str]` of controlled action codes; committee and issuance events reference immutable approved snapshots.
- A6: `require_clinical_action(user, *, action_code, encounter, at=None) -> None` raises `PermissionDenied` without an applicable authority; it is additive to patient-module/object authorization.
- A7: `annual_training_summary(employee, *, year, policy) -> dict` returns clock minutes/hours, JP, SKP, completion and coverage separately; `open_fppe(*, actor, employee, unit, trigger_ref, review_deadline) -> case` creates a restricted review case, not an automatic sanction.
- A9: `submit_staff_request(*, actor, kind, payload, idempotency_key) -> request`; `decide_staff_request(request, *, actor, decision, reason) -> request`, scoped by employee/unit and request type.
- A10: `record_attendance(*, actor, shift_id, event, recorded_at, position, idempotency_key) -> event`; reviewed corrections are append-only. A9 and A10's capabilities and models are separate from Diklat attendance.
- A11: `build_kps_pack(*, actor, employee_ids, framework_id, as_of) -> artifact` checks export permissions and reviewed active-edition mappings; `publish_kps_artifact(*, actor, artifact, requirement_id) -> EvidenceFile` publishes only a reviewed sanitized derivative and records its private-source audit reference.

## Task A1 — Correct metrics and origin/period scope before expanding dashboard (P0)

**Depends on:** B1 provenance policy; B2 employment history and B3 exact matching for full compliance activation.

- [ ] Add RED regression tests to existing dashboard/analytics suites: 201 eligible employees with a failing last employee; mixed demo/real/unclassified rows; training outside the year; inactive employment outside report dates; two unrelated units with different beds/visits; approved staffing plan whose dates are contained but not equal.
- [ ] Implement `resolve_metric_population`, remove the silent 200-row truncation, and count requirements and fully complete employees as distinct named metrics. Use scoped batching/prefetch/query aggregation without changing the denominator to meet a response-time budget.
- [ ] Correct turnover using dated separations and documented average-headcount sampling; return unavailable without coverage. Correct BOR through reviewed unit-to-room mapping and effective-dated bed capacity; if those sources are absent, disable the unit-period result instead of querying hospital totals. Require matching staffing/BOR windows or explicit reviewed comparable aggregation.
- [ ] Exclude inactive/demo/unclassified employment from production FTE calculations using approved as-of policy; preserve historic approved results and calculation version. Recalculate a new version, never overwrite prior approvals. Validate total allocations against employment FTE from B2, not merely an unconditional 1.00 ceiling.
- [ ] GREEN gate: all new metric cases pass and no signed URL, NIK or health detail enters caches. Cache keys/invalidation cover period, origin policy, grants, rules, completion and source revisions.

Required regression using the existing dashboard suite setup, with 201 scoped employees and one active typed requirement created in this task:

```python
metrics = build_hc_dashboard(self.user, filters={})
self.assertEqual(metrics['compliance_scope_count'], 201)
```

Do not silently replace `compliance_pct` semantics: label its existing staff-completion meaning and add a separately named requirement-completeness ratio. If renaming existing context keys, update every template/test usage in this same task.

## Task A2 — Ten-group navigation and permission parity (P1)

**Depends on:** no new workflow models; destinations stay feature-gated until their owner task passes.

- [ ] Add RED menu tests for each existing role plus explicit hospital grant, expired/revoked grant, null-unit head, own-only staff, scoped committee, K3 read-only clinician, assessor and technical superuser without health grant. Copy profile/config/grant setup from `sdm/tests/test_dashboard.py:27-57`.
- [ ] Implement one navigation registry in `sdm/navigation.py`, consumed by context processor, dashboard cards and `_hc_navigation`; use the same authorization resolver as object access. A hospital-scope `unit=None` grant must not disappear from menu discovery.
- [ ] Group current links into the tree above. Keep all existing route names and retain recruitment, orientation, TNA/training, talent/scenarios. Give each group an accessible heading and keyboard-expandable compact menu rather than ten unrelated button rows.
- [ ] Update existing five-level-card and sidebar assertions in `test_dashboard.py`, `test_level_routes.py`, `accounts/tests_sidebar_visibility.py`, `akreditasi/tests_kontrol_dasbor.py`; preserve the control hub's no-sidebar shell and original three other products.
- [ ] GREEN gate: desktop/mobile navigation, no broken URL reverse, no dead link to an undelivered group; direct URL tests prove the hidden/visible menu is not the enforcement boundary.

## Task A3 — Legal EWS, contracts and urgent reminders (P1)

**Depends on:** B2/B3 typed licenses/employment/documents, A1 population scope.

- [ ] Add RED tests for expired, due today, 7/8/30/31/90/91 days, lifetime STR, contract end, revoked SPK, another practice-site SIP and replaced versions.
- [ ] Extend expiry display to disjoint bands `expired`, `0–7`, `8–30`, `31–90` while retaining old 31–60/61–90 reporting only where explicitly labelled. Treat the source's three months as a documented 90-day operational window, not silently mix calendar months and days. Avoid double notifications during the transition from legacy bands.
- [ ] Compute legal status from current reviewed licenses and SPK interval/revocation, not generic upload status. Include missing-file/source-unverified states. A verified valid document near expiry remains valid with an urgency warning; no-date unknown and lifetime are distinct.
- [ ] Extend `PengingatSDM` idempotency to recipient + target UUID/version + policy/band, store target identity for non-document reminders, and resolve/archive stale unread reminders after completion/replacement/revocation. Recheck recipient active status/scope when listing and delivering; no health content in general reminders.
- [ ] GREEN gate: repeat/concurrent `hc_reminders` produces no duplicate recipient-target warning; employee/HR queue drill-down obeys identical scope. Schedule through approved external infrastructure, not request threads; dry-run is nonmutating.

## Task A4 — Workload planning, recruitment link and separate WISN method (P1/P2)

**Depends on:** B2 real employment capacity, A1 trustworthy population/scope.

- [ ] Add RED tests for period-specific workload, no historical coverage, support allowance counted twice, 0 denominator, part-time/split assignments, unit descendants and explicit shortages linked to recruitment proposals.
- [ ] Add `sdm/models/beban_kerja.py`: approved workload snapshots with unit/profession/period, operating hours, bed-capacity/BOR source references, visits/service volume and standard-minute provenance. Store unknowns as unknown; beds/BOR are contextual inputs, not unexplained FTE multipliers.
- [ ] Preserve current activity FTE. Explain required FTE, rounded headcount, actual allocation and gap; choose the approved plan for the selected unit/profession/period rather than showing all historic approvals together. Link a staffing proposal to an existing `Lowongan`, retaining approval/source assumptions and not automatically hiring.
- [ ] For the separately approved WISN increment, implement `calculate_wisn` with an independently reviewed formula/worksheet for available working time, standard workload, category allowance factor and individual allowance. Save method-specific raw inputs/version/results; tests compare to an approved hospital worksheet. Reject unsupported combinations instead of calling activity FTE WISN.
- [ ] GREEN gate: `test_formasi`, new `test_wisn` and recruitment compatibility pass; unsupported WISN stays visibly unavailable until a reviewed calculation policy and reference worksheet are supplied. Approval freezes inputs, results and data coverage.

## Task A5 — Self-submission, committees, issuance and trainees (P1/P2)

**Depends on:** B3 reviewed typed documents, A3 legal status. A6 consumes this task's privilege codes.

- [ ] Add RED self/committee/issuer tests: no self-approval, wrong profession/case denied, revoked grant, changed source version, missing PSV, previous SPK, expired credential and duplicate issue request.
- [ ] Extend current request/PSV/decision workflow with controlled clinical action codes and explicit committee appointment/profession/case scope. Separate submission, recommendation and issuance authorization; preserve immutable decisions and source document versions. Keep free-text legacy privileges visible as unclassified, never infer an action entitlement from wording.
- [ ] Expose staff-owned application/self-assessment, committee work queue, approval-to-issuance form, numbered SPK download, recredentialing and revocation with audit/reason. `effective_privileges` checks approved snapshot, site, unit, time and revocation. Printed authenticated output may include a validation code/hash; do not label it certified digital signature without a real provider.
- [ ] Add trainee placement fields to employment/credential extensions: institution, program/cohort, start/end, supervisor employee, temporary allowed action codes and countersignature requirement. Enforce active qualified supervisor and no independent prescribing/sign-off; trainees do not inflate independent qualified-staff counts.
- [ ] GREEN gate: existing recruitment/credential tests plus `test_clinical_privilege_workflow` pass; trainee end date/supervisor revocation removes temporary authority immediately; archived SPK and earlier RKK stay readable to authorized reviewers.

## Task A6 — Versioned job descriptions and controlled clinical RME enforcement (P1 design, P2 rollout)

**Depends on:** B2 placements, A5 effective privileges; clinical owner approval before enforcement.

- [ ] Add RED tests for position/version-specific jobdesc assignment and individual acknowledgment, a new revision requiring renewed acknowledgment, transfer preserving history, direct foreign-unit writes, no active SPK, revoked action and trainee supervisor/countersignature.
- [ ] Create `MasterUraianTugas` and `PenerimaanUraianTugas` in the new model file: versioned content, position/unit/profession applicability, approval/effective interval and employee acknowledgment of the exact revision. Link sanitized jobdesc documents via existing e-file, not a new public file store.
- [ ] Implement `require_clinical_action`. Maintain explicit action-code-to-EMR-operation mapping. Enumerate actual clinical writes first (`cppt_tambah`, `igd_cppt_quick_add`, `resep_buat`, DPJP verification and other reviewed signing paths); apply existing module/encounter/object guards **and** privilege guard server-side, not only hide buttons. Form-supplied profession/name cannot choose the authority of the author.
- [ ] Rehearse report-only enforcement on a sanitized staff mapping, resolve legitimate legacy clinicians and approve coverage with the clinical owner. Then enable enforcement per approved action/unit. Emergency exceptions use a separately approved time-bound, reasoned and audited clinical policy; the existing occupational-health break-glass does not confer prescribing authority.
- [ ] GREEN gate: `pasien.tests_clinical_privileges` and existing patient-module/clinical suites pass with explicit doctor, nurse, pharmacist, trainee, unit head, assessor and admin expectations. Technical admin/module access does not automatically authorize clinical signing. Read-only patient access and existing records remain available under their existing legitimate scope.

## Task A7 — Complete performance/orientation journeys, OPPE/FPPE and annual learning (P2)

**Depends on:** B2 employment dates, A5 privilege identity, A1 period scope.

- [ ] Add RED tests for creating/editing a draft appraisal with criteria, finalization immutability, acknowledgment/appeal, orientation assignment/completion, annual training eligibility, repeated attendance and overlapping sessions.
- [ ] Finish scoped operator forms for period/appraisal/item input and training session/participant/attendance/evaluation/certificate management; current service-only pieces become usable journeys. Keep TNA source references and manual approved findings; no patient-identifiable narrative is exposed to HR.
- [ ] Implement `annual_training_summary`: count accepted attendance/completion minutes in Asia/Jakarta annual windows, deduplicate course participation and report clock hours, JP and SKP separately. Start policy target at the source's 20 clock hours/year only after hospital approval; define eligibility/exemptions/proration explicitly. Incomplete history reports partial coverage, not noncompliance as a final fact.
- [ ] Add `EvaluasiPraktikKlinis` and `KasusFPPE` in the new model file with type `OPPE/FPPE`, employee/unit/privilege snapshot, period or trigger reference, reviewer, restricted indicators, recommendation, follow-up and immutable finalized revision. `open_fppe` accepts approved references for new privileges/incidents/other reviewed triggers without automatic punitive decisions or score changes.
- [ ] GREEN gate: `test_oppe_fppe`, `test_annual_training`, current performance/training/orientation tests and operator E2E pass. OPPE/FPPE is visibly distinct from generic KPI/SKP and recredential recommendations require human committee review.

## Task A8 — Make existing K3 services usable without widening health access (P2)

**Depends on:** hospital-approved health record/access/retention policy; B1 verified employee links.

- [ ] Add RED end-to-end object tests for create/read/update MCU and immunization, exposure incident/action/closure, K3 read-only clinician, nonmedical HR denial, employee-limited status and expired break-glass.
- [ ] Add missing scoped forms/routes/templates for existing `PemeriksaanKesehatanKerja`, `ImunisasiPegawai`, risk/incident follow-up and closure using current service signatures; do not introduce duplicate medical/incident tables.
- [ ] Separate general K3 hazard/incident operational permissions from explicit clinical record permissions. Store medical attachments privately; general dashboard shows only approved due/fitness status and aggregate counts with coverage, never diagnoses, test results or exposure detail.
- [ ] Reuse linked organizational risk records and action workflow; staff accident classification remains different from patient-safety incidents. Record sensitive reads/downloads and time-limited emergency access without clinical contents in the audit text.
- [ ] GREEN gate: `test_k3`, `test_k3_journeys`, file/export denial and revoked-grant cases; at least one representative occupational-health journey accepted by an authorized K3 clinician on sanitized data.

## Task A9 — Own-profile portal, training requests and optional leave (P1/P2)

**Depends on:** B6 optional account activation/B7 reviewed profile corrections; A3 reminders; leave separately approved.

- [ ] Add RED tests for a linked staff account with no general HC grant, no employee link, someone else's UUID, changed employment unit, double submission, reviewer conflict and unauthorized document category.
- [ ] Implement `/human-capital/saya/` in `sdm/portal_views.py`: current own employee/profile summary, legal dates, permitted uploads, orientations, learning, own SPK and reminders. Add self-object checks; do not grant a whole-unit HR capability to make the portal work. Reuse B7 changes rather than a second profile-edit mechanism.
- [ ] Create request model/service for training requests with review/history, linking approved requests to existing `KebutuhanPelatihan`/`PesertaDiklat` workflows. No auto-pass/evaluation/certification from a request approval.
- [ ] For optional leave: add leave type/calendar/entitlement ledger, date and partial-day rules, designated approver, overlap/concurrent-decision protection and append-only reversals. Do not invent leave balances from tenure or subtract from payroll. Until approved entitlement/opening balances exist, leave balance is unavailable and approval is blocked with a clear configuration reason.
- [ ] GREEN gate: portal works for own-only staff while foreign-unit directory and HR/health/reviewer notes remain denied; leave and training request replay/approval tests pass. Staff without accounts remain manageable through authorized HR, not excluded from operational lists.

## Task A10 — Optional shifts, digital attendance and remuneration bridge (P3)

**Depends on:** real employee/placement census, approved shift/attendance policy; A9 leave if roster excludes leave; explicit scope expansion approval.

- [ ] Add RED cases for overlapping shifts, split assignments, overnight shifts across dates, timezone, duplicate check-in/out, missing checkout, retroactive correction, device time tampering, declined/inaccurate position and concurrent attendance.
- [ ] Create `ShiftDinas`, `PenugasanShift`, `PeristiwaPresensi`, `KoreksiPresensi`, `LokasiPresensi` models and separate capabilities for roster management/attendance review. Publish versioned unit rosters, retain historical revisions and enforce allocation/rest policies approved by the hospital.
- [ ] Implement `record_attendance` using server receipt time plus supplied event timestamp, scoped shift/employee and idempotency. Optional browser geolocation records an at-event point/accuracy and checks an approved radius; no continuous tracking. Declined/poor position uses an explicit manual-review fallback, not invented location or an automatic verified attendance.
- [ ] Derive approved effective work minutes from paired events and approved break/leave/correction policy. Keep planned FTE, realized attendance hours and training attendance distinct; staffing recalculation creates a new version. Export Decimal-based approved hours/overtime/KPI inputs with scope/period/provenance for an external remuneration system; no salary calculation or automatic payment.
- [ ] GREEN gate: `test_presensi`, overnight/duplicate/authorization browser journeys and export reconciliation; only accepted events count as verified hours. No hardware purchase or paid geofence dependency is required.

## Task A11 — Active-edition reports and sanitized KPS evidence packs (P1/P2)

**Depends on:** B3 typed matching, A1/A3 metrics, A7 annual learning, C1–C5 edition and evidence contracts.

- [ ] Add RED report tests: reviewed mapping without `QualityRecord`, archived framework mapping, mixed professions/sites, duplicate versions, missing rules, restricted export, assessor redaction, forbidden health/private URLs and changed source after pack approval.
- [ ] Fix `compliance_audit` mapping resolution against explicit framework/EP/rule identity and reviewed active state, independent of whether an assessment record exists. Treat upload, verified validity, mapped evidence readiness and accreditation score as separate dimensions.
- [ ] Implement reports for typed STR/SIP at local practice site, annual hours with target/coverage and a permission-filtered KPS staff sample pack (doctor/nurse/other-health/nonclinical/trainee as applicable). Include edition, as-of date, rule version, applicable denominator, missing/rejected/expired/unreviewed reasons and immutable artifact provenance.
- [ ] Implement `build_kps_pack` and `publish_kps_artifact`: render a sanitized derivative, approve the exact source snapshot, then attach it through the existing `EvidenceReq`/`EvidenceFile` workflow with explicit review status. Never auto-approve an `EvidenceFile` or change `QualityRecord.score`. Private originals remain in the HC vault, not copied to public evidence URLs.
- [ ] GREEN gate: XLSX/PDF parse/open, no formula injection or PDF markup injection from text fields, expected redactions, exact selected framework/scope and no assessment-score mutations. Evidence approval must be revoked/reviewed when its source changes.

## Task A12 — Release/UAT and operational acceptance (P0 gate)

- [ ] Reconcile every requested menu row to the owner task and tested route; mark undelivered optional operations explicitly. Preserve legacy five-level capability coverage even after removing five-level visual labels.
- [ ] Run targeted tests per task first, then isolated `sdm`, `accounts`, relevant `akreditasi` and `pasien` suites. Use the real framework's runner and copied fixture idioms, not invented generic test helpers. Repeat on PostgreSQL for constraints/concurrent approvals.
- [ ] Run browser acceptance for HR intake/import; head staffing/review; staff self-portal; committee RKK/SPK; Diklat annual report; K3 private review; assessor sanitized pack; director authorized aggregates. Test 360px/mobile, keyboard focus, wide-table overflow and no-data states.
- [ ] Before authorized deployment, verify private bucket/anonymous-denial, source/rule approvals, scheduling, backup/restore and package versions. Apply migrations manually; collect static and retain tracked artifacts. Record evidence in `docs/qa/hc-improvement-release.md`; do not infer deployment from a passing local suite.
- [ ] Rollback: disable new menu destinations/actions with grants/feature settings, preserve employee/history/approved versions, stop optional attendance ingestion if needed and keep legacy routes. Clinical-enforcement rollback requires an approved controlled policy, not a global authorization bypass.

## Delivery order and acceptance

| Release | Tasks | Usable result |
|---|---|---|
| Foundation correctness | B1–B3, C1–C3, A1 | Reviewed census/source baseline and trustworthy document/metric identity |
| Core HC improvement | B4–B8, A2–A5, A9 own-profile subset, A11 base reports | Five-step intake/import, active legal EWS, navigable staff operations and reviewed reports |
| Clinical/development completion | A6–A8, A11 sample/evidence publication; C4–C7 | Jobdesc/clinical boundary, OPPE/FPPE, annual learning, restricted K3 and approved 2024 evidence |
| Optional workforce operations | A9 leave, A10 | Reviewed leave/roster/presence and remuneration export, no payroll |

**Source coverage:** All ten final tree groups and the trainee discussion have owner tasks above. FTE and WISN are different calculation methods; twenty clock hours is not twenty JP; SPK printout is not certified electronic signature. These explicit distinctions keep the requested UI from overclaiming functionality.

**Execution handoff:** Review and approve release scope before implementation. Recommended method: subagent-driven vertical increments with one integration owner for shared `sdm/views.py`, URLs, grants, document metadata and analytics; optional operations must not block shipping core intake/legal/report corrections. No checkbox in this document is an implementation-completion claim.
