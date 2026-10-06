# Registration Redesign: Two-Box Architecture (Pasien Baru & Pasien Lama) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the registration module (`pendaftaran_dashboard` & `kunjungan_baru`) into two distinct, structured boxes ("Pasien Baru" and "Pasien Lama") per standard hospital workflow, featuring instant patient search by RM/name, automatic RM and Visit number generation, comprehensive demographic & emergency contact capture, and seamless routing to IGD / Poliklinik.

**Architecture:** 
1. Expand Django `Pasien` model with official demographic (tempat lahir, agama, status kawin, pendidikan, pekerjaan, wilayah RT/RW/Kelurahan/Kecamatan/Kota/Provinsi, email) and Emergency Contact fields (nama PJ, hubungan, kontak, alamat PJ).
2. Implement robust generator utilities for `generate_no_rm()` and `generate_no_kunjungan()` with race-safe sequential formats.
3. Build a fast live-search API (`api_cari_pasien`) returning patient matches by No. RM, NIK, or Name with full demographic previews.
4. Revamp UI in `templates/pasien/pendaftaran_dashboard.html` and `templates/pasien/kunjungan_form.html` to present two clear side-by-side or stacked container cards:
   - **Box 1 (Pasien Lama):** Instant search-and-select RM/Name, auto-filled visit number, penjamin selector, complaint, destination routing (IGD / Poliklinik + DPJP).
   - **Box 2 (Pasien Baru):** Comprehensive Section A (Patient Identity), Section B (Emergency Contact), Section C (Chief Complaint), Section D (Service Destination), auto-generated RM and Visit numbers, creating both `Pasien` and `KunjunganPasien` in one atomic transaction.

**Tech Stack:** Django 5.x, PostgreSQL/SQLite, Bootstrap 5.3.3, Vanilla JS / Fetch API, Django Test Framework.

**Spec:** `C:\Users\cubeb\Downloads\perbaikan Menu pendaftaran 610.docx`

---

## Global Constraints

- **Language Constraint:** Plans must always be written in English.
- **UI Architecture:** Distinct 2-box visual layout ("Pasien Baru" and "Pasien Lama"), responsive with Bootstrap 5.
- **Safety & Integrity:** Patient creation and visit creation for new patients must occur inside an atomic database transaction (`transaction.atomic`).
- **No Manual RM / Visit Number Typing Required:** System must auto-generate unique `no_rm` and `no_kunjungan` automatically while still allowing manual override if required.
- **Backward Compatibility:** All existing 66 tests across the application must continue to pass without regression.

---

## Review Focus

1. **Auto-number uniqueness collision:** Multiple patients or visits registered on the same day must generate sequential numbers without unique constraint violations.
2. **Patient search latency & matching:** Search by partial RM or case-insensitive patient name must return accurate results and gracefully handle empty queries.
3. **Emergency contact address replication:** Checking "Alamat sama dengan pasien" must automatically sync the domicile address to the emergency contact address without wiping manual edits.
4. **Service Destination Routing:** Selecting "IGD" vs "Poli Spesialis" must dynamically reveal/validate Triage vs Poliklinik & DPJP dropdown choices.
5. **Form validation and atomic rollback:** If visit creation fails (e.g. invalid date or invalid destination), the newly created patient record must not be orphaned if intended as a single atomic action, or error messages must be clearly presented.

---

### Task 1: Expand `Pasien` Model and Database Migrations

**Files:**
- Modify: `pasien/models.py`
- Test: `pasien/tests_revisi_pendaftaran_dua_kotak.py`

**Interfaces:**
- Consumes: Django `models.Model`
- Produces: New fields on `Pasien`:
  - `tempat_lahir` (CharField, max_length=100, blank=True)
  - `agama` (CharField, max_length=20, choices=AGAMA_CHOICES, blank=True)
  - `status_perkawinan` (CharField, max_length=20, choices=STATUS_KAWIN_CHOICES, blank=True)
  - `pendidikan_terakhir` (CharField, max_length=30, choices=PENDIDIKAN_CHOICES, blank=True)
  - `pekerjaan` (CharField, max_length=100, blank=True)
  - `rt_rw` (CharField, max_length=20, blank=True)
  - `kelurahan` (CharField, max_length=100, blank=True)
  - `kecamatan` (CharField, max_length=100, blank=True)
  - `kota_kabupaten` (CharField, max_length=100, blank=True)
  - `provinsi` (CharField, max_length=100, blank=True)
  - `email` (EmailField, blank=True)
  - `nama_pj` (CharField, max_length=150, blank=True)
  - `hubungan_pj` (CharField, max_length=50, blank=True)
  - `no_hp_pj` (CharField, max_length=30, blank=True)
  - `alamat_pj` (TextField, blank=True)

- [ ] **Step 1: Write the failing unit tests for new Pasien demographic & emergency contact fields**

```python
# pasien/tests_revisi_pendaftaran_dua_kotak.py
from django.test import TestCase
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien

class PasienModelExpansionTest(TestCase):
    def test_pasien_demographic_and_emergency_contact_fields(self):
        p = Pasien.objects.create(
            no_rm="RM-2026-0001",
            nik="3201234567890001",
            nama_lengkap="Budi Santoso",
            tempat_lahir="Bandung",
            tanggal_lahir="1990-05-15",
            jenis_kelamin="L",
            agama="ISLAM",
            status_perkawinan="MENIKAH",
            pendidikan_terakhir="S1",
            pekerjaan="PNS",
            alamat="Jl. Merdeka No. 10",
            rt_rw="002/005",
            kelurahan="Babakan",
            kecamatan="Coblong",
            kota_kabupaten="Bandung",
            provinsi="Jawa Barat",
            no_hp="081234567890",
            email="budi@example.com",
            nama_pj="Siti Aminah",
            hubungan_pj="Istri",
            no_hp_pj="081298765432",
            alamat_pj="Jl. Merdeka No. 10",
        )
        self.assertEqual(p.tempat_lahir, "Bandung")
        self.assertEqual(p.agama, "ISLAM")
        self.assertEqual(p.nama_pj, "Siti Aminah")
        self.assertEqual(p.hubungan_pj, "Istri")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.PasienModelExpansionTest -v2`
Expected: FAIL with `TypeError: Pasien() got unexpected keyword arguments`

- [ ] **Step 3: Update `pasien/models.py` with demographic and emergency contact fields**

Add choices and fields to `Pasien` model in `pasien/models.py`.

- [ ] **Step 4: Run makemigrations and migrate**

Run: `.venv/Scripts/python.exe manage.py makemigrations pasien`
Run: `.venv/Scripts/python.exe manage.py migrate`

- [ ] **Step 5: Run tests and ensure they pass**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.PasienModelExpansionTest -v2`
Expected: PASS

- [ ] **Step 6: Commit changes**

```bash
git add pasien/models.py pasien/migrations/ pasien/tests_revisi_pendaftaran_dua_kotak.py
git commit -m "feat(pendaftaran): add demographic and emergency contact fields to Pasien model"
```

---

### Task 2: Implement Auto-Generation Utilities for No. RM and No. Kunjungan

**Files:**
- Create: `pasien/utils.py` (or add to `pasien/models.py`)
- Modify: `pasien/models.py`
- Test: `pasien/tests_revisi_pendaftaran_dua_kotak.py`

**Interfaces:**
- Produces:
  - `generate_no_rm() -> str`: Generates format `RM-YYYYMM-XXXX` (e.g. `RM-202610-0001`) checking database to guarantee uniqueness.
  - `generate_no_kunjungan(jenis: str = 'RAJAL') -> str`: Generates format `KUNJ-YYYYMMDD-XXXX` or prefix-based (e.g. `IGD-20261006-0001`, `REG-20261006-0001`).

- [ ] **Step 1: Write unit tests for auto-generation utilities**

```python
# In pasien/tests_revisi_pendaftaran_dua_kotak.py
from pasien.models import generate_no_rm, generate_no_kunjungan

class AutoNumberGenerationTest(TestCase):
    def test_generate_no_rm_format_and_sequence(self):
        rm1 = generate_no_rm()
        self.assertTrue(rm1.startswith("RM-"))
        p1 = Pasien.objects.create(
            no_rm=rm1,
            nama_lengkap="Pasien 1",
            tanggal_lahir="1990-01-01",
            jenis_kelamin="L"
        )
        rm2 = generate_no_rm()
        self.assertNotEqual(rm1, rm2)

    def test_generate_no_kunjungan_format(self):
        kunj_no = generate_no_kunjungan(jenis='IGD')
        self.assertTrue(kunj_no.startswith("IGD-") or kunj_no.startswith("KUNJ-"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.AutoNumberGenerationTest -v2`
Expected: FAIL with `ImportError: cannot import name 'generate_no_rm'`

- [ ] **Step 3: Implement `generate_no_rm()` and `generate_no_kunjungan()`**

Add functions in `pasien/models.py` with sequential date-based numbering logic.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.AutoNumberGenerationTest -v2`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add pasien/models.py pasien/tests_revisi_pendaftaran_dua_kotak.py
git commit -m "feat(pendaftaran): add generate_no_rm and generate_no_kunjungan utility functions"
```

---

### Task 3: Patient Live Search API (`api_cari_pasien`)

**Files:**
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Test: `pasien/tests_revisi_pendaftaran_dua_kotak.py`

**Interfaces:**
- Route: `GET /pasien/api/cari/?q=<query>`
- Returns JSON:
  ```json
  {
    "results": [
      {
        "id": 1,
        "no_rm": "RM-202610-0001",
        "nik": "3201234567890001",
        "nama_lengkap": "Budi Santoso",
        "tanggal_lahir": "15/05/1990",
        "umur": 36,
        "jenis_kelamin": "Laki-laki",
        "alamat": "Jl. Merdeka No. 10",
        "no_hp": "081234567890",
        "penjamin_default": "BPJS",
        "no_bpjs": "00012345678"
      }
    ]
  }
  ```

- [ ] **Step 1: Write unit test for `api_cari_pasien`**

```python
# In pasien/tests_revisi_pendaftaran_dua_kotak.py
from django.urls import reverse

class ApiCariPasienTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='petugas', password='password123')
        self.client.login(username='petugas', password='password123')
        self.pasien = Pasien.objects.create(
            no_rm="RM-001099",
            nik="3273010101900001",
            nama_lengkap="Ahmad Dahlan",
            tanggal_lahir="1990-01-01",
            jenis_kelamin="L",
            no_hp="0811223344"
        )

    def test_search_by_rm(self):
        res = self.client.get(reverse('pasien:api_cari_pasien') + '?q=001099')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['nama_lengkap'], "Ahmad Dahlan")

    def test_search_by_nama(self):
        res = self.client.get(reverse('pasien:api_cari_pasien') + '?q=Ahmad')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['results'][0]['no_rm'], "RM-001099")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.ApiCariPasienTest -v2`
Expected: FAIL with `NoReverseMatch`

- [ ] **Step 3: Implement view `api_cari_pasien` and URL mapping**

In `pasien/views.py`:
Filter `Pasien.objects.filter(Q(no_rm__icontains=q) | Q(nama_lengkap__icontains=q) | Q(nik__icontains=q))[:15]`.
In `pasien/urls.py`:
`path('api/cari/', views.api_cari_pasien, name='api_cari_pasien'),`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.ApiCariPasienTest -v2`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add pasien/views.py pasien/urls.py pasien/tests_revisi_pendaftaran_dua_kotak.py
git commit -m "feat(pendaftaran): add api_cari_pasien live search endpoint"
```

---

### Task 4: Unified Registration View for Both Pasien Lama & Pasien Baru

**Files:**
- Modify: `pasien/views.py` (`kunjungan_baru` and `pendaftaran_dashboard`)
- Modify: `pasien/urls.py`
- Test: `pasien/tests_revisi_pendaftaran_dua_kotak.py`

**Interfaces:**
- Supports:
  - Mode 1: Pasien Lama registration (receives `pasien_id`, `no_kunjungan`, `penjamin`, `catatan_admisi`, `tujuan_pelayanan` / `jenis_kunjungan`, `poliklinik`, `dpjp`, `triage`).
  - Mode 2: Pasien Baru registration (receives `nama_lengkap`, `nik`, `tempat_lahir`, `tanggal_lahir`, `jenis_kelamin`, `agama`, `status_perkawinan`, `pendidikan_terakhir`, `pekerjaan`, `alamat`, `rt_rw`, `kelurahan`, `kecamatan`, `kota_kabupaten`, `provinsi`, `no_hp`, `email`, `penjamin`, `no_bpjs`, `nama_pj`, `hubungan_pj`, `no_hp_pj`, `alamat_pj`, `catatan_admisi`, `tujuan_pelayanan`, `poliklinik`, `dpjp`, `triage`).
  - Creates `Pasien` + `KunjunganPasien` inside `transaction.atomic()`.

- [ ] **Step 1: Write integration tests for Pasien Baru atomic registration and Pasien Lama visit**

```python
# In pasien/tests_revisi_pendaftaran_dua_kotak.py
class PendaftaranDuaKotakFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admisi', password='password123')
        self.client.login(username='admisi', password='password123')

    def test_daftar_pasien_baru_creates_patient_and_kunjungan(self):
        payload = {
            'is_pasien_baru': '1',
            'nama_lengkap': 'Dewi Lestari',
            'nik': '3201998877660001',
            'tempat_lahir': 'Surabaya',
            'tanggal_lahir': '1995-08-20',
            'jenis_kelamin': 'P',
            'agama': 'ISLAM',
            'status_perkawinan': 'BELUM_MENIKAH',
            'pendidikan_terakhir': 'S1',
            'pekerjaan': 'Karyawan Swasta',
            'alamat': 'Jl. Diponegoro No. 45',
            'rt_rw': '003/001',
            'kelurahan': 'Wonokromo',
            'kecamatan': 'Wonokromo',
            'kota_kabupaten': 'Surabaya',
            'provinsi': 'Jawa Timur',
            'no_hp': '081233445566',
            'email': 'dewi@example.com',
            'penjamin': 'BPJS',
            'no_bpjs': '000987654321',
            'nama_pj': 'Bambang Sudarmono',
            'hubungan_pj': 'Orang Tua',
            'no_hp_pj': '081299887766',
            'alamat_pj': 'Jl. Diponegoro No. 45',
            'catatan_admisi': 'Demam tinggi 3 hari dan mual',
            'jenis_kunjungan': 'RAJAL',
            'poliklinik': 'POLI_PENYAKIT_DALAM',
            'dpjp': 'dr. Budi Santoso, Sp.PD',
        }
        res = self.client.post(reverse('pasien:kunjungan_baru'), payload, follow=True)
        self.assertEqual(res.status_code, 200)
        p = Pasien.objects.filter(nik='3201998877660001').first()
        self.assertIsNotNone(p)
        self.assertEqual(p.nama_lengkap, 'Dewi Lestari')
        self.assertEqual(p.nama_pj, 'Bambang Sudarmono')
        self.assertEqual(p.kunjungan.count(), 1)
        k = p.kunjungan.first()
        self.assertEqual(k.jenis_kunjungan, 'RAJAL')
        self.assertEqual(k.catatan_admisi, 'Demam tinggi 3 hari dan mual')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.PendaftaranDuaKotakFlowTest -v2`
Expected: FAIL (missing handling of `is_pasien_baru` in `kunjungan_baru`)

- [ ] **Step 3: Update `pasien/views.py` `kunjungan_baru` to handle `is_pasien_baru`**

Wrap in `with transaction.atomic():`
If `is_pasien_baru`:
  Generate `no_rm = generate_no_rm()`.
  Create `Pasien(...)`.
If not:
  Retrieve `Pasien` via `pasien_id`.
Generate `no_kunjungan = generate_no_kunjungan(jenis=jenis_kunjungan)` if not provided or blank.
Create `KunjunganPasien(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.PendaftaranDuaKotakFlowTest -v2`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add pasien/views.py pasien/tests_revisi_pendaftaran_dua_kotak.py
git commit -m "feat(pendaftaran): enable atomic combined registration for new patients in kunjungan_baru"
```

---

### Task 5: Redesign UI: 2-Box Visual Layout (Pasien Lama & Pasien Baru)

**Files:**
- Modify: `templates/pasien/pendaftaran_dashboard.html`
- Modify: `templates/pasien/kunjungan_form.html`
- Test: `pasien/tests_revisi_pendaftaran_dua_kotak.py`

**Design & Components:**
- Clear visual partition:
  - **Left Box / Card 1: 🗂️ PASIEN LAMA (Pernah Berkunjung)**
    - Search bar with instant autocomplete / live results dropdown (type RM or Name).
    - Selected Patient Info Card: Display RM, NIK, Name, Age, Domicile, Penjamin badge.
    - No. Kunjungan: Auto-generated badge / field (`value="{{ auto_no_kunjungan }}"`).
    - Penjamin Biaya: Select/Radio (Umum, BPJS, Asuransi Lainnya).
    - Keluhan Pasien: Textarea / text input.
    - Tujuan Pelayanan:
      - Radio 1: **IGD** (Triage pill: Merah/Kuning/Hijau/Hitam, Dokter Jaga IGD).
      - Radio 2: **Poli Spesialis** (Pilihan 17 Poliklinik Spesialis, DPJP Dokter Spesialis terhubung otomatis).
    - Button: `[💾 Daftarkan Kunjungan Pasien Lama]`.
  - **Right Box / Card 2: 🆕 PASIEN BARU (Pendaftaran Pertama Kali)**
    - Accordion or grouped sections:
      - **A. IDENTITAS PRIBADI PASIEN**:
        - Nama Lengkap (sesuai KTP/KIA).
        - No. RM: Auto-generated system badge (`RM-XXXXXX`).
        - NIK (16 digit) with live duplicate verification alert.
        - Tempat, Tanggal Lahir (DD/MM/YYYY).
        - Jenis Kelamin (Radio: Laki-laki / Perempuan).
        - Agama (Islam, Kristen, Katolik, Hindu, Buddha, Konghucu).
        - Status Perkawinan (Belum Menikah, Menikah, Duda/Janda).
        - Pendidikan Terakhir (SD/SMP/SMA, D3/D4, S1/S2/S3, Lainnya).
        - Pekerjaan.
        - Alamat Domisili Lengkap (Alamat, RT/RW, Kelurahan, Kecamatan, Kota/Kab, Provinsi).
        - No. HP / WhatsApp & Email.
        - Penjamin Biaya (Umum, BPJS, Asuransi Lainnya).
      - **B. PENANGGUNG JAWAB PASIEN (EMERGENCY CONTACT)**:
        - Nama Penanggung Jawab.
        - Hubungan dengan Pasien (Suami/Istri, Orang Tua, Anak, Kerabat / Lainnya).
        - No. Telepon / WhatsApp PJ.
        - Alamat: Checkbox "Sama dengan pasien" (auto-copy) / input alamat beda.
      - **C. KELUHAN PASIEN**: isian bebas.
      - **D. TUJUAN PELAYANAN**:
        - Pilihan: 1. IGD / 2. Poli Spesialis (+ Poli & DPJP).
    - Button: `[💾 Daftarkan Pasien Baru & Kunjungan]`.
  - Also provide quick tab switches ("Dua Kotak Berdampingan" vs "Tab Pasien Lama" / "Tab Pasien Baru") for flexible desktop/mobile viewports.

- [ ] **Step 1: Write template test checking two boxes and required form elements**

```python
# In pasien/tests_revisi_pendaftaran_dua_kotak.py
class PendaftaranDuaKotakTemplateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='staff', password='password123')
        self.client.login(username='staff', password='password123')

    def test_pendaftaran_dashboard_renders_two_boxes(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'PASIEN LAMA')
        self.assertContains(res, 'PASIEN BARU')
        self.assertContains(res, 'inputCariPasienLama')
        self.assertContains(res, 'IDENTITAS PRIBADI PASIEN')
        self.assertContains(res, 'PENANGGUNG JAWAB PASIEN')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.PendaftaranDuaKotakTemplateTest -v2`
Expected: FAIL

- [ ] **Step 3: Update `templates/pasien/pendaftaran_dashboard.html` and `templates/pasien/kunjungan_form.html`**

Implement the 2-box interface, live search autocomplete script, emergency contact copy script, and dynamic routing script.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak.PendaftaranDuaKotakTemplateTest -v2`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add templates/pasien/pendaftaran_dashboard.html templates/pasien/kunjungan_form.html pasien/tests_revisi_pendaftaran_dua_kotak.py
git commit -m "feat(pendaftaran): implement 2-box UI layout for Pasien Lama and Pasien Baru"
```

---

### Task 6: Full Regression Verification and Integration Testing

**Files:**
- Test: All test suites in `pasien/` and `accounts/`

- [ ] **Step 1: Run the new test suite**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_dua_kotak -v2`
Expected: All tests PASS

- [ ] **Step 2: Run full regression test suite across the whole project**

Run: `.venv/Scripts/python.exe manage.py test pasien accounts akreditasi -v1`
Expected: Ran 69+ tests in <120s, OK.

- [ ] **Step 3: Commit and Push to remote branch**

```bash
git -c credential.helper="" -c credential.helper="!gh auth git-credential" push origin master
```
