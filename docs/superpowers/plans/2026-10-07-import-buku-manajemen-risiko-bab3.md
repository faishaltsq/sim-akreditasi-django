# Import Buku Manajemen Risiko RS (Bab III Onwards) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import 333+ standardized risk register records from `Downloads/buku manajemen resiko rs.docx` (Bab III onwards) into the ARIMA database (`RisikoUnit` & related `UnitKerja`), complete with risk categories, severity grading, quality indicators, and action plans.

**Architecture:** A standalone Django management command `import_buku_risiko_bab3` parses the pre-extracted JSON dataset (`docs/risiko_buku_bab3_extracted.json`), resolves or creates target `UnitKerja` nodes with proper hierarchies, maps clinical/managerial categories into Standar 5.15 categories, assigns default risk grading/priorities, and idempotent-upserts `RisikoUnit` records with audit verification.

**Tech Stack:** Python 3.12, Django 5.x, PostgreSQL/SQLite, python-docx.

**Spec:** `Downloads/buku manajemen resiko rs.docx` (Bab III: Resiko Level 1, Bab IV: Unsur Pelaksana Operasional & IRJ, Bab V: Manajemen Risiko IGD & Rawat Inap/Intensif, Bab VI: Bagian Umum, Fasilitas & K3RS, Bab VII: Keuangan & Akuntansi, Bab VIII: TI & Digitalisasi, and Instalasi Penunjang).

## Global Constraints

- **Language:** Code identifiers, docstrings, and plan document must be in English. User communication in Bahasa Indonesia.
- **Data Integrity:** Idempotent execution (running multiple times must not duplicate records; match on `unit`, `jenis_risiko`, `tahun=2026`).
- **Category Compatibility:** All imported risks must use valid `KATEGORI_CHOICES` (`KLINIS`, `OPERASIONAL`, `FINANSIAL`, `REPUTASI`, `HUKUM_KEPATUHAN`, `FASILITAS_LINGKUNGAN`, `MANAJERIAL`).
- **Safety:** Wrap import operations inside database transactions (`transaction.atomic`). Include `--dry-run` flag support.
- **Zero Regression:** All existing 102 tests must continue to pass cleanly.

## Review Focus

1. **Unmatched Unit Names:** Sub-heading names in the book (e.g. `3.2.1.1 Subbag Rekrutmen & Administrasi Kepegawaian`) might not have exact string matches in the existing 212 `UnitKerja` records.
   *Test:* Resolver function tests fuzzy matching + falls back to creating cleanly structured units under correct parent.
2. **Missing Severity Grading in Source Tables:** The book's tables in Bab III+ contain columns: `No`, `Kategori Risiko`, `Jenis Risiko`, `Deskripsi Risiko`, `Indikator Mutu`, `Strategi Mitigasi`, `Rencana Aksi`, but do NOT include explicit numerical `dampak` and `probabilitas` columns.
   *Test:* Default grading logic assigns plausible scores based on clinical vs managerial category (e.g., Clinical default Dampak=4, Probabilitas=3 => Skor=12 Moderate/Tinggi; Managerial default Dampak=3, Probabilitas=3 => Skor=9 Sedang).
3. **Empty / Null Action Plan Fields:** Some rows in the source tables have multi-line or empty action plans.
   *Test:* Sanitizer cleans trailing numbers, strips whitespace, and ensures `strategi_mitigasi` and `rencana_aksi` are never null.
4. **Idempotency on Re-run:** Running the command twice must not create duplicates or overwrite custom evaluations.
   *Test:* Test verifying consecutive runs report created vs updated counts accurately without expanding record count.
5. **Indikator Mutu Linking:** Source tables reference indicator names (e.g., `INM: Kepatuhan Kebersihan Tangan`).
   *Test:* Indicator parser stores text in `rencana_aksi` / risk metadata, and links to existing `IndikatorMutu` records when fuzzy matches succeed.

---

### Task 1: Unit Resolver & Data Extraction Normalizer

**Files:**
- Create: `akreditasi/management/commands/import_buku_risiko_bab3.py`
- Create: `akreditasi/tests_import_buku_risiko.py`

**Interfaces:**
- Consumes: `docs/risiko_buku_bab3_extracted.json`.
- Produces: `UnitResolver` class with `resolve_or_create(sub_heading, chapter_heading) -> UnitKerja`.

- [ ] **Step 1: Write failing unit tests for unit resolution and row normalization**

```python
# akreditasi/tests_import_buku_risiko.py
from django.test import TestCase
from akreditasi.models import UnitKerja
from akreditasi.management.commands.import_buku_risiko_bab3 import normalize_row, resolve_unit

class UnitResolverAndNormalizationTest(TestCase):
    def test_normalize_row_maps_fields_and_defaults(self):
        raw = {
            "No": "1",
            "Kategori Risiko": "Klinis",
            "Jenis Risiko": "Medication Error",
            "Deskripsi Risiko": "Salah pembacaan resep manual",
            "Indikator Mutu": "INM: Kepatuhan Identifikasi Pasien",
            "Strategi Mitigasi": "Risk Reduction",
            "Rencana Aksi": "E-Prescribing ARIMA"
        }
        res = normalize_row(raw)
        self.assertEqual(res['kategori_risiko'], 'KLINIS')
        self.assertEqual(res['jenis_risiko'], 'Medication Error')
        self.assertGreaterEqual(res['dampak'], 1)
        self.assertGreaterEqual(res['probabilitas'], 1)

    def test_resolve_unit_finds_existing_or_creates(self):
        unit = resolve_unit("4.1.1 Poliklinik Penyakit Dalam", "BAB IV  INSTALASI RAWAT JALAN (IRJ)")
        self.assertIsNotNone(unit)
        self.assertIn("Penyakit Dalam", unit.name)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_import_buku_risiko`
Expected: FAIL (module/functions not yet created)

- [ ] **Step 3: Implement data normalization and unit resolver in `import_buku_risiko_bab3.py`**

Create `akreditasi/management/commands/import_buku_risiko_bab3.py` with mapping tables, regex cleaners, and lookup dictionary for the 44 sections.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_import_buku_risiko`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add akreditasi/management/commands/import_buku_risiko_bab3.py akreditasi/tests_import_buku_risiko.py
git commit -m "feat(risiko): add unit resolver and row normalizer for Buku Risiko Bab 3"
```

---

### Task 2: Management Command Core Logic (Upsert & Transaction)

**Files:**
- Modify: `akreditasi/management/commands/import_buku_risiko_bab3.py`
- Modify: `akreditasi/tests_import_buku_risiko.py`

**Interfaces:**
- Consumes: CLI args `--dry-run`, `--tahun=2026`, `--json-path=...`
- Produces: `RisikoUnit` records inserted/updated in database.

- [ ] **Step 1: Write test for management command execution and idempotency**

```python
from django.core.management import call_command
from akreditasi.risiko_models import RisikoUnit

class ImportBukuRisikoCommandTest(TestCase):
    def test_dry_run_does_not_persist_records(self):
        call_command('import_buku_risiko_bab3', dry_run=True)
        self.assertEqual(RisikoUnit.objects.count(), 0)

    def test_execution_creates_records_and_is_idempotent(self):
        call_command('import_buku_risiko_bab3')
        first_count = RisikoUnit.objects.count()
        self.assertGreater(first_count, 100)
        
        # Second run should not create duplicate records
        call_command('import_buku_risiko_bab3')
        second_count = RisikoUnit.objects.count()
        self.assertEqual(first_count, second_count)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_import_buku_risiko.ImportBukuRisikoCommandTest`
Expected: FAIL

- [ ] **Step 3: Implement `handle()` in `Command` class**

Add CLI flags, transaction wrapper, loop through 333 rows, upsert using `RisikoUnit.objects.update_or_create()`, output progress summary.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_import_buku_risiko`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add akreditasi/management/commands/import_buku_risiko_bab3.py akreditasi/tests_import_buku_risiko.py
git commit -m "feat(risiko): implement import_buku_risiko_bab3 management command with idempotency"
```

---

### Task 3: Execute Full Import & Validate Against Database

**Files:**
- Execute: `.venv/Scripts/python.exe manage.py import_buku_risiko_bab3`
- Inspect: Verification query script checking total count, category distribution, and unit coverage.

**Interfaces:**
- Consumes: `docs/risiko_buku_bab3_extracted.json`
- Produces: 333+ imported records in SQLite/PostgreSQL.

- [ ] **Step 1: Run `--dry-run` to audit preview counts**

Run: `.venv/Scripts/python.exe manage.py import_buku_risiko_bab3 --dry-run`
Expected: Output showing ~333 candidates, 0 errors, dry-run roll-back.

- [ ] **Step 2: Run live import**

Run: `.venv/Scripts/python.exe manage.py import_buku_risiko_bab3`
Expected: ~333 records created/updated successfully.

- [ ] **Step 3: Run audit script to verify database state**

Check total count, category distribution, units mapped, and verify no orphan foreign keys.

- [ ] **Step 4: Commit state and documentation report**

```bash
git add docs/
git commit -m "chore(risiko): verify live import of 333 risk register records from Buku Bab 3"
```

---

### Task 4: Full Regression & Push

**Files:**
- Test: Full Django test suite (`manage.py test`).

- [ ] **Step 1: Run entire test suite**

Run: `.venv/Scripts/python.exe manage.py test`
Expected: 104+ tests pass with zero errors.

- [ ] **Step 2: Push to remote master**

```bash
git push origin master
```
