# Human Capital Staff Identity — Reconciled Delivery Roadmap

> **For agentic workers:** Read this roadmap before either companion plan. Use `executing-plans` or `subagent-driven-development` only after the user approves execution. This planning task changes plan documents only; it authorizes no implementation, migration, seeding, grant, email, commit, push, or deployment.

**Goal:** Deliver the staff-identity requirements in `input identitas karyawan.docx` — KTP smart-scan intake, separate official-photo/KTP slots, a complete Digital Staff Profile, and the requested directory upgrade — by completing the existing `sdm` implementation rather than rebuilding it.

**Architecture:** Keep `sdm.Pegawai` (UUID) as the single canonical identity, keep effective-dated `PenempatanPegawai`, typed `DokumenPegawai`/`VersiDokumen` with private storage, and keep the `sdm` route namespace. Repair the five-step intake that already exists but is broken at three points, then extend it additively. OCR is a pluggable, feature-flagged adapter — never a hard dependency of the intake form. Directory work is presentation plus two new scoped read endpoints, not a second employee master.

**Stack:** Existing Django 6.1.2 / templates / Bootstrap 5.3.3 / openpyxl / reportlab / Supabase private storage. No SPA, no paid HR service, no new frontend framework.

---

## Plan package

| File | Scope | Depends on |
|---|---|---|
| `2026-10-25_090000-hc-staff-identity-roadmap.md` (this file) | Source register, delta analysis, verified defects, decisions, release order, acceptance | — |
| `2026-10-25_090000-staff-intake-v2.md` | Five-step intake repair and completion, photo/KTP slots, STR/SIP/education, RBAC role, Excel import, activation, Digital Staff Profile | This roadmap |
| `2026-10-25_090000-hc-directory-enhancement.md` | Avatar column, extra columns, contact chips, dependent filters, live search, Excel/PDF export, bulk actions | This roadmap; avatar rendering depends on intake plan Task 4 |
| `2026-10-25_090000-ktp-smart-scan.md` | Pluggable KTP OCR adapter, preprocessing, field parser, confirm-before-fill UI | This roadmap; independent of the other two |

All four files live in `.hermes/plans/`. Plan prose is English; quoted Indonesian strings are literal product copy and must not be translated during execution.

## Supersession

`.hermes/plans/2026-10-24_201051-staff-intake-completion.md` is **superseded** by `2026-10-25_090000-staff-intake-v2.md`. Do not execute both. The old plan was written against source hash `7688458b…` and never executed; the new intake plan re-states its still-valid contracts in full so an executor needs only one document, and adds the items the new source introduces.

`.hermes/plans/2026-10-24_201051-hc-additions-roadmap.md` and `2026-10-24_201051-hc-menu-integration.md` remain valid for the **ten-group navigation** workstream. This package does not touch navigation groups, the control shell, clinical modules, or the STARKES catalogue. Where they disagree with this package, this package wins only for staff-identity scope.

`docs/superpowers/plans/2026-10-24-staff-intake-efile.md` and `2026-10-24-human-capital-menu-workflows.md` remain useful domain context. Their create-all-models steps are stale: those model families already exist in `sdm/migrations/0015`–`0025`.

## Source register

| Input | SHA-256 | Scope |
|---|---|---|
| `C:/Users/cubeb/Downloads/input identitas karyawan.docx` | `60e0691b825244a07e93d0a39f8bc4220396a8ba0d21c3b323f55c00d7b4e803` | Two intake methods, five form steps, KTP OCR smart-scan, separate photo/KTP slots, post-input outputs, directory upgrade |
| `C:/Users/cubeb/Downloads/Input Data Staf.docx` (previous revision) | `7688458b28949f7b15ffd3121ea689e69ffad08d191fb91ccf55726b48ce3940` | Superseded by the above; retained for delta only |

The new document is 70 extracted lines against the previous 54. A line-level diff was run, not an eyeball comparison.

## Delta analysis — what is actually new

Most of the new document restates requirements already planned. Only three blocks are genuinely new:

| # | New requirement | Source lines | Status in codebase | Owner plan |
|---|---|---|---|---|
| N1 | KTP Smart Scan / OCR auto-fill (NIK, name, birth, sex, religion, marriage, address) | 10–12 | **Absent.** No OCR library in `requirements.txt`, no adapter, no endpoint, no UI | `ktp-smart-scan` |
| N2 | Separate official-photo slot (directory avatar) and KTP-photo slot | 13 | **Absent.** No photo field on any `sdm` model; `accounts.UserProfile.photo_url` is an unused `URLField` | `staff-intake-v2` Task 4 + `hc-directory-enhancement` Task 1 |
| N3 | Directory upgrade block: avatar, name capitalization, Nomor column, FTE tooltip, quick contact, tenure, supervisor, dependent filters, live search, Excel/PDF export, bulk actions | 51–70 | **Absent** except name/Nomor/FTE columns that already render but lack the described affordances | `hc-directory-enhancement` |

Everything else in the document — five-step structure, NIP generation, name/title split, WhatsApp/email, domicile-same-as-KTP, employment status dropdown, TMT, main unit/sub-unit, structural/functional position, weekly hours, profession category, last education, STR with lifetime option, SIP with practice-site number, three RBAC levels, account active/inactive, 5 MB drag-and-drop attachments, digital profile, account auto-generation, audit trail, bulk Excel import — is a **restatement** of requirements already covered by the superseded plan. The intake plan still has to deliver them because that plan was never executed.

## Verified defects (probe evidence, not code reading)

Read-only probes were run on `master` at `1f6b179` with `DJANGO_SETTINGS_MODULE=config.control_test_settings`. Each finding below was reproduced.

**D1 — Every wizard step from 2 onward raises `NoReverseMatch`.**

`templates/sdm/pegawai/wizard.html:58` reverses `sdm:pegawai_wizard_step` with two positional arguments; the route accepts one.

```
step 1: HTTP 200
step 2: EXCEPTION NoReverseMatch: Reverse for 'pegawai_wizard_step' with arguments '(1, UUID('56d130d2-…'))' not found.
       1 pattern(s) tried: ['human\-capital/pegawai/input/baru/(?P<step>[0-9]+)/\Z']
step 3: EXCEPTION NoReverseMatch: … arguments '(2, UUID(…))' …
```

The same bug exists at `templates/sdm/pegawai/wizard_finalize.html:33` (`'sdm:pegawai_wizard_step' 5 draft.pk`). The working route is `sdm:pegawai_wizard_resume` with named `step` and `draft_id`.

**D2 — The step-5 main action is an anchor, so step 5 never submits.** `wizard.html:69` renders `<a href="{% url 'sdm:pegawai_intake_finalize' draft.pk %}">`. The form at `wizard.html:25` has no `enctype="multipart/form-data"` and no file input (`multipart/form-data` present: `False`; `type="file"` present: `False`).

**D3 — Finalization accepts an incomplete draft.** `sdm/intake_views.py:189` sets `required_steps = {'1', '2'}`. Probe: a draft containing only steps 1 and 2 finalized successfully —

```
finalize with steps 1-2 only -> 302 /human-capital/pegawai/1cbf181d-…/
employees created: 1 | placements: 1
```

Step 4 (account/access) is read into `step4` and never used. Step 5 writes document metadata only when `dokumen_judul` is non-empty, and always as `document_type='OTHER'` with no file version.

**D4 — Stale-tab protection is defeated.** `sdm/intake_views.py:157` passes `expected_version=draft.version` from a freshly loaded row, so the browser's version never participates. `wizard.html` sends no `expected_version` field at all.

**D5 — Replay cannot return the original result.** `DrafInputPegawai` has no result link (`finalized_employee` absent — probe: `finalized_employee attr: False`). Replaying finalization on a finalized draft redirects to step 1 instead of the created employee.

**D6 — Placement bypasses the FTE service.** `sdm/intake_views.py:250` calls `PenempatanPegawai.objects.create(...)` directly. `save_assignment()` — which enforces the peak-allocation ≤ 1.00 rule and serializes per employee — is never called (`grep -c save_assignment sdm/intake_views.py` → `0`).

**D7 — The Digital Staff Profile does not exist.** `templates/sdm/pegawai/detail.html` renders six fields and three tabs. Probe on the employee created above: `detail HTTP 200 | shows personal profile section: False`. `profil_pribadi`, `riwayat_kepegawaian`, `riwayat_pendidikan`, and `izin_profesi` are written by the finalizer and never displayed (`grep -c profil_pribadi templates/sdm/pegawai/detail.html` → `0`).

**D8 — Step 3 cannot express the source's STR + multiple SIP model.** `IntakeStep3Form` is a flat form with one `izin_subtype`. `IzinProfesiPegawai` already supports many rows with `lokasi_praktik` and `is_local_rs`, so the model is right and the form is wrong.

**D9 — Step 4 has no role and no account status.** `IntakeStep4Form` exposes only `create_account` and `email`. The source's three-level RBAC and active/inactive account state are unrepresented.

**D10 — Excel import has no routes.** `sdm/services/impor_pegawai.py` implements `preview_staff_import` and `apply_staff_import`; `sdm/urls.py` registers none of them, `sdm/import_views.py` does not exist, and no template exists. `apply_staff_import` uses `float()` for FTE, creates the employee then re-reads it by NIP, and calls `PenempatanPegawai.objects.create` directly.

**D11 — Account activation has no HTTP surface.** `sdm/services/undangan.py` implements `invite_staff_account` and `accept_staff_invitation`; `accounts/urls.py` has no activation route and no view module. `templates/accounts/email/invitation_body.txt` contains the literal placeholder `http://example.com/aktivasi/{{ token }}`. `invite_staff_account` sends mail inside its own call despite the post-commit comment.

**D12 — Dead route handler.** `sdm/views.py:189 def pegawai_create` is unreachable: `sdm/urls.py:13` maps `pegawai/baru/` to `intake_views.intake_wizard`.

**D13 — Typo in shipped copy.** `'Tanggal Berthi'` appears at `sdm/models/intake.py:240`, `sdm/forms/intake.py:216`, and `sdm/migrations/0015_add_intake_models.py:105`. Fix the source in a new migration's `AlterField`, not by editing `0015`.

**D14 — Photo/avatar has no storage path.** No `sdm` model carries an image field; `accounts.UserProfile.photo_url` (`URLField`) is referenced by zero templates and zero views.

## Environment facts that constrain the plans

| Fact | Evidence | Consequence |
|---|---|---|
| `Pillow 12.3.0` is installed but **not declared** | `importlib.metadata.version('pillow')` → `12.3.0`; `grep -c Pillow requirements.txt` → `0` | Any new `from PIL import` breaks a fresh deploy. The plan that adds image handling must add the pin to `requirements.txt` in the same task. |
| `pytesseract` is importable but the tesseract binary is absent | `pytesseract.get_tesseract_version()` → `TesseractNotFoundError`; no binary under `Program Files` or `AppData\Local\Programs` | Local OCR cannot run today. A local-OCR adapter must fail closed with an explicit unavailable reason. |
| Configured AI provider is text-only | `akreditasi/system_models.py` `AI_MODEL_CHOICES` = `deepseek-chat`, `deepseek-reasoner` | DeepSeek cannot read an image. KTP OCR cannot be implemented by calling the existing AI service. This is a decision gate, not an implementation detail. |
| Vercel build cannot install system packages | `vercel.json` uses `@vercel/python` only | A tesseract-based adapter requires Railway/nixpacks (`nixpacks.toml` exists) or a different host. |
| `sdm` migration `0025_add_presensi_models` is unapplied locally | `showmigrations sdm` → `[ ] 0025_add_presensi_models` | New migrations start at the next number the graph produces (`0026` expected); never reuse `0025`. |
| Local DB has **zero** employees | `Pegawai.objects.count()` → `0` | The document's "lowercase demo name" and "empty Nomor" complaints describe demo data that does not exist locally. Do not write a data migration for it; ship a read-only audit command and fix the seeder. |
| `MasterProfesiPegawai` has zero rows and no seeding command | `MasterProfesiPegawai.objects.count()` → `0`; `grep -rln MasterProfesiPegawai` → model, migration, `__init__` only | A profession-master FK must tolerate an empty master and must not block intake. |
| Measured baseline test count | `python -m django test sdm` → `Ran 291 tests … OK` | Any plan that changes `sdm` must end at ≥ 291 passing with 0 failures. |
| Measured focused baseline | `test_directory test_staff_import test_staff_invitation` → `Ran 20 tests … OK` | These 20 must stay green; the intake plan rewrites one of them deliberately (see its Task 3). |

## Decisions recorded before implementation

| # | Decision | Rationale |
|---|---|---|
| X1 | No password is ever emailed. Activation uses a single-use expiring link and a user-chosen password. | The source asks for "Username dan Temporary Password". A temporary password in email is a credential leak with no compensating benefit; the activation link achieves the same onboarding outcome. |
| X2 | OCR never writes to the form automatically. Extracted values are shown for per-field confirmation. | KTP OCR misreads digits; an auto-filled NIK that the operator does not re-read becomes a wrong identity on an accreditation record. |
| X3 | OCR is feature-flagged off by default and is never a precondition for saving an employee. | The provider decision is unresolved and the local binary is missing. Manual entry must always work. |
| X4 | Official photo is stored as a **private** derivative object and served through an authenticated, cache-controlled view — never a public bucket URL. | A face is personal data; `accounts.UserProfile.photo_url` as a public URL is exactly the pattern to avoid. |
| X5 | `atasan_langsung` is a nullable FK on `PenempatanPegawai`, not on `Pegawai`. | Supervisors change; the placement table is already effective-dated, so history comes free. `UnitKerja.pic_name` is a free-text string and cannot answer "who reports to whom". |
| X6 | The directory `Nomor` column hides itself when no row on the current page has a number; it is never replaced with a masked NIK. | A directory listing is the wrong place to expose identity numbers to unit heads. |
| X7 | Contact chips (phone/WhatsApp/email) render only for callers holding `can_manage_hc_employees` on that employee, or for the employee's own row. | The superseded plan already requires unit heads to see operational data without contact export. |
| X8 | Bulk actions are limited to scoped status change and scoped Excel export of the selected rows. No bulk ZIP of private documents. | A ZIP of private files multiplies signed-URL issuance and turns one click into an unbounded egress event. |
| X9 | Do not auto-title-case stored names. Add a `nama_tampil` property that composes titles, and fix the seeder. | Auto-capitalization corrupts `de`, `bin`, `Muhammad`, and degree suffixes. |
| X10 | Keep `Pegawai.status` (AKTIF/NONAKTIF), employment category, TMT, placement start, and authentication account status as four separate facts. | The source conflates them; collapsing them silently deactivates logins when an employment record ends. |

## Release order

Each release is independently shippable and independently verifiable.

| Release | Content | Blocking gate |
|---|---|---|
| **R0** | Apply local migration `0025`; record the real baseline numbers | `showmigrations sdm` shows all applied; `python -m django test sdm` still `OK` |
| **R1** | Wizard repair: D1, D2, D3, D4, D5, D6, D12, D13 — intake plan Tasks 1–3 | A complete five-step draft finalizes; an incomplete one does not; steps 2–5 render |
| **R2** | Photo + KTP slots, staged attachments, Digital Staff Profile — intake plan Tasks 4 and 7 | A real file reaches private storage; the profile page shows every captured field |
| **R3** | Legalitas/education formsets, profession master FK, sub-unit, step-4 RBAC — intake plan Tasks 5 and 6 | One person can hold one STR and two site-specific SIPs; no intake path grants an admin role |
| **R4** | Excel import UI and account activation — intake plan Tasks 8 and 9 | Preview creates zero canonical rows; a real activation link activates exactly one account |
| **R5** | Directory enhancement — directory plan Tasks 1–7 | Avatar, tenure, supervisor, filters, live search, export, bulk status all work within grant scope |
| **R6** | KTP smart scan — smart-scan plan Tasks 1–6 | Flag off ⇒ zero behaviour change; flag on with no provider ⇒ explicit unavailable reason, never a 500 |
| **R7** | Migration rehearsal, browser verification, QA report — intake plan Task 10 | Recorded evidence file with executed commands and real output |

R5 depends on R2 for the avatar source object. R6 is independent of R3–R5 and may ship at any point after R1.

## Global constraints

- Planning only until execution approval. No implementation, migration, seeding, grant provisioning, live email, live storage call, commit, push, or deployment in this planning turn.
- Preserve all existing employee UUIDs, accounts, units, credential rows, file references, and workflow history. Blank legacy fields stay unknown; never manufacture NIK, birthdate, TMT, or verification status.
- Use the existing authorization boundaries: `require_hc_capability`, `visible_units`, `visible_employees`, `save_assignment`, `PeristiwaSDM`, `store_private_document`. Do not add a parallel permission system.
- UI copy stays Bahasa Indonesia. Empty configuration renders `Belum dikonfigurasi`; insufficient data renders `Belum dapat dihitung`; not applicable renders `Tidak berlaku` — never `0%`.
- NIK is a 16-character ASCII digit string when supplied, preserving leading zeros. Never an integer, never locale-formatted.
- Intake attachments: PDF/JPG/JPEG only, `5_242_880` bytes per file, UI text `Maksimal 5 MiB per berkas`. Existing PNG versions stay downloadable; do not rewrite legacy history to fit the new policy.
- Never place NIK, contact data, file bytes, activation secrets, or private URLs in cookies, query strings, shared cache, logs, or audit descriptions.
- New migrations are generated from the actual graph. `0025` is unapplied locally; expected next is `0026`, but the executor records the real number rather than assuming it.
- Commit, push, and deployment require separate user instruction. Task completion is not commit permission.

## Acceptance for the whole package

The operator can: scan or type an identity into five steps and reach a complete profile page; upload a photo that appears as the directory avatar; hold one STR and multiple site SIPs; create a login by activation link without ever emailing a password; import a reviewed workbook whose rows either all land with their personal and legal data or are blocked with visible reasons; and use a directory that shows photo, tenure, supervisor, contact, and working filters with Excel/PDF export — all inside grant scope, with every write audited, and with OCR either working behind its flag or honestly reported unavailable.

## Explicitly NOT in this plan

Do not implement, and do not fix while here:

- The ten-group HC navigation tree, the Integrated Control shell, or the control-hub readability work — separately owned by `2026-10-24_201051-hc-menu-integration.md` and `2026-10-24_185444-control-readability-emr-registration.md`.
- Shift scheduling, attendance, leave approval, payroll, or remuneration calculation.
- Clinical privilege enforcement, SPK issuance, or RME write authorization.
- STARKES catalogue data, indicator data, or workforce census provenance.
- The dead `sdm/views.py:189 pegawai_create` handler: delete it only if a task says so; do not repurpose it.
- Any auto-title-casing of stored names, any data migration that rewrites existing `Pegawai` rows, and any repair of `sdm/migrations/0015`.
