# Renstra Roadmap Admin CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengubah data Roadmap Renstra RS (2026–2030) yang saat ini berstatus hardcoded python dictionary menjadi model database dinamis (`RenstraRoadmap` & `RenstraFokusItem`), sehingga Super Admin / Tim Mutu dapat menambah, mengedit isu strategis, warna, ikon, dan butir fokus indikator mutu per tahun langsung dari Django Admin.

**Architecture:** 
- Membuat model database `RenstraRoadmap` (tahun, isu strategis, sub-tema, deskripsi, urutan, ikon, warna, aktif) dan model relasi `RenstraFokusItem` (foreign key ke RenstraRoadmap, relasi opsional ke IndikatorMutu, target, satuan, unit kerja).
- Membuat migrasi database Django dan auto-seeder data 2026–2030 awal dari data hardcoded yang ada agar tidak ada downtime/regresi visual.
- Mendaftarkan kedua model ke Django Admin (`akreditasi/admin.py`) dengan `TabularInline` untuk fokus indikator, pencarian, dan visual badge.
- Merefaktor view konsumen utama (`akreditasi/views.py` fungsi `dashboard` dan `akreditasi/indikator_views.py` fungsi `indikator_dashboard`) untuk membaca dari ORM database dengan fallback ke dictionary default jika database kosong.

**Tech Stack:** Django 5.2, PostgreSQL (Supabase) / SQLite, Bootstrap Icons, Django Admin.

**Spec:** Dokumen Renstra RS MonsisKami 2026–2030 & Dashboard Akreditasi ARIMA.

---

## Global Constraints

- Semua migrasi wajib kompatibel dengan SQLite lokal dan Supabase PostgreSQL production.
- Jika tabel kosong atau tahun belum terdaftar di database, kode views wajib memiliki graceful fallback ke hardcoded default agar dashboard tidak melempar HTTP 500.
- Icon pilihan wajib berupa class Bootstrap Icons yang valid (misal `bi-cpu`, `bi-gear-wide-connected`, `bi-hospital`, `bi-tree`, `bi-trophy`).
- Warna pilihan wajib berupa kode HEX (misal `#0d6efd`) atau Bootstrap color preset.
- Endpoint dan filter `?tahun=<YYYY>` di dashboard indikator mutu tetap mempertahankan kontrak URL yang ada.

## Review Focus

1. **Tahun baru ditambahkan di Admin (misal 2031)**: Dashboard utama dan roadmap stepper otomatis merender kartu tahun 2031 secara dinamis tanpa restart/redeploy server.
2. **Tahun dinonaktifkan (`aktif=False`)**: Tahun tersebut tidak muncul di stepper roadmap publik namun tetap tersimpan di admin.
3. **Fokus item ditautkan ke IndikatorMutu**: Link indikator di halaman dashboard indikator mutu otomatis tersinkronisasi dengan kode referensi `IndikatorMutu`.
4. **Fallback bila database tabel baru kosong**: Sistem tidak melempar `OperationalError` atau `KeyError`, melainkan fallback ke data statis 2026–2030.
5. **Performa query ORM**: Query roadmap di dashboard dioptimasi menggunakan `prefetch_related('fokus_items__indikator_mutu')` untuk mencegah N+1 queries.

---

### Task 1: Buat Model `RenstraRoadmap` dan `RenstraFokusItem` di `akreditasi/risiko_models.py`

**Files:**
- Modify: `akreditasi/risiko_models.py`
- Test: `tests/test_renstra_models.py`

**Interfaces:**
- Produces: `RenstraRoadmap` (fields: `tahun`, `isu_strategis`, `sub_tema`, `deskripsi`, `ikon`, `warna_hex`, `aktif`, `urutan`)
- Produces: `RenstraFokusItem` (fields: `roadmap`, `nomor`, `nama_fokus`, `indikator_mutu`, `target_label`, `target_nilai`, `satuan`, `unit_kerja_label`)

- [ ] **Step 1: Tulis unit test untuk model baru**

```python
# tests/test_renstra_models.py
import pytest
from django.test import TestCase
from akreditasi.risiko_models import RenstraRoadmap, RenstraFokusItem

class RenstraModelTest(TestCase):
    def test_create_renstra_roadmap_and_fokus(self):
        roadmap = RenstraRoadmap.objects.create(
            tahun=2031,
            isu_strategis="Smart Hospital AI",
            sub_tema="Integrasi LLM & Telemedisin",
            deskripsi="Transformasi layanan berbasis AI",
            ikon="bi-robot",
            warna_hex="#6610f2",
            aktif=True,
            urutan=6
        )
        fokus = RenstraFokusItem.objects.create(
            roadmap=roadmap,
            nomor=1,
            nama_fokus="Akurasi Diagnosa AI Decision Support",
            target_label="≥ 95%",
            target_nilai=95.0,
            satuan="%",
            unit_kerja_label="Komite Medik"
        )
        self.assertEqual(str(roadmap), "Renstra 2031 — Smart Hospital AI")
        self.assertEqual(roadmap.fokus_items.count(), 1)
        self.assertEqual(str(fokus), "2031 #1: Akurasi Diagnosa AI Decision Support")
```

- [ ] **Step 2: Jalankan test untuk memastikan test gagal (model belum ada)**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py test tests.test_renstra_models`
Expected: `ImportError: cannot import name 'RenstraRoadmap'`

- [ ] **Step 3: Tambahkan definisi model di `akreditasi/risiko_models.py`**

```python
# akreditasi/risiko_models.py
class RenstraRoadmap(models.Model):
    tahun = models.PositiveIntegerField('Tahun Renstra', unique=True, db_index=True)
    isu_strategis = models.CharField('Isu Strategis', max_length=200)
    sub_tema = models.CharField('Sub-Tema / Fokus Utama', max_length=250, blank=True)
    deskripsi = models.TextField('Deskripsi Rencana Strategis', blank=True)
    ikon = models.CharField('Class Bootstrap Icon', max_length=50, default='bi-flag',
                            help_text='Contoh: bi-cpu, bi-gear-wide-connected, bi-hospital, bi-tree, bi-trophy')
    warna_hex = models.CharField('Kode Warna Hex', max_length=20, default='#0d6efd',
                                 help_text='Contoh: #0d6efd, #6f42c1, #198754, #20c997, #fd7e14')
    urutan = models.PositiveSmallIntegerField('Urutan Tampil', default=1)
    aktif = models.BooleanField('Aktif Ditampilkan', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Roadmap Renstra Tahunan'
        verbose_name_plural = 'Roadmap Renstra RS (2026–2030)'
        ordering = ['urutan', 'tahun']

    def __str__(self):
        return f'Renstra {self.tahun} — {self.isu_strategis}'


class RenstraFokusItem(models.Model):
    roadmap = models.ForeignKey(RenstraRoadmap, on_delete=models.CASCADE, related_name='fokus_items')
    nomor = models.PositiveSmallIntegerField('Nomor Urut Fokus', default=1)
    nama_fokus = models.CharField('Nama Indikator / Program Fokus', max_length=255)
    indikator_mutu = models.ForeignKey('IndikatorMutu', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='renstra_fokus',
                                       help_text='Tautkan ke Master Indikator Mutu (opsional)')
    kode_ref = models.CharField('Kode Ref Cadangan', max_length=50, blank=True,
                                help_text='Contoh: IMP-RM-01, INM-08 (jika tidak memilih FK)')
    target_label = models.CharField('Target Label Teks', max_length=100, default='100%')
    target_nilai = models.DecimalField('Nilai Target Numerik', max_digits=8, decimal_places=2, default=100.0)
    satuan = models.CharField('Satuan', max_length=30, default='%')
    unit_kerja_label = models.CharField('Unit Kerja Penanggung Jawab', max_length=150, blank=True)

    class Meta:
        verbose_name = 'Butir Fokus Indikator Renstra'
        verbose_name_plural = 'Butir Fokus Indikator Renstra'
        ordering = ['nomor']

    def __str__(self):
        return f'{self.roadmap.tahun} #{self.nomor}: {self.nama_fokus}'
```

- [ ] **Step 4: Generate migrasi Django `makemigrations akreditasi`**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py makemigrations akreditasi --name="create_renstra_roadmap_models"`
Expected: File `akreditasi/migrations/0028_create_renstra_roadmap_models.py` dibuat.

- [ ] **Step 5: Terapkan migrasi ke SQLite lokal dan Supabase PostgreSQL**

Run:
1. `python manage.py migrate akreditasi`
2. `DATABASE_URL='...' python manage.py migrate akreditasi`
Expected: `Applying akreditasi.0028_create_renstra_roadmap_models... OK`

- [ ] **Step 6: Jalankan test dan verifikasi lulus**

Run: `python manage.py test tests.test_renstra_models`
Expected: `Ran 1 test ... OK`

- [ ] **Step 7: Commit Task 1**

Run:
`git add akreditasi/risiko_models.py akreditasi/migrations/ tests/`
`git commit -m "feat(renstra): buat model RenstraRoadmap dan RenstraFokusItem"`

---

### Task 2: Data Migration / Seeder Otomatis untuk Data 2026–2030

**Files:**
- Create: `akreditasi/management/commands/seed_renstra_db.py`
- Modify: `akreditasi/migrations/0029_populate_renstra_from_dict.py` (Data migration)

**Interfaces:**
- Consumes: `RENSTRA_ANNUAL_FOCUS` dari `akreditasi/indikator_views.py` & `RENSTRA_LABELS` dari `akreditasi/views.py`
- Produces: 5 baris `RenstraRoadmap` (2026–2030) dan 15 baris `RenstraFokusItem` (3 per tahun) di database.

- [ ] **Step 1: Buat script seeder idempotent di `seed_renstra_db.py`**

Isi script: membaca dictionary statis yang sudah ada, meng-insert jika belum ada record, dan mencocokkan `kode_ref` dengan `IndikatorMutu` yang ada di database.

- [ ] **Step 2: Eksekusi seeder di lokal dan production Supabase**

Run: `python manage.py seed_renstra_db`
Expected: `Sukses seed 5 tahun Renstra (2026-2030) dan 15 butir fokus indikator.`

- [ ] **Step 3: Verifikasi query DB**

Run: `python -c "from akreditasi.risiko_models import RenstraRoadmap; print(RenstraRoadmap.objects.count())"`
Expected: Output `5`

- [ ] **Step 4: Commit Task 2**

Run:
`git add akreditasi/management/commands/seed_renstra_db.py akreditasi/migrations/`
`git commit -m "feat(renstra): tambahkan seeder migrasi data Renstra 2026-2030 ke database"`

---

### Task 3: Daftarkan ke Django Admin dengan Custom UI & Inlines

**Files:**
- Modify: `akreditasi/admin.py`

**Interfaces:**
- Produces: Tampilan admin `Roadmap Renstra RS (2026–2030)` di `/admin/akreditasi/renstraroadmap/`
- Fitur Admin:
  - List display: `tahun`, `preview_badge` (render warna + ikon), `isu_strategis`, `sub_tema`, `jumlah_fokus`, `urutan`, `aktif`
  - Inline: `RenstraFokusItemInline` (TabularInline dengan autocomplete atau dropdown `indikator_mutu`)
  - List editable: `urutan`, `aktif`
  - Filter: `aktif`, `tahun`
  - Search fields: `tahun`, `isu_strategis`, `sub_tema`, `deskripsi`

- [ ] **Step 1: Tulis Admin class dengan format HTML color badge preview**

```python
# akreditasi/admin.py
from django.utils.html import format_html
from .risiko_models import RenstraRoadmap, RenstraFokusItem

class RenstraFokusItemInline(admin.TabularInline):
    model = RenstraFokusItem
    extra = 1
    fields = ['nomor', 'nama_fokus', 'indikator_mutu', 'kode_ref', 'target_label', 'satuan', 'unit_kerja_label']
    raw_id_fields = ['indikator_mutu']

@admin.register(RenstraRoadmap)
class RenstraRoadmapAdmin(admin.ModelAdmin):
    list_display = ['tahun', 'preview_badge', 'isu_strategis', 'sub_tema', 'total_fokus', 'urutan', 'aktif']
    list_editable = ['urutan', 'aktif']
    list_filter = ['aktif']
    search_fields = ['tahun', 'isu_strategis', 'sub_tema', 'deskripsi']
    inlines = [RenstraFokusItemInline]

    def preview_badge(self, obj):
        return format_html(
            '<span style="background:{}; color:#fff; padding:3px 8px; border-radius:4px; font-weight:bold;">'
            '<i class="bi {}"></i> {}</span>',
            obj.warna_hex, obj.ikon, obj.tahun
        )
    preview_badge.short_description = 'Preview Visual'

    def total_fokus(self, obj):
        return obj.fokus_items.count()
    total_fokus.short_description = 'Fokus Items'
```

- [ ] **Step 2: Jalankan Django check untuk memverifikasi admin registration**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit Task 3**

Run:
`git add akreditasi/admin.py`
`git commit -m "feat(admin): daftarkan RenstraRoadmap & RenstraFokusItem ke Django admin dengan visual badge"`

---

### Task 4: Refactor Views (`dashboard` & `indikator_dashboard`) untuk Menggunakan ORM Database

**Files:**
- Modify: `akreditasi/views.py` (fungsi `dashboard`)
- Modify: `akreditasi/indikator_views.py` (fungsi `indikator_dashboard` & helper)

**Interfaces:**
- Consumes: `RenstraRoadmap.objects.filter(aktif=True).prefetch_related('fokus_items__indikator_mutu')`
- Output View: Context `renstra_years`, `current_renstra`, `renstra_all`, `tahun_choices` tetap identik secara struktur sehingga template frontend tidak pecah.

- [ ] **Step 1: Refactor `akreditasi/views.py`**
  - Ganti perulangan hardcoded `for yr in range(2026, 2031):` dengan query `RenstraRoadmap.objects.filter(aktif=True)`.
  - Jika tabel belum ada / kosong, fallback ke list default (fail-safe).
  - Hitung capaian per tahun dari `CatatanIndikator` secara dinamis.

- [ ] **Step 2: Refactor `akreditasi/indikator_views.py`**
  - Buat helper function `get_renstra_dict()` yang membaca dari database `RenstraRoadmap` dan menyusun format dict yang kompatibel dengan template.
  - Sediakan fallback ke `RENSTRA_ANNUAL_FOCUS` statis jika query kosong.

- [ ] **Step 3: Verifikasi respons view lokal**

Run:
```bash
python -c "
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
from akreditasi.risiko_models import RenstraRoadmap
for r in RenstraRoadmap.objects.all():
    print(r.tahun, r.isu_strategis, r.fokus_items.count())
"
```
Expected: 5 baris tahun dengan masing-masing 3 fokus item tercetak.

- [ ] **Step 4: Commit Task 4**

Run:
`git add akreditasi/views.py akreditasi/indikator_views.py`
`git commit -m "refactor(views): alihkan roadmap Renstra dan fokus tahunan dari hardcoded dict ke model database"`

---

### Task 5: Testing End-to-End, Verifikasi Admin, dan Deployment

**Files:**
- Verify: Endpoint `/admin/akreditasi/renstraroadmap/`
- Verify: Endpoint `/akreditasi/dashboard/`
- Verify: Endpoint `/akreditasi/indikator/dashboard/?tahun=2026`

- [ ] **Step 1: Jalankan comprehensive test suite**

Run: `python manage.py test akreditasi.tests`

- [ ] **Step 2: Collect static aset admin & dashboard**

Run: `python manage.py collectstatic --no-input`

- [ ] **Step 3: Git push ke GitHub `master`**

Run: `git push origin master`

- [ ] **Step 4: Verifikasi live HTTP di Vercel Production**

Run: `curl -s -I "https://sim-akreditasi-django.vercel.app/akreditasi/dashboard/"`
Expected: `HTTP/2 200` atau `HTTP/2 302`

---

## Plan Self-Review Checklist

1. **Spec Coverage:**
   - [x] Custom/edit/tambah tahun roadmap di admin? Ditangani via `RenstraRoadmap` & `RenstraRoadmapAdmin`.
   - [x] Custom/edit/tambah fokus program/indikator per tahun? Ditangani via `RenstraFokusItem` & Inlines.
   - [x] Kustomisasi visual (warna, ikon, deskripsi)? Kolom `warna_hex`, `ikon`, `sub_tema`, `deskripsi` disediakan.
   - [x] Urutan & aktifasi? Kolom `urutan` dan `aktif` disediakan.
2. **No Placeholders:** Semua nama model, field, method, dan command tertulis eksplisit.
3. **Graceful Fallback:** Terdapat mekanisme fallback ke dictionary awal jika tabel database kosong, sehingga mencegah downtime.
