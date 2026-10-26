# Staff Intake Completion Implementation Plan

> **For agentic workers:** Read `2026-10-24_201051-hc-additions-roadmap.md` first. Use `executing-plans` or `subagent-driven-development` only after approval. Every implementation increment follows RED → minimal implementation → GREEN → review; commit green checkpoints only when commits are authorized.

**Goal:** Make the existing staff-input feature fulfill the supplied five-step individual onboarding and Excel-import requirements, producing a complete private staff profile and optional working account activation.

**Architecture:** Keep `Pegawai` as canonical identity and extend the existing draft/import/invitation models. Move the existing finalizer into `sdm/services/intake.py`, share field validation/canonical persistence between wizard and import, and stage private attachments against the draft before binding them to employee document versions. All account/email work follows a successful personnel transaction and cannot silently duplicate or undo employment records.

**Specification:** `C:/Users/cubeb/Downloads/Input Data Staf.docx`; verified source hash and current source/schema/data differences are recorded in the companion roadmap. The old `docs/superpowers/plans/2026-10-24-staff-intake-efile.md` is supporting domain context, not a create-all-models instruction.

## Global constraints

- Planning only until execution approval. Preserve unrelated work, existing UUIDs, accounts, documents, and routes. No staff/grant seeding, actual email, live storage call, deployment, or commit during planning.
- Use existing `can_view_hc`, `can_manage_hc_employees`, `can_manage_hc_documents`, `save_assignment`, private storage, and `PeristiwaSDM` boundaries.
- User-interface literals stay Indonesian. Do not put NIK, contact data, file bytes, activation secrets, or private URLs in cookies, query strings, broad cache, or audit descriptions.
- NIK is a string of sixteen ASCII digits when supplied; preserve leading zeros. Legacy missing data remains unknown.
- Separate `AKTIF/NONAKTIF`, PPA/non-PPA classification, employment category, TMT, placement start, and authentication account status.
- PDF/JPG/JPEG intake files: maximum 5,242,880 bytes each; explicit UI text `Maksimal 5 MiB per berkas`. Existing PNG files remain downloadable; do not change legacy history to force the intake policy.
- No password is emailed. Activation uses a single-use expiring link and user-chosen password.
- Core staff registration does not depend on having an email/account. Account roles and scopes require explicit delegation authority; an HR form must not grant global administrator or health access.
- Source includes migrations through `0025`, local database records through `0024`; generate new migration numbers from the current graph, never reuse an old number.

## Current defects to target

1. Previous-step links reverse `pegawai_wizard_step` with two arguments although it accepts one. Use `pegawai_wizard_resume` with named `step` and `draft_id`.
2. Step five's main action is an anchor, so it does not submit its fields. Forms have no file field, multipart encoding, or `request.FILES` binding.
3. Wizard updates ignore the version submitted by the browser. The finalizer receives a newly loaded server version, defeating stale-tab protection.
4. Finalizer requires only steps 1/2, ignores step four, creates document metadata without file versions, bypasses `save_assignment`, and ignores its idempotency key.
5. A finalized draft has no result-employee link. Replay cannot return the original result reliably.
6. Step three supports one arbitrary permit rather than simultaneous STR and multiple practice-site SIPs. Step two lacks explicit subunit selection; profession master is not linked to employees.
7. Staff detail/edit views expose only the old small field set, so newly stored private/employment/education/license data is not a complete Digital Staff Profile.
8. Import service lacks download/upload/preview/confirmation routes and persists only a subset of the source fields.
9. Invitation service sends immediately despite its post-commit comment; idempotency key is unused; denylist is not a delegation allowlist; acceptance lacks an HTTP page and row locking. The current email template contains `http://example.com/aktivasi/{{ token }}`.

These are code-inspection findings, not fresh runtime test results. Add reproductions before fixing them.

## File ownership

Modify existing:
- `sdm/forms/intake.py`, `sdm/forms/pegawai.py`, `sdm/forms/dokumen.py`.
- `sdm/intake_views.py`, `sdm/services/intake.py`, `sdm/services/impor_pegawai.py`, `sdm/services/undangan.py`.
- `sdm/models/intake.py`, `sdm/models/undangan.py`, `sdm/models/pegawai.py`, `sdm/models/dokumen.py`, `sdm/models/__init__.py`.
- `sdm/storage.py`, `sdm/storage_backend.py`, `sdm/urls.py`, relevant profile handlers in `sdm/views.py`.
- `accounts/urls.py`, `templates/accounts/email/invitation_body.txt`.
- Existing tests `sdm/tests/test_directory.py`, `test_staff_import.py`, `test_staff_invitation.py`, `test_private_documents.py`, `test_storage_backend.py`, `test_dokumen.py`.
- Existing templates `templates/sdm/pegawai/{wizard,wizard_finalize,list,detail}.html`; read untracked files before editing them.

Create during implementation:
- `sdm/import_views.py`, `sdm/forms/impor.py`, `accounts/staff_activation_views.py`.
- `sdm/tests/test_intake.py`, `sdm/tests/test_intake_uploads.py`, `sdm/tests/test_staff_import_routes.py`, `accounts/tests_staff_activation.py`.
- `templates/sdm/pegawai/{import_upload,import_preview,import_result}.html`, `templates/accounts/{staff_activation,staff_activation_complete}.html`.
- Generated migrations, `docs/qa/staff-intake-completion-verification.md`.

Do not create duplicate identity, batch, invitation, profession, education, employment, permit, or document model families: those already exist.

## Preparation — establish isolated baseline

- [ ] Read current target files and `git status --short`; protect all control/seed/catalogue/untracked work.
- [ ] Run during execution:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory sdm.tests.test_staff_import sdm.tests.test_staff_invitation sdm.tests.test_private_documents sdm.tests.test_storage_backend sdm.tests.test_dokumen sdm.tests.test_penempatan --verbosity 1
```

Expected: record actual baseline and exit code. Do not treat unrelated fixture/template failures as the intended RED or assume the old test count. All tests use SQLite `:memory:`; mock storage and email.

## S1 — Repair wizard navigation, submission, and draft versioning

Each checkbox is a 2–5 minute action; stop after the focused checks, not after editing markup alone.

- [ ] Add these methods inside existing `PegawaiDirectoryViewTests` in `sdm/tests/test_directory.py`; its current helpers supply a scoped manager/root and locmem-compatible test client:

```python
    def test_resumed_step_renders_previous_link_for_same_draft(self):
        self.client.force_login(self.manager)
        draft = DrafInputPegawai.objects.create(
            owner=self.manager, current_step=2, version=1,
            expires_at=timezone.now() + timedelta(days=1),
            draft_data={'1': {'nama_depan': 'Fixture'}},
        )
        response = self.client.get(reverse('sdm:pegawai_wizard_resume', kwargs={
            'step': 2, 'draft_id': draft.pk,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('sdm:pegawai_wizard_resume', kwargs={
            'step': 1, 'draft_id': draft.pk,
        }))
        self.assertContains(response, 'name="expected_version"')

    def test_stale_draft_post_does_not_overwrite_saved_step(self):
        self.client.force_login(self.manager)
        draft = DrafInputPegawai.objects.create(
            owner=self.manager, current_step=2, version=2,
            expires_at=timezone.now() + timedelta(days=1),
            draft_data={'1': {'nama_depan': 'Current'}},
        )
        response = self.client.post(reverse('sdm:pegawai_wizard_resume', kwargs={
            'step': 1, 'draft_id': draft.pk,
        }), {'nama_depan': 'Stale', 'expected_version': '1'})
        self.assertEqual(response.status_code, 409)
        draft.refresh_from_db()
        self.assertEqual(draft.version, 2)
        self.assertEqual(draft.draft_data['1']['nama_depan'], 'Current')
```

- [ ] RED command:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory.PegawaiDirectoryViewTests.test_resumed_step_renders_previous_link_for_same_draft sdm.tests.test_directory.PegawaiDirectoryViewTests.test_stale_draft_post_does_not_overwrite_saved_step --verbosity 2
```

Expected: route reversal or missing version contract and stale-write failure, not a database connection failure.

- [ ] Replace the exact broken URL in `wizard.html`:

```django
{% url 'sdm:pegawai_wizard_resume' step=prev_step draft_id=draft.pk %}
```

In `wizard_finalize.html`, the last-step edit link is:

```django
{% url 'sdm:pegawai_wizard_resume' step=5 draft_id=draft.pk %}
```

Keep these within the existing conditional where a draft exists.

- [ ] Add an expected-version hidden field to both forms:

```django
{% if draft %}<input type="hidden" name="expected_version" value="{{ draft.version }}">{% endif %}
```

Change the wizard form to `enctype="multipart/form-data"` and the step-five action to a submit button with the literal `Simpan dokumen & tinjau`. The final confirmation remains a separate POST, not a side effect of following a link.

- [ ] In `intake_wizard`, lock the owner-filtered draft within `transaction.atomic()` for resumed POST, parse a required positive integer `expected_version`, compare before saving, and return the bound form with a visible conflict explanation and HTTP 409 on mismatch. Missing/malformed version returns a validation error without mutation. New draft creation is the only versionless POST.
- [ ] Add form-level validation through `validate_personal_data`; copy the normalized return values back into the persisted payload. Invalid NIK/future birthdate must fail the corresponding step immediately, not only finalization. Use one full name without titles as the visible concept; preserve mononyms and separately entered titles without guessing splits for legacy names.
- [ ] Track completed step keys separately from `current_step`; allow backwards navigation but block unvisited forward steps with a redirect to the earliest incomplete step. Invalidating an earlier employment/unit answer must force dependent data to be revalidated.
- [ ] GREEN: rerun the focused command; expect `OK`. Add page-level GET tests for steps 1–5 and final review; assert all return 200 for valid draft states and all forms POST to the same owner/draft.

## S2 — One canonical, replay-safe finalization boundary

**Interfaces:** retain `finalize_staff_intake(*, actor, draft_id, expected_version, idempotency_key) -> Pegawai`, with its implementation moved from `sdm/intake_views.py` to `sdm/services/intake.py`. Import it in the view; do not leave a second implementation.

- [ ] In new `sdm/tests/test_intake.py`, use the same user/config/grant setup as `PegawaiDirectoryViewTests`. Add RED cases for missing steps 3/4/5, expired/foreign/revoked draft, stale version, duplicate NIP/NIK, invalid FTE/date interval, selected foreign unit, and final replay. A blank but explicitly completed optional step is allowed; an absent step is not completed.
- [ ] Add `finalized_employee` (nullable protected FK to `Pegawai`) and `finalization_key` (nullable unique string, max_length=100) to `DrafInputPegawai`. `edited_employee` retains its existing edit-draft meaning; do not overload it as the result link.
- [ ] Implement finalization in this exact order:
  1. Enter one atomic block; fetch the owner-filtered draft with `select_for_update()`.
  2. Recheck operator status/capability, current unit and document scopes.
  3. If already finalized, return its result only when the supplied finalization key matches; reject a different key. Do not reject legitimate replay merely because the pre-finalization version is old.
  4. Otherwise enforce current version, expiry, DRAFT state, and completed keys `1` through `5`.
  5. Rebind all forms/formsets from the draft with the current actor; reject newly inactive/foreign master choices and invalid contracts/permits. Convert Decimal/date values once and use normalized values consistently.
  6. Create `Pegawai`, private profile, employment, education, permits and placement using `full_clean()` and existing `save_assignment`. No `count()+1` NIP generation, placeholder person name, default fabricated TMT, or raw float FTE.
  7. Bind staged attachments through S4, create PENDING document versions and sanitized audit rows.
  8. Set finalized employee/key/state, increment version, and record one `employee_created` audit event; commit once.
  9. Schedule optional invitation via S6 after commit; return the same employee on all matching retries.
- [ ] Update `test_create_employee_uses_scoped_unit_and_assignment_service` in `sdm/tests/test_directory.py:109-152`: keep its original placement/audit assertions, add `expected_version` to each resumed POST, submit all five steps, then final-review version/key. Its current direct finalization after step two must no longer remain a success fixture.
- [ ] Change the confirmation view to consume the browser version/key, not `draft.version` generated by a fresh fetch. Add a genuine summary with missing-step status; remove the unconditional claim `5 dari 5 (seluruh langkah telah diisi)` for incomplete drafts.
- [ ] GREEN:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_intake sdm.tests.test_directory sdm.tests.test_penempatan --verbosity 2
```

Expected: `OK`; retries preserve employee/placement/audit counts. PostgreSQL concurrency tests must prove simultaneous finalize creates one result; SQLite passing alone does not validate row locks.

## S3 — Finish the source fields and usable Digital Staff Profile

- [ ] Write failing form/service/profile tests in `sdm/tests/test_intake.py` and `sdm/tests/test_directory.py` for the exact rows in the coverage table below, including an existing legacy employee without those relationships.

| Source requirement | Existing source to extend | Completion contract |
|---|---|---|
| NIP manual/configured generation | `UrutanNomorPegawai`, `Pegawai.nomor_pegawai` | Preserve supplied NIP; optional configured counter is locked and unique; if no pattern, manual entry remains available |
| NIK, name/titles, birth, sex/religion/marriage | `ProfilPribadiPegawai`, `IntakeStep1Form` | NIK ASCII string; full-name presentation supports mononyms; no automatic legacy name splitting |
| Phone/email/KTP/domicile | Same personal profile | Contact email is not “verified” merely because entered; same-as-KTP copies only when checked and validates the final stored result |
| Employment category, TMT, weekly hours | `RiwayatKepegawaian`, `IntakeStep2Form` | Keep employment and placement dates distinct; expose full-time reference separately; validate positive hours and contract intervals |
| Main unit/subunit | Existing `UnitKerja` and placements | Optional subunit must descend from the selected main unit and be within grant scope; persist the actual placement leaf and retain main-unit context explicitly |
| Profession/master | `MasterProfesiPegawai`, preserved profession text | Add nullable reviewed-master FK on `Pegawai`; new choices use active master, legacy unmatched text stays unclassified |
| Education/institution | `RiwayatPendidikanPegawai` | Preserve explicit degree/institution/date and typed diploma/transcript version links |
| STR plus SIP/SIPA | `IzinProfesiPegawai`, step-three formsets | One person may enter STR and multiple site-specific SIPs; lifetime applies to the individual STR, not every permit; support nonclinical no-permit path |
| Account status/access | Existing step four + S6 | No account, invite, or reviewed exact account linkage; employee status does not silently toggle login status |
| Documents | Typed documents + S4 | Actual file versions, independent statuses and protected download; metadata-only is not uploaded |
| Post-intake profile | `pegawai_detail`, `pegawai_edit`, detail template | Show personal, employment/placement, education, permits, document status, account-invitation status, and audit with field-level permissions |

- [ ] Implement these additions additively. Prefer formsets for repeated education/licenses and a focused detail context builder; avoid enlarging `sdm/views.py` with another unrelated service family. Every new FK or relation gets a generated migration and protected access checks.
- [ ] HR sees permitted personal fields; unit heads see scoped operational data with masked NIK and no unnecessary address/contact export; staff use own-only view from menu plan M3. Shared view objects must not leak full private profiles into caches.
- [ ] Add known-date-only age/tenure display. No retirement date appears without an approved retirement policy. `date_of_placement` must never be relabeled as TMT.
- [ ] GREEN: rerun S2 plus `sdm.tests.test_pegawai_models`, `sdm.tests.test_directory`, `sdm.tests.test_akses`. Expect `OK`, legacy profiles render without nullable-relation errors, foreign object GET/POST remains denied.

## S4 — Real private attachments, not empty document rows

**New model:** `LampiranDrafPegawai` in `sdm/models/intake.py`, exported through `sdm/models/__init__.py`.

Fields: UUID; draft FK with owner derived from draft; artifact kind; immutable opaque storage key; SHA-256; size; content type; safe original filename; issuance/expiry; optional permit/education draft reference; state `STAGED/BOUND/DELETE_PENDING/DELETED`; nullable bound-version FK; timestamps. Never store raw file bytes or public URLs in the JSON draft.

**New interfaces in `sdm/services/intake.py`:**
- `stage_intake_attachment(*, actor, draft_id, expected_version, file_obj, artifact_kind, metadata) -> LampiranDrafPegawai`.
- `remove_intake_attachment(*, actor, attachment_id, expected_version) -> None`.

- [ ] Add RED tests in `sdm/tests/test_intake_uploads.py`: exact limit/limit+1, PDF and JPEG signatures, fake MIME, rejected intake PNG, duplicate submission, foreign draft/key, revoked upload grant, missing file, provider timeout, rollback, and cleanup retry. Reuse `StoredPrivateObject` and storage mocks from `test_private_documents.py`; tests never contact Supabase.
- [ ] Implement a real file input and typed document rows in step five. Bind `request.POST, request.FILES`; drag/drop is progressive enhancement of the same input and must work by keyboard without JavaScript.
- [ ] Require both scoped personnel-management and document-upload authority; if an operator lacks document rights, show an explicit pending-document workflow rather than pretending an upload succeeded. Do not give document-management grants automatically.
- [ ] Upload into private draft-owned opaque paths after checking owner/version/state; validate extension, declared MIME and bytes, bounded reads and per-file size before provider request. Recheck draft state under lock before attaching the returned object; cleanup on stale version or failed metadata commit.
- [ ] At finalization bind the existing private object to typed `DokumenPegawai`/`VersiDokumen`, preserving hash/size and PENDING status. Shared storage gains explicit `jenis_berkas` and permit/education binding support; do not make all credential rows `OTHER`.
- [ ] Remote storage is not transactional with PostgreSQL. Failed binding leaves retryable staging state; no successful-profile claim until required operations finish. Draft expiry schedules deletion by stored private key with retryable `DELETE_PENDING`; cleanup is explicit, never a GET-side bucket deletion.
- [ ] Preserve old files and download controls. Do not broaden `_is_own_credential` into unrestricted self-upload of employment/role/verification changes; self uploads follow own-only rules and review.
- [ ] GREEN:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_intake_uploads sdm.tests.test_private_documents sdm.tests.test_storage_backend sdm.tests.test_dokumen sdm.tests.test_legacy_credentials --verbosity 2
```

Expected: `OK`, no provider network calls, every successful new upload has a stored object plus a version, no automatic VERIFIED status. A typed STR does not satisfy SIP, photo does not satisfy KTP, diploma does not satisfy transcript; site-specific SIP selection remains exact.

## S5 — Versioned template, scoped Excel preview/apply, and result pages

**Create:** `sdm/import_views.py`, `sdm/forms/impor.py`, import templates, `sdm/tests/test_staff_import_routes.py`. Extend existing import service/tests, not a second importer.

Proposed NEW route contracts in `sdm/urls.py`:

```python
path('pegawai/impor/', import_views.import_upload, name='pegawai_import'),
path('pegawai/impor/template/', import_views.import_template, name='pegawai_import_template'),
path('pegawai/impor/<uuid:batch_id>/', import_views.import_preview, name='pegawai_import_preview'),
path('pegawai/impor/<uuid:batch_id>/terapkan/', import_views.import_apply, name='pegawai_import_apply'),
path('pegawai/impor/<uuid:batch_id>/hasil/', import_views.import_result, name='pegawai_import_result'),
```

Register these before the generic employee UUID route and import the new view module. They do not exist in the inspected baseline.

- [ ] Add this RED test inside existing `StaffImportTests` in `sdm/tests/test_staff_import.py`:

```python
    def test_preview_blocks_unit_outside_operator_scope(self):
        foreign = UnitKerja.objects.create(name='Foreign unit', code='IMPORT-FOREIGN')
        batch = preview_staff_import(
            actor=self.manager,
            workbook=self._workbook([[
                'FOREIGN-001', 'Fixture', 'NON_PPA', 'Administrasi', 'Staf',
                'AKTIF', 'TETAP', foreign.code, str(self.today), '', '1.00',
            ]]),
            idempotency_key='foreign-preview',
        )
        self.assertEqual(batch.state, 'BLOCKED')
        self.assertEqual(batch.row_create, 0)
        self.assertEqual(batch.row_blocked, 1)
        self.assertFalse(Pegawai.objects.filter(nomor_pegawai='FOREIGN-001').exists())
```

Run `sdm.tests.test_staff_import.StaffImportTests.test_preview_blocks_unit_outside_operator_scope`; expected RED because the parser currently loads all units.

- [ ] Fix preview to use `visible_units(actor, capability='can_manage_hc_employees')`. Unknown and foreign unit errors must not reveal foreign personnel data. Scope/owner/hash checks occur before returning even an already-APPLIED batch.
- [ ] Add RED route tests: authorized template XLSX download, upload → owned preview, no canonical rows before confirmation, blocked confirmation denied, GET apply returns 405, foreign batch denied, successful apply/result/profile, stale preview rejected, repeated apply returns recorded result.
- [ ] Harden parser: read at most 5,242,881 bytes, inspect ZIP metadata before openpyxl with total uncompressed cap 50,000,000 bytes, reject encryption/macros/external links/formulas, parse with `data_only=False`, cap nonempty staff rows at 2,000, require unique known headers/version. Use Decimal for FTE; reject NaN/infinity and Excel-coerced numeric NIK/NIP instead of guessing zeros. ISO dates are documented; valid native Excel dates may be normalized explicitly, not locale-guessed.
- [ ] Export a versioned v2 workbook with `Staf`, `Pendidikan`, `Izin`, and controlled-value/unit reference sheets. Cross-sheet identity is the exact NIP; employee fields cover S3, education rows allow multiple degrees, permit rows allow STR plus multiple SIPs. Do not import files, tokens, elevated-role flags, or plain passwords from spreadsheets. Preserve deliberate v1 parser compatibility for the existing minimal tests, clearly label its limited field coverage; never pretend v1 carries all new fields.
- [ ] Persist immutable normalized preview decisions/error cells and a scope+owner+file/version hash. Preview idempotency key reuse returns the same batch only for the same owner/file/scope; changed payload is a conflict. CREATE-only initial release must explicitly block existing NIP, not fuzzy-merge by name. Reviewed updates remain a separate owner-authorized extension.
- [ ] Use shared S2/S3 canonical validation/persistence for apply so employment, personal, education and permit rows are not silently dropped. Lock batch inside transaction, recheck current scope/master values/uniqueness/hash, apply all valid rows atomically only after explicit confirmation, audit each employee and the batch, record result employee UUIDs. No email is sent by preview; optional invitations are separately reviewed post-commit.
- [ ] Add `Impor Excel` and `Unduh template` beside `Tambah staf` in `templates/sdm/pegawai/list.html`, guarded by actual permissions. Menu plan M2 consumes these routes only after this gate passes.
- [ ] GREEN:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_staff_import sdm.tests.test_staff_import_routes sdm.tests.test_intake sdm.tests.test_penempatan --verbosity 2
```

Expected: `OK`; failed apply changes no canonical counts, repeated apply does not duplicate, all v2 fields survive round-trip to the profile.

## S6 — Optional account activation, delivery status, and no privilege escalation

**Existing interface:** `invite_staff_account(*, actor, employee, email, role, idempotency_key)` and `accept_staff_invitation(*, token, password)`. Keep them but fulfill their contracts.

**New routes in `accounts/urls.py`:**

```python
path('staf/aktivasi/<str:token>/', staff_activation_views.activate, name='staff_activate'),
path('staf/aktivasi-selesai/', staff_activation_views.complete, name='staff_activation_complete'),
```

**New HR route in `sdm/urls.py`:** `pegawai/<uuid:employee_id>/undangan/` named `pegawai_invitation`, served by a focused POST-only handler in `sdm/intake_views.py`; supports explicit invite/resend/revoke decisions after scoped employee lookup. Do not let query parameters choose arbitrary email targets or roles.

- [ ] Add RED tests to `test_staff_invitation.py` and new `accounts/tests_staff_activation.py` for real HTTPS link in locmem email, acceptance form GET with no mutation, strong-password POST, mismatch/weak password, expiry, replay, revoked invite, changed email, already-linked employee, same-key retry, mail failure, post-commit timing, and concurrent acceptance.
- [ ] Fix the existing expiry test: it currently stores `token_digest='expired-digest'` and submits that string as the raw token, which tests hash mismatch, not expiry. Store `sha256(raw.encode()).hexdigest()` and submit the raw token; assert `ValidationError`, never broad `Exception`.
- [ ] Change step four default to no-account until explicitly selected. When selected, require email, requested active/inactive account state and approved delegable role context. Reject unknown role codes by `UserProfile.ROLE_CHOICES` plus an explicit configured delegation allowlist, not only the current forbidden-role denylist. Do not automatically set role=ADMIN_RS/KEPALA_UNIT or issue HC/health grants from intake. If no approved role fits a nonclinical employee, preserve account-less employment and show the pending policy decision.
- [ ] Store invitation intent in the personnel transaction; deliver through `transaction.on_commit`. Mail errors record retryable status without propagating a false employee-creation failure. Idempotency must be durable and owner/employee bound; add required invitation key/state fields additively, hash raw tokens, recheck employee/contact version, and use row locks plus constraints for acceptance/reuse.
- [ ] Build the activation URL from a configured trusted `PUBLIC_BASE_URL` plus `reverse('accounts:staff_activate', kwargs={'token': token})`; require HTTPS outside local/test and do not trust arbitrary Host headers. Pass `activation_url` to the email template and replace `http://example.com/aktivasi/{{ token }}` with `{{ activation_url }}`.
- [ ] Activation uses Django password validation and CSRF, throttles retries, emits generic invalid/expired responses, and never mutates on GET. Redact token-bearing request paths from logs and use a restrictive referrer policy/no third-party page assets. Matching accepted retries do not create another account; unrelated existing accounts are never silently attached by email alone.
- [ ] After activation, link the exact employee/account and open the own-only portal from menu plan M3. No broad HR grant is added to make that page work. User status/employee status remain separate.
- [ ] GREEN:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_staff_invitation accounts.tests_staff_activation sdm.tests.test_staff_portal --verbosity 2
```

Expected: `OK`; use `captureOnCommitCallbacks(execute=True)` for `TestCase` delivery assertions and `TransactionTestCase`/PostgreSQL for race behavior. No live email is sent during automated tests.

## S7 — Browser UX, migration rehearsal, and evidence

- [ ] Run complete focused gate:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_intake sdm.tests.test_intake_uploads sdm.tests.test_directory sdm.tests.test_staff_import sdm.tests.test_staff_import_routes sdm.tests.test_staff_invitation accounts.tests_staff_activation sdm.tests.test_private_documents sdm.tests.test_storage_backend sdm.tests.test_dokumen sdm.tests.test_penempatan sdm.tests.test_staff_portal --verbosity 1
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django check
git diff --check
```

Expected: tests `OK`, system check no errors, whitespace exit code 0. Record actual counts; a migration-disabled suite proves behavior, not schema installation.

- [ ] Rehearse migrations on a disposable PostgreSQL database with migrations enabled, including a fresh schema and upgrade through the existing HC graph. Assert row/UUID/attachment references survive. Actual local/production migration is a separate approved operation. No guessed migration number or DB URL in the plan.
- [ ] Verify real browser journeys at 1440×900, 768×1024, and 360×800 using synthetic accounts: complete five steps, validation/back/resume/stale-tab, upload success/failure, review/finalize/replay, full profile, import preview/error/corrected apply, optional invitation/acceptance, own-only portal. The final result must be a working journey, not isolated screenshots.
- [ ] Match existing ARIMA brand; body/fields 16px, labels/descriptions >=14px, metadata >=13px, touch controls >=44px, two columns on desktop and one on mobile. Stepper uses readable text and `aria-current="step"`; error summary links to fields; full labels wrap. Replace inline 0.65rem step labels with scoped CSS; retain standard file input and keyboard access.
- [ ] Measure DOM overflow/computed fonts and screenshot both ends of the journey. No page overflow; only table wrappers may scroll. Use private-storage/email mocks for local E2E; real staging delivery/download is separately labeled and requires an approved target/account.
- [ ] Write `docs/qa/staff-intake-completion-verification.md` with executed commands, environment/runtime, RED evidence, GREEN results, migration rehearsal, browser artifacts, failed/blocked gates, and any approved policy decisions. Never label all-source requirements complete if advanced dependencies remain blocked.
- [ ] If commits are authorized, commit only reviewed green groups S1–S2, S3–S4, S5, S6–S7 with explicit file lists and `git diff --cached --check`. Do not use `git add .`, commit unrelated control work, push, or deploy.

## Review focus and risks

- Stale tabs and concurrent submits must not overwrite or duplicate employees; PostgreSQL locking requires its own proof.
- Uploaded objects and database transactions have different failure boundaries; preserve cleanup/retry state and truthful UI status.
- A field named `email_terverifikasi` is not proof of email verification; contact and login identity must not drift silently.
- NIP format, retirement policy, account role delegation, and reviewed workforce source need explicit hospital decisions; core UI fixes do not depend on invented defaults.
- Excel v2 parity costs a larger importer, but prevents “successful import” from discarding personal/legal data. Keep old minimal v1 compatibility visibly scoped.
- Own-only portal authorization is coordinated with menu plan M3; do not run conflicting edits in parallel.

## Definition of done

The user can add one staff member with all five steps and actual private files, import a reviewed workbook without hidden data loss, view the complete profile, and optionally activate the exact linked account. Happy path, validation, scope denial, version conflict, retries, external failure, and browser flows have fresh evidence. Existing legacy data/roles remain intact, and no unapproved live setup or deployment occurs.
