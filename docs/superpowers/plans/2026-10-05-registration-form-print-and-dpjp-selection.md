# Implementation Plan: Patient Admission Form Print & DPJP Doctor Selection

**Specification Documents:**
- `Downloads/Dibuatkan Formulir pendaftaran pasien masuk kea rima.docx` (Official Admission Registration Form for ARIMA RS MonsisKami)
- Reference UI Screenshot: `image_6d6229.png` (`sim-akreditasi-django.vercel.app/pasien/pendaftaran/` showing DPJP Specialist input field and visit admission form)

**Date:** 2026-10-05  
**Author:** AI Engineering & QA Team  
**Status:** DRAFT (Ready for Execution)

---

## 1. Executive Summary & Objectives

This implementation plan fulfills the user requirement to upgrade the front-office admission desk and patient registration workflow in ARIMA RS MonsisKami:

1. **Attending Doctor (DPJP) Selection Menu (`Menu dr. / DPJP: Memilih Dokter`)**:
   - Replace the plain free-text `<input type="text" name="dpjp">` in both `pendaftaran_dashboard.html` and `kunjungan_form.html` with a structured, reactive selection menu (`<select name="dpjp">`).
   - Map doctors by polyclinic/specialty (Cardiology, Pulmonology, Internal Medicine, General Surgery, Pediatrics, Obgyn, Ophthalmology, Neurology, ENT, Dental, Orthopedics, Dermatology, Psychiatry, General/Emergency).
   - Integrate with system users (`UserProfile` where `profesi in ['DOKTER_SPESIALIS', 'DOKTER_UMUM']`).
   - Automatically filter/suggest matching specialist doctors when the user selects a polyclinic (e.g., selecting *Poli Jantung* auto-filters to cardiologists: `dr. Faisal, Sp.JP`, `dr. Bambang, Sp.JP, FIHA`).
   - Include a manual input toggle option ("➕ Dokter Lainnya / Ketik Manual") for visiting physicians or locums.

2. **Prefilled Patient Admission Form Print (`Cetak Formulir Pendaftaran Pasien Masuk`)**:
   - Implement the complete, standard A4 printable registration form matching `Dibuatkan Formulir pendaftaran pasien masuk kea rima.docx`:
     - **Header**: RS MONSISKAMI - Sistem Informasi & Manajemen Risiko Terintegrasi (ARIMA), Jl. Health Avenue No. 1, Telp: (021) 555-0199.
     - **Section A (Kategori Pendaftaran)**: Patient status (Baru vs. Lama with No. RM) and service category (Rawat Jalan / Rawat Inap / UGD).
     - **Section B (Identitas Pribadi Pasien)**: Full name, 16 individual NIK boxes, Place & Date of Birth, Gender, Religion, Marital Status, Education, Occupation, Complete address (RT/RW, Kelurahan, Kecamatan, Kota/Kab, Provinsi), Phone/WhatsApp, Email.
     - **Section C (Penanggung Jawab / Emergency Contact)**: Emergency contact name, relationship, phone, and address (from `GeneralConsentRawatInap` if present or patient emergency contact).
     - **Section D (Jaminan / Cara Pembayaran)**: Payment method (Umum / Tunai, BPJS Kesehatan + No. Kartu, Asuransi Swasta + Nama Asuransi & No. Polis).
     - **Section E (Tujuan Pelayanan)**: Destination clinic/polyclinic, Selected DPJP doctor, Visit schedule (Date & Time WIB).
     - **Section F (Informasi Risiko & Skrining Awal ARIMA)**: Drug/food allergies, Special needs / fall risk indicators (wheelchair/cane, geriatric >= 60 yrs, sensory impairment), Primary language.
     - **Section G (Pernyataan & Persetujuan General Consent)**: Patient/guardian consent declaration, signature block, clear full name.
     - **Khusus Petugas Admisi / ARIMA System**: Auto-generated No. RM, Registration timestamp, Registration officer name, and verification badge.
   - Dedicated print view `cetak_formulir_pendaftaran(request, pk)` and route `pasien:cetak_formulir_pendaftaran`.
   - Add direct "Cetak Formulir" buttons in `pendaftaran_dashboard.html`, `kunjungan_detail.html`, and after registration submission.

---

## 2. Architecture & File Impacts

| File Path | Nature | Description |
|---|---|---|
| `pasien/models.py` | Model / Constants | Add `DPJP_CHOICES` dictionary and list mapping clinics to specialist physicians; add helper on `KunjunganPasien` to resolve attending doctor metadata. |
| `pasien/views.py` | Views | Add `cetak_formulir_pendaftaran(request, pk)` print view; inject `dpjp_choices` into `pendaftaran_dashboard` and `kunjungan_baru` contexts. |
| `pasien/urls.py` | Routes | Register `path('kunjungan/<int:pk>/cetak-formulir-pendaftaran/', views.cetak_formulir_pendaftaran, name='cetak_formulir_pendaftaran')`. |
| `templates/pasien/cetak_formulir_pendaftaran.html` | Template | A4 print-ready layout with 16-box NIK display, structured sections A-G, interactive checkboxes, and admission metadata. |
| `templates/pasien/pendaftaran_dashboard.html` | Template | Replace DPJP text input with `<select name="dpjp">` linked dynamically to `poliSelect`; add "Cetak Formulir" button to recent visits table. |
| `templates/pasien/kunjungan_form.html` | Template | Replace DPJP text input with `<select name="dpjp">` linked dynamically to `poliSelect`. |
| `templates/pasien/kunjungan_detail.html` | Template | Add "Cetak Formulir Pendaftaran" in document actions dropdown. |
| `pasien/tests_revisi_pendaftaran_formulir.py` | Tests | Test suite validating DPJP choice rendering, form submission, and prefilled registration form printing. |

---

## 3. Step-by-Step Implementation Tasks

### Task 1: Define Doctor Directory (`DPJP_CHOICES`) and Context Helpers

**Files:**
- Modify: `pasien/models.py`
- Modify: `pasien/views.py`
- Create: `pasien/tests_revisi_pendaftaran_formulir.py`

- [ ] **Step 1: Write failing test for DPJP choices and context availability**

```python
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from pasien.models import Pasien, KunjunganPasien, DPJP_CHOICES
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()

class DPJPSelectionTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='petugas_admisi', password='password123')
        self.profile = UserProfile.objects.create(user=self.user, role='KEPALA_UNIT')
        self.client.login(username='petugas_admisi', password='password123')

    def test_pendaftaran_dashboard_contains_dpjp_choices(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('dpjp_choices', res.context)
        self.assertContains(res, 'dr. Faisal, Sp.JP')

    def test_kunjungan_baru_contains_dpjp_choices(self):
        res = self.client.get(reverse('pasien:kunjungan_baru'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('dpjp_choices', res.context)
        self.assertContains(res, 'dr. Faisal, Sp.JP')
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_formulir.DPJPSelectionTestCase
```

- [ ] **Step 3: Define `DPJP_CHOICES` and helper in `pasien/models.py` & pass to contexts in `pasien/views.py`**

Define `DPJP_CHOICES` grouped by polyclinic:
- Poli Jantung: `dr. Faisal, Sp.JP`, `dr. Bambang, Sp.JP, FIHA`
- Poli Paru: `dr. Indah, Sp.P`, `dr. Gunawan, Sp.P, FAPSR`
- Poli Penyakit Dalam: `dr. Budi Santoso, Sp.PD`, `dr. Siti Rahma, Sp.PD-KGEH`
- Poli Bedah: `dr. Hendra, Sp.B`, `dr. Ahmad, Sp.B, FICS`
- Poli Anak: `dr. Nurul, Sp.A`, `dr. Maya, Sp.A, M.Biomed`
- Poli Kebidanan (Obgyn): `dr. Rina, Sp.OG`, `dr. Dewi, Sp.OG(K)`
- Poli Mata: `dr. Farida, Sp.M`
- Poli Saraf: `dr. Eko, Sp.S`
- Poli THT-KL: `dr. Haryanto, Sp.THT-KL`
- Poli Gigi: `drg. Amanda, Sp.KG`, `drg. Rizki`
- Poli Orthopedi: `dr. Kevin, Sp.OT`
- Poli Kulit & Kelamin: `dr. Citra, Sp.DV`
- Poli Jiwa: `dr. Hadi, Sp.KJ`
- Poli Rehabilitasi Medik: `dr. Lina, Sp.KFR`
- Dokter Jaga IGD / Umum: `dr. Jaga IGD`, `dr. Pratama`, `dr. Intan`

Inject into `pendaftaran_dashboard` and `kunjungan_baru` contexts.

- [ ] **Step 4: Run test to verify it passes**

---

### Task 2: Implement A4 Prefilled Registration Form View & Template

**Files:**
- Create: `templates/pasien/cetak_formulir_pendaftaran.html`
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Test: `pasien/tests_revisi_pendaftaran_formulir.py`

- [ ] **Step 1: Write failing test for `cetak_formulir_pendaftaran` view**

```python
    def test_cetak_formulir_pendaftaran_view(self):
        p = Pasien.objects.create(
            no_rm='RM-FORM-001',
            nama_lengkap='Siti Aminah',
            nik='3201234567890001',
            tanggal_lahir='1988-08-17',
            jenis_kelamin='P',
            alamat='Jl. Merdeka No. 45 RT 02/03',
            no_hp='081234567890',
            no_bpjs='0001234567890',
            alergi_obat='Amoxicillin'
        )
        k = KunjunganPasien.objects.create(
            pasien=p,
            no_kunjungan='KUNJ-FORM-001',
            jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            dpjp='dr. Faisal, Sp.JP',
            penjamin='BPJS',
            tanggal_masuk=timezone.now(),
            catatan_admisi='Nyeri dada kiri menjalar'
        )
        url = reverse('pasien:cetak_formulir_pendaftaran', kwargs={'pk': k.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'FORMULIR PENDAFTARAN PASIEN')
        self.assertContains(res, 'Siti Aminah')
        self.assertContains(res, '3201234567890001')
        self.assertContains(res, 'dr. Faisal, Sp.JP')
        self.assertContains(res, 'Poli Jantung')
```

- [ ] **Step 2: Create `templates/pasien/cetak_formulir_pendaftaran.html`**

Implement full sections A through G per spec:
1. Header RS MONSISKAMI + ARIMA System.
2. Section A: Kategori Pendaftaran (Pasien Baru/Lama, Jenis Layanan).
3. Section B: Identitas Pasien with 16 individual NIK square boxes, TTL, Gender, Agama, Alamat, HP/WA.
4. Section C: Penanggung Jawab Pasien (Emergency Contact).
5. Section D: Jaminan / Pembayaran (Umum, BPJS No Kartu, Asuransi).
6. Section E: Tujuan Pelayanan (Poli, DPJP, Tanggal/Jam Masuk).
7. Section F: Informasi Risiko & Skrining Awal (Alergi Obat, Kebutuhan Khusus / Risiko Jatuh, Bahasa).
8. Section G: Pernyataan & Persetujuan General Consent + Tanda Tangan.
9. Khusus Petugas Admisi / ARIMA System table.
10. Print stylesheet `@media print` with clean formatting, zero page bleed, and no-print buttons.

- [ ] **Step 3: Implement `cetak_formulir_pendaftaran` in `pasien/views.py` and register URL route in `pasien/urls.py`**

- [ ] **Step 4: Run test to verify it passes**

---

### Task 3: UI Integration of DPJP Select & Print Buttons

**Files:**
- Modify: `templates/pasien/pendaftaran_dashboard.html`
- Modify: `templates/pasien/kunjungan_form.html`
- Modify: `templates/pasien/kunjungan_detail.html`
- Test: `pasien/tests_revisi_pendaftaran_formulir.py`

- [ ] **Step 1: Replace DPJP text input in `pendaftaran_dashboard.html` (Tab 1 & Tab 2)**
  - In `panelRajal`: Replace `<input type="text" name="dpjp">` with `<select name="dpjp" id="dpjpSelect" class="form-select form-select-sm">`.
  - Add JS listener: When `poliSelect` changes, filter or auto-select matching specialist from `dpjpSelect`.
  - Add fallback "➕ Ketik Dokter Lainnya..." option.
  - Add "Cetak Formulir Pendaftaran" action button in recent registrations table (Tab 1, Tab 2, and Tab 6).

- [ ] **Step 2: Replace DPJP text input in `kunjungan_form.html`**
  - Replace `<input type="text" name="dpjp">` with `<select name="dpjp" id="dpjpSelect" class="form-select form-select-sm">`.
  - Connect dynamic filtering with `poliSelect`.

- [ ] **Step 3: Add "Cetak Formulir Pendaftaran" to `kunjungan_detail.html`**
  - Add button in document print button group / dropdown.

- [ ] **Step 4: Write UI integration tests and verify**

```python
    def test_pendaftaran_dashboard_renders_print_button_and_dpjp_select(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'dpjpSelect')
        self.assertContains(res, 'cetak_formulir_pendaftaran')
```

---

## 4. Regression & Verification Strategy

- Run dedicated test suite:
  ```bash
  .venv/Scripts/python.exe manage.py test pasien.tests_revisi_pendaftaran_formulir
  ```
- Run full regression across all related modules:
  ```bash
  .venv/Scripts/python.exe manage.py test pasien.tests_revisi_igd pasien.tests_revisi_igd_klinis pasien.tests_revisi_pendaftaran pasien.tests_revisi_pendaftaran_formulir pasien.tests_laboratorium pasien.tests_route_rbac accounts.tests_unit_rbac accounts.tests_sidebar_visibility akreditasi.tests_ai
  ```
- Expected result: 60+ PASS, 0 failures.
- Verify Git status, commit, and push to `origin/master`.
