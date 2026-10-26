# ARIMA Improvement — Verified Baseline and Source Register

**Captured:** 2026-10-24, local development workspace.  
**Repository:** `C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django`.  
**Branch:** `master`.  
**Purpose:** Shared evidence for the three improvement tracks. This is not a production inventory or an implementation-completion claim.

## 1. Source documents

All three DOCX documents were read in full, including their tables/text extraction. Their packages contain no embedded media requiring image interpretation. Source filenames are preserved verbatim.

| Document in `C:/Users/cubeb/Downloads/` | SHA-256 | Requirements used |
|---|---|---|
| `struktur menu ideal Human capital.docx` | `ef7651202ed97bb39ecfcbb0a799294c5ada0e101a4fe4cecf7d613ac3afda0d` | Ten functional navigation groups; EWS; workforce/FTE/WISN; e-file; credentials; OPPE/FPPE; job descriptions; K3; self-service; reports; shifts/presence; trainees |
| `Input Data Staf.docx` | `7688458b28949f7b15ffd3121ea689e69ffad08d191fb91ccf55726b48ce3940` | Individual five-step intake, Excel intake, personal/employment/professional details, access provisioning, attachments and audit |
| `Cara melakukan perubahan sal.docx` | `0d6a5e7db568f0e9c996fa1343eae33daf4d2985a500784281049c0f57b0cd75` | Edition transition, historical archive, evidence mapping, RDWOS, staging validation and go-live |

The menu document has eleven numbered discussion sections but its final visual tree has ten top-level groups: trainees belong under e-file. Recruitment and advanced analytics from the earlier implementation remain available as submenus; the new tree must not remove them.

## 2. Evidence collection boundary

- The existing `db.sqlite3` was opened through SQLite URI `mode=ro` and `PRAGMA query_only=ON`.
- Only aggregate personnel/account results were collected; no employee names, identity numbers, contact details, secrets or private file URLs are copied into these plans.
- No production database, cloud bucket, live clinical service or deployment was queried.
- Source inspection covered current models, routes, forms, workflow services, tests, prior plans and runbooks. Database tables distinguish implemented schema from installed operational data.
- Scratch probes reside outside the repository under `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/`; they are not application deliverables.

## 3. Current data: do not substitute prior-plan numbers

| Entity / coverage | Measured local result | Planning consequence |
|---|---:|---|
| Authentication users / account profiles | 1,343 / 1,343 | Accounts are not the workforce census |
| Account profiles with unit | 1,317 | Unitless accounts exist; default-deny scope remains necessary |
| Profiles with employee-number prefix `HC-` | 1,295 | The account matrix contains seeded data |
| Organizational units | 219 | Reuse existing hierarchy; do not recreate unit masters |
| `sdm.Pegawai` | 425 | Existing employment UUIDs must be preserved |
| Employees linked to accounts | 425 | Account-less intake is supported by schema but has no current example |
| Employees with number prefix `HC-` | 425 | All current employee rows match the seeder's synthetic-number convention |
| Employee categories | 425 `PPA`, zero `NON_PPA` | This is not a verified clinical/non-clinical workforce distribution |
| Employee account roles | 211 `KEPALA_UNIT`, 214 `STAF_NAKES` | Role-matrix fixtures must not become clinical staffing truth |
| `PenempatanPegawai` | 425 across 217 units | Every current employee has one placement |
| Placement start dates | All 2026-10-23 | Backfill dates do not establish real TMT or historical staffing coverage |
| `HcGrant` | 5,256 | Do not re-provision everything or assume no access has been configured |
| HC audit events | 5 | Existing audit infrastructure exists, but this is not an onboarding audit history |
| Canonical HC documents / versions | 0 / 0 | An existing e-file UI is not evidence that real personnel files are installed |
| Requirement rules / reviewed KPS mappings | 0 / 0 | Compliance is not configured; an empty matrix must not yield 100% |
| Legacy `NakesCredential` | 13 | Preserve records while reconciling identities and provenance |
| Legacy credential owners with `Pegawai` link | 0 of 13 | Exact owner reconciliation must precede a usable canonical migration |
| Legacy credentials with cloud/local file reference | 0 of 13 | Metadata-only records cannot become verified private-file objects |
| Legacy-to-HC document links | 0 | Reconciliation has not populated this local database |
| Workforce plans / results / activities | 0 / 0 / 0 | FTE code exists, but actual staffing needs cannot yet be calculated from approved inputs |
| Recruitment, credential cases, SPK and orientation | All inspected tables empty | Deliver missing operator journeys and data setup, not another parallel model family |
| Training, appraisal, TNA and K3 records | All inspected tables empty | Use honest empty states; no live coverage/performance claim |
| Analytics snapshots, talent and scenarios | All inspected tables empty | Do not enable predictive or staffing/BOR claims from account fixtures |
| Accreditation frameworks | 1 | No installed local 2024 framework was observed |
| Framework identity | Name `STARKES Edisi 2022 / Kemenkes RI`; `version='2026'`; active | Instrument edition and target/accreditation year are currently ambiguous |
| EP rows | 1,053 under that framework | Do not assume the 794-item rehearsal catalogue is already installed |
| Evidence requirements / evidence files | 769 / 1 | Requirement rows are not uploaded evidence; preserve and inventory the existing evidence file |
| `QualityRecord` | 298 | These are populated assessment records, not disposable seed placeholders |
| Records with positive score | 298 | Unreviewed same-code score relocation changes meaningful data |
| Records with evaluation notes / baseline text | 276 / 11 | Archive must preserve text as well as numeric scores |

Seeder provenance: the existing, untracked `accounts/management/commands/seed_akun_per_unit.py:319-321` creates deterministic `HC-<unit>-<role>-<id>` numbers. That command also creates employee/placement rows for operational roles. The prefix and shape establish fixture provenance for this baseline; they are **not** a future production classifier. Add explicit provenance and a reviewed classification artifact before filtering, merging or hiding any existing row. Do not infer that an unmarked record is real.

Legacy-credential status/type groups exist, including verified, pending and expired STR/SIP/SPK/training metadata. Because all thirteen lack file references and account-to-employee ownership links, do not copy their `VERIFIED` flags into claims of verified canonical files.

## 4. Existing assets to extend

| Asset | Current source | Reuse rule |
|---|---|---|
| Employment identity and dated allocations | `sdm/models/pegawai.py` | Extend `Pegawai`; retain `akun` nullable OneToOne and stable UUIDs |
| Individual creation | `sdm/forms/pegawai.py`, `sdm/views.py:174-214`, `templates/sdm/pegawai/form.html` | Current flow is a small single form; preserve its atomic employee/placement save |
| Scope/grants | `sdm/akses.py`, `sdm/models/akses.py` | Capability plus authorized unit/object scope; no global access from missing unit |
| Private files | `sdm/storage.py`, `sdm/storage_backend.py` | Opaque private keys, authorized short-lived download, no public fallback |
| Audit | `sdm/models/audit.py` | Reuse event mechanism; record changes without copying sensitive values |
| Document rules | `sdm/models/dokumen.py`, `sdm/services/kepatuhan.py` | Add precise applicability, document identity and evidence binding before seeding rules |
| Staffing calculation | `sdm/services/formasi.py` | Reuse Decimal calculation/versioning; do not relabel activity FTE as WISN |
| All five HC maturity levels | `sdm/models/`, `sdm/services/`, `sdm/urls.py`, `sdm/views.py` | Existing code is real; verify remaining UI and data completeness separately |
| Catalogue edition resolution | `akreditasi/models.py` (`Framework.active`) | Extend the existing resolver, not a second edition-selection mechanism |
| 2024 tooling | `akreditasi/management/commands/import_instrumen_2024.py`, `starkes_2024_cutover.py` | Harden guarded operations; do not reimplement a generic import |

### Confirmed e-file matching defect

`sdm/services/kepatuhan.py:93-98` selects a latest version by broad `document_type`, not a specific legal-document subtype or requirement binding. `DokumenPegawai` stores generic `CREDENTIAL`, `EDUCATION`, `IDENTITY`, etc. Consequently, creating separate STR/SIP/SPK rules with the same generic type would allow one file to be selected for several distinct requirements. Neither the filename nor upload count resolves this defect. Track B must introduce explicit reviewed matching before track A activates requirement matrices or compliance reports.

### Confirmed employment/intake gaps

`Pegawai.status` is only `AKTIF`/`NONAKTIF`, not Tetap/PKWT/Mitra. The model has no NIK, split name/title, birth/contact/address, employment contract category, employment TMT, weekly hours, structured education, typed license/location or account-invitation state. `PenempatanPegawai.tanggal_mulai` is a placement date, not employment TMT. `sdm/urls.py` has neither an Excel-import workflow nor a five-step intake workflow. `accounts/urls.py` exposes account CRUD but no activation/password-reset routes.

## 5. Reconcile earlier artifacts, do not inherit completion claims

- `2026-10-23-arima-human-capital-scope.md` still says proposed/not implemented. Its companion implementation plan and release evidence say implementation exists. Current source confirms the app exists; the old scope status is stale, while operational setup remains incomplete.
- The older plan's 45 account profiles and four nonblank employee numbers no longer describe this database. Current counts above supersede them for planning.
- `docs/security/starkes-2024-cutover.md` describes a rehearsal with 794 active EP and 31 moved assessment records. The current local SQLite database has no 2024 framework. Rehearsal, current local state and production state are distinct environments.
- Do not assume decree-derived EP and the separate survey instrument provide identical RDWOS coverage. Track C owns source/provenance reconciliation.
- New shift/presence/leave features expand the earlier HC scope, which explicitly excluded them. They are isolated optional increments, not retrospective claims that the earlier feature failed its approved scope.

## 6. Additional source/parser verification

The existing parser was executed read-only against both locally available 2024 PDFs, with Django database settings overridden to SQLite `:memory:` and no migration/import calls.

| Source | Measured result |
|---|---|
| `starkes 2024.pdf` — KMK HK.01.07/MENKES/1596/2024 | 356 pages; SHA-256 `22d2247e6a2b272789141536ca4539f99ebb825ad6c7bfe61106d065aa453116`; parser emitted 794 unique EP across 16 prefixes, 792 without extracted RDWOS |
| `instrumen standar survey akreditasi  rs 2024.pdf` — Dirjen HK.02.02/D/47104/2024 | 415 pages; SHA-256 `fde4091e97bd4b9de944994e3764a125bdc83f07d3fba680ecb5023bb478dd80`; parser emitted 732 unique EP across 16 prefixes, 105 without extracted RDWOS |
| Existing JSON fixture | SHA-256 `6ea5400d457ae734ddabd5f773b0d412522888e51e7e4e87ec2970408646f936`; 783 EP entries but only 700 unique keys across 15 prefixes, no PROGNAS; 179 entries without evidence types |

These are extraction inventories, not owner-validated official totals. The importer truncates text to 300 characters; the decree and survey instrument are different source classes. Track C must reconcile both sources and replace/quarantine the unreviewed fixture before any live import. The prior rehearsal's 794 count alone is not a valid RDWOS-completeness gate.

Additional static findings incorporated in the menu/transition plans: silent 200-person compliance sampling; nonannual any-course training coverage; turnover ignoring requested dates; BOR ignoring its unit argument and historical capacity; hospital-scope grants omitted from HC navigation; mapping dependent on an assessment row; global accreditation dashboard mixing editions; archive writes unguarded; code-only score relocation; guarded cutover preview not parsing the source. These are findings from code inspection, not claims of production exploits or newly executed feature tests.

## 7. Verification actually executed for this planning task

Interpreter discovery:

- Project `.venv/Scripts/python.exe`: Python **3.12.10**, installed Django **6.1.1**.
- `requirements.txt`: pins Django **6.1.2**. This version mismatch is recorded, not silently repaired during planning.

Execution used a scratch bootstrap overriding the database to SQLite `:memory:`, cache to locmem, mail to locmem, file output to scratch and static storage to a test backend **before Django setup**. The live local SQLite and any configured remote database were not test targets.

| Check | Actual result |
|---|---|
| `call_command('check')` under isolated settings | No issues; one pre-existing silenced check |
| `call_command('test', 'sdm', 'akreditasi.tests_starkes_2024', verbosity=1, interactive=False)` | **246 tests, OK**, 14.728 seconds reported by runner |
| Read-only SQLite inventory | Successful; aggregate snapshot saved outside repository |
| Document hashing/package inspection | All three readable; no embedded media |

Passing current tests does not establish the missing requirements. Several gaps above are behavior absent from the current suite. No fresh PostgreSQL rehearsal, full cross-app regression, browser E2E, bucket verification or production deployment was performed.

## 8. Working-tree preservation

Pre-existing untracked paths: `accounts/management/`, `docs/akun_per_unit_report.txt`, `docs/superpowers/plans/2026-10-23-qa-fleet-1295-akun.md`, `qa/`. They are user work and must not be overwritten, staged, removed or normalized by these plans. No commits, pushes, catalogue imports, staff imports, grants or migrations were applied while preparing the improvement package.
