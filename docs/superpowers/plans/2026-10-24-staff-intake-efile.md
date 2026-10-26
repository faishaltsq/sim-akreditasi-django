# Staff Intake, e-File and Account Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing staff directory into the five-step individual intake and reviewed Excel-import workflow in `Input Data Staf.docx`, preserving current identities, dated placements, private documents and scoped access.

**Architecture:** Keep `sdm.Pegawai` as the canonical employment identity, independent of login. Add restricted personal data, effective-dated employment details, structured qualification/license metadata and staged intake/import records; call the existing placement, document, audit and grant boundaries rather than duplicating them. Account invitation is optional, post-commit and retryable; one failed email must not roll back a valid personnel record or provision an elevated role.

**Tech Stack:** Existing Django monolith/templates/Bootstrap, SQLite development and PostgreSQL/Supabase deployment, `openpyxl`, existing private storage and audit services. No SPA, paid HR service or background worker is required.

**Spec:** `C:/Users/cubeb/Downloads/Input Data Staf.docx`; shared evidence `docs/superpowers/plans/2026-10-24-arima-improvement-baseline.md`; menu/report dependencies in `2026-10-24-human-capital-menu-workflows.md`.

## Global Constraints

- This is a **proposed plan**, not authorization to implement, import, migrate, provision accounts, change grants or deploy.
- Preserve all existing employee UUIDs, accounts, units, credential rows, file references and workflow history. Blank old fields remain unknown; never manufacture birthdates, NIK, TMT, qualification or verified status.
- Keep `status=AKTIF/NONAKTIF` separate from employment category Tetap/PKWT/Dokter Mitra/Tenaga Lepas/Magang/Residen.
- UI copy stays Bahasa Indonesia; plan and technical contracts are English. Preserve product name `Arima Human Capital` and URL namespace `sdm`.
- Use current `HcGrant`, `require_hc_capability`, `visible_units`, `visible_employees`, `save_assignment` and private storage/audit infrastructure.
- NIK is a string with exactly 16 ASCII digits when supplied, never an integer. Dates and employee identifiers must not be converted by Excel formatting.
- Intake PDF/JPG/JPEG attachments have a strict **5 MiB / 5,242,880 bytes** per-file limit, matching the source's 5 MB intent with a documented binary limit. Existing PNG versions remain readable; do not delete them. Keep shared legacy storage compatibility separately configurable.
- Do not email temporary passwords. Deliver the requested account activation outcome with an expiring, single-use activation link and user-chosen password. This deliberately replaces the source's password-in-email mechanism while retaining its onboarding goal.
- Do not equate a seeded role/unit account with a hospital employee, or mutate seeded fixtures into real staff automatically.
- New numbered migrations are generated from the actual graph; current local applied HC schema reaches `0013_pengingat_target_type`, not the older runbook's `0011`.
- Commit/push/deployment require separate user instructions; task completion alone is not commit permission.

## Review Focus

1. A partially completed wizard, expired draft or revoked operator grant must not create a half-employee, leaked upload or account.
2. Duplicate identifiers, spreadsheet coercion and retry/concurrent import must not silently merge distinct people or duplicate accounts.
3. STR, SIP, SPK, KTP, photo, diploma and transcript must satisfy only the exact applicable requirement, not every generic document of the same type.
4. Personnel intake permission must not grant system-admin, committee approval or occupational-health access; self-service cannot edit its own role, placement or verification status.
5. Existing unknown dates, synthetic data and metadata-only legacy credentials must remain visibly unverified; completion percentages and historical FTE cannot manufacture missing evidence.

## Baseline and root-cause analysis

The source describes a complete multi-step form and automated accounts. Current `PegawaiCreateForm` only exposes employee number/name/category/profession/job/status plus a first placement (`sdm/forms/pegawai.py:15-66`). `pegawai_create` saves employee/placement/audit atomically (`sdm/views.py:174-214`), but has no contact data, educational history, typed license, import preview or activation email. `accounts/urls.py` has no activation/password-reset journey. Extend those flows; do not create a new employee master.

The 425 employee rows all use the deterministic seeder number prefix and date 2026-10-23 placements. The thirteen legacy credential owners have no linked employee; none of those credentials has a file reference. A blanket `backfill_hc_employees --apply` is not a substitute for a reviewed staff census: the current command defaults to all profiles, can blank colliding employee numbers, uses account profession as classification and uses today's placement date (`sdm/management/commands/backfill_hc_employees.py:28-98`). This plan adds a **separate reviewed reconciliation command**, leaving the existing command available for its existing scope.

Most importantly, `sdm/services/kepatuhan.py:93-98` selects by broad `document_type`. Multiple `CREDENTIAL` rules could select the same STR version for SIP/SPK too. Fix matching before installing the requirement matrix.

### Overlap

The earlier `2026-10-23-arima-human-capital.md` established HC models, services and Level 1–5 routes. **This plan does not implement that plan again.** It adds intake completeness, typed compliance identity, safe import and activation. Track A owns navigation, extended operations and consuming these fields; track C owns accreditation catalogue identity and cross-edition mapping. Neither track may redefine these identity/document contracts.

### Explicitly NOT in this plan

Payroll, shifts/presence, OPPE/FPPE, qualified electronic-signature provider integration, patient-EMR rewriting and automatic catalogue replacement: **do not implement, do not fix while here**. Optional shift/leave work is owned by track A. Do not alter or commit the pre-existing untracked account-matrix command or QA outputs.

## Data and interface contracts — NEW unless explicitly marked existing

| Object | Fields / invariant |
|---|---|
| Existing `Pegawai` | Stable UUID, optional account OneToOne, current operational status, current display name/profession. Add `data_origin` with `UNCLASSIFIED/DEMO/VERIFIED_IMPORT/MANUAL`, reviewed provenance and verification date; default existing rows to `UNCLASSIFIED`, not real |
| `MasterProfesiPegawai` | NEW in `sdm/models/pegawai.py`: stable code/name, group `MEDIS/KEPERAWATAN_KEBIDANAN/NAKES_LAIN/NON_KLINIS`, active/review metadata; optional employee FK alongside the preserved legacy profession text. Unmapped values remain unclassified, not guessed |
| `UrutanNomorPegawai` | NEW in `sdm/models/intake.py`: configured numbering scope/period/format and next counter; row-locked generation plus final unique employee-number constraint; no reassignment of existing NIP |
| `ProfilPribadiPegawai` | Restricted OneToOne employee: NIK nullable, name without titles, front/back titles, birthplace/date, sex, religion, marital status, phone, verified contact email, KTP address and domicile plus same-address flag. Audit field changes without recording raw values |
| `RiwayatKepegawaian` | Employee, category, actual TMT, end date, contract dates/number, weekly contractual hours, full-time reference hours, job title and review/provenance. Dates may remain null for legacy unknowns; applicable intervals cannot conflict |
| `RiwayatPendidikanPegawai` | Employee, level `D3/S1/PROFESI/S2/SP1/SP2/OTHER`, institution, program, completion date and references to exact approved diploma/transcript versions |
| `IzinProfesiPegawai` | Employee, subtype `STR/SIP/SIPA/OTHER`, document number, issuer, profession, validity mode `DATED/LIFETIME`, issuance/expiry, practice organization/location and local-RS flag. Multiple SIPs are allowed; the applicable local practice site must be identified |
| Extended `DokumenPegawai` / `AturanDokumen` | A stable explicit `jenis_berkas` discriminator such as `KTP/FOTO/IJAZAH/TRANSKRIP/STR/SIP/SIPA/KONTRAK/SK_PENGANGKATAN/SPK_RKK/URAIAN_TUGAS/SERTIFIKAT`; optional structured-license binding and approved practice scope. Retain broad type for sensitivity/grouping, not proof identity |
| `DrafInputPegawai` | UUID, owner, optional edited employee, current step, typed draft data, version/concurrency token, expiry, state. Drafts are restricted persisted records, not raw NIK/file bytes in cookies or URLs |
| `BatchImporPegawai` | UUID, uploader, template version, file hash, idempotency key, scope, preview hash, reviewed decisions, state and counts; no implicit upsert from names |
| `UndanganAkunPegawai` | Employee, intended existing/nonprivileged account, email snapshot/version, token digest, expiry, sent/failed/accepted/revoked state and attempt metadata. A clear token is never persisted or logged |

### Service boundaries

Existing: `save_assignment(assignment)` in `sdm/services/penempatan.py`; `store_private_document(...)` in `sdm/storage.py`; requirement result types in `sdm/services/kepatuhan.py`.

New boundaries to implement in the task that names them:

- `validate_personal_data(data: dict) -> dict`: normalized validated values, field errors via `ValidationError`.
- `finalize_staff_intake(*, actor, draft_id, expected_version, idempotency_key) -> Pegawai`: revalidate object/unit permissions, commit canonical rows once, produce audit, enqueue optional invitation.
- `preview_staff_import(*, actor, workbook, idempotency_key) -> BatchImporPegawai`: parse/validate to immutable preview; create no canonical staff/account/placement rows.
- `apply_staff_import(*, actor, batch_id, preview_hash) -> BatchImporPegawai`: revalidate scope/hash and apply only approved error-free create/update decisions, with row/batch audit.
- `invite_staff_account(*, actor, employee, email, role, idempotency_key) -> UndanganAkunPegawai`: explicit role/grant delegation policy, not merely an intake permission.
- `accept_staff_invitation(*, token, password) -> user`: Django password validation, active/unexpired/single-use binding and replay protection.
- `reconcile_hc_staff --reviewed-artifact <path>`: **new dry-run-only default command**. `--apply` requires explicit reviewed employee/account/unit decisions, provenance and date policy; no approximate-name matching or silent blanking of collisions.

## File ownership map

Modify existing:

- `sdm/models/pegawai.py`, `sdm/models/dokumen.py`, `sdm/models/__init__.py`: additive identity, employment and precise matching metadata.
- `sdm/forms/pegawai.py`, `sdm/forms/dokumen.py`, `sdm/forms/__init__.py`: scoped forms and explicit file metadata.
- `sdm/views.py`, `sdm/urls.py`: compatibility entry points; delegate new workflows to focused modules.
- `sdm/services/kepatuhan.py`, `sdm/storage.py`, `sdm/storage_backend.py`: exact matching and intake-bound storage configuration.
- `sdm/akses.py`, `sdm/signals.py`, `sdm/admin.py`: scoped field access, cache invalidation and restricted administration.
- `accounts/urls.py`, `accounts/models.py`: explicit invitation routes/configurable permission integration if required by the policy; preserve existing role choices.
- `templates/sdm/pegawai/form.html`, `detail.html`, `list.html`; `sdm/tests/test_directory.py`, `test_dokumen.py`, `test_private_documents.py`, `test_storage_backend.py`, `test_legacy_credentials.py`.

Create NEW:

- `sdm/models/intake.py`, `sdm/models/undangan.py`; `sdm/services/intake.py`, `impor_pegawai.py`, `undangan.py`; `sdm/forms/intake.py`; `sdm/intake_views.py`.
- `sdm/management/commands/reconcile_hc_staff.py`; generated `sdm/migrations/` files and an accounts migration only if its fields change.
- `templates/sdm/pegawai/wizard.html`, `import_preview.html`, `import_result.html`, `activation.html`.
- `sdm/tests/test_intake.py`, `test_staff_import.py`, `test_staff_invitation.py`, `test_staff_reconciliation.py`; `accounts/tests_staff_activation.py`.
- `docs/qa/staff-intake-release.md`, `docs/security/staff-import-activation.md`.

## Task B1 — Classify existing fixtures and reconcile the real staff census (P0)

**Depends on:** approved personnel source and record-classification policy. **Produces:** reviewed provenance without deleting any row.

- [ ] Write `test_staff_reconciliation.py` using Django `TestCase`, `get_user_model()`, `UserProfile`, `UnitKerja`, `Pegawai`, and `PenempatanPegawai`, as in the existing `test_directory.py:20-62`. Fixtures must include a seeded-number employee, an unmarked legacy owner, duplicate NIP and a real account-less staff row.
- [ ] Run the new test module against isolated SQLite; the command/migration is absent and must fail RED.
- [ ] Add provenance fields with neutral defaults. Implement `reconcile_hc_staff` dry-run and reviewed-artifact apply: map exact user IDs/employee UUIDs/unit IDs, record unknown TMT as unknown, and reject ambiguous collision rows rather than blanking identifiers.
- [ ] Test idempotent apply, changed source hash, foreign unit, stale reviewed artifact, existing employment history, all thirteen metadata-only credentials and mixed demo/real data. Opening balances may record an as-of placement date **with provenance**, never claim it as actual hiring date.
- [ ] GREEN gate: all existing IDs/counts preserved unless an explicit create action is approved; no deletes or implicit account-to-workforce expansion. Record aggregate before/after and unresolved rows in `docs/qa/staff-intake-release.md`.

Executable assertion to include after the dry-run fixture is set up:

```python
before = (Pegawai.objects.count(), PenempatanPegawai.objects.count())
call_command('reconcile_hc_staff', reviewed_artifact=str(reviewed_artifact))
self.assertEqual(before, (Pegawai.objects.count(), PenempatanPegawai.objects.count()))
```

`reviewed_artifact` is a temporary JSON file created by this test under the test/scratch directory, not a production mapping path.

## Task B2 — Add complete personal, employment and qualification fields (P1)

**Depends on:** B1 provenance. **Produces:** profile/employment/license records from the contracts above.

- [ ] Add RED tests in `test_intake.py`: NIK missing versus malformed, exactly sixteen ASCII digits, future birthdate, whitespace phone/email, split titles, same-address copying, employment TMT distinct from placement start, weekly hours greater than zero and contract end before start. Pin concurrent NIP generation, duplicate manual NIP, an unmapped profession and the difference between PPA and medical-staff grouping.
- [ ] Add the additive models/fields and `validate_personal_data`. Preserve legacy `nama_lengkap` verbatim until reviewed split values exist; do not parse existing names automatically. Formatting a new full display name must not append titles twice. Add a hospital-approved profession master grouping medical, nursing/midwifery, other health and nonclinical staff; do not equate `PPA` directly with medical or infer qualifications from an account role. For NIP, preserve existing valid numbers and allow manual/imported numbers; optional generation uses a configured hospital format plus a transactionally locked counter (`UrutanNomorPegawai`, NEW in `sdm/models/intake.py`), never `count()+1`. An unconfigured format leaves the field explicitly pending rather than inventing an institutional numbering scheme.
- [ ] Treat unverified personal email separately from authentication identity. Keep contact edits from silently changing the login address. Do not require email/account creation to register a staff member.
- [ ] Add form-level and service-level field permissions: employee may propose allowed contact corrections; HR may approve employment changes; unit head sees only permitted operational fields; neither generic export nor assessor sees full NIK/address by default.
- [ ] GREEN gate: account-less/non-PPA, part-time/mitra and multiple-SIP staff work; null old fields stay null; SQLite and PostgreSQL migration rehearsals preserve UUID/account relationships. Date conflicts and foreign-unit placement changes roll back.

Validation examples to pin without involving unrelated fields:

```python
self.assertEqual(validate_personal_data({'nik': '0011223344556677'})['nik'], '0011223344556677')
with self.assertRaises(ValidationError):
    validate_personal_data({'nik': '001122334455667'})
with self.assertRaises(ValidationError):
    validate_personal_data({'nik': '１２３４５６７８９０１２３４５６'})
```

## Task B3 — Fix exact document/requirement matching and private-upload limits (P0)

**Depends on:** no operational rule seeding before this task. **Produces:** exact artifact identity consumed by track A.

- [ ] Add failing cases to `test_dokumen.py`: verified STR cannot satisfy SIP/SPK; photo cannot satisfy KTP; diploma cannot satisfy transcript; a second external-clinic SIP cannot satisfy the local-RS SIP requirement; a higher version number on another document must not win arbitrarily.
- [ ] Extend typed metadata/bindings and update `_latest_version` to select the exact applicable artifact/license/practice context and current non-superseded revision. Existing untyped records stay `UNCLASSIFIED`/pending manual binding and do not satisfy a precise requirement automatically.
- [ ] Move lifetime validity to the specific legal document/license, not a profession-wide assumption that makes every STR lifelong. Missing expiry is valid only with approved explicit `LIFETIME`. Keep warnings distinct from validity: a verified unexpired near-expiry document remains legally valid while also expiring soon.
- [ ] Thread an explicit intake limit/type policy through `get_private_storage`/storage calls. Enforce 5,242,880 bytes in browser/form/service/backend; reject fake MIME/signature, oversize, path traversal and disallowed intake PNG without breaking download of existing PNG. Stage private objects with deterministic cleanup metadata; provider failure cannot create `VERIFIED` rows.
- [ ] GREEN gate: run `sdm.tests.test_dokumen sdm.tests.test_private_documents sdm.tests.test_storage_backend sdm.tests.test_legacy_credentials`. Test exact limit and limit+1, lifetime/dated STR, due today, superseded/rejected versions, legacy untyped records and cross-employee signed-download denial.

Pin the existing public result API rather than inventing a second compliance calculator:

```python
result = evaluate_employee_compliance(employee, as_of=today, ruleset=[sip_rule])
self.assertEqual(result.results[0].state, 'MISSING')  # only a typed STR was uploaded
self.assertEqual(result.completeness_pct, 0.0)
```

`employee`, `today`, `sip_rule` and the verified typed STR are created in the test's `setUp` using the current `test_dokumen.py` fixture style, extended with the new discriminator fields from this task.

## Task B4 — Replace the flat create form with resumable five-step intake (P1)

**Depends on:** B2 and B3. **Produces:** `finalize_staff_intake` and working five-step UI.

- [ ] Add RED tests for five named steps: `Identitas & Kontak`, `Kepegawaian & Penempatan`, `Legalitas & Pendidikan`, `Akun & Akses`, `Dokumen Pendukung`; include back/next/resume, server validation, draft expiration and keyboard navigation.
- [ ] Implement draft-owned state and optimistic version checks. Recheck current permissions/unit choices at **every** step and final submit. Store uploads only in private storage; never put file bytes or sensitive draft values into signed cookies, query strings or application logs.
- [ ] Default account creation to optional. Existing `sdm:pegawai_create` opens the wizard while preserving its route name; keep existing POST compatibility deliberately until updating `test_directory.py`. The wizard must support incomplete-but-saved draft without showing that draft as an active employee.
- [ ] Implement `finalize_staff_intake`: validate all steps and staged objects; use one database transaction for employee/profile/employment/qualification/placement/document binding/audit; use the existing placement validation. Final retries return the same UUID. External file/email work uses staged state and compensating cleanup, not a falsely atomic remote-storage transaction.
- [ ] GREEN gate: `test_intake`, existing directory/document suites and browser journey at desktop/mobile. Simulate expired draft, concurrent tab, revoked grant, remote storage timeout and a failed optional invitation; no duplicate employee or orphan accepted object.

## Task B5 — Versioned Excel template, preview and explicit import decisions (P1)

**Depends on:** B1–B3. **Produces:** preview/apply boundaries, no automatic fuzzy merge.

- [ ] Add RED cases in `test_staff_import.py` for a valid create, account-less staff, empty row, duplicate NIP within a workbook, duplicate against database, unknown unit code, malformed NIK, date ambiguity, role escalation, formula cell, unexpected columns and repeat/concurrent apply.
- [ ] Generate an `.xlsx` template using existing `openpyxl`: a versioned `Staf` sheet plus controlled-value/unit reference sheets. Use strings for NIK/NIP/phone, ISO `YYYY-MM-DD` dates and exact unit codes; explicitly separate employment category, operational status, employment TMT and placement start. Do not accept attachments embedded in spreadsheets.
- [ ] Implement bounded parser limits: 5 MiB workbook, at most 2,000 nonempty staff rows and bounded ZIP uncompressed size, no macros/external links/formula evaluation. Return a Bahasa Indonesia row/column error list without exposing existing personnel details beyond the importer's scope.
- [ ] Preview stores workbook hash, template version, scope and action per row (`CREATE`, explicitly reviewed `UPDATE_BY_UUID`, `BLOCKED`). A display-name match never authorizes merge; existing UUID or approved exact employee-number resolution is required. Default all-or-nothing apply rejects a batch with blocking errors. Recheck uniqueness/scope on apply and reject a stale preview; no partial silent success.
- [ ] GREEN gate: preview creates **zero canonical employees/placements/accounts**; apply preserves identifiers, audits each row, and repeat apply returns recorded result. Files with forced numeric/coerced NIK are rejected with correction instructions, not repaired by zero-padding guessed digits.

Required invariants using objects created in this task:

```python
before = (Pegawai.objects.count(), PenempatanPegawai.objects.count())
batch = preview_staff_import(actor=manager, workbook=workbook, idempotency_key='preview-001')
self.assertEqual(before, (Pegawai.objects.count(), PenempatanPegawai.objects.count()))
applied = apply_staff_import(actor=manager, batch_id=batch.pk, preview_hash=batch.preview_hash)
again = apply_staff_import(actor=manager, batch_id=batch.pk, preview_hash=batch.preview_hash)
self.assertEqual(applied.pk, again.pk)
```

The test creates `manager` with the same profile/config/grant idiom as `test_directory.py`, and `workbook` with `openpyxl.Workbook` serialized to an in-memory upload.

## Task B6 — Optional login activation without privilege escalation (P1)

**Depends on:** B2/B4 or B5. **Produces:** invitation and acceptance contracts.

- [ ] Write RED tests in `test_staff_invitation.py` and `accounts/tests_staff_activation.py`: optional no-account path; reuse reviewed exact existing account; duplicate/case-normalized email conflict; successful invite, expiry, replay, revocation, changed email, mail failure and retry.
- [ ] Implement invitation state and Django token/password mechanisms. Create new accounts inactive/unusable until acceptance; rate-limit issuance and acceptance, validate redirect destinations and do not disclose whether unrelated email addresses exist. A token binds invitation, employee and current email version.
- [ ] Define explicit delegation checks: an operator with only `can_manage_hc_employees` cannot create `SUPER_ADMIN`, global ADMIN_RS or committee/health privileges. Role and scope changes go through existing account administration authorization. Staff default is existing `STAF_NAKES` only where appropriate; account-less nonclinical employment remains valid without falsely labelling its employee profession.
- [ ] Send mail only after personnel transaction commit through a recorded retryable delivery state. Failure shows `Profil tersimpan; undangan belum terkirim` and an authorized resend action. Use environment mail configuration; no hardcoded password, mail server or paid dependency. Do not send an activation link before the invite record exists.
- [ ] GREEN gate: replay is denied, expired/changed-contact invitation cannot activate, no health/global grant is created, and a mail timeout leaves exactly one employee and one resumable invitation record.

## Task B7 — Reviewable self-service corrections and staff detail tabs (P2)

**Depends on:** B2–B6. **Produces:** permitted own-profile update workflow used by track A's portal.

- [ ] Add RED role/object tests: employee's own contact change proposal, head's scoped staffing summary, HR approval, rejected request with reason, and foreign employee UUID tampering.
- [ ] Build detail tabs for identity (masked), employment/placements, education, licenses and documents. Display missing configuration/data honestly; raw MCU/health content stays behind existing explicit clinical grants.
- [ ] Separate direct-edit fields from reviewed-change requests. Never allow self-service writes to NIP/NIK identity approval, profession, employment category, unit/FTE, role, verified-document flags or SPK authority. Editing a reviewed legal detail invalidates the applicable review state rather than silently retaining it.
- [ ] Add audit events for proposal/approval/rejection/sensitive download without values. Extend dashboard cache invalidation for the new data that actually feeds its summaries.
- [ ] GREEN gate: `test_directory`, `test_akses`, `test_intake`, `test_private_documents` plus browser upload/correction/resume journey; no other employee or health content leaks through list, detail, export or download.

## Task B8 — Controlled configuration, reconciliation and release (P0 gate)

**Depends on:** B1–B7; catalogue-based KPS mapping waits for C1–C4.

- [ ] Install approved profession/qualification/employment choices using idempotent reviewed configuration, not speculative mappings from names or current seeded account roles. Keep `SDM`, `BAG-SDM`, `BAG-DIKLIT`, `UNIT-KREDENSIAL` as distinct existing units unless a separately approved organization change says otherwise.
- [ ] Rehearse the reviewed thirteen-owner reconciliation on a sanitized copy. Metadata-only credentials stay metadata-only with missing-file status; do not claim a private object has been migrated when no source bytes exist. Verify all new file objects through the existing inventory/checksum/anonymous-denial runbook.
- [ ] Run isolated SQLite and PostgreSQL migrations on empty and populated copies, targeted RED/GREEN suites, then `sdm`, `accounts`, accreditation/legacy compatibility regressions and browser five-step/import/activation journeys. Record real outputs in `docs/qa/staff-intake-release.md`.
- [ ] Align installed packages to the reviewed `requirements.txt` before final release verification; current installed Django 6.1.1 differs from pinned 6.1.2. Do not silently update dependencies in this planning task.
- [ ] After deployment authorization: take verified backup; apply additive migrations explicitly; configure private storage/mail and expiry/cleanup scheduling; collect static and retain tracked `staticfiles/`; verify actual role/unit endpoints and a controlled real staff intake. Rollback disables new intake/import/invitation actions but preserves all canonical staff/files/audit and existing routes.

## Acceptance matrix for the source document

| Source requirement | Owner | Release gate |
|---|---|---|
| Bulk standardized Excel import | B5 | Template → preview → reviewed apply; idempotent; no fuzzy merge |
| Five-step individual form | B4 | All five usable, resumable, validated and scoped |
| NIP/NIK/name/contact/address | B2 | Correct types, masked access, old unknown values preserved |
| Contract status/TMT/unit/subunit/job/weekly hours | B2/B4 | Employment and placement history remain distinct; actual FTE capacity has an explicit reference |
| Profession/education/STR lifetime/SIP practice sites | B2/B3 | Typed qualifications/permits; one artifact cannot satisfy another |
| RBAC/account state | B6 | Explicit delegation, optional account, tested activation |
| Drag-drop supporting documents ≤5 MB | B3/B4 | 5 MiB documented limit, private staged uploads, exact MIME/signature |
| New staff profile after save | B4/B5/B7 | One canonical UUID with complete applicable tabs |
| Automated activation email | B6 | Expiring single-use link, retry state; no password in email |
| Input audit trail | B1–B8 | Actor/time/object/action recorded without sensitive content |

**Execution handoff:** Review this plan together with the shared baseline. Resolve personnel source/provenance policy and identity/document schema first; implement this track before enabling menu compliance metrics. Recommended execution is subagent-driven with an independent identity/access review per task. No tasks are marked complete by this planning deliverable.
