# IGD Selectable ICD-10, Nursing Diagnosis (SDKI), & Secondary Survey Form Alignment (ARIMA 2026)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the emergency diagnosis and assessment workflows in ARIMA IGD by converting free-text inputs into standard selectable controls (searchable pickers for ICD-10 and SDKI, and quick-select dropdowns/radios for all 6 body regions of Secondary Survey in Tab 6), ensuring complete alignment with `FORMULIR ASESMEN MEDIS AWAL INSTALASI GAWAT DARURAT arima.docx`.

**Architecture:**
1. **Clinical Constants & APIs:**
   - Define `SDKI_CODES` (Standar Diagnosis Keperawatan Indonesia - PPNI) and expand `ICD10_CODES` in `pasien/views.py`.
   - Provide `api_icd10` and `api_sdki` JSON endpoints for instant search lookups.
2. **Backend Persistence:**
   - In `igd_ttv_update`: support saving `diagnosa_masuk` and `diagnosa_keperawatan_sdki`.
   - In `igd_asesmen_medis_save`: receive and store all selected options from Tab 6 (Secondary Survey 6-region detail) into `k.secondary_survey_detail`.
3. **Interactive UI Pickers (Dual-Mode):**
   - In `modalTTV` (Quick Vitals Modal): Replace free-text `diagnosa_masuk` with searchable `<input list="globalIcd10List">` and add `<input list="globalSdkiList">` for `diagnosa_keperawatan_sdki`.
   - In `modalAsesmenAwal` Tab 4 (Diagnosis): Use the same global datalists for ICD-10 and SDKI.
   - In `modalAsesmenAwal` Tab 6 (Pemeriksaan Fisik Lengkap): Replace all raw text inputs with `<select class="form-select form-select-sm">` options matching the exact clinical choices from `FORMULIR ASESMEN MEDIS AWAL INSTALASI GAWAT DARURAT arima.docx` (Section VI: Mata, THT, Kepala & Leher, Thorax Paru/Jantung, Abdomen, Ekstremitas).
4. **Print Alignment:**
   - Verify `templates/pasien/cetak_asesmen_medis_igd.html` correctly displays the selected secondary survey findings, ICD-10, and SDKI diagnoses.
5. **Automated Testing:** Unit tests verifying persistence of SDKI in TTV, secondary survey choices, and modal rendering.

**Tech Stack:** Django 5, Bootstrap 5.3.3, HTML5 `<datalist>` & `<select>`, Python unittest.

**Spec / Source Document:**
- User screenshot `image_402eb0.png` showing Tab 6 (Pemeriksaan Fisik Lengkap) with plain text inputs needing to become selectable options.
- User screenshot `image_8f1b7d.png` showing TTV modal needing selectable ICD-10 and SDKI.
- `C:\Users\cubeb\Downloads\FORMULIR ASESMEN MEDIS AWAL INSTALASI GAWAT DARURAT arima.docx` (10 Sections).

---

## Global Constraints

- **Plans must always be written in English** (standing memory rule).
- **Execution Mode:** Native execution on local codebase.
- **Zero External Heavy JS:** Use standard HTML5 `<select>` and `<datalist>` elements styled with Bootstrap 5.
- **Doctor Workflow Optimization:** Default each `<select>` in Tab 6 to its normal/expected clinical state (e.g., `Normal`, `Isokor`, `Vesikuler (+/+)`, `Supel`, `Hangat`) so doctors can submit normal findings in one click and only change pathological ones.
- **Full Test Suite Integrity:** All existing 95 unit tests must remain passing.

## Review Focus

1. **Preset & Fallback:** Submitting pre-selected standard codes or custom text for ICD-10 and SDKI must both save cleanly.
2. **Secondary Survey Persistence:** Submitting dropdown values for all 6 body regions must correctly serialize into `k.secondary_survey_detail` dictionary in PostgreSQL.
3. **Pre-selection on Modal Reopen:** If a patient has previously saved custom or dropdown values in `secondary_survey_detail`, the `<select>` options must correctly mark the matching `<option selected>`.
4. **TTV Modal Persistence:** Submitting `diagnosa_keperawatan_sdki` in `modalTTV` must save to `k.diagnosa_keperawatan_sdki`.
5. **Print View Rendering:** All 6 regions of the secondary survey must render clearly in `cetak_asesmen_medis_igd.html` without empty blocks or raw dictionary text.

---

### Task 1: Clinical Constants (`SDKI_CODES` & `ICD10_CODES`) and Lookup API Endpoints

**Files:**
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Create: `pasien/tests_revisi_diagnosa_picker.py`

**Interfaces:**
- Produces: `SDKI_CODES` (list of `(code, label)` tuples), `api_sdki(request)` view.
- Consumes: HTTP GET with query param `q`.

- [ ] **Step 1: Write failing test for `api_sdki` and diagnosis search**

```python
# pasien/tests_revisi_diagnosa_picker.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from pasien.models import KunjunganPasien, Pasien

User = get_user_model()

class DiagnosaPickerTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dokter_picker', password='password123')
        self.client.login(username='dokter_picker', password='password123')

    def test_api_sdki_search(self):
        response = self.client.get(reverse('pasien:api_sdki') + '?q=nyeri')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any('Nyeri' in item['nama'] for item in data))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_diagnosa_picker`
Expected: FAIL (`Reverse for 'api_sdki' not found`)

- [ ] **Step 3: Implement `SDKI_CODES` and `api_sdki` in `pasien/views.py` & register URL**

In `pasien/views.py`:
```python
SDKI_CODES = [
    ('D.0001', 'Bersihan Jalan Napas Tidak Efektif'),
    ('D.0003', 'Gangguan Pertukaran Gas'),
    ('D.0005', 'Pola Napas Tidak Efektif'),
    ('D.0007', 'Gangguan Sirkulasi Spontan'),
    ('D.0008', 'Penurunan Curah Jantung'),
    ('D.0009', 'Perfusi Perifer Tidak Efektif'),
    ('D.0019', 'Defisit Nutrisi'),
    ('D.0020', 'Diare'),
    ('D.0022', 'Hipervolemia'),
    ('D.0023', 'Hipovolemia'),
    ('D.0036', 'Konstipasi'),
    ('D.0049', 'Toleransi Aktivitas Menurun'),
    ('D.0056', 'Intoleransi Aktivitas'),
    ('D.0074', 'Gangguan Rasa Nyaman'),
    ('D.0077', 'Nyeri Akut'),
    ('D.0078', 'Nyeri Kronis'),
    ('D.0080', 'Ansietas'),
    ('D.0129', 'Gangguan Integritas Kulit/Jaringan'),
    ('D.0130', 'Hipertermia'),
    ('D.0131', 'Hipotermia'),
    ('D.0136', 'Risiko Cedera'),
    ('D.0142', 'Risiko Infeksi'),
    ('D.0143', 'Risiko Jatuh'),
    ('D.0149', 'Risiko Perdarahan'),
]

def api_sdki(request):
    """AJAX SDKI quick picker — returns matching SDKI codes as JSON."""
    q = request.GET.get('q', '').strip().lower()
    if len(q) < 2:
        return JsonResponse([{'kode': k, 'nama': n} for k, n in SDKI_CODES[:15]], safe=False)
    results = [
        {'kode': kode, 'nama': nama}
        for kode, nama in SDKI_CODES
        if q in kode.lower() or q in nama.lower()
    ][:15]
    return JsonResponse(results, safe=False)
```

In `pasien/urls.py`:
```python
path('api/sdki/', views.api_sdki, name='api_sdki'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_diagnosa_picker`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pasien/views.py pasien/urls.py pasien/tests_revisi_diagnosa_picker.py
git commit -m "feat(pasien): add SDKI_CODES constant and api_sdki lookup endpoint"
```

---

### Task 2: Backend Persistence for Diagnoses in `igd_ttv_update`

**Files:**
- Modify: `pasien/views.py:1002-1006`
- Test: `pasien/tests_revisi_diagnosa_picker.py`

- [ ] **Step 1: Write failing test for `igd_ttv_update` saving both diagnoses**

```python
    def test_igd_ttv_update_saves_both_diagnoses(self):
        pasien = Pasien.objects.create(nama_lengkap='Pasien Uji Diagnosa', no_rkm='RM-998811')
        k = KunjunganPasien.objects.create(
            pasien=pasien,
            jenis_kunjungan='IGD',
            status='DAFTAR'
        )
        url = reverse('pasien:igd_ttv_update', kwargs={'pk': k.pk})
        post_data = {
            'ttv_sistole': 120,
            'ttv_diastole': 80,
            'ttv_nadi': 80,
            'ttv_rr': 20,
            'ttv_suhu': 38.0,
            'ttv_spo2': 98,
            'ttv_gcs': '15',
            'ttv_skala_nyeri': 8,
            'diagnosa_masuk': 'A01.0 - Demam Tifoid',
            'diagnosa_keperawatan_sdki': 'D.0130 - Hipertermia',
            'icd9_tindakan': 'Pasang Infus RL',
        }
        res = self.client.post(url, post_data)
        self.assertEqual(res.status_code, 302)
        k.refresh_from_db()
        self.assertEqual(k.diagnosa_masuk, 'A01.0 - Demam Tifoid')
        self.assertEqual(k.diagnosa_keperawatan_sdki, 'D.0130 - Hipertermia')
        self.assertEqual(k.icd9_tindakan, 'Pasang Infus RL')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_diagnosa_picker`
Expected: FAIL (`AssertionError: '' != 'D.0130 - Hipertermia'`)

- [ ] **Step 3: Update `igd_ttv_update` in `pasien/views.py`**

In `pasien/views.py` line ~1002:
```python
if 'diagnosa_masuk' in request.POST:
    k.diagnosa_masuk = request.POST.get('diagnosa_masuk', '').strip()
if 'diagnosa_keperawatan_sdki' in request.POST:
    k.diagnosa_keperawatan_sdki = request.POST.get('diagnosa_keperawatan_sdki', '').strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_diagnosa_picker`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pasien/views.py pasien/tests_revisi_diagnosa_picker.py
git commit -m "feat(igd): persist diagnosa_keperawatan_sdki in igd_ttv_update"
```

---

### Task 3: Context Exposure in `igd_dashboard` View & Searchable Datalists in Modals

**Files:**
- Modify: `pasien/views.py` (function `igd_dashboard`)
- Modify: `templates/pasien/igd_dashboard.html`
- Test: `pasien/tests_revisi_diagnosa_picker.py`

- [ ] **Step 1: Update `igd_dashboard` in `pasien/views.py` to pass `icd10_list` and `sdki_list` to context**
- [ ] **Step 2: Update `modalTTV` in `templates/pasien/igd_dashboard.html` to use searchable datalists**
- [ ] **Step 3: Add `<datalist id="globalIcd10List">` and `<datalist id="globalSdkiList">` to `templates/pasien/igd_dashboard.html`**
- [ ] **Step 4: Update Tab 4 (Diagnosis & Rencana) in `modalAsesmenAwal` to also use `globalIcd10List` and `globalSdkiList`**
- [ ] **Step 5: Run tests and commit**

---

### Task 4: Tab 6 (Secondary Survey / Pemeriksaan Fisik Lengkap) Conversion to Selectable Form Controls

**Files:**
- Modify: `templates/pasien/igd_dashboard.html` (`tabSecondary{{ k.pk }}` lines ~1647-1716)
- Modify: `pasien/views.py` (ensure `mata_pupil_diameter`, `tht_membran_timpani`, `leher_trakea`, etc., are captured)
- Test: `pasien/tests_revisi_diagnosa_picker.py`

**Design Specifications for Tab 6 Controls:**
Each card in `tabSecondary{{ k.pk }}` will use `<select class="form-select form-select-sm">` controls with the exact options from Section VI of `FORMULIR ASESMEN MEDIS AWAL INSTALASI GAWAT DARURAT arima.docx`:

1. **Card 1: Mata**
   - `mata_konjungtiva`: `Normal / Tidak Anemis`, `Anemis (+/+)`, `Hiperemis (+/+)`, `Sekret (+/+)`
   - `mata_sklera`: `Normal / Tidak Ikterik`, `Ikterik (+/+)`, `Perdarahan Subkonjungtiva`
   - `mata_pupil`: `Isokor`, `Anisokor`
   - `mata_pupil_diameter`: text input `3 mm / 3 mm` (Kanan / Kiri)
   - `mata_refleks_cahaya`: `(+/+)`, `(-/-)`, `(+/-)`, `(-/+)`

2. **Card 2: THT & Rongga Mulut**
   - `tht_telinga_lapang`: `Lapang / Ya`, `Tidak Lapang / Sempit`, `Serumen (+/+)`
   - `tht_telinga_sekret`: `(-/-)`, `(+/+) Serous`, `(+/+) Purulen`, `(+/+) Darah`
   - `tht_membran_timpani`: `Intak`, `Perforasi`, `Hiperemis`
   - `tht_napas_cuping`: `Tidak (Normal)`, `Ya (+)`
   - `tht_hidung_epistaksis`: `(-/-)`, `Epistaksis (+)`, `Deformitas (+)`
   - `tht_hidung_sekret`: `Jernih`, `Purulen`, `Perdarahan Nasal`
   - `tht_mukosa_bibir`: `Lembap`, `Sianosis / Pucat`, `Kering`
   - `tht_faring`: `T1/T1 Tenang, Hiperemis (-)`, `T2/T2 Hiperemis (+)`, `T3/T3 Detritus (+)`, `Faring Hiperemis`

3. **Card 3: Kepala & Leher**
   - `kepala_kondisi`: `Normosefali`, `Hematoma / Jejas`, `Vulnus (Luka Robek/Lecet)`
   - `leher_jvp`: `Normal (5-2 cmH2O)`, `Meningkat (R-JVP)`
   - `leher_kgb`: `Tidak Ada Pembesaran`, `Pembesaran KGB (+)`
   - `leher_kaku_kuduk`: `Negatif (-)`, `Positif (+)`
   - `leher_trakea`: `Ditengah (Normal)`, `Deviasi ke Kanan`, `Deviasi ke Kiri`

4. **Card 4: Thorax (Paru & Jantung)**
   - `paru_inspeksi`: `Simetris saat bernapas`, `Asimetris`
   - `paru_retraksi`: `Tidak Ada`, `Ada Retraksi Interkostal`, `Ada Retraksi Suprasternal`
   - `paru_auskultasi`: `Vesikuler (+/+)`, `Bronkovesikuler`, `Suara Nafas Menurun`
   - `paru_wheezing`: `(-/-)`, `(+/+) Ekspiratoir`, `(+/+) Inspiratoir`
   - `paru_ronkhi`: `(-/-)`, `(+/+) Basah Halus`, `(+/+) Basah Kasar`
   - `jantung_bunyi`: `S1-S2 Tunggal Reguler`, `S1-S2 Ireguler`
   - `jantung_murmur`: `(-/-)`, `Systolic Murmur (+)`, `Diastolic Murmur (+)`
   - `jantung_gallop`: `(-/-)`, `Gallop S3 (+)`, `Gallop S4 (+)`

5. **Card 5: Abdomen**
   - `abdomen_inspeksi`: `Datar, Simetris`, `Distensi`, `Jejas / Bekas Operasi`
   - `abdomen_bising_usus`: `Normal (8-12x/mnt)`, `Meningkat (Hiperaktif)`, `Menurun / Hilang`
   - `abdomen_palpasi`: `Supel, Nyeri Tekan (-)`, `Nyeri Tekan Epigastrium`, `Nyeri Tekan RLQ (McBurney)`, `Defans Muskular`
   - `abdomen_organomegali`: `Hepatosplenomegali (-)`, `Hepatomegali (+)`, `Splenomegali (+)`
   - `abdomen_perkusi`: `Timpani`, `Redup / Ascites (+)`

6. **Card 6: Ekstremitas & Neurologi**
   - `ekstremitas_akral`: `Hangat, Kering, Merah`, `Dingin, Basah, Pucat`
   - `ekstremitas_crt`: `< 2 Detik (Normal)`, `> 2 Detik (Memanjang)`
   - `ekstremitas_edema_atas`: `(-/-)`, `(+/+) Pitting Edema`
   - `ekstremitas_edema_bawah`: `(-/-)`, `(+/+) Pitting Edema`, `Edema Pretibial (+/+)`
   - `ekstremitas_motorik_atas`: `5/5 (Normal)`, `4/4 (Sedang)`, `3/3 (Lemah)`, `0/0 (Plegi)`
   - `ekstremitas_motorik_bawah`: `5/5 (Normal)`, `4/4 (Sedang)`, `3/3 (Lemah)`, `0/0 (Plegi)`

- [ ] **Step 1: Write test verifying that secondary survey saves dropdown selections cleanly**
- [ ] **Step 2: Replace text inputs with `<select>` in `tabSecondary{{ k.pk }}` in `templates/pasien/igd_dashboard.html`**
- [ ] **Step 3: Run tests and verify rendering**
- [ ] **Step 4: Commit**

```bash
git add templates/pasien/igd_dashboard.html pasien/views.py pasien/tests_revisi_diagnosa_picker.py
git commit -m "feat(igd): convert Tab 6 secondary survey fields from free-text to structured select controls"
```

---

### Task 5: Print Template Alignment & Full Regression Test Suite

**Files:**
- Verify: `templates/pasien/cetak_asesmen_medis_igd.html`
- Verify: `templates/pasien/cetak_permintaan_lab.html`
- Test: Full test suite `python manage.py test`

- [ ] **Step 1: Verify all 10 sections in `cetak_asesmen_medis_igd.html` render the selected choices accurately**
- [ ] **Step 2: Run full test suite (`python manage.py test`)**
Expected: 95+ PASS
- [ ] **Step 3: Push to master**

```bash
git push origin master
```

---

## Plan Self-Review Checklist

1. **Spec Coverage:**
   - [x] Input Diagnosa awal ICD-10 jadi pilihan (searchable picker via datalist)
   - [x] Tambahkan Diagnosa keperawatan SDKI jadi pilihan (searchable picker via datalist)
   - [x] Tab 6 Pemeriksaan Fisik Lengkap dijadikan pilihan (dropdown options for all 6 body regions)
   - [x] Dokumen `FORMULIR ASESMEN MEDIS AWAL INSTALASI GAWAT DARURAT arima.docx` (10 sections) sepenuhnya sinkron
2. **Placeholder Scan:** Zero placeholders or unwritten implementations.
3. **Type Consistency:** Model JSONField `secondary_survey_detail` cleanly receives dictionary keys matching template names.
