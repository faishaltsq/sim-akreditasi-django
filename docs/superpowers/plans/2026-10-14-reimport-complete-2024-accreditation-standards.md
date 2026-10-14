# Complete 2024 Hospital Accreditation Standards & Assessment Elements (EP) Ingestion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse, validate, and comprehensively ingest the complete 16 chapters, ~196 standards, and ~780+ Assessment Elements (Elemen Penilaian / EP) with RDWOS evidence requirements from the Ministry of Health (Kemenkes) 2024 Accreditation Instrument (`instrumen standar survey akreditasi  rs 2024.pdf`) into PostgreSQL/SQLite, upgrading legacy 2022 codes without losing existing hospital assessment records.

**Architecture:** Build a resilient, idempotent PDF extraction and parsing pipeline in `akreditasi/management/commands/import_instrumen_2024.py`. Map and reconcile legacy nomenclature (e.g., ARK → AKP, legacy PROGNAS/IPKP → PPK/PROGNAS 2024), create/update canonical `Category`, `StandardItem`, and `EvidenceReq` records, and preserve or backfill existing `QualityRecord` self-assessments safely.

**Tech Stack:** Python, Django 5.x ORM, `pypdf`, regex parsing engine, PostgreSQL (Supabase) / SQLite.

**Spec:** Kemenkes Decree No. HK.02.02/D/47104/2024 (`instrumen standar survey akreditasi  rs 2024.pdf`), based on KMK HK.01.07/MENKES/1596/2024.

---

## Global Constraints

- Plans and technical specifications must be written in English.
- No existing `QualityRecord` data (assessments, baseline scores, uploaded documents) may be deleted or corrupted during re-import.
- Re-import must be idempotent: running the command multiple times yields the exact same clean dataset without duplicate codes or broken foreign keys.
- Standard codes must follow canonical Kemenkes format: `[BAB] [NUM] EP [NUM]` (e.g. `TKRS 1 EP 1`, `AKP 1.1 EP 2`, `MFK 8.2 EP 3`).
- All evidence requirements (`EvidenceReq`) must extract the category type (R, D, W, O, S), title, and mandatory flag.

---

## Gap Analysis Summary (Current DB vs 2024 Instrument)

| No | Category / Chapter | Current DB EP Count | 2024 PDF Instrument EP | Gap / Missing Elements | Action |
|---|---|:---:|:---:|---|---|
| 1 | **TKRS** (Tata Kelola Rumah Sakit) | 28 EP | 79 EP | 51 EP missing; missing standards TKRS 3, TKRS 7.1, TKRS 13-15 incomplete | Ingest full 17 standards (79 EP) |
| 2 | **KPS** (Kualifikasi & Pendidikan Staf) | 32 EP | 79 EP | 47 EP missing; missing KPS 8.1, KPS 10.1, KPS 13, KPS 15, KPS 18-19 | Ingest full 19 standards (79 EP) |
| 3 | **MFK** (Manajemen Fasilitas & Keselamatan) | 21 EP | 65 EP | 44 EP missing; missing MFK 8.1, 8.2, 8.3, MFK 11 | Ingest full 12 standards (65 EP) |
| 4 | **PMKP** (Peningkatan Mutu & Keselamatan Pasien) | 18 EP | 42 EP | 24 EP missing; PMKP 4.1, PMKP 11 missing | Ingest full 11 standards (42 EP) |
| 5 | **MRMIK** (Manajemen Rekam Medis & Info) | 14 EP | 47 EP | 33 EP missing; MRMIK 2.1, 2.2, 13.1 missing | Ingest full 14 standards (47 EP) |
| 6 | **PPI** (Pencegahan & Pengendalian Infeksi) | 28 EP | 66 EP | 38 EP missing; PPI 1.1, 7.1, 7.2, 10.1, 11.1 missing | Ingest full 16 standards (66 EP) |
| 7 | **AKP** (Akses dan Kontinuitas Pelayanan) | 23 EP (legacy **ARK**) | 70 EP | 47 EP missing; uses obsolete "ARK" prefix instead of "AKP" | Migrate ARK → AKP & ingest 70 EP |
| 8 | **HPK** (Hak Pasien dan Keluarga) | 11 EP | 23 EP | 12 EP missing; HPK 1.1–1.5, 2.1–2.2 missing | Ingest full 7 standards (23 EP) |
| 9 | **PP** (Pengkajian Pasien) | 16 EP | 57 EP | 41 EP missing; PP 1.1–1.3, PP 3.1–3.9 missing | Ingest full 19 standards (57 EP) |
| 10 | **PAP** (Pelayanan dan Asuhan Pasien) | 19 EP | 44 EP | 25 EP missing; PAP 1.1–1.2, PAP 2.1–2.7 missing | Ingest full 14 standards (44 EP) |
| 11 | **PAB** (Pelayanan Anestesi dan Bedah) | 20 EP | 42 EP | 22 EP missing; PAB 3.1–3.2, PAB 6.1, PAB 7.1–7.4 missing | Ingest full 14 standards (42 EP) |
| 12 | **PKPO** (Pelayanan Kefarmasian & Obat) | 20 EP | 49 EP | 29 EP missing; PKPO 3.1–3.3, PKPO 4.1, 5.1, 6.1, 7.1 missing | Ingest full 13 standards (49 EP) |
| 13 | **KE** (Komunikasi dan Edukasi) | 7 EP | 17 EP | 10 EP missing; KE 4, 5, 6, 7 missing | Ingest full 7 standards (17 EP) |
| 14 | **SKP** (Sasaran Keselamatan Pasien) | 10 EP | 24 EP | 14 EP missing; SKP 3.1, SKP 6.1 missing | Ingest full 6 standards (24 EP) |
| 15 | **PROGNAS** (Program Nasional) | 26 EP | 42 EP | 16 EP missing; PONEK, TB, HIV, Stunting, PPRA sub-items | Ingest full 5 programs (42 EP) |
| 16 | **PPK / IPKP** (Pendidikan Pelayanan Kesehatan) | 6 EP | 24 EP | 18 EP missing; PDF uses "PPK 1 - PPK 6" | Ingest full 6 standards (24 EP) |
| **TOTAL** | **16 Chapters** | **299 EP** | **~780 EP** | **~480+ Assessment Elements Missing (61% gap)** | **Full Re-ingestion Required** |

---

## Review Focus

1. **Foreign Key Integrity with QualityRecord**: Legacy `QualityRecord` links to `StandardItem` via OneToOne. When standard codes are updated (e.g. `ARK 1 EP 1` → `AKP 1 EP 1`), ensure existing user notes, scores, and uploaded evidence are seamlessly preserved.
2. **RDWOS Evidence Separation**: In 2024 instrument, each EP has specific proof types (Regulasi, Dokumen, Wawancara, Observasi, Simulasi). Ingest these into `EvidenceReq` linked to each `StandardItem`.
3. **Database Performance on 780+ EP**: List views, category filters, and matrix pages must load efficiently using `select_related('category')` and cached aggregates.
4. **Sub-standard Numbering Normalization**: Standards like `TKRS 3.1`, `MFK 8.2`, `MRMIK 13.1`, `PPI 7.2` must sort logically, not alphabetically (e.g. `TKRS 2` before `TKRS 10`).
5. **Dry-Run Mode**: Provide a `--dry-run` flag in the management command so administrators can preview additions, modifications, and migrations before committing.

---

## Task Decomposition

### Task 1: Build 2024 Accreditation PDF Parser Engine

**Files:**
- Create: `akreditasi/services/instrumen_parser.py`
- Test: `akreditasi/tests_instrumen_parser.py`

**Interfaces:**
- Consumes: PDF binary file at `C:\Users\cubeb\Downloads\instrumen standar survey akreditasi  rs 2024.pdf`.
- Produces: Structured dictionary of 16 chapters, standards, assessment elements (EP), descriptions, and RDWOS evidence requirements.

- [ ] **Step 1: Write unit tests for PDF parser**
  Test extraction of chapters (TKRS, KPS, MFK, etc.), standards (TKRS 1, TKRS 7.1), EP letters (a, b, c...), and RDWOS tags.
- [ ] **Step 2: Run test to verify it fails**
  `python manage.py test akreditasi.tests_instrumen_parser -v 2`
- [ ] **Step 3: Implement `InstrumenParser` service in `akreditasi/services/instrumen_parser.py`**
  Parse text, identify sections by regex, extract tabular EP columns (Elemen Penilaian, Kelengkapan Bukti, Skoring), and output clean JSON/dict.
- [ ] **Step 4: Run test to verify parser passes and outputs all 16 chapters**
- [ ] **Step 5: Commit parser service**
  `git commit -m "feat(akreditasi): implement 2024 accreditation instrument pdf parser"`

---

### Task 2: Build Management Command `import_instrumen_2024`

**Files:**
- Create: `akreditasi/management/commands/import_instrumen_2024.py`
- Test: `akreditasi/tests_import_command.py`

**Interfaces:**
- Consumes: `InstrumenParser` output.
- Produces: Database records in `Category`, `StandardItem`, `EvidenceReq`, and safely migrates `QualityRecord`.

- [ ] **Step 1: Write integration tests for import command**
  Test `--dry-run`, test legacy code migration (ARK → AKP), test idempotent re-runs, and test that existing `QualityRecord` data is preserved.
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `import_instrumen_2024` command**
  - `--pdf-path`: Path to PDF file.
  - `--dry-run`: Preview changes without saving.
  - `--category`: Filter import to a single chapter (e.g. `TKRS`) for incremental verification.
  - Handle legacy code aliasing (`ARK` → `AKP`, `IPKP` → `PPK`).
  - Batch create `StandardItem` and `EvidenceReq` inside `transaction.atomic()`.
- [ ] **Step 4: Run tests and verify 100% pass**
- [ ] **Step 5: Commit management command**
  `git commit -m "feat(akreditasi): add idempotent 2024 accreditation standard import command"`

---

### Task 3: Execute Dry-Run & Verify Complete Chapter Data

**Files:**
- Target: Local DB & Staging DB.

- [ ] **Step 1: Run `--dry-run` against the 2024 PDF**
  Verify the exact counts for each chapter match the gap analysis table (~780 EP total).
- [ ] **Step 2: Audit sample standards from each group (TKRS, KPS, MFK, PMKP, AKP, SKP, PROGNAS)**
  Check that standard descriptions, sub-titles, and RDWOS evidence requirements match the PDF text.
- [ ] **Step 3: Verify existing user records**
  Ensure no `QualityRecord` baseline data or scores are overwritten or orphaned.

---

### Task 4: Execute Live Import & Database Synchronization

**Files:**
- DB: PostgreSQL (Supabase) / SQLite.

- [ ] **Step 1: Execute `python manage.py import_instrumen_2024`**
- [ ] **Step 2: Verify total count of EP in database increases from 299 to ~780+**
- [ ] **Step 3: Verify all 16 chapters have complete EP coverage**
- [ ] **Step 4: Run full regression test suite (67+ tests)**
  `python manage.py test`

---

### Task 5: UI & Filter Optimization for 780+ EP

**Files:**
- Modify: `templates/akreditasi/standard_list.html`
- Modify: `templates/akreditasi/dashboard.html`
- Modify: `akreditasi/views.py`

- [ ] **Step 1: Optimize chapter dropdown & sub-standard quick-jump tabs**
  Allow users to filter by Sub-Standar (e.g., click `TKRS 7` directly to see its 6 EP).
- [ ] **Step 2: Add progress bar per chapter showing completion percentage of 2024 EP**
- [ ] **Step 3: Verify responsive layout and quick search on standard list page**
- [ ] **Step 4: Commit UI optimizations**
  `git commit -m "feat(ui): optimize standard list and dashboard navigation for 2024 standards"`

---

### Task 6: Production Deployment & Verification

- [ ] **Step 1: Commit and push changes to `master`**
- [ ] **Step 2: Run database migration/import script on production**
- [ ] **Step 3: Verify Vercel deployment and test live URL**
  `curl -s -I "https://sim-akreditasi-django.vercel.app/standar/"`
