# Modul Buku Kinerja Elektronik (Logbook 5 Tahunan) Sesuai PMK No. 13 Tahun 2025 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 5-year electronic clinical performance logbook (Buku Kinerja Elektronik SDMK 5 Tahunan) pursuant to Peraturan Menteri Kesehatan (PMK) No. 13 Tahun 2025 across data models, 5-year timeline aggregations, 3-domain tracking (Clinical Actions, Continuous SKP, Anti-Bullying/Ethics), credentialing requirements, draft editors, and ReportLab official PDF generation.

**Architecture:** Extend `DOKUMEN_KREDENSIAL_REGISTRY` with `LOGBOOK_5TAHUN` and register `LOGBOOK_5TAHUN` in `DokumenSyaratKredensial`. Implement multi-year logbook recap aggregation in `sdm/services/logbook.py` supporting 5-year bucketed matrices per action and supervision mode. Build a dedicated ReportLab document engine producing the official 4-part document (SDMK Profile with SATUSEHAT integration, 3-Domain matrices, Pasal 180 Evaluation Checklist, and Digital Authentication with 3-party endorsements).

**Tech Stack:** Django 5+, Python 3.12+, PostgreSQL / SQLite, ReportLab PDF, Bootstrap 5 UI.

**Spec:** `C:\Users\cubeb\Downloads\logbook Berdasarkan Peraturan Menteri Kesehatan Nomor 13 Tahun 2025 tentang Pengelolaan Sumber Daya Manusia Kesehatan.docx`

---

## Global Constraints

- **Regulatory Compliance:** Adhere strictly to PMK No. 13 Tahun 2025 (5-year credentialing cycle, Tim Ad Hoc Kredensial, SPK validity 5 years, Pasal 180 rekredensial evaluation criteria, anti-bullying / bebas perundungan rekam jejak, and SATUSEHAT ID SDMK readiness).
- **Backwards Compatibility:** Maintain existing `LOGBOOK_36BULAN` functionality intact; `LOGBOOK_5TAHUN` is added alongside without breaking existing test suites or historic records.
- **Privacy (PII):** Individual patient identities remain protected; clinical logbook aggregations only record standardized action codes, action labels, dates, and de-identified patient references.
- **Standardized Catalogs:** Prioritize action codes and naming from `KatalogTindakan` (499 clinical items), mapping to ICD-9-CM / standard national competency catalogs.

---

## Review Focus

1. **5-Year Window Date Boundary:** Verification that the 5-year logbook recap accurately calculates 60 months / 5 years trailing from the specified target date, without off-by-one year or leap-day indexing bugs.
2. **Multi-Domain Data Segregation:** Clean separation of Domain 1 (Clinical Volume), Domain 2 (SKP Accumulation across 4 mandatory categories), and Domain 3 (Ethics & Anti-Bullying evaluation per year T1..T5).
3. **Pasal 180 Checklist Validation:** Accurate representation of the 5 evaluation criteria and 3 recommendation outcomes (Dikabulkan Sepenuhnya, Dikabulkan dengan Pembatasan, Penambahan Kompetensi) by Tim Ad Hoc.
4. **ReportLab Multi-Page Flow:** Robust layout rendering that handles large catalogues of actions without crashing or overflowing table cell boundaries, maintaining standard A4 margins.
5. **Autosave and Persistence on Finalize:** Guarantee that manual inputs across all 3 domains are persisted into `DrafDokumenKredensial.isian` upon saving or finalization.

---

## File Structure

```
sdm/
├── models/
│   └── kredensial.py                  # Modify: Add LOGBOOK_5TAHUN choice & REKREDENSIAL 5-th metadata
├── services/
│   ├── dokumen_kredensial.py          # Modify: Add LOGBOOK_5TAHUN registry, manual fields, ReportLab renderer
│   ├── logbook.py                     # Modify: Add logbook_recap_5tahun() 5-year bucketed aggregation
│   └── syarat_kredensial.py           # Modify: Add LOGBOOK_5TAHUN to evaluation logic
├── views.py                           # Modify: Add context & tab/filter handling for 5-year logbook
├── forms/
│   └── logbook.py                     # Modify/Extend: Support 5-year draft input structures
├── management/
│   └── commands/
│       └── seed_logbook_5tahun_demo.py # Create: Management command demoing PMK 13/2025 5-year logbook
└── tests/
    └── test_logbook_5tahun_pmk13.py   # Create: Comprehensive test suite for 5-year logbook
templates/
└── sdm/
    └── kredensial/
        └── dokumen_edit.html          # Modify: Enhanced grouped UI for 5-year 3-domain logbook form
```

---

## Tasks

### Task 1: Extend Data Models & Registry for PMK 13/2025 5-Year Logbook

**Files:**
- Modify: `sdm/models/kredensial.py:318-335`
- Modify: `sdm/services/dokumen_kredensial.py:54-135`
- Modify: `sdm/services/syarat_kredensial.py:8-25, 80-100`
- Test: `sdm/tests/test_logbook_5tahun_pmk13.py`

**Interfaces:**
- Consumes: `DokumenSyaratKredensial.JENIS_CHOICES`, `DOKUMEN_KREDENSIAL_REGISTRY`
- Produces: `LOGBOOK_5TAHUN` registered as official generatable credential document with 3-domain fields and Pasal 180 checklist.

- [x] **Step 1: Write the failing test**

```python
# sdm/tests/test_logbook_5tahun_pmk13.py
from django.test import TestCase
from sdm.models.kredensial import DokumenSyaratKredensial
from sdm.services.dokumen_kredensial import REGISTRY

class Logbook5TahunRegistryTests(TestCase):
    def test_logbook_5tahun_in_choices_and_registry(self):
        choice_keys = [k for k, _ in DokumenSyaratKredensial.JENIS_CHOICES]
        self.assertIn('LOGBOOK_5TAHUN', choice_keys)
        self.assertIn('LOGBOOK_5TAHUN', REGISTRY)
        spec = REGISTRY['LOGBOOK_5TAHUN']
        self.assertEqual(spec['sertifikat_jenis'], 'LOGBOOK')
        manual_keys = [k for k, _ in spec['manual_fields']]
        # Domain 2 SKP fields
        self.assertIn('skp_pelayanan', manual_keys)
        self.assertIn('skp_pelatihan', manual_keys)
        self.assertIn('skp_seminar', manual_keys)
        self.assertIn('skp_publikasi', manual_keys)
        self.assertIn('target_skp_dirjen', manual_keys)
        # Domain 3 Anti-bullying & Ethics
        self.assertIn('etik_perundungan_t1', manual_keys)
        self.assertIn('etik_perundungan_t5', manual_keys)
        # Pasal 180 Rekredensial Decision
        self.assertIn('rekomendasi_tim_adhoc', manual_keys)
        self.assertIn('nama_ketua_tim_adhoc', manual_keys)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_5tahun_pmk13.Logbook5TahunRegistryTests`
Expected: FAIL with `AssertionError: 'LOGBOOK_5TAHUN' not found in choice_keys`

- [x] **Step 3: Implement minimal changes in models, registry, and syarat**

In `sdm/models/kredensial.py`, add `('LOGBOOK_5TAHUN', 'Buku Kinerja Elektronik (Logbook 5 Tahunan)')` to `DokumenSyaratKredensial.JENIS_CHOICES`.

In `sdm/services/dokumen_kredensial.py`, register `LOGBOOK_5TAHUN`:
```python
'LOGBOOK_5TAHUN': {
    'title': 'Buku Kinerja Elektronik (Logbook 5 Tahunan)',
    'auto_fields': IDENTITY_FIELDS + [
        ('id_sdmk', 'ProfilPribadiPegawai.nik atau SATUSEHAT ID'),
        ('nomor_str', 'IzinProfesiPegawai (STR Seumur Hidup)'),
        ('nomor_sip', 'IzinProfesiPegawai (SIP Aktif RS)'),
        ('rekap_5tahun', 'logbook_recap_5tahun()'),
    ],
    'manual_fields': [
        ('periode_siklus', 'diisi periode tahun (misal: 2021 s.d. 2026)'),
        ('jenjang_klinis_usulan', 'jenjang klinis yang diusulkan untuk 5 tahun ke depan'),
        # Ranah 2: SKP 4 Kategori (Target vs T1..T5)
        ('skp_pelayanan', 'JSON/teks: Target & capaian T1-T5 Pelayanan / Praktik Langsung'),
        ('skp_pelatihan', 'JSON/teks: Target & capaian T1-T5 Pelatihan & Fellowship'),
        ('skp_seminar', 'JSON/teks: Target & capaian T1-T5 Seminar / Workshop / Mentoring'),
        ('skp_publikasi', 'JSON/teks: Target & capaian T1-T5 Publikasi Ilmiah & Inovasi IPTEK'),
        ('target_skp_dirjen', 'Target total SKP Direktur Jenderal Kemenkes'),
        ('total_skp_diperoleh', 'Total akumulasi perolehan SKP 5 tahun'),
        # Ranah 3: Disiplin, Etik & Bebas Perundungan
        ('etik_perundungan_t1', 'Tahun 1: Catatan etik & rekam jejak bebas perundungan'),
        ('etik_perundungan_t2', 'Tahun 2: Catatan etik & rekam jejak bebas perundungan'),
        ('etik_perundungan_t3', 'Tahun 3: Catatan etik & rekam jejak bebas perundungan'),
        ('etik_perundungan_t4', 'Tahun 4: Catatan etik & rekam jejak bebas perundungan'),
        ('etik_perundungan_t5', 'Tahun 5: Catatan etik & rekam jejak bebas perundungan'),
        # Pasal 180 Checklist & Rekomendasi Tim Ad Hoc
        ('checklist_kualifikasi_str_sip', 'Kesesuaian kualifikasi pendidikan, STR & SIP (MS/TMS)'),
        ('checklist_target_volume_pelayanan', 'Pemenuhan target volume pelayanan/klinik (MS/TMS)'),
        ('checklist_kecukupan_skp', 'Kecukupan Satuan Kredit Profesi (MS/TMS)'),
        ('checklist_kesehatan_fisik_mental', 'Catatan kesehatan fisik dan mental (MS/TMS)'),
        ('checklist_etik_disiplin_perundungan', 'Rekam jejak etik, disiplin, dan bebas perundungan (MS/TMS)'),
        ('rekomendasi_tim_adhoc', 'DIKABULKAN SEPENUHNYA / DIKABULKAN DENGAN PEMBATASAN / PENAMBAHAN KOMPETENSI'),
        ('catatan_rekomendasi_adhoc', 'Catatan rincian rekomendasi Tim Ad Hoc Kredensial'),
        ('nama_pendamping', 'Nama Pendamping / Pejabat Penilai Klinis'),
        ('nama_ketua_tim_adhoc', 'Nama Ketua Tim Ad Hoc Kredensial RS'),
        ('nip_ketua_tim_adhoc', 'NIP/NUTR Ketua Tim Ad Hoc Kredensial RS'),
        ('nama_pimpinan_fasyankes', 'Nama Direktur RS / Pimpinan Fasyankes'),
    ],
    'signatory_role': 'Tim Ad Hoc Kredensial & Direktur RS',
    'sertifikat_jenis': 'LOGBOOK',
    'sworn_statement': False,
}
```

In `sdm/services/syarat_kredensial.py`, update `evaluate_requirements` to treat `LOGBOOK_5TAHUN` as satisfied if entries exist in 5-year trailing window or draft is finalized.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_5tahun_pmk13.Logbook5TahunRegistryTests`
Expected: PASS (exit 0)

- [x] **Step 5: Run makemigrations for model choice change**

Run: `.venv/Scripts/python.exe manage.py makemigrations sdm`
Expected: Created migration `sdm/migrations/0064_alter_dokumensyaratkredensial_jenis.py`

---

### Task 2: Implement 5-Year Logbook Recap Aggregation (`sdm/services/logbook.py`)

**Files:**
- Modify: `sdm/services/logbook.py:12-65`
- Test: `sdm/tests/test_logbook_5tahun_pmk13.py`

**Interfaces:**
- Consumes: `EntriLogbookKlinis`, `employee`, trailing 5 years / 60 months
- Produces: `logbook_recap_5tahun(employee, years=5)` returning yearly action counts (T1..T5), ICD-9-CM / Catalog codes, Mandiri vs Pelimpahan Kewenangan (Mandat / Delegasi / Supervisi), and overall verification status.

- [x] **Step 1: Write the failing test**

```python
# In sdm/tests/test_logbook_5tahun_pmk13.py
from datetime import timedelta
from django.utils import timezone
from sdm.services.logbook import logbook_recap_5tahun
from sdm.models import EntriLogbookKlinis, KatalogTindakan, MasterJenjangProfesi, MasterProfesiPegawai

class Logbook5TahunRecapTests(TestCase):
    def test_logbook_recap_5tahun_yearly_buckets(self):
        # Create test entries distributed across years T1 (4 years ago) to T5 (current year)
        # Assert returned dictionary structure contains 'tahunan', 'per_tindakan', 'total_5tahun'
        # with T1, T2, T3, T4, T5 counts accurately summed.
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_5tahun_pmk13.Logbook5TahunRecapTests`
Expected: FAIL with `ImportError: cannot import name 'logbook_recap_5tahun' from 'sdm.services.logbook'`

- [x] **Step 3: Implement `logbook_recap_5tahun`**

In `sdm/services/logbook.py`:
Implement `logbook_recap_5tahun(employee, *, years=5, end_date=None)`:
1. Divide the 5-year window into 5 annual intervals `[T1_start, T1_end) ... [T5_start, T5_end]`.
2. Group entries by action (katalog or free-text), aggregating Mandiri, Supervisi, Kolaborasi, and yearly volumes (T1, T2, T3, T4, T5).
3. Compute total 5-year volume and verified count.
4. Extract Catalog Code / ICD-9-CM representation.
5. Return structured dictionary ready for both template tables and ReportLab table formatters.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_5tahun_pmk13.Logbook5TahunRecapTests`
Expected: PASS (exit 0)

---

### Task 3: Build ReportLab PDF Generation for Modul Buku Kinerja 5 Tahunan

**Files:**
- Modify: `sdm/services/dokumen_kredensial.py:330-540`
- Test: `sdm/tests/test_logbook_5tahun_pmk13.py`

**Interfaces:**
- Consumes: `DrafDokumenKredensial` with `jenis == 'LOGBOOK_5TAHUN'`, `render_pdf(draf)`
- Produces: Formatted multi-page PDF with:
  1. Header & Bagian I: Profil SDMK (NIP/NIK/ID SDMK, STR Seumur Hidup, SIP & Fasyankes)
  2. Bagian II: Ranah 1 Tindakan Keprofesian (Tabel 5 Tahunan T1..T5 + Total + Status Verifikasi)
  3. Bagian II: Ranah 2 SKP (Tabel 4 Kategori Pengembangan Profesi Berkelanjutan)
  4. Bagian II: Ranah 3 Etik & Rekam Jejak Bebas Perundungan (Tabel T1..T5)
  5. Bagian III: Lembar Keputusan Rekredensial 5 Tahunan (Checklist Pasal 180 & Rekomendasi Tim Ad Hoc)
  6. Bagian IV: Otentikasi Digital SATUSEHAT & Pengesahan 3 Pihak (SDMK, Tim Ad Hoc, Pimpinan RS).

- [x] **Step 1: Write the failing test**

```python
# In sdm/tests/test_logbook_5tahun_pmk13.py
from sdm.services.dokumen_kredensial import generate_draft, render_pdf
from sdm.tests.test_dokumen_kredensial import pdf_text

class Logbook5TahunPdfRenderTests(TestCase):
    def test_render_pdf_logbook_5tahun_contains_pmk13_sections(self):
        draf = generate_draft(self.pegawai, 'LOGBOOK_5TAHUN', user=self.user)
        draf.isian = {
            'periode_siklus': '2021 s.d. 2026',
            'jenjang_klinis_usulan': 'Perawat Klinik III (PK III)',
            'skp_pelayanan': 'Target 25 SKP (Capaian: 28 SKP)',
            'skp_pelatihan': 'Target 15 SKP (Capaian: 16 SKP)',
            'skp_seminar': 'Target 10 SKP (Capaian: 12 SKP)',
            'skp_publikasi': 'Target 5 SKP (Capaian: 6 SKP)',
            'target_skp_dirjen': '50 SKP',
            'total_skp_diperoleh': '62 SKP',
            'etik_perundungan_t1': 'Baik / Nihil Pelanggaran | Bebas Kasus Perundungan | Layak Lanjut',
            'etik_perundungan_t5': 'Baik / Nihil Pelanggaran | Bebas Kasus Perundungan | Siap Rekredensial',
            'checklist_kualifikasi_str_sip': 'MS',
            'checklist_target_volume_pelayanan': 'MS',
            'checklist_kecukupan_skp': 'MS',
            'checklist_kesehatan_fisik_mental': 'MS',
            'checklist_etik_disiplin_perundungan': 'MS',
            'rekomendasi_tim_adhoc': 'DIKABULKAN SEPENUHNYA',
            'nama_ketua_tim_adhoc': 'Dr. H. Subagyo, Sp.A',
            'nip_ketua_tim_adhoc': '197505122003121002',
            'nama_pimpinan_fasyankes': 'Dr. dr. H. Fachruddin, Sp.B, MARS',
        }
        draf.save()

        pdf_bytes = render_pdf(draf)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        text = pdf_text(pdf_bytes)
        self.assertIn('BUKU KINERJA ELEKTRONIK (LOGBOOK 5 TAHUNAN)', text.upper())
        self.assertIn('PERATURAN MENTERI KESEHATAN NOMOR 13 TAHUN 2025', text.upper())
        self.assertIn('RANAH 1: PELAYANAN / KEWENANGAN KLINIS', text.upper())
        self.assertIn('RANAH 2: PENGEMBANGAN PROFESI BERKELANJUTAN (KECUKUPAN SKP)', text.upper())
        self.assertIn('RANAH 3: CATATAN EVALUASI PERILAKU, ETIK, DAN BEBAS PERUNDUNGAN', text.upper())
        self.assertIn('LEMBAR KEPUTUSAN PENILAIAN REKREDENSIAL', text.upper())
        self.assertIn('DIKABULKAN SEPENUHNYA', text)
        self.assertIn('TIM AD HOC KREDENSIAL', text.upper())
        self.assertIn('SATUSEHAT', text)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_5tahun_pmk13.Logbook5TahunPdfRenderTests`
Expected: FAIL (sections not yet in `render_pdf` for `LOGBOOK_5TAHUN`)

- [x] **Step 3: Implement dedicated 5-year ReportLab layout**

In `sdm/services/dokumen_kredensial.py`:
1. Add `_render_logbook_5tahunan(draf, employee, identity, answers, styles)`:
   - Header with formal title referencing PMK No. 13 Tahun 2025.
   - Bagian I Profile Table: Employee details + STR Seumur Hidup, SIP & Tempat Praktik, ID SDMK SATUSEHAT.
   - Bagian II Ranah 1: Table of clinical volume with 5 annual buckets (T1..T5), action catalog codes, and verification tags.
   - Bagian II Ranah 2: Table of 4 CPD/SKP categories (Pelayanan, Pelatihan, Seminar/Workshop, Publikasi) with target vs achievement and total vs Dirjen target.
   - Bagian II Ranah 3: Table of annual ethics & anti-bullying assessments (T1..T5).
   - Bagian III Lembar Keputusan Rekredensial (Pasal 180): 5 checkboxes (Kualifikasi & STR/SIP, Volume, SKP, Kesehatan, Bebas Perundungan) + 3 recommendation options.
   - Bagian IV Otentikasi Digital: 3 signatures (SDMK Pemohon, Ketua Tim Ad Hoc Kredensial, Direktur RS) with SATUSEHAT electronic authentication seal.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_5tahun_pmk13.Logbook5TahunPdfRenderTests`
Expected: PASS (exit 0)

---

### Task 4: Enhance Draft Edit UI for 3-Domain Form Structure

**Files:**
- Modify: `templates/sdm/kredensial/dokumen_edit.html`
- Modify: `sdm/views.py:3130-3185`
- Test: `sdm/tests/test_logbook_5tahun_pmk13.py`

**Interfaces:**
- Consumes: `dokumen_kredensial_edit`, `manual_fields`, `draf`
- Produces: Grouped accordion/tab form sections for `LOGBOOK_5TAHUN` (Profil & Periode, Ranah 2 SKP, Ranah 3 Etik & Anti-Perundungan, Penilaian Rekredensial Tim Ad Hoc).

- [x] **Step 1: Write the failing test**

```python
# In sdm/tests/test_logbook_5tahun_pmk13.py
class Logbook5TahunUiTests(TestCase):
    def test_dokumen_edit_renders_grouped_pmk13_sections(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('sdm:dokumen_kredensial_edit', args=['LOGBOOK_5TAHUN']))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Buku Kinerja Elektronik (Logbook 5 Tahunan)', content)
        self.assertIn('Pengembangan Profesi Berkelanjutan (SKP)', content)
        self.assertIn('Bebas Perundungan', content)
        self.assertIn('Tim Ad Hoc', content)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_5tahun_pmk13.Logbook5TahunUiTests`
Expected: FAIL (missing section groupings)

- [x] **Step 3: Update views & template for 3-domain grouping**

In `sdm/views.py`:
In `dokumen_kredensial_edit`: enrich `manual_fields` with `group` attribute for `LOGBOOK_5TAHUN` (`periode`, `skp`, `etik_perundungan`, `penilaian_adhoc`, `tanda_tangan`).

In `templates/sdm/kredensial/dokumen_edit.html`:
Render field groups using clean cards with badges corresponding to the 3 PMK 13/2025 domains.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_5tahun_pmk13.Logbook5TahunUiTests`
Expected: PASS (exit 0)

---

### Task 5: Management Seeder & End-to-End Verification

**Files:**
- Create: `sdm/management/commands/seed_logbook_5tahun_demo.py`
- Test: Run command and verify PDF generation and database consistency.

- [x] **Step 1: Create management command `seed_logbook_5tahun_demo`**
Populate demo user (e.g. Dokter Spesialis / Ners Senior), 5-year clinical actions distributed over T1–T5, CPD/SKP records across 4 categories, annual anti-bullying verification records, and generate finalized 5-year logbook document.

- [x] **Step 2: Execute command in terminal**
Run: `.venv/Scripts/python.exe manage.py seed_logbook_5tahun_demo`
Expected: Successfully generated demo SDMK, 5-year logbook draft, and finalized PDF.

- [x] **Step 3: Run comprehensive test suite**
Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_5tahun_pmk13 sdm.tests.test_logbook_36bulan_kredensial_modul sdm.tests.test_dokumen_kredensial sdm.tests.test_dokumen_kredensial_ui`
Expected: All tests pass (0 failures, exit 0).

- [x] **Step 4: Django system check & static assets**
Run: `.venv/Scripts/python.exe manage.py check && .venv/Scripts/python.exe manage.py collectstatic --noinput`
Expected: 0 issues, static files processed.
