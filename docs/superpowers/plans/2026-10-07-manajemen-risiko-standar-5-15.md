# Standar 5.15 Manajemen Risiko: 6 Risk Categories & Identification Fields (Masalah & Data) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the hospital risk management enhancements from `Tambahan untuk manajemen resiko 5.15.docx` into the ARIMA Risk Management module by adding `Masalah` and `Data` fields above `Deskripsi Risiko`, expanding `Kategori Risiko` into the full 6 integrated healthcare risk categories with clinical examples, and updating model schemas, migrations, views, UI forms, detail displays, and unit tests.

**Architecture:**
1. **Model & Database Layer (`akreditasi/risiko_models.py` & Migration):**
   - Expand `RisikoUnit.kategori_risiko` `max_length` from 12 to 30.
   - Update `RisikoUnit.KATEGORI_CHOICES` from 2 options (`KLINIS`, `MANAJERIAL`) to the 6 integrated standard categories:
     1. `KLINIS`: Risiko Klinis (Clinical Risk)
     2. `OPERASIONAL`: Risiko Operasional (Operational Risk)
     3. `FINANSIAL`: Risiko Finansial (Financial Risk)
     4. `REPUTASI`: Risiko Reputasi (Reputational Risk)
     5. `HUKUM_KEPATUHAN`: Risiko Hukum dan Kepatuhan (Legal & Compliance Risk)
     6. `FASILITAS_LINGKUNGAN`: Risiko Fasilitas, B3, dan Lingkungan (Facility & Environmental Risk)
     *(Retain `MANAJERIAL` as a backward-compatible legacy choice for existing records).*
   - Add `masalah` (`models.TextField`, blank=True, default='') and `data_pendukung` (`models.TextField`, blank=True, default='') to `RisikoUnit`.
   - Generate and apply Django migration `0029_risikounit_masalah_data_and_6_kategori.py`.
2. **View & Controller Layer (`akreditasi/risiko_views.py` & `akreditasi/ai_service.py`):**
   - Update `risiko_input`: parse `masalah` and `data` (saved to `data_pendukung`) from `request.POST`.
   - Update `risiko_daftar`: support filtering by the 6 new categories.
   - Update `ai_service.py` and `static/js/ai-assist.js`: inject `masalah` and `data` into DeepSeek prompt contexts for higher-quality AI risk mitigation plans.
3. **Template & Interactive UI Layer (`risiko_form.html`, `risiko_detail.html`, `risiko_daftar.html`):**
   - In `risiko_form.html`: Place `Masalah` and `Data (Bukti Masalah / Baseline)` fields directly above `Deskripsi Risiko`.
   - Add an interactive category guide / quick-preset chips under `Jenis Risiko` populated dynamically when a user selects one of the 6 categories (e.g. *Medication error*, *Pending BPJS claims*, *Genset failure*, etc.).
   - In `risiko_detail.html`: Display `Masalah` and `Data Pendukung` cards in the risk summary section.
   - In `risiko_daftar.html`: Display styled badge colors for each of the 6 risk categories.
4. **Test Suite (`akreditasi/tests_manajemen_risiko_515.py`):**
   - Comprehensive unit tests verifying model validation, form submissions, filter queries, and detail views.

**Tech Stack:** Django 5, PostgreSQL / SQLite (test), Bootstrap 5.3.3, DeepSeek AI prompt service.

**Spec / Source Document:**
- `Downloads/Tambahan untuk manajemen resiko 5.15.docx`:
  - Section 1: "Tambahkan dalam identifikasi resiko, diatas menu deskripsi resiko dengan menu masalah dan data"
  - Section 2: "Pada menu Kategori resiko tambahkan pilihan kategori resiko menjadi 6, yaitu: Risiko Klinis, Risiko Operasional, Risiko Finansial, Risiko Reputasi, Risiko Hukum dan Kepatuhan, Risiko Fasilitas, B3, dan Lingkungan beserta contoh masing-masing."

---

## Global Constraints

- **Plans must always be written in English** (standing memory rule).
- **Execution Mode:** Native execution on local codebase.
- **Zero External Heavy JS:** Native Bootstrap 5 + Vanilla JavaScript for interactive chips and category change listeners.
- **Backward Compatibility:** Existing 12 database records in `RisikoUnit` (including `MANAJERIAL`) must remain fully intact and operational without data loss.
- **Full Test Suite Integrity:** All existing unit tests across `akreditasi` and `pasien` must continue to pass (100% green).

## Review Focus

1. **Length constraints:** `kategori_risiko` has `max_length=30` to prevent database truncation on `FASILITAS_LINGKUNGAN` (20 characters) and `HUKUM_KEPATUHAN` (15 characters).
2. **Form validation:** Both `masalah` and `data` can be submitted via POST and stored safely, even when empty or containing multiline text.
3. **Filter queries:** Filtering by any of the 6 categories in `risiko_daftar` filters records accurately.
4. **Detail presentation:** Viewing an existing risk without `masalah`/`data` degrades gracefully (shows "—" or clean empty state) rather than breaking layout.
5. **AI context enrichment:** `ai-assist.js` captures `masalah` and `data` when available so DeepSeek AI receives richer context when composing mitigation plans.

---

### Task 1: Model Schema Update & Database Migration

**Files:**
- Modify: `akreditasi/risiko_models.py:25-54`
- Create: `akreditasi/migrations/0029_risikounit_masalah_data_and_6_kategori.py` (via `makemigrations`)
- Create: `akreditasi/tests_manajemen_risiko_515.py`

**Interfaces:**
- Produces: `RisikoUnit.masalah`, `RisikoUnit.data_pendukung`, and expanded `RisikoUnit.KATEGORI_CHOICES`.

- [ ] **Step 1: Write failing test for new fields and 6 categories**

```python
# akreditasi/tests_manajemen_risiko_515.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import RisikoUnit


class Standar515ManajemenRisikoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='risk.officer', password='password123')
        self.unit = UnitKerja.objects.create(name='Instalasi Farmasi', code='FARM-TEST', level=2)
        self.client = Client()
        self.client.login(username='risk.officer', password='password123')

    def test_model_supports_all_6_categories_and_masalah_data(self):
        categories = [
            'KLINIS',
            'OPERASIONAL',
            'FINANSIAL',
            'REPUTASI',
            'HUKUM_KEPATUHAN',
            'FASILITAS_LINGKUNGAN',
        ]
        for cat in categories:
            r = RisikoUnit.objects.create(
                unit=self.unit,
                tahun=2026,
                periode='TRIWULAN_1',
                kategori_risiko=cat,
                jenis_risiko=f'Test Risiko {cat}',
                masalah='Terjadi peningkatan antrean dan komplain waktu tunggu',
                data_pendukung='Data log farmasi: waktu tunggu resep racikan rata-rata 65 menit (standar <30 menit)',
                deskripsi_risiko='Keterlambatan penyiapan obat mengakibatkan risiko ketidakpuasan pasien',
                dampak=3,
                probabilitas=4,
                strategi_mitigasi='KURANGI',
                rencana_aksi='Evaluasi alur dispensing dan tambah 1 asisten apoteker jam sibuk',
                pj_mitigasi='Ka. Instalasi Farmasi',
                created_by=self.user,
            )
            self.assertEqual(r.kategori_risiko, cat)
            self.assertEqual(r.masalah, 'Terjadi peningkatan antrean dan komplain waktu tunggu')
            self.assertIn('65 menit', r.data_pendukung)

    def test_legacy_manajerial_choice_still_supported(self):
        r = RisikoUnit.objects.create(
            unit=self.unit,
            tahun=2026,
            periode='TAHUNAN',
            kategori_risiko='MANAJERIAL',
            jenis_risiko='Legacy Risk Record',
            deskripsi_risiko='Legacy data test',
            dampak=2,
            probabilitas=2,
            strategi_mitigasi='TERIMA',
            rencana_aksi='Monitoring rutin',
            pj_mitigasi='Ka. Bagian Umum',
            created_by=self.user,
        )
        self.assertEqual(r.kategori_risiko, 'MANAJERIAL')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_manajemen_risiko_515`
Expected: FAIL with `TypeError: RisikoUnit() got unexpected keyword argument 'masalah'`

- [ ] **Step 3: Update `akreditasi/risiko_models.py`**

```python
    KATEGORI_CHOICES = [
        ('KLINIS',               'Risiko Klinis (Clinical Risk)'),
        ('OPERASIONAL',          'Risiko Operasional (Operational Risk)'),
        ('FINANSIAL',            'Risiko Finansial (Financial Risk)'),
        ('REPUTASI',             'Risiko Reputasi (Reputational Risk)'),
        ('HUKUM_KEPATUHAN',      'Risiko Hukum dan Kepatuhan (Legal & Compliance Risk)'),
        ('FASILITAS_LINGKUNGAN', 'Risiko Fasilitas, B3, dan Lingkungan (Facility & Environmental Risk)'),
        # Backward compatibility for existing records
        ('MANAJERIAL',           'Risiko Manajerial (Legacy)'),
    ]

    unit             = models.ForeignKey(UnitKerja, on_delete=models.CASCADE, verbose_name='Unit Kerja')
    tahun            = models.IntegerField('Tahun', default=2026)
    periode          = models.CharField('Periode', max_length=12, choices=PERIODE_CHOICES)
    kategori_risiko  = models.CharField('Kategori Risiko', max_length=30, choices=KATEGORI_CHOICES)
    jenis_risiko     = models.CharField('Jenis Risiko', max_length=200)

    # Identifikasi Risiko: Masalah & Data Pendukung (Standar 5.15)
    masalah          = models.TextField('Masalah', blank=True, default='')
    data_pendukung   = models.TextField('Data / Bukti Pendukung', blank=True, default='')

    deskripsi_risiko = models.TextField('Deskripsi Risiko')
```

- [ ] **Step 4: Generate and run migrations**

Run: `.venv/Scripts/python.exe manage.py makemigrations akreditasi`
Run: `.venv/Scripts/python.exe manage.py migrate akreditasi`

- [ ] **Step 5: Run tests and verify they pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_manajemen_risiko_515`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add akreditasi/risiko_models.py akreditasi/migrations/ akreditasi/tests_manajemen_risiko_515.py
git commit -m "feat(risiko): add masalah, data_pendukung, and 6 standard risk categories per Standar 5.15"
```

---

### Task 2: Controller & View Logic Updates (`akreditasi/risiko_views.py`)

**Files:**
- Modify: `akreditasi/risiko_views.py:252-295`
- Test: `akreditasi/tests_manajemen_risiko_515.py`

**Interfaces:**
- Consumes: `request.POST.get('masalah')`, `request.POST.get('data')` / `request.POST.get('data_pendukung')`.
- Produces: Saved `RisikoUnit` record with `masalah` and `data_pendukung`.

- [ ] **Step 1: Write test for `risiko_input` view POST handling**

```python
    def test_risiko_input_view_post_saves_masalah_and_data(self):
        url = reverse('akreditasi:risiko_input')
        payload = {
            'unit': self.unit.id,
            'tahun': 2026,
            'periode': 'TRIWULAN_2',
            'kategori_risiko': 'OPERASIONAL',
            'jenis_risiko': 'Gangguan Jaringan Server IT ARIMA',
            'masalah': 'Server ARIMA lambat saat jam sibuk pelayanan pagi',
            'data_pendukung': 'Uptime monitoring menunjukkan response time >5000ms pada pukul 08:00-10:00',
            'deskripsi_risiko': 'Kegagalan sistem server IT aplikasi ARIMA saat pelayanan berlangsung menghambat registrasi dan resep',
            'dampak': 4,
            'probabilitas': 3,
            'strategi_mitigasi': 'KURANGI',
            'pj_mitigasi': 'Tim IT & SIMRS',
            'rencana_aksi': 'Upgrade RAM server dan optimasi database PostgreSQL',
            'biaya_mitigasi': '5000000',
        }
        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        r = RisikoUnit.objects.filter(jenis_risiko='Gangguan Jaringan Server IT ARIMA').first()
        self.assertIsNotNone(r)
        self.assertEqual(r.kategori_risiko, 'OPERASIONAL')
        self.assertEqual(r.masalah, 'Server ARIMA lambat saat jam sibuk pelayanan pagi')
        self.assertIn('5000ms', r.data_pendukung)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_manajemen_risiko_515`
Expected: FAIL because `risiko_input` doesn't pass `masalah` and `data_pendukung` to `RisikoUnit`.

- [ ] **Step 3: Update `risiko_input` in `akreditasi/risiko_views.py`**

In `akreditasi/risiko_views.py:268-286`:
```python
            risiko = RisikoUnit(
                unit_id=int(request.POST['unit']),
                tahun=int(request.POST['tahun']),
                periode=request.POST['periode'],
                kategori_risiko=request.POST['kategori_risiko'],
                jenis_risiko=request.POST['jenis_risiko'],
                masalah=request.POST.get('masalah', '').strip(),
                data_pendukung=(request.POST.get('data') or request.POST.get('data_pendukung') or '').strip(),
                deskripsi_risiko=request.POST['deskripsi_risiko'],
                dampak=int(request.POST['dampak']),
                probabilitas=int(request.POST['probabilitas']),
                indikator_mutu_terkait_id=int(indikator_id) if indikator_id else None,
                target_capaian_indikator=float(target_capaian) if target_capaian else None,
                strategi_mitigasi=request.POST['strategi_mitigasi'],
                rencana_aksi=request.POST['rencana_aksi'],
                pj_mitigasi=request.POST['pj_mitigasi'],
                biaya_mitigasi=request.POST.get('biaya_mitigasi') or 0,
                target_selesai=request.POST.get('target_selesai') or None,
                status='IDENTIFIKASI',
                created_by=request.user,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_manajemen_risiko_515`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add akreditasi/risiko_views.py akreditasi/tests_manajemen_risiko_515.py
git commit -m "feat(risiko): persist masalah and data_pendukung in risiko_input view"
```

---

### Task 3: UI Enhancement for Risk Identification Form (`risiko_form.html`)

**Files:**
- Modify: `templates/akreditasi/risiko_form.html`
- Modify: `static/js/ai-assist.js`

**Interfaces:**
- Form inputs: `name="masalah"`, `name="data"`.
- Dynamic JavaScript: Category change listener providing category descriptions and quick-pick examples from the Word document.

- [ ] **Step 1: Update `templates/akreditasi/risiko_form.html`**

Insert the new inputs right above `Deskripsi Risiko`:
```html
                        {# Standar 5.15: Masalah dan Data Pendukung #}
                        <div class="row g-3 mb-3">
                            <div class="col-md-6">
                                <label class="form-label" style="font-size:.8rem; font-weight:600;">
                                    <i class="bi bi-exclamation-circle text-danger me-1"></i>Masalah <span class="text-muted fw-normal">(Issue Statement)</span>
                                </label>
                                <textarea name="masalah" class="form-control form-control-sm" rows="2"
                                          placeholder="Uraikan masalah aktual atau potensi masalah yang dihadapi…"></textarea>
                                <small class="text-muted" style="font-size:.68rem;">Masalah nyata/potensial yang mendasari munculnya risiko ini</small>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label" style="font-size:.8rem; font-weight:600;">
                                    <i class="bi bi-file-earmark-bar-graph text-primary me-1"></i>Data / Bukti Pendukung <span class="text-muted fw-normal">(Baseline)</span>
                                </label>
                                <textarea name="data" class="form-control form-control-sm" rows="2"
                                          placeholder="Data kuantitatif/kualitatif pendukung (cth: angka insiden, % komplain, hasil audit)…"></textarea>
                                <small class="text-muted" style="font-size:.68rem;">Fakta, data capaian, atau bukti pendukung adanya masalah</small>
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="form-label" style="font-size:.8rem; font-weight:600;">Deskripsi Risiko <span class="text-danger">*</span></label>
                            <textarea name="deskripsi_risiko" class="form-control form-control-sm" rows="3" required placeholder="Deskripsikan risiko secara rinci…"></textarea>
                        </div>
```

- [ ] **Step 2: Add interactive category helper with examples in `risiko_form.html`**

Add an interactive preview banner under `Kategori Risiko` that displays the clinical explanation and clickable example chips matching `Tambahan untuk manajemen resiko 5.15.docx`:
- **KLINIS**: Kesalahan pemberian dosis obat (medication error), HAIs, Pasien jatuh rawat inap, Komplikasi surgical safety checklist.
- **OPERASIONAL**: Gangguan server IT/ARIMA, Kekosongan stok obat esensial, Keterlambatan lab kritis, Understaffing perawat.
- **FINANSIAL**: Penolakan klaim BPJS Kesehatan, Pembengkakan biaya sarana, Kebocoran penerimaan kasir/pendaftaran.
- **REPUTASI**: Keluhan viral di medsos, Pemberitaan negatif insiden medis, Penurunan skor kepuasan pasien.
- **HUKUM_KEPATUHAN**: Kebocoran kerahasiaan rekam medis, Keterlambatan izin operasional/SIP/STR, Sengketa informed consent.
- **FASILITAS_LINGKUNGAN**: Kegagalan genset saat OK aktif, Kebocoran limbah B3/kimia lab, Kebakaran/kegagalan APAR.

- [ ] **Step 3: Update `static/js/ai-assist.js` to send `masalah` and `data` to AI payload**

In `static/js/ai-assist.js:110-118`:
Include `masalah` and `data` in the payload body sent to `/ai/mitigasi-risiko/`.

- [ ] **Step 4: Run full test suite to verify no regressions**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests akreditasi.tests_ai akreditasi.tests_manajemen_risiko_515`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/akreditasi/risiko_form.html static/js/ai-assist.js
git commit -m "feat(risiko): add Masalah and Data inputs and interactive category examples to risiko_form"
```

---

### Task 4: Risk Detail Display & Risk List Badging Updates

**Files:**
- Modify: `templates/akreditasi/risiko_detail.html:68-80`
- Modify: `templates/akreditasi/risiko_daftar.html:138-142`
- Modify: `templates/akreditasi/risiko_evaluasi.html:40-48`
- Test: `akreditasi/tests_manajemen_risiko_515.py`

**Interfaces:**
- Display: `{{ risiko.masalah }}`, `{{ risiko.data_pendukung }}`.
- Visual badges: Distinct colors for each of the 6 categories.

- [ ] **Step 1: Write test for detail view rendering of `masalah` and `data_pendukung`**

```python
    def test_risiko_detail_displays_masalah_and_data(self):
        r = RisikoUnit.objects.create(
            unit=self.unit,
            tahun=2026,
            periode='TRIWULAN_1',
            kategori_risiko='FASILITAS_LINGKUNGAN',
            jenis_risiko='Kegagalan Genset Saat OK Aktif',
            masalah='Genset otomatis sering terlambat menyala saat pemadaman PLN mendadak',
            data_pendukung='Hasil uji berkala IPSRS: transfer switch otomatis mengalami delay 18 detik (standar <10 detik)',
            deskripsi_risiko='Risiko terhentinya pasokan listrik saat operasi darurat berlangsung',
            dampak=5,
            probabilitas=2,
            strategi_mitigasi='HINDARI',
            rencana_aksi='Penggantian modul Automatic Transfer Switch (ATS) dan servis berkala genset',
            pj_mitigasi='Ka. IPSRS',
            created_by=self.user,
        )
        url = reverse('akreditasi:risiko_detail', kwargs={'risiko_id': r.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Genset otomatis sering terlambat menyala')
        self.assertContains(response, 'transfer switch otomatis mengalami delay 18 detik')
        self.assertContains(response, 'Fasilitas, B3, dan Lingkungan')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_manajemen_risiko_515`
Expected: FAIL because `risiko_detail.html` does not render `masalah` and `data_pendukung`.

- [ ] **Step 3: Update `templates/akreditasi/risiko_detail.html`**

In `templates/akreditasi/risiko_detail.html`:
Add structured blocks for:
```html
                    {% if risiko.masalah %}
                    <div class="mb-3">
                        <label class="text-muted d-block mb-1" style="font-size:.75rem;"><i class="bi bi-exclamation-circle text-danger me-1"></i>Masalah</label>
                        <p class="p-2 rounded border-start border-3 border-danger" style="background:#fff1f2; font-size:.82rem; color:#9f1239;">{{ risiko.masalah|linebreaksbr }}</p>
                    </div>
                    {% endif %}

                    {% if risiko.data_pendukung %}
                    <div class="mb-3">
                        <label class="text-muted d-block mb-1" style="font-size:.75rem;"><i class="bi bi-file-earmark-bar-graph text-primary me-1"></i>Data / Bukti Pendukung</label>
                        <p class="p-2 rounded border-start border-3 border-primary" style="background:#eff6ff; font-size:.82rem; color:#1e40af;">{{ risiko.data_pendukung|linebreaksbr }}</p>
                    </div>
                    {% endif %}
```

- [ ] **Step 4: Update `templates/akreditasi/risiko_daftar.html` category badge styling**

Provide badge color differentiation for the 6 categories:
- Klinis: Red (`bg-danger-subtle text-danger border border-danger-subtle`)
- Operasional: Blue (`bg-primary-subtle text-primary border border-primary-subtle`)
- Finansial: Emerald (`bg-success-subtle text-success border border-success-subtle`)
- Reputasi: Indigo (`bg-indigo-subtle text-indigo border border-indigo-subtle` or `bg-info text-dark`)
- Hukum & Kepatuhan: Amber (`bg-warning-subtle text-warning border border-warning-subtle`)
- Fasilitas & B3: Orange / Dark (`bg-secondary text-white`)

- [ ] **Step 5: Run tests and verify they pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_manajemen_risiko_515`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add templates/akreditasi/risiko_detail.html templates/akreditasi/risiko_daftar.html templates/akreditasi/risiko_evaluasi.html akreditasi/tests_manajemen_risiko_515.py
git commit -m "feat(risiko): render masalah, data_pendukung, and category badges in detail and list templates"
```

---

### Task 5: End-to-End Verification & Full Regression Testing

**Files:**
- Test: Full Django test suite across all apps (`akreditasi`, `pasien`, `accounts`).

- [ ] **Step 1: Run complete test suite**

Run: `.venv/Scripts/python.exe manage.py test`
Expected: 100+ tests PASS (0 failures, 0 errors).

- [ ] **Step 2: Inspect git diff & push to master**

Run: `git status` and `git push origin master`
Expected: Clean deploy to Vercel production.
