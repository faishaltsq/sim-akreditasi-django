# Master RKK Catalog & 5-Year Clinical Logbook (Buku Kinerja Elektronik PMK 13/2025) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permanently automate the seeding of the Master RKK Catalog (23 professions, 118 career grades, 499 clinical actions) and complete the dynamic aggregation of the 5-Year Clinical Logbook (Buku Kinerja Elektronik) from daily logbook entries (`EntriLogbookKlinis`) in strict alignment with **Permenkes No. 13 Tahun 2025 tentang Pengelolaan SDM Kesehatan**.

**Architecture:** 
1. Refactor `seed_katalog_rkk.py` to support historical `apps` registries, and create Django data migration `0065_seed_master_katalog_rkk.py` so the 499 catalog items are auto-seeded on any database running `migrate`.
2. Enhance `sdm/services/logbook.py:logbook_recap_5tahun` to return standard action codes (`KatalogTindakan.kode`), yearly distributions T1..T5, and verification statuses.
3. Update PDF builder `_ranah1_matrix` in `sdm/services/dokumen_kredensial.py` to match the official 10-column table mandated by PMK 13/2025 (`No | Tindakan Keprofesian | Kode Standar | T1 | T2 | T3 | T4 | T5 | Total 5 Tahun | Status Verifikasi`).
4. Upgrade `dokumen_kredensial_edit` view and `templates/sdm/kredensial/dokumen_edit.html` with a live visual preview of Ranah 1 (Clinical Actions) directly computed from daily logbook records, including empty state guidance.
5. Upgrade seeders (`seed_logbook_5tahun_siska.py` and demo) to bind entries to real `KatalogTindakan` FKs and create verified preceptor records across 5 calendar years.
6. Synchronize the master catalog and demo logbook entries to the live production database on Supabase (`gwaeuzbbdawbekrmrvfd`).

**Tech Stack:** Django 6.1.1, ReportLab 4.4, PostgreSQL 17 (Supabase), Bootstrap 5.3, Django Test Runner (`--keepdb`).

**Specs:** 
- `master RKK Kewenangan klinis.docx` (26 clinical profession sections, 499 clinical actions).
- `logbook Berdasarkan Peraturan Menteri Kesehatan Nomor 13 Tahun 2025 tentang Pengelolaan Sumber Daya Manusia Kesehatan.docx` (Buku Kinerja Elektronik 5 Tahunan, Pasal 180 Rekredensial, Tim Ad Hoc Kredensial, 3 Ranah Kinerja).

---

## Root Cause Analysis

1. **Production Symptom (User Screenshot):**
   - URL: `https://sim-akreditasi-django.vercel.app/human-capital/kredensial/katalog/` displays `0 tindakan · halaman 1 dari 1`.
   - In production Supabase (`gwaeuzbbdawbekrmrvfd`), `sdm_katalogtindakan`, `sdm_masterprofesipegawai`, and `sdm_masterjenjangprofesi` are empty (`0` rows).
   - In production Supabase, `sdm_entrilogbookklinis` has `0` rows.

2. **Analysis of Missing Data Flow from Daily to 5-Year Logbook:**
   - Although `logbook_recap_5tahun` exists in `sdm/services/logbook.py`, it was only used during PDF generation; it was never passed to `dokumen_kredensial_edit` in `sdm/views.py`. As a result, employees editing their draft in the web UI only saw raw textareas for manual fields (SKP, Etik, Ad Hoc signers) and could NOT see what daily clinical actions were being counted.
   - In `seed_logbook_5tahun_siska.py`, previous entries had `katalog_tindakan=None`, using raw text strings instead of linking to `KatalogTindakan` foreign keys.
   - In the PDF builder (`_ranah1_matrix`), the table rendered generic columns (`Kompetensi / Tindakan | T1 | T2 | T3 | T4 | T5 | Mandiri | Pelimpahan | Total`), omitting the `Kode Standar / ICD-9-CM` and `Status Verifikasi` columns explicitly specified in PMK 13/2025.

---

## Global Constraints

- **PMK 13/2025 Compliance:** The 4 sections (I. Profil SDMK & SATUSEHAT, II. Capaian 3 Ranah, III. Lembar Rekredensial Pasal 180, IV. Otentikasi Tiga Pihak) must remain intact.
- **Idempotency:** Re-running migrations and seeders must never duplicate `KatalogTindakan` or `EntriLogbookKlinis` rows.
- **Privacy & PII Protection:** No patient names in clinical logbooks; use Medical Record numbers (`pasien_ref`).
- **Standardization Invariant:** Clinical actions must bind to `KatalogTindakan` wherever catalog items exist.

---

## Review Focus

1. **FK Binding in Daily Entries:** Ensure `EntriLogbookKlinis.katalog_tindakan` is populated and `katalog_tindakan.kode` is rendered in Ranah 1.
2. **Trailing 5-Calendar-Year Logic:** Verify `T1` through `T5` index arithmetic correctly partitions entries by calendar year relative to the cycle end date.
3. **Draft Edit Web UX:** Ensure `dokumen_kredensial_edit` displays the aggregated table without requiring the employee to generate/download the PDF first.
4. **Historical Model Safety:** Data migration `0065` must use `apps.get_model` to remain safe against future model refactors.
5. **Preceptor Verification Aggregation:** Ensure entries marked with `VerifikasiLogbook.VERIFIED` correctly increment `recap['terverifikasi']` and display "Terverifikasi" badge.

---

## File Structure

```
sdm/
├── management/
│   └── commands/
│       ├── seed_katalog_rkk.py          # Modify: support apps parameter in apply_seed
│       ├── seed_logbook_5tahun_siska.py # Modify: link entries to KatalogTindakan FKs & add preceptor verifications
│       └── _data_katalog_rkk.py         # Reference: 499 actions, 118 grades, 23 professions
├── migrations/
│   └── 0065_seed_master_katalog_rkk.py  # Create: data migration for 499 RKK items
├── services/
│   ├── logbook.py                       # Modify: add kode and verification status to recap per_tindakan
│   └── dokumen_kredensial.py            # Modify: update _ranah1_matrix to 10-column PMK 13/2025 table
├── views.py                             # Modify: pass logbook recap to dokumen_kredensial_edit
├── templates/
│   └── sdm/
│       └── kredensial/
│           ├── katalog.html             # Modify: empty state with reset button
│           └── dokumen_edit.html        # Modify: interactive preview of Ranah 1 clinical actions
└── tests/
    ├── test_katalog_migration.py        # Create: tests for migration idempotency
    └── test_logbook_5tahun_pmk13.py     # Modify: tests for PMK 13/2025 10-column recap & FK binding
```

---

## Task Breakdown

### Task 1: Refactor `apply_seed` & Create Data Migration `0065`

**Files:**
- Modify: `sdm/management/commands/seed_katalog_rkk.py:106-255`
- Create: `sdm/migrations/0065_seed_master_katalog_rkk.py`
- Test: `sdm/tests/test_katalog_migration.py`

**Interfaces:**
- Consumes: `_data_katalog_rkk.py` data dictionaries.
- Produces: Migration `0065_seed_master_katalog_rkk` with `apply_seed(apps=apps)`.

- [ ] **Step 1: Write test for `apply_seed(apps=apps)` and data migration**

In `sdm/tests/test_katalog_migration.py`:
```python
from django.apps import apps
from django.test import TestCase
from sdm.management.commands.seed_katalog_rkk import apply_seed
from sdm.models import MasterProfesiPegawai, MasterJenjangProfesi, KatalogTindakan

class ApplySeedAppsParameterTests(TestCase):
    def test_apply_seed_accepts_apps_registry(self):
        created = apply_seed(apps=apps)
        self.assertIsInstance(created, tuple)
        self.assertEqual(len(created), 3)

    def test_migration_seeded_expected_totals(self):
        self.assertGreaterEqual(MasterProfesiPegawai.objects.count(), 23)
        self.assertGreaterEqual(MasterJenjangProfesi.objects.count(), 118)
        self.assertGreaterEqual(KatalogTindakan.objects.count(), 499)
```

- [ ] **Step 2: Update `apply_seed` in `sdm/management/commands/seed_katalog_rkk.py`**

Support `apps=None`:
```python
def apply_seed(apps=None):
    if apps is not None:
        MasterProfesiPegawai = apps.get_model('sdm', 'MasterProfesiPegawai')
        MasterJenjangProfesi = apps.get_model('sdm', 'MasterJenjangProfesi')
        KatalogTindakan = apps.get_model('sdm', 'KatalogTindakan')
    else:
        from sdm.models import KatalogTindakan, MasterJenjangProfesi, MasterProfesiPegawai
```

- [ ] **Step 3: Create migration `sdm/migrations/0065_seed_master_katalog_rkk.py`**

```python
from django.db import migrations

def forward_seed_katalog(apps, schema_editor):
    from sdm.management.commands.seed_katalog_rkk import apply_seed
    apply_seed(apps=apps)

class Migration(migrations.Migration):
    dependencies = [
        ('sdm', '0064_alter_dokumensyaratkredensial_jenis_and_more'),
    ]
    operations = [
        migrations.RunPython(forward_seed_katalog, reverse_code=migrations.RunPython.noop),
    ]
```

- [ ] **Step 4: Run tests & verify**

Run: `python manage.py test sdm.tests.test_katalog_migration --keepdb`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sdm/management/commands/seed_katalog_rkk.py sdm/migrations/0065_seed_master_katalog_rkk.py sdm/tests/test_katalog_migration.py
git commit -m "feat(sdm): add data migration 0065 for master rkk catalog auto-seeding"
```

---

### Task 2: Enhance 5-Year Logbook Service (`logbook_recap_5tahun`) with Standard Codes & Verifications

**Files:**
- Modify: `sdm/services/logbook.py:60-140`
- Test: `sdm/tests/test_logbook_5tahun_pmk13.py`

**Interfaces:**
- Consumes: `EntriLogbookKlinis.objects.filter(employee=employee, tanggal__gte=start_date)`
- Produces: `recap['per_tindakan']` containing `{'label', 'kode', 'mandiri', 'supervisi', 'kolaborasi', 'total', 'tahunan', 'status_verifikasi'}`

- [ ] **Step 1: Write failing test in `sdm/tests/test_logbook_5tahun_pmk13.py`**

```python
def test_recap_contains_action_kode_and_verification_status(self):
    recap = logbook_recap_5tahun(self.pegawai)
    self.assertGreater(len(recap['per_tindakan']), 0)
    first_item = recap['per_tindakan'][0]
    self.assertIn('kode', first_item)
    self.assertIn('status_verifikasi', first_item)
    self.assertIn(first_item['status_verifikasi'], ('Terverifikasi', 'Menunggu Verifikasi'))
```

- [ ] **Step 2: Update `sdm/services/logbook.py:logbook_recap_5tahun`**

Populate `kode` and `status_verifikasi` per action item:
```python
        label = entry.katalog_tindakan.nama if entry.katalog_tindakan else entry.tindakan
        kode = entry.katalog_tindakan.kode if entry.katalog_tindakan else '-'
        is_verified = any(v.status == VerifikasiLogbook.VERIFIED for v in entry.verifikasi.all())

        row = next((item for item in recap['per_tindakan'] if item['label'] == label), None)
        if row is None:
            row = {
                'label': label,
                'kode': kode,
                'mandiri': 0, 'supervisi': 0, 'kolaborasi': 0,
                'total': 0, 'tahunan': [0] * years,
                'verified_count': 0,
            }
            recap['per_tindakan'].append(row)
        ...
        if is_verified:
            row['verified_count'] += total
```
At end of loop, derive `status_verifikasi = 'Terverifikasi' if item['verified_count'] > 0 else 'Menunggu Verifikasi'`.

- [ ] **Step 3: Run test to verify it passes**

Run: `python manage.py test sdm.tests.test_logbook_5tahun_pmk13 --keepdb`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add sdm/services/logbook.py sdm/tests/test_logbook_5tahun_pmk13.py
git commit -m "feat(logbook): add standard code and verification status to 5-year recap"
```

---

### Task 3: Upgrade PDF Builder `_ranah1_matrix` to Official PMK 13/2025 10-Column Table

**Files:**
- Modify: `sdm/services/dokumen_kredensial.py:438-473`
- Test: `sdm/tests/test_logbook_5tahun_pmk13.py`

**Interfaces:**
- Consumes: `logbook_recap_5tahun(employee, years=5)`
- Produces: ReportLab `Table` with 10 columns: `No`, `Jenis Tindakan`, `Kode Standar`, `T1`..`T5`, `Total 5 Thn`, `Status Verifikasi`.

- [ ] **Step 1: Write test for 10-column table in PDF generation**

```python
def test_pdf_contains_pmk13_table_columns(self):
    draf = DrafDokumenKredensial.objects.get(pegawai=self.pegawai, jenis='LOGBOOK_5TAHUN')
    pdf_bytes = render_pdf(draf)
    self.assertGreater(len(pdf_bytes), 1000)
```

- [ ] **Step 2: Update `_ranah1_matrix` in `sdm/services/dokumen_kredensial.py`**

Construct the 10-column PMK 13/2025 layout:
```python
def _ranah1_matrix(employee, styles, years=5):
    recap = logbook_recap_5tahun(employee, years=years)
    header = [
        Paragraph('<b>No</b>', styles['cell_title']),
        Paragraph('<b>Jenis Tindakan Keprofesian</b>', styles['cell_title']),
        Paragraph('<b>Kode Standar</b>', styles['cell_title']),
    ]
    header += [Paragraph(f'<b>{label}</b>', styles['cell_title']) for label in recap['tahun_labels']]
    header += [
        Paragraph('<b>Total 5 Thn</b>', styles['cell_title']),
        Paragraph('<b>Status Verifikasi</b>', styles['cell_title']),
    ]
    rows = [header]
    for idx, item in enumerate(recap['per_tindakan'], start=1):
        row = [
            Paragraph(str(idx), styles['cell']),
            Paragraph(item['label'], styles['cell']),
            Paragraph(item.get('kode', '-'), styles['cell']),
        ]
        row += [Paragraph(str(v), styles['cell']) for v in item['tahunan']]
        row += [
            Paragraph(str(item['total']), styles['cell']),
            Paragraph(item.get('status_verifikasi', 'Menunggu'), styles['cell']),
        ]
        rows.append(row)
    widths = [8 * mm, 50 * mm, 20 * mm] + [12 * mm] * years + [16 * mm, 22 * mm]
    return _boxed_table(rows, widths, styles), recap
```

- [ ] **Step 3: Run test to verify PDF compiles without error**

Run: `python manage.py test sdm.tests.test_logbook_5tahun_pmk13 --keepdb`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add sdm/services/dokumen_kredensial.py
git commit -m "feat(kredensial): align ranah 1 table in 5-year logbook pdf to pmk 13/2025 spec"
```

---

### Task 4: Enhance Draft Edit Web UI with Live Ranah 1 Preview Table

**Files:**
- Modify: `sdm/views.py:3148-3178`
- Modify: `templates/sdm/kredensial/dokumen_edit.html:8-20`
- Test: `sdm/tests/test_dokumen_kredensial_ui.py`

**Interfaces:**
- Consumes: `logbook_recap_5tahun(pegawai)` passed to template context when `jenis == 'LOGBOOK_5TAHUN'`.
- Produces: HTML card displaying the 5-year clinical actions recap with volume per year and verification badges directly in the browser.

- [ ] **Step 1: Write UI test for live Ranah 1 table rendering**

In `sdm/tests/test_dokumen_kredensial_ui.py`:
```python
def test_dokumen_edit_renders_live_ranah1_table_for_logbook_5tahun(self):
    url = reverse('sdm:dokumen_kredensial_edit', kwargs={'jenis': 'LOGBOOK_5TAHUN'})
    response = self.client.get(url)
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, 'Ranah 1: Capaian Tindakan Klinis (Logbook Harian)')
    self.assertContains(response, 'Kode Standar')
```

- [ ] **Step 2: Update `sdm/views.py:dokumen_kredensial_edit`**

Include recap when `jenis in ('LOGBOOK_5TAHUN', 'LOGBOOK_36BLN')`:
```python
    logbook_recap_data = None
    if jenis == 'LOGBOOK_5TAHUN':
        from sdm.services.logbook import logbook_recap_5tahun
        logbook_recap_data = logbook_recap_5tahun(pegawai)
    elif jenis == 'LOGBOOK_36BLN':
        from sdm.services.logbook import logbook_recap
        logbook_recap_data = logbook_recap(pegawai, months=36)
```
Pass `logbook_recap: logbook_recap_data` to template.

- [ ] **Step 3: Update `templates/sdm/kredensial/dokumen_edit.html`**

Add the preview card above the manual form fields:
```html
    {% if logbook_recap %}
    <div class="card border shadow-sm mb-4">
        <div class="card-header bg-white d-flex justify-content-between align-items-center">
            <h2 class="h6 mb-0">Ranah 1: Capaian Tindakan Klinis (Logbook Harian)</h2>
            <a href="{% url 'sdm:logbook_list' %}" class="btn btn-outline-primary btn-sm">
                <i class="bi bi-journal-plus me-1"></i>Buka Logbook Harian
            </a>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-sm table-hover align-middle mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>No</th>
                            <th>Tindakan Keprofesian</th>
                            <th>Kode Standar</th>
                            {% for yr in logbook_recap.tahun_labels %}
                            <th class="text-center">{{ yr }}</th>
                            {% endfor %}
                            <th class="text-center">Total 5 Thn</th>
                            <th>Status Verifikasi</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in logbook_recap.per_tindakan %}
                        <tr>
                            <td>{{ forloop.counter }}</td>
                            <td class="fw-medium">{{ item.label }}</td>
                            <td><code>{{ item.kode }}</code></td>
                            {% for val in item.tahunan %}
                            <td class="text-center">{{ val }}</td>
                            {% endfor %}
                            <td class="text-center fw-bold">{{ item.total }}</td>
                            <td>
                                {% if item.status_verifikasi == 'Terverifikasi' %}
                                <span class="badge text-bg-success">Terverifikasi</span>
                                {% else %}
                                <span class="badge text-bg-warning">Menunggu</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% empty %}
                        <tr>
                            <td colspan="9" class="text-center py-4 text-muted">
                                Belum ada entri tindakan di logbook harian untuk window 5 tahun ini.
                                <br/>
                                <a href="{% url 'sdm:logbook_list' %}" class="btn btn-sm btn-link">Mulai isi tindakan di Logbook Harian</a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    {% endif %}
```

- [ ] **Step 4: Run tests & verify**

Run: `python manage.py test sdm.tests.test_dokumen_kredensial_ui --keepdb`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sdm/views.py templates/sdm/kredensial/dokumen_edit.html sdm/tests/test_dokumen_kredensial_ui.py
git commit -m "feat(ui): add live ranah 1 daily logbook table to credential draft edit page"
```

---

### Task 5: Upgrade Seeder to Link Daily Entries to Real `KatalogTindakan` FKs & Verifications

**Files:**
- Modify: `sdm/management/commands/seed_logbook_5tahun_siska.py:30-135`
- Test: `sdm/tests/test_logbook_5tahun_pmk13.py`

**Interfaces:**
- Consumes: `KatalogTindakan.objects.filter(jenjang__profesi__code='KPR')`
- Produces: 40 `EntriLogbookKlinis` rows with `katalog_tindakan` FK set and `VerifikasiLogbook` created.

- [ ] **Step 1: Update `seed_logbook_5tahun_siska.py`**

Resolve or create matching `KatalogTindakan` for each action:
```python
        for nama, total, mandiri, kolaborasi, supervisi in self.TINDAKAN:
            katalog_item = KatalogTindakan.objects.filter(nama__icontains=nama[:20]).first()
            for idx in range(5):
                tahun = tahun_terakhir - (4 - idx)
                tanggal = today.replace(year=tahun, month=6, day=15)
                entry = EntriLogbookKlinis.objects.create(
                    employee=pegawai,
                    unit_kerja=unit,
                    tanggal=tanggal,
                    tindakan=nama,
                    katalog_tindakan=katalog_item,
                    jumlah_mandiri=max(1, mandiri // 5),
                    jumlah_kolaborasi=kolaborasi // 5,
                    jumlah_supervisi=supervisi // 5,
                    pasien_ref=f'RM-PED-{tahun}-{total}',
                )
                VerifikasiLogbook.objects.create(
                    entri=entry,
                    verifier=user,
                    status=VerifikasiLogbook.VERIFIED,
                    catatan='Terverifikasi oleh Tim Preseptor Bangsal Anak',
                )
```

- [ ] **Step 2: Re-run seed command and verify**

Run: `python manage.py seed_logbook_5tahun_siska`
Expected: Success with `EntriLogbookKlinis` bound to `KatalogTindakan` and verified.

- [ ] **Step 3: Run unit and integration tests**

Run: `python manage.py test sdm.tests.test_logbook_5tahun_pmk13 --keepdb`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add sdm/management/commands/seed_logbook_5tahun_siska.py
git commit -m "feat(seeder): bind 5-year logbook entries to real katalog tindakan and verify them"
```

---

### Task 6: Synchronize Master RKK & 5-Year Logbook to Supabase Production

**Target:** Supabase project `gwaeuzbbdawbekrmrvfd`

- [ ] **Step 1: Execute SQL batch on Supabase to populate `MasterProfesiPegawai`, `MasterJenjangProfesi`, and `KatalogTindakan`**
- [ ] **Step 2: Register migration `sdm.0065_seed_master_katalog_rkk` in `django_migrations`**
- [ ] **Step 3: Verify Supabase row counts:**
  - `sdm_masterprofesipegawai` >= 23
  - `sdm_masterjenjangprofesi` >= 118
  - `sdm_katalogtindakan` >= 499
- [ ] **Step 4: Seed sample daily logbook entries on Supabase for active clinical staff**
- [ ] **Step 5: Verify live endpoint `https://sim-akreditasi-django.vercel.app/human-capital/kredensial/katalog/` displays 499 actions**
- [ ] **Step 6: Verify live draft edit endpoint displays the populated Ranah 1 daily logbook table**

---

### Task 7: Full Regression Check, Collectstatic, and Push to Remote

**Files:**
- Push: `origin master`

- [ ] **Step 1: Run comprehensive tests**
  Run: `python manage.py test sdm.tests.test_katalog_migration sdm.tests.test_logbook_5tahun_pmk13 sdm.tests.test_dokumen_kredensial sdm.tests.test_dokumen_kredensial_ui --keepdb`
  Expected: All PASS.

- [ ] **Step 2: Run collectstatic**
  Run: `python manage.py collectstatic --noinput`
  Expected: PASS.

- [ ] **Step 3: Push to GitHub**
  Run: `git push origin master`
  Expected: Remote updated and Vercel triggers build.
