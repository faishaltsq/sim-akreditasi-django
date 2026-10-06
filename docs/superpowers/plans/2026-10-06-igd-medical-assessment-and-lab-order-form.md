# IGD Initial Medical Assessment & Laboratory Request Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the standard Emergency Department (IGD) Initial Medical Assessment Form (10 structured sections with triage ATS/ESI, primary/secondary survey checklists, SBAR handover) and the comprehensive Laboratory Request Form with categorized test parameters based on `FORMULIR ASESMEN MEDIS AWAL INSTALASI GAWAT DARURAT arima.docx`.

**Architecture:** Extend `KunjunganPasien` and `OrderPenunjang` models with structured clinical fields, upgrade the modal in `igd_dashboard.html` with full 10-section tabbed/interactive checklists, introduce a dedicated laboratory test order modal with parameter catalogs and normal reference ranges, and provide two official A4 print views (`cetak_asesmen_medis_igd.html` and `cetak_permintaan_lab.html`).

**Tech Stack:** Django 5.x, Python 3.11+, PostgreSQL/SQLite, Bootstrap 5.3.3, Vanilla JS, Django Templates.

**Spec:** `Downloads/FORMULIR ASESMEN MEDIS AWAL INSTALASI GAWAT DARURAT arima.docx`

---

## Global Constraints

- **Language Constraint:** Plans must always be written in English.
- **UI Guidelines:** Checkbox/radio pill buttons for checklists ("tinggal centang"), no modals placed inside `<table>` or `<tbody>`, responsive and compact layout with clear badge indicators.
- **Sanitization & Security:** Patient data handled securely, unit-level least privilege RBAC respected.
- **Hospital Identity:** "RS MONSISKAMI ARIMA", Jl. Sehat Utama No. 123, Banjarnegara.

## Review Focus

1. **Response Time & ATS/ESI Triage:** Triage category selection (1-5) must properly reflect severity levels and time targets.
2. **Interactive Head-to-Toe & Secondary Survey Checklists:** Checkboxes for Eye, ENT, Head-Neck, Thorax, Abdomen, and Extremities must accurately serialize and deserialize without loss.
3. **Lab Parameter Order Catalog:** Multi-parameter selection across 6 categories (Hematology, Hemostasis, Clinical Chemistry, Immuno-Serology, Urinalysis/Stool, Microbiology) must store as structured JSON in `OrderPenunjang`.
4. **SBAR Handover & Disposition:** Disposition paths (Inpatient, Outpatient, SISRUTE Transfer, PAPS, Deceased) and SBAR transfer notes must be completely captured with timestamps and sign-off fields.
5. **Print Layout Fidelity:** Both A4 print templates must render with clean page breaks, official letterhead, and accurate tick boxes.

---

## Task Structure

### Task 1: Model Expansion for IGD Medical Assessment & Lab Order Catalog

**Files:**
- Modify: `pasien/models.py`
- Test: `pasien/tests_revisi_asesmen_medis_igd.py`

**Interfaces:**
- Consumes: Existing `KunjunganPasien`, `OrderPenunjang` models
- Produces: Enhanced clinical fields on `KunjunganPasien` (Triage ATS/ESI, Response Time, Secondary Survey JSON/text, SBAR Handover, Disposition) and `OrderPenunjang.parameter_list` JSONField.

- [ ] **Step 1: Write failing tests for expanded models**

```python
# pasien/tests_revisi_asesmen_medis_igd.py
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien, OrderPenunjang

class IgdMedicalAssessmentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('dr_jaga', password='password123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-202610-0001',
            nama_lengkap='Budi Santoso',
            tanggal_lahir='1985-05-12',
            jenis_kelamin='L',
            alamat='Banjarnegara'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='IGD-20261006-0001',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            created_by=self.user
        )

    def test_assessment_and_triage_fields(self):
        self.kunjungan.cara_datang = 'AMBULANS'
        self.kunjungan.triase_kategori = 'KATEGORI_2'
        self.kunjungan.gcs_e = 4
        self.kunjungan.gcs_v = 5
        self.kunjungan.gcs_m = 6
        self.kunjungan.suhu_lokasi = 'Aksila'
        self.kunjungan.nadi_kekuatan = 'Kuat'
        self.kunjungan.nadi_irama = 'Reguler'
        self.kunjungan.pernapasan_pola = 'Spontan'
        self.kunjungan.spo2_alat = 'Udara Bebas'
        self.kunjungan.skala_nyeri_sifat = 'Akut'
        self.kunjungan.metode_risiko_jatuh = 'Morse Fall Scale'
        self.kunjungan.status_emosional = 'Kooperatif'
        self.kunjungan.hambatan_komunikasi = 'Tidak Ada'
        self.kunjungan.kebutuhan_spiritual = 'Tidak Ada'
        self.kunjungan.rpd_checklist = ['HT', 'DM']
        self.kunjungan.secondary_survey_detail = {
            'mata': {'konjungtiva': 'Normal', 'sklera': 'Normal', 'pupil': 'Isokor'},
            'tht': {'telinga': 'Lapang', 'hidung': 'Normal', 'tenggorokan': 'Tenang'},
            'kepala_leher': {'kepala': 'Normosefali', 'leher': 'Normal'},
            'thorax': {'paru': 'Vesikuler (+/+)', 'jantung': 'S1-S2 Reguler'},
            'abdomen': {'inspeksi': 'Datar', 'bising_usus': 'Normal', 'palpasi': 'Supel'},
            'ekstremitas': {'akral': 'Hangat', 'crt': '< 2 Detik', 'edema': 'Tidak Ada'}
        }
        self.kunjungan.sbar_situation = 'Pasien datang dengan nyeri dada kiri'
        self.kunjungan.sbar_background = 'Riwayat HT tidak terkontrol 3 tahun'
        self.kunjungan.sbar_assessment = 'Sindrom Koroner Akut (UAP) - Hemodinamik Stabil'
        self.kunjungan.sbar_recommendation = 'Rawat Inap Ruang ICCU / Bedah, pasang monitor vital'
        self.kunjungan.save()

        k = KunjunganPasien.objects.get(pk=self.kunjungan.pk)
        self.assertEqual(k.cara_datang, 'AMBULANS')
        self.assertEqual(k.triase_kategori, 'KATEGORI_2')
        self.assertEqual(k.gcs_e + k.gcs_v + k.gcs_m, 15)
        self.assertIn('HT', k.rpd_checklist)
        self.assertEqual(k.secondary_survey_detail['mata']['pupil'], 'Isokor')
        self.assertEqual(k.sbar_assessment, 'Sindrom Koroner Akut (UAP) - Hemodinamik Stabil')

    def test_order_penunjang_parameter_list(self):
        order = OrderPenunjang.objects.create(
            kunjungan=self.kunjungan,
            jenis='LAB',
            nama_pemeriksaan='Panel Darah Lengkap & Kimia Klinik',
            prioritas='CITO',
            parameter_list=[
                {'category': 'HEMATOLOGI', 'item': 'Darah Rutin (Hb, Ht, Leukosit, Trombosit, Ery)'},
                {'category': 'KIMIA KLINIK', 'item': 'Glukosa Darah Sewaktu (GDS)'},
                {'category': 'KIMIA KLINIK', 'item': 'Troponin T / Troponin I'}
            ]
        )
        self.assertEqual(len(order.parameter_list), 3)
        self.assertEqual(order.prioritas, 'CITO')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.IgdMedicalAssessmentModelTest -v2`
Expected: FAIL with missing fields on `KunjunganPasien` and `OrderPenunjang`.

- [ ] **Step 3: Update `pasien/models.py` and run migrations**

Add the required fields to `KunjunganPasien`:
- `cara_datang`: CharField with choices `[('SENDIRI', 'Sendiri / Keluarga'), ('RUJUKAN', 'Rujukan (RS/Puskesmas/Klinik)'), ('AMBULANS', 'Ambulans'), ('POLISI', 'Polisi')]`
- `waktu_asesmen_dokter`: TimeField / DateTimeField (null=True, blank=True)
- `waktu_disposisi`: TimeField / DateTimeField (null=True, blank=True)
- `triase_kategori`: CharField `[('KAT_1', 'Kategori 1 (Resusitasi / Merah)'), ('KAT_2', 'Kategori 2 (Emergensi / Merah)'), ('KAT_3', 'Kategori 3 (Urgensi / Kuning)'), ('KAT_4', 'Kategori 4 (Non-Urgensi / Hijau)'), ('KAT_5', 'Kategori 5 (Rutin / Hitam)')]`
- `gcs_e`, `gcs_v`, `gcs_m`: PositiveSmallIntegerField (null=True, blank=True)
- `suhu_lokasi`, `nadi_kekuatan`, `nadi_irama`, `pernapasan_pola`, `spo2_alat`: CharField
- `skala_nyeri_sifat`: CharField (Akut / Kronis)
- `metode_risiko_jatuh`: CharField (Morse / Humpty Dumpty / Get Up and Go)
- `status_emosional`, `hambatan_komunikasi`, `kebutuhan_spiritual`: CharField
- `rpd_checklist`: JSONField (default=list, blank=True)
- `secondary_survey_detail`: JSONField (default=dict, blank=True)
- `tindakan_medis_checklist`: JSONField (default=list, blank=True)
- `penunjang_radiologi_checklist`: JSONField (default=list, blank=True)
- `penunjang_ekg`: CharField
- `penunjang_hasil_kritis`: TextField
- `sbar_situation`, `sbar_background`, `sbar_assessment`, `sbar_recommendation`: TextField
- `petugas_handover_perawat`, `petugas_handover_jam`, `petugas_handover_dokter`, `petugas_handover_dokter_jam`: CharField / TimeField
- Add `parameter_list` JSONField and `kondisi_sampel` (Puasa/Tidak Puasa/Hamil) to `OrderPenunjang`.

Run migrations:
`manage.py makemigrations pasien`
`manage.py migrate`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.IgdMedicalAssessmentModelTest -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pasien/models.py pasien/migrations/* pasien/tests_revisi_asesmen_medis_igd.py
git commit -m "feat(asesmen): add clinical assessment, triage ATS/ESI, secondary survey, SBAR, and lab order catalog models"
```

---

### Task 2: Backend Logic & Views for Assessment Save, Lab Ordering, and Printables

**Files:**
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Test: `pasien/tests_revisi_asesmen_medis_igd.py`

**Interfaces:**
- Consumes: Updated `KunjunganPasien` and `OrderPenunjang` models
- Produces:
  - `igd_asesmen_medis_save(request, pk)`: Complete multi-tab assessment saving view
  - `order_lab_create(request, pk)`: Endpoint for generating laboratory request with checked parameters
  - `cetak_asesmen_medis_igd(request, pk)`: Official A4 print view for IGD Medical Assessment
  - `cetak_permintaan_lab(request, pk, order_id=None)`: Official A4 print view for Laboratory Order Form

- [ ] **Step 1: Write failing tests for views**

```python
# In pasien/tests_revisi_asesmen_medis_igd.py
class IgdAssessmentViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff_igd', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 2})
        UserProfile.objects.create(user=self.user, role='KEPALA_UNIT', unit_kerja=self.unit_igd)
        self.client.login(username='staff_igd', password='password123')
        self.pasien = Pasien.objects.create(no_rm='RM-202610-0002', nama_lengkap='Siti Aminah', tanggal_lahir='1990-02-14', jenis_kelamin='P')
        self.kunjungan = KunjunganPasien.objects.create(pasien=self.pasien, no_kunjungan='IGD-20261006-0002', jenis_kunjungan='IGD', tanggal_masuk=timezone.now())

    def test_save_comprehensive_assessment(self):
        data = {
            'cara_datang': 'RUJUKAN',
            'triase_kategori': 'KAT_2',
            'gcs_e': '4', 'gcs_v': '5', 'gcs_m': '6',
            'ttv_sistole': '130', 'ttv_diastole': '80',
            'ttv_nadi': '88', 'ttv_rr': '20', 'ttv_suhu': '36.8', 'ttv_spo2': '98',
            'skala_nyeri': '5', 'skala_nyeri_sifat': 'Akut',
            'anamnesis_rps': 'Sesak napas memberat sejak 2 jam lalu',
            'rpd_check': ['DM', 'Asma'],
            'mata_pupil': 'Isokor',
            'sbar_situation': 'Pasien sesak napas akut',
            'sbar_assessment': 'Serangan Asma Sedang',
            'disposisi_tindak_lanjut': 'RAWAT_INAP'
        }
        res = self.client.post(reverse('pasien:igd_asesmen_medis_save', args=[self.kunjungan.pk]), data)
        self.assertRedirects(res, reverse('pasien:igd_dashboard'))
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.cara_datang, 'RUJUKAN')
        self.assertEqual(self.kunjungan.triase_kategori, 'KAT_2')
        self.assertIn('DM', self.kunjungan.rpd_checklist)

    def test_create_lab_order_and_print(self):
        data = {
            'prioritas': 'CITO',
            'kondisi_sampel': 'Tidak Puasa',
            'catatan_klinis': 'Kecurigaan Infark Miokard Akut',
            'parameters': [
                'HEMATOLOGI|Darah Rutin (Hb, Ht, Leukosit, Trombosit, Ery)',
                'KIMIA KLINIK|Troponin T / Troponin I',
                'KIMIA KLINIK|CK-MB'
            ]
        }
        res = self.client.post(reverse('pasien:order_lab_create', args=[self.kunjungan.pk]), data)
        self.assertEqual(res.status_code, 302)
        order = OrderPenunjang.objects.filter(kunjungan=self.kunjungan, jenis='LAB').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.prioritas, 'CITO')
        self.assertEqual(len(order.parameter_list), 3)

        # Test Lab Request Print View
        print_res = self.client.get(reverse('pasien:cetak_permintaan_lab', args=[self.kunjungan.pk, order.pk]))
        self.assertEqual(print_res.status_code, 200)
        self.assertContains(print_res, 'FORMULIR PERMINTAAN PEMERIKSAAN LABORATORIUM')
        self.assertContains(print_res, 'Troponin T / Troponin I')

    def test_print_asesmen_medis_igd(self):
        res = self.client.get(reverse('pasien:cetak_asesmen_medis_igd', args=[self.kunjungan.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'FORMULIR ASESMEN MEDIS AWAL INSTALASI GAWAT DARURAT')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.IgdAssessmentViewsTest -v2`
Expected: FAIL with ReverseNotError / undefined views.

- [ ] **Step 3: Implement views in `pasien/views.py` and register routes in `pasien/urls.py`**

- `igd_asesmen_medis_save(request, pk)`: Reads all form fields from POST, handles checkboxes for RPD, Secondary Survey, Medical Procedures, Radiologi, SBAR Handover, and updates `KunjunganPasien`.
- `order_lab_create(request, pk)`: Parses checked laboratory parameters with their categories and stores into `OrderPenunjang(jenis='LAB', parameter_list=...)`.
- `cetak_asesmen_medis_igd(request, pk)`: Renders `templates/pasien/cetak_asesmen_medis_igd.html`.
- `cetak_permintaan_lab(request, pk, order_id=None)`: Renders `templates/pasien/cetak_permintaan_lab.html`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.IgdAssessmentViewsTest -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pasien/views.py pasien/urls.py pasien/tests_revisi_asesmen_medis_igd.py
git commit -m "feat(asesmen): add backend handlers and print views for IGD medical assessment and lab orders"
```

---

### Task 3: Interactive 10-Section IGD Medical Assessment Modal

**Files:**
- Modify: `templates/pasien/igd_dashboard.html`
- Test: `pasien/tests_revisi_asesmen_medis_igd.py`

**Interfaces:**
- Consumes: Context `kunjungan_list` with expanded fields
- Produces: Tabbed / Accordion interface in `modalAsesmenAwal{{ k.pk }}` matching standard 10 sections from Word doc:
  1. Tab 1: **Data Pasien & Waktu (Response Time) + Triase ATS/ESI (Kategori 1–5)**
  2. Tab 2: **Primary Survey (GCS, TTV, Skala Nyeri NPRS/VAS, Skrining Jatuh & Gizi MST)**
  3. Tab 3: **Asesmen Psikososiospiritual, Hambatan & Anamnesis (RPS, RPD Checkboxes, Alergi, Pengobatan)**
  4. Tab 4: **Secondary Survey / Pemeriksaan Fisik Lengkap (Mata, THT, Kepala-Leher, Thorax, Abdomen, Ekstremitas)**
  5. Tab 5: **Penunjang (Lab, Radiologi, EKG), Diagnosis & Rencana Tindakan/Tatalaksana**
  6. Tab 6: **Disposisi & Handover SBAR (Situation, Background, Assessment, Recommendation, TTD/Jam)**

- [ ] **Step 1: Write template verification test**

```python
class IgdModalTemplateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff_igd', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 2})
        UserProfile.objects.create(user=self.user, role='KEPALA_UNIT', unit_kerja=self.unit_igd)
        self.client.login(username='staff_igd', password='password123')
        self.pasien = Pasien.objects.create(no_rm='RM-202610-0003', nama_lengkap='Agus Triyono', tanggal_lahir='1982-08-17', jenis_kelamin='L')
        self.kunjungan = KunjunganPasien.objects.create(pasien=self.pasien, no_kunjungan='IGD-20261006-0003', jenis_kunjungan='IGD', tanggal_masuk=timezone.now())

    def test_igd_dashboard_renders_10_section_modal(self):
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'TRIASE KATEGORI (ATS / ESI Level)')
        self.assertContains(res, 'Kategori 1 (Resusitasi / Merah)')
        self.assertContains(res, 'SECONDARY SURVEY: PEMERIKSAAN FISIK LENGKAP')
        self.assertContains(res, 'Catatan Serah Terima Pasien (SBAR Handover)')
        self.assertContains(res, 'Cetak Formulir Asesmen IGD')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.IgdModalTemplateTest -v2`
Expected: FAIL.

- [ ] **Step 3: Update `templates/pasien/igd_dashboard.html` modal**

- Replace old modal content with the structured 10-section tabbed layout.
- Include quick button: "🖨️ Cetak Asesmen Medis IGD (A4)" and "🧪 Order Laboratorium".
- Keep all modals outside the `<table>` element.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.IgdModalTemplateTest -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/pasien/igd_dashboard.html pasien/tests_revisi_asesmen_medis_igd.py
git commit -m "feat(igd): render standard 10-section medical assessment modal in IGD dashboard"
```

---

### Task 4: Interactive Laboratory Request Modal & Parameter Catalog

**Files:**
- Create/Modify: `templates/pasien/modal_order_lab.html` or inline in `templates/pasien/igd_dashboard.html`
- Modify: `templates/pasien/kunjungan_detail.html`
- Test: `pasien/tests_revisi_asesmen_medis_igd.py`

**Interfaces:**
- Consumes: Laboratory test parameter catalog defined in docx (Hematology, Hemostasis, Chemistry, Immuno-Serology, Urinalysis/Feces, Microbiology)
- Produces: Interactive modal `#modalOrderLab{{ k.pk }}` with searchable checkboxes, reference values, priority toggle (CITO/Rutin), and fasting options.

- [ ] **Step 1: Write test for lab order modal rendering**

```python
    def test_lab_order_modal_renders_categories(self):
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertContains(res, 'FORMULIR PERMINTAAN PEMERIKSAAN LABORATORIUM')
        self.assertContains(res, 'HEMATOLOGI')
        self.assertContains(res, 'HEMOSTASIS / KOAGULASI')
        self.assertContains(res, 'KIMIA KLINIK')
        self.assertContains(res, 'IMMUNO-SEROLOGI')
        self.assertContains(res, 'URINALISIS & FESES')
        self.assertContains(res, 'MIKROBIOLOGI')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.IgdModalTemplateTest.test_lab_order_modal_renders_categories -v2`
Expected: FAIL.

- [ ] **Step 3: Implement Lab Order Modal in template**

- Add complete 6-category parameters with normal reference values:
  - Hematologi (Darah Rutin, Diff Count, LED, Golongan Darah, GDT)
  - Hemostasis (BT/CT, PT/APTT/INR, D-Dimer)
  - Kimia Klinik (Ginjal & Elektrolit, Fungsi Hati, GDS/GDP/HbA1c, Profil Lipid, Jantung: Troponin & CK-MB)
  - Immuno-serologi (HBsAg, Anti-HCV, Anti-HIV, Widal/Tubex, NS1 Dengue, Swab Antigen/PCR)
  - Urinalisis & Feses (Urine Lengkap, Tes Kehamilan, Feses Lengkap)
  - Mikrobiologi (Gram/BTA, Kultur, AGD)
- Include priority radio (CITO / Rutin) and fasting status.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.IgdModalTemplateTest.test_lab_order_modal_renders_categories -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/pasien/igd_dashboard.html templates/pasien/kunjungan_detail.html
git commit -m "feat(lab): implement interactive laboratory order modal with 6-category parameter catalog"
```

---

### Task 5: Official A4 Printable Templates

**Files:**
- Create: `templates/pasien/cetak_asesmen_medis_igd.html`
- Create: `templates/pasien/cetak_permintaan_lab.html`
- Test: `pasien/tests_revisi_asesmen_medis_igd.py`

**Interfaces:**
- Consumes: `kunjungan`, `pasien`, `order` objects
- Produces: Clean, standard hospital A4 printable HTML with `@media print` CSS, hospital letterhead ("RS MONSISKAMI ARIMA"), borders, checkmarks, and signature blocks.

- [ ] **Step 1: Write test for printable templates**

```python
class PrintableTemplatesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('admin_print', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 2})
        UserProfile.objects.create(user=self.user, role='ADMIN_UTAMA', unit_kerja=self.unit_igd)
        self.client.login(username='admin_print', password='password123')
        self.pasien = Pasien.objects.create(no_rm='RM-202610-0004', nama_lengkap='Bambang Pamungkas', tanggal_lahir='1980-06-10', jenis_kelamin='L', no_bpjs='0001234567890')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='IGD-20261006-0004',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            dpjp='dr. Darno, Sp.B'
        )

    def test_cetak_asesmen_medis_igd_html(self):
        res = self.client.get(reverse('pasien:cetak_asesmen_medis_igd', args=[self.kunjungan.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'RS MONSISKAMI ARIMA')
        self.assertContains(res, 'FORMULIR ASESMEN MEDIS AWAL INSTALASI GAWAT DARURAT')
        self.assertContains(res, 'Bambang Pamungkas')

    def test_cetak_permintaan_lab_html(self):
        order = OrderPenunjang.objects.create(
            kunjungan=self.kunjungan,
            jenis='LAB',
            nama_pemeriksaan='Panel Darah Rutin & GDS',
            prioritas='CITO',
            parameter_list=[{'category': 'HEMATOLOGI', 'item': 'Darah Rutin (Hb, Ht, Leukosit, Trombosit, Ery)'}]
        )
        res = self.client.get(reverse('pasien:cetak_permintaan_lab', args=[self.kunjungan.pk, order.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'FORMULIR PERMINTAAN PEMERIKSAAN LABORATORIUM')
        self.assertContains(res, 'CITO')
        self.assertContains(res, 'Darah Rutin (Hb, Ht, Leukosit, Trombosit, Ery)')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.PrintableTemplatesTest -v2`
Expected: FAIL.

- [ ] **Step 3: Create templates**

- Write `templates/pasien/cetak_asesmen_medis_igd.html` matching the exact formatting from the Word document.
- Write `templates/pasien/cetak_permintaan_lab.html` with tabular parameter listing, normal reference ranges, and doctor sign-off.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_asesmen_medis_igd.PrintableTemplatesTest -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/pasien/cetak_asesmen_medis_igd.html templates/pasien/cetak_permintaan_lab.html pasien/tests_revisi_asesmen_medis_igd.py
git commit -m "feat(print): create official A4 print templates for IGD assessment and laboratory requests"
```

---

### Task 6: Full Regression Verification & Quality Gate

**Files:**
- Test all: `pasien`, `accounts`, `akreditasi`

- [ ] **Step 1: Run full test suite**

Run: `.venv/Scripts/python.exe manage.py test pasien accounts akreditasi -v1`
Expected: All 90+ tests PASS.

- [ ] **Step 2: Verify git status and push**

Run: `git status`
Run: `git push origin master`
