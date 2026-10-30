# Unifikasi Logbook Harian & Logbook Klinis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify "Logbook Harian" (shift-based unit logbook) and "Logbook Saya" (individual clinical action logbook) into 1 single menu & 1 unified page (`/logbook/`), enhance Logbook Harian with structured clinical actions ("Tindakan Klinis") selected from `Katalog tindakan klinis.docx` with categories (Mandiri, Kolaborasi, Supervisi), and automatically synchronize shift actions to staff's personal credentialing logbook (`EntriLogbookKlinis`).

**Architecture:** 
1. Transcribe and seed the comprehensive clinical procedures from `Katalog tindakan klinis.docx` into `sdm.KatalogTindakan` (covering Dokter Umum, Spesialis, Subspesialis, and 18 Nakes categories).
2. Extend `sdm.EntriLogbookKlinis` with nullable foreign keys to `akreditasi.LogbookHarian` and `akreditasi.LogbookPasien`, ensuring zero double-entry: recording a clinical procedure during a shift in Logbook Harian simultaneously logs it to the staff member's 36-month credentialing record.
3. Add a dedicated "Tindakan Klinis Shift" section to `templates/akreditasi/logbook_detail.html` with catalog autocomplete/select, category picker (`Mandiri` default, `Kolaborasi`, `Supervisi`), and patient selector.
4. Unify the `/logbook/` index page (`templates/akreditasi/logbook_daftar.html`) with dual-tab support ("Logbook Harian Shift" and "Logbook Saya"), and collapse the sidebar into 1 unified "Logbook" menu item.

**Tech Stack:** Django 5, Bootstrap 5, SQLite (dev) / Supabase PostgreSQL (prod), Django ORM migrations.

**Spec:** User prompt analysis + `C:\Users\cubeb\Downloads\Katalog tindakan klinis.docx` + existing `akreditasi/logbook.py` and `sdm/models/logbook.py`.

---

## Global Constraints

- Plan document is written in **English**; UI copy, labels, help text, and test strings stay in **Bahasa Indonesia**.
- Follow established patterns from `akreditasi/logbook.py` and `sdm/views.py`: use `_catat` for audit logging and strict RBAC guards.
- All timestamps must be timezone-aware using `django.utils.timezone.localtime`.
- All database migrations must be additive and reversible without dropping existing columns.
- Test baseline: all 64 existing `akreditasi` logbook tests and 27 `sdm` logbook tests must remain green.

## Review Focus

1. **Dual Attribution:** When a clinical action is logged in Logbook Harian, `EntriLogbookKlinis` must populate `employee` with the current staff user's `Pegawai`, and copy `pasien_ref` from `LogbookPasien.no_rm` or initials.
2. **Category Counting:** In `EntriLogbookKlinis`, `kategori='M'` must increment `jumlah_mandiri=1`, `'K'` must increment `jumlah_kolaborasi=1`, and `'S'` must increment `jumlah_supervisi=1` so credentialing 36-month aggregations work seamlessly without modification.
3. **Locking Integrity:** When a `LogbookHarian` is approved (`status='DISETUJUI'`), adding or deleting clinical actions from that shift must be forbidden.
4. **Sidebar Unification:** Consolidate navigation so users see one clear "Logbook" menu, preventing navigation ambiguity while preserving direct URL routing for both tabs.
5. **Incident vs Action Boundary:** Clarify that Section IV ("Kejadian Keselamatan Shift") handles IKP safety incidents / shift nihilism ("Tidak Ada Kejadian"), while the new Section handles clinical medical/nursing procedures ("Tindakan Klinis").

---

## File Structure

- Create: `sdm/management/commands/seed_katalog_klinis_docx.py` (Parser and seeder for docx clinical catalog)
- Create: `sdm/migrations/0062_entrilogbookklinis_logbook_harian_and_pasien.py` (Model extension)
- Create: `akreditasi/tests/test_logbook_tindakan_unifikasi.py` (New comprehensive tests)
- Modify: `sdm/models/logbook.py` (Add `logbook_harian` and `logbook_pasien` FKs)
- Modify: `akreditasi/logbook.py` (Add `logbook_simpan_tindakan`, `logbook_hapus_tindakan`, and tabbed `logbook_daftar`)
- Modify: `akreditasi/urls.py` (Register action endpoints)
- Modify: `templates/akreditasi/logbook_detail.html` (Add Tindakan Klinis section & patient action badges)
- Modify: `templates/akreditasi/logbook_daftar.html` (Add tabbed interface for Harian vs Saya)
- Modify: `templates/includes/sidebar.html` (Unify sidebar menu item to single "Logbook")

---

### Task 1: Seed Clinical Action Catalog from DOCX into `KatalogTindakan`

**Files:**
- Create: `sdm/management/commands/seed_katalog_klinis_docx.py`
- Test: `sdm/tests/test_seed_katalog_docx.py`

**Interfaces:**
- Consumes: `C:\Users\cubeb\Downloads\Katalog tindakan klinis.docx`, `sdm.models.MasterProfesiPegawai`, `sdm.models.MasterJenjangProfesi`
- Produces: Populated `sdm.models.KatalogTindakan` with codes `K-DOCX-...` or profession-mapped codes.

- [ ] **Step 1: Write failing test for catalog seeder**

```python
# sdm/tests/test_seed_katalog_docx.py
from django.core.management import call_command
from django.test import TestCase
from sdm.models import KatalogTindakan, MasterProfesiPegawai, MasterJenjangProfesi

class SeedKatalogDocxTest(TestCase):
    def test_seed_katalog_docx_populates_general_practitioner_actions(self):
        call_command('seed_katalog_klinis_docx', dry_run=False)
        self.assertTrue(KatalogTindakan.objects.filter(nama__icontains='Anamnesis dan Pemeriksaan Fisik').exists())
        self.assertTrue(KatalogTindakan.objects.filter(nama__icontains='Pemasangan & Pelepasan Infus').exists())
        self.assertTrue(KatalogTindakan.objects.filter(nama__icontains='Resusitasi Jantung Paru').exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_seed_katalog_docx`
Expected: FAIL (command `seed_katalog_klinis_docx` does not exist).

- [ ] **Step 3: Implement `seed_katalog_klinis_docx.py`**

Implement management command `sdm/management/commands/seed_katalog_klinis_docx.py` containing transcribed clinical actions from the docx:
- Dokter Umum: Anamnesis, IV line, Kateter Urin, NGT, Terapi O2 & RJP, EKG, Hecting & Debridement, AGD, Thoracocentesis, Informed Consent.
- Spesialis & Subspesialis (Sp.PD, Sp.B, Sp.A, Sp.OG, Sp.JP, Sp.S, Sp.An, Sp.Rad, Sp.PK, Sp.PA, Sp.OT, Sp.THT, Sp.M, Sp.KK, Sp.KJ, Sp.P, and all Sp-K).
- 18 Nakes: Perawat (PK I-IV), Bidan (Klinis I-IV), Apoteker, Elektromedis, Sanitarian, Dietisien/Nutrisionis, TTK, Perawat Anestesi, PMIK, Terapi Wicara, Okupasi, Ortotik, Fisioterapi, Psikolog Klinis, Radiografer, Fisikawan Medis, ATLM, Ahli K3.
Upsert with `get_or_create` on `kode` and associate with the appropriate `MasterJenjangProfesi` or create fallback jenjang if missing.

- [ ] **Step 4: Run test and verify it passes**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_seed_katalog_docx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sdm/management/commands/seed_katalog_klinis_docx.py sdm/tests/test_seed_katalog_docx.py
git commit -m "feat(sdm): seed clinical procedures catalog from docx specification"
```

---

### Task 2: Model Extension: Connect `LogbookHarian` to `EntriLogbookKlinis`

**Files:**
- Modify: `sdm/models/logbook.py:20-56`
- Create: `sdm/migrations/0062_entrilogbookklinis_logbook_harian_and_pasien.py` (via `makemigrations`)
- Test: `sdm/tests/test_logbook_harian_integration.py`

**Interfaces:**
- Consumes: `akreditasi.models.LogbookHarian`, `akreditasi.models.LogbookPasien`
- Produces: `EntriLogbookKlinis.logbook_harian`, `EntriLogbookKlinis.logbook_pasien`

- [ ] **Step 1: Write failing test for model integration**

```python
# sdm/tests/test_logbook_harian_integration.py
from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from akreditasi.logbook_models import LogbookHarian, LogbookPasien
from sdm.models import Pegawai, EntriLogbookKlinis, KatalogTindakan

class LogbookHarianIntegrationTest(TestCase):
    def test_entri_logbook_links_to_logbook_harian_and_pasien(self):
        unit = UnitKerja.objects.create(code='IGD-TEST', name='IGD Test', level=1)
        user = User.objects.create_user('nurse1', password='x')
        emp = Pegawai.objects.create(user=user, nama_lengkap='Nurse 1', nik='1234567890123456')
        lb = LogbookHarian.objects.create(unit=unit, tanggal=date(2026, 11, 1), shift='PAGI')
        pasien = LogbookPasien.objects.create(logbook=lb, nama_pasien='Tn. Ahmad', no_rm='RM001')
        katalog = KatalogTindakan.objects.create(kode='TEST-INFUS', nama='Pemasangan Infus', jenjang_id=None)
        
        entry = EntriLogbookKlinis.objects.create(
            employee=emp,
            tanggal=lb.tanggal,
            unit_kerja=unit,
            logbook_harian=lb,
            logbook_pasien=pasien,
            katalog_tindakan=katalog,
            kategori='M',
            jumlah_mandiri=1,
            created_by=user,
        )
        self.assertEqual(entry.logbook_harian, lb)
        self.assertEqual(entry.logbook_pasien, pasien)
        self.assertIn(entry, lb.tindakan_klinis.all())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_harian_integration`
Expected: FAIL (`logbook_harian` field not found).

- [ ] **Step 3: Modify `sdm/models/logbook.py` and run `makemigrations`**

Add to `EntriLogbookKlinis`:
```python
    logbook_harian = models.ForeignKey(
        'akreditasi.LogbookHarian', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tindakan_klinis', verbose_name='Logbook Harian Shift',
    )
    logbook_pasien = models.ForeignKey(
        'akreditasi.LogbookPasien', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tindakan_klinis', verbose_name='Baris Pasien Logbook',
    )
```
Run `makemigrations sdm`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_logbook_harian_integration`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sdm/models/logbook.py sdm/migrations/0062_*.py sdm/tests/test_logbook_harian_integration.py
git commit -m "feat(sdm): add logbook_harian and logbook_pasien foreign keys to EntriLogbookKlinis"
```

---

### Task 3: Backend Views & Endpoints for Shift Clinical Actions

**Files:**
- Modify: `akreditasi/logbook.py`
- Modify: `akreditasi/urls.py`
- Test: `akreditasi/tests/test_logbook_tindakan_views.py`

**Interfaces:**
- Consumes: `POST /logbook/<pk>/tindakan/`, `POST /logbook/<pk>/tindakan/<uuid:tindakan_id>/hapus/`
- Produces: Persisted `EntriLogbookKlinis` with correct category counters and audit logs.

- [ ] **Step 1: Write failing view tests**

```python
# akreditasi/tests/test_logbook_tindakan_views.py
from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from akreditasi.logbook_models import LogbookHarian, LogbookPasien
from sdm.models import Pegawai, KatalogTindakan, EntriLogbookKlinis

class LogbookTindakanViewTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(code='IGD-01', name='IGD', level=1)
        self.user = User.objects.create_user('perawat1', password='x')
        UserProfile.objects.create(user=self.user, role='STAF_NAKES', unit_kerja=self.unit)
        self.emp = Pegawai.objects.create(user=self.user, nama_lengkap='Perawat 1', nik='1122334455667788')
        self.lb = LogbookHarian.objects.create(unit=self.unit, tanggal=date(2026, 11, 1), shift='PAGI', dibuat_oleh=self.user)
        self.pasien = LogbookPasien.objects.create(logbook=self.lb, nama_pasien='Tn. Anton', no_rm='RM101')
        self.katalog = KatalogTindakan.objects.create(kode='TIND-01', nama='Pemasangan Infus')
        self.client.force_login(self.user)

    def test_simpan_tindakan_mandiri_creates_entri_klinis(self):
        url = reverse('akreditasi:logbook_simpan_tindakan', args=[self.lb.pk])
        resp = self.client.post(url, {
            'pasien_id': self.pasien.pk,
            'katalog_id': self.katalog.pk,
            'kategori': 'M',
            'catatan': 'Jalur perifer lancar',
        })
        self.assertEqual(resp.status_code, 302)
        entri = EntriLogbookKlinis.objects.get(logbook_harian=self.lb)
        self.assertEqual(entri.employee, self.emp)
        self.assertEqual(entri.kategori, 'M')
        self.assertEqual(entri.jumlah_mandiri, 1)
        self.assertEqual(entri.jumlah_kolaborasi, 0)
        self.assertEqual(entri.jumlah_supervisi, 0)
        self.assertEqual(entri.pasien_ref, 'RM101')

    def test_simpan_tindakan_kolaborasi_and_supervisi_sets_correct_counts(self):
        url = reverse('akreditasi:logbook_simpan_tindakan', args=[self.lb.pk])
        self.client.post(url, {
            'pasien_id': self.pasien.pk,
            'katalog_id': self.katalog.pk,
            'kategori': 'K',
        })
        entri_k = EntriLogbookKlinis.objects.filter(logbook_harian=self.lb, kategori='K').first()
        self.assertEqual(entri_k.jumlah_kolaborasi, 1)
        self.assertEqual(entri_k.jumlah_mandiri, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests.test_logbook_tindakan_views`
Expected: FAIL (URL `logbook_simpan_tindakan` not found).

- [ ] **Step 3: Implement views in `akreditasi/logbook.py` and register in `akreditasi/urls.py`**

1. Implement `logbook_simpan_tindakan(request, pk)`:
   - Validate logbook status is editable (`boleh_ubah`).
   - Extract `katalog_id` or free text `tindakan_bebas`.
   - Resolve `kategori` (`M`, `K`, `S`).
   - Resolve `Pegawai` from `request.user.pegawai_hc` (fallback to target employee if chosen).
   - Set counter: `jumlah_mandiri = 1 if kategori == 'M' else 0`, `jumlah_kolaborasi = 1 if kategori == 'K' else 0`, `jumlah_supervisi = 1 if kategori == 'S' else 0`.
   - Save `EntriLogbookKlinis` and create `AuditLog`.
2. Implement `logbook_hapus_tindakan(request, pk, tindakan_id)`:
   - Ensure logbook is editable and user is author or has permission.
   - Delete entry and redirect.
3. Update `logbook_detail`:
   - Pass `tindakan_shift = logbook.tindakan_klinis.select_related('employee', 'katalog_tindakan', 'logbook_pasien').all()`
   - Pass `katalog_tindakan_pilihan = KatalogTindakan.objects.filter(is_active=True).order_by('nama')[:300]`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests.test_logbook_tindakan_views`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add akreditasi/logbook.py akreditasi/urls.py akreditasi/tests/test_logbook_tindakan_views.py
git commit -m "feat(akreditasi): implement logbook_simpan_tindakan and logbook_hapus_tindakan endpoints"
```

---

### Task 4: UI Enhancement in `logbook_detail.html` (Tindakan Klinis Shift)

**Files:**
- Modify: `templates/akreditasi/logbook_detail.html:85-165,310-395`
- Test: `akreditasi/tests/test_logbook_detail_template.py`

**Interfaces:**
- Consumes: `tindakan_shift`, `katalog_tindakan_pilihan`, `KATEGORI_CHOICES`
- Produces: Interactive form for adding clinical actions (Mandiri, Kolaborasi, Supervisi) and summary table.

- [ ] **Step 1: Write template test to assert clinical action elements exist**

```python
# akreditasi/tests/test_logbook_detail_template.py
from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from akreditasi.logbook_models import LogbookHarian, LogbookPasien
from sdm.models import Pegawai

class LogbookDetailTemplateTest(TestCase):
    def test_logbook_detail_renders_tindakan_klinis_section_and_categories(self):
        unit = UnitKerja.objects.create(code='IGD-01', name='IGD', level=1)
        user = User.objects.create_user('perawat1', password='x')
        UserProfile.objects.create(user=user, role='STAF_NAKES', unit_kerja=unit)
        Pegawai.objects.create(user=user, nama_lengkap='Perawat 1', nik='1122334455667788')
        lb = LogbookHarian.objects.create(unit=unit, tanggal=date(2026, 11, 1), shift='PAGI', dibuat_oleh=user)
        self.client.force_login(user)
        
        resp = self.client.get(reverse('akreditasi:logbook_detail', args=[lb.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Tindakan Klinis Shift', content)
        self.assertIn('Mandiri', content)
        self.assertIn('Kolaborasi', content)
        self.assertIn('Supervisi', content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests.test_logbook_detail_template`
Expected: FAIL ('Tindakan Klinis Shift' not in content).

- [ ] **Step 3: Update `templates/akreditasi/logbook_detail.html`**

Add the dedicated section between Pasien Shift and Personel Shift (or right after Pasien Shift):
- Render form with:
  - Pasien dropdown (options: `b.pk` - `b.nama_pasien (RM: b.no_rm)`).
  - Tindakan select with datalist/select from catalog + option for free text.
  - Kategori radio pill buttons: `Mandiri (M)` [default checked, badge green], `Kolaborasi (K)` [badge blue], `Supervisi (S)` [badge warning].
  - Pelaksana indicator (defaults to active user / employee).
  - Submit button: `+ Catat Tindakan Klinis`.
- Render table of `tindakan_shift`:
  - Columns: Jam/Waktu, Pasien, Tindakan Klinis, Kategori (Badge), Pelaksana, Catatan, Aksi.
  - Delete button for draft shifts.
- In Section I (Daftar Pasien Shift):
  - In the "Tindakan" column, display badges for actions performed on that patient during this shift.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests.test_logbook_detail_template`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/akreditasi/logbook_detail.html akreditasi/tests/test_logbook_detail_template.py
git commit -m "feat(ui): add structured tindakan klinis shift section and badges in logbook_detail"
```

---

### Task 5: Unify Index Dashboard & Sidebar into 1 Menu (1 Page)

**Files:**
- Modify: `akreditasi/logbook.py:165-203`
- Modify: `templates/akreditasi/logbook_daftar.html`
- Modify: `templates/includes/sidebar.html:164-167,369-373`
- Test: `akreditasi/tests/test_logbook_unifikasi_dashboard.py`

**Interfaces:**
- Consumes: `GET /logbook/?tab=harian` and `GET /logbook/?tab=saya`
- Produces: Unified single-page experience containing both unit shift logbooks and personal clinical entries.

- [ ] **Step 1: Write failing tests for unified dashboard and sidebar**

```python
# akreditasi/tests/test_logbook_unifikasi_dashboard.py
from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from sdm.models import Pegawai, EntriLogbookKlinis

class LogbookUnifikasiDashboardTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(code='IGD-01', name='IGD', level=1)
        self.user = User.objects.create_user('staf1', password='x')
        UserProfile.objects.create(user=self.user, role='STAF_NAKES', unit_kerja=self.unit)
        self.emp = Pegawai.objects.create(user=self.user, nama_lengkap='Staf Nakes', nik='9988776655443322')
        self.client.force_login(self.user)

    def test_logbook_daftar_supports_tab_saya(self):
        resp = self.client.get(reverse('akreditasi:logbook_daftar') + '?tab=saya')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Logbook Saya', content)
        self.assertIn('Rekap 36 Bulan', content)

    def test_sidebar_has_unified_logbook_menu(self):
        resp = self.client.get(reverse('akreditasi:logbook_daftar'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Logbook Pelayanan &amp; Klinis', content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests.test_logbook_unifikasi_dashboard`
Expected: FAIL.

- [ ] **Step 3: Update `akreditasi/logbook.py`, `templates/akreditasi/logbook_daftar.html`, and `templates/includes/sidebar.html`**

1. In `akreditasi/logbook.py` (`logbook_daftar`):
   - Read `tab = request.GET.get('tab', 'harian')`.
   - When `tab == 'saya'`:
     - Fetch personal clinical logbook entries for `request.user.pegawai_hc` (from `EntriLogbookKlinis`).
     - Calculate 36-month recap (total mandiri, kolaborasi, supervisi).
     - Provide quick-add form context for personal entries.
2. In `templates/akreditasi/logbook_daftar.html`:
   - Render Bootstrap nav-tabs at the top:
     - `[Tab 1] Logbook Harian Shift (Unit / IGD / Ranap)`
     - `[Tab 2] Logbook Saya (Tindakan Klinis Pribadi)`
   - Tab 1 displays shift filters, shift list, and "+ Buat Logbook Shift".
   - Tab 2 displays 36-month recap metrics, filter by kategori (M/K/S), quick personal entry, and entry table.
3. In `templates/includes/sidebar.html`:
   - Under "Mutu dan kinerja", rename link title to "Logbook Pelayanan & Klinis" (Label: `Logbook`).
   - Under "Kredensial saya", update "Logbook saya" to point directly to `{% url 'akreditasi:logbook_daftar' %}?tab=saya`, so clicking it seamlessly navigates to the unified page on the personal tab without duplicating separate modules.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests.test_logbook_unifikasi_dashboard`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add akreditasi/logbook.py templates/akreditasi/logbook_daftar.html templates/includes/sidebar.html akreditasi/tests/test_logbook_unifikasi_dashboard.py
git commit -m "feat(ui): unify logbook harian and logbook saya into single menu and tabbed page"
```

---

### Task 6: Full Regression Suite & Verification

**Files:**
- Test: Run all tests in `akreditasi` and `sdm` suites.

- [ ] **Step 1: Run comprehensive test suite**

Run: `.venv/Scripts/python.exe manage.py test akreditasi sdm`
Expected: ALL PASS with 0 errors.

- [ ] **Step 2: Verify git status is clean**

Run: `git status --short`
Ensure only planned files are touched.

- [ ] **Step 3: Commit final integration verification if needed**

```bash
git commit -m "chore(logbook): finalize unified logbook harian and clinical actions module"
```
