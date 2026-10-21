# Logbook Harian IGD & Rawat Inap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Logbook harian per shift untuk IGD dan rawat inap — rekap shift dihitung otomatis dari EMR, checklist akreditasi (HPK/KE/SKP), bukti upload, IKP terhubung ke `InsidenKeselamatan`, dan lembar serah terima (SBAR).

**Architecture:** Model baru di `akreditasi/logbook_models.py` dengan 5 tabel (`LogbookHarian`, `LogbookPasien`, `LogbookChecklist`, `LogbookBukti`, `LogbookKejadian`). Modul view `akreditasi/logbook.py` mengikuti pola `mutu_laporan.py` (guard RBAC `_boleh_lapor_unit`-persis, audit via `_catat`). Pasien shift ditarik dari `KunjunganPasien` — buah input form cuma kolom khas shift; angka rekap seksi I selalu dihitung, tidak pernah diinput. Kejadian seksi IV menulis langsung ke `InsidenKeselamatan` yang sudah dipakai `rekap_ikp()` sehingga laporan mutu ikut menghitungnya tanpa perubahan kode.

**Tech Stack:** Django 5 (SQLite dev / Postgres prod), reportlab (di bawah laporan mutu cetak/PDF), Django messages framework, template {% include %}.

**Spec:** `docs/qa/analisis-logbook-harian-igd-ranap-2026-10-21.md` (analisis kedua docx + pemetaan model EMR + keputusan desain).

## Global Constraints

- Komentar, label, help_text, dan pesan UI **Bahasa Indonesia**; file plan ini **English**.
- JANGAN menambah logika di `akreditasi/views.py` — gunakan modul `akreditasi/logbook.py`.
- Mengikuti kaidah pola yang sudah dipakai `mutu_laporan.py`: `ROLE_BOLEH_BUAT`, `ROLE_LINGKUP_RS`, guard `_cek_laporan`-persis-dengan-redirect-Peringatan, `AuditLog` DI SETIAP aksi POST.
- Semua DateTime **aware** — `django.utils.timezone.localtime` dengan `TIME_ZONE='Asia/Jakarta'`, `USE_TZ=True`.
- Migration yang dibuat `akreditasi/0048_logbook_harian_igd_ranap` (nomor dicek `ls akreditasi/migrations/` sebelum `makemigrations`).
- Kredensial/API key jangan pernah masuk ke file; task tidak menyentuh konfigurasi sistem.
- Setiap Task dimulai dengan unit test merah → implement → hijau → commit. Nomor test yang lurus kapan lulus dihitung dari output, bukan dari teks plan ini.
- File upload harus melewati `validate_uploaded_file` + `sanitize_filename` (dari `akreditasi/file_security.py`) + `upload_to_supabase_storage` (`akreditasi/supabase_storage.py`), dan mengikut `upload_bukti_ajax` di views.py:863 masih `size_mb = f"{file_obj.size / (1024 * 1024):.1f} MB"`.

## Review Focus

- **Bed kosong tapi kunjungan sudah terbuka** — pasien datang belum dibagi bed ( пожару antar shift). Tabel baris harus tetap ter-render dengan `bed=NULL` (kolom No. Bed kosong), bukan `None` crash. Diuji di Task 3.
- **Waktu asesmen dokter dalam bentuk `HH.MM`**, bukan `HH:MM` — parse `9.05` harus jadi `09:05` dan menghitung RT ≥ 0, bukan datetime negatif. Diuji di Task 2.
- **Shift Malam 21.00 → 07.00 next-day** — pencarian kunjungan jendela tidak boleh memakai `__date` di `tanggal_masuk` saja. `shift_window()` harus mengembalikan `akhir` tanggal+1. Diuji di Task 1.
- **`fungsional_adl` nilai yang tidak didokumenkan** (bebas text cadangan) — pemetaan Dependency harus toleran: startswith(`'Mandiri'`)→M, startswith(`'Bantuan'`)→P, startswith(`'Ketergantungan'`)→T, pre-default T jika kosong/tak dikenal, dan tampilkan apa ada. Diuji di Task 3.
- **Kejadian harus tercatat di `InsidenKeselamatan`** — jika form menolak validasi (jenis/keparahan wajib), petugas bisa kehilangan data kejadian. Jangan batasi jenis - cukup pakai `JENIS_CHOICES` yang sudah ada. Diuji di Task 5.
- **Kepala IRIN melihat logbook seluruh bangsal anak** — scope harus bekerja ke turunan via `unit_scope_ids()`. Kepala Unit Unit sesuai (BANGSAL-*), pemimpin instalan (IRIN), dan ADMIN_RS berbeda cara pandang. Diuji di Task 6.

---

### Task 1: Model + Konstanta Shift (logbook_models.py)

**Files:**
- Create: `akreditasi/logbook_models.py`
- Create: `akreditasi/migrations/0048_logbook_harian_igd_ranap.py` (via `makemigrations`)
- Test: `akreditasi/tests_logbook_models.py`

**Interfaces:**
- Consumes: `UnitKerja` (`akreditasi.models`), `Ruangan`, `Bed`, `KunjunganPasien`, `Pasien` (`pasien.models`)
- Produces: `LogbookHarian`, `LogbookPasien`, `LogbookChecklist`, `LogbookBukti`, `LogbookKejadian`, `parse_jam(s)` helper, `JENIS_LOGBOOK`, `STATUS.choices`, `CHECKLIST_IGD`, `CHECKLIST_RANAP` (?)

- [ ] **Step 1: Tulis test model gagal**

```python
# akreditasi/tests_logbook_models.py
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from akreditasi.models import UnitKerja
from akreditasi.logbook_models import (
    LogbookHarian, LogbookPasien, LogbookChecklist,
    LogbookBukti, LogbookKejadian, parse_jam,
)
from pasien.models import Pasien, Ruangan, Bed, KunjunganPasien
from django.contrib.auth.models import User


def buat_unit(kode, nama, tipe='RUANGAN'):
    return UnitKerja.objects.create(code=kode, name=nama, level=2, tipe_unit=tipe)


def buat_perawat(username):
    u = User.objects.create_user(username, password='x')
    u.profile.role = 'STAF_NAKES'
    u.profile.unit_kerja = buat_unit(kode=username, nama=f'Unit {username}')
    u.profile.save(update_fields=['unit_kerja'])
    return u


class LogbookHarianModelTest(TestCase):

    def setUp(self):
        self.user = buat_perawat('log_t1')
        self.parent = buat_unit('IRIN_LB', 'IRIN logbook', tipe='INSTALASI')
        self.ruang = buat_unit('R-K1_LB', 'Bangsal Mawar logbook')
        self.ruang.parent = self.parent
        self.ruang.save(update_fields=['parent'])
        self.ruangan = Ruangan.objects.create(
            kode='R-K1_LB2', nama='Bangsal Mawar logbook',
            kelas='1', jenis='RANAP', kapasitas=4)

    def dst...
```

- [ ] **Step 2: Jalankan — harus ImportError** (`manage.py test akreditasi.tests_logbook_models` → *ModuleNotFoundError*).
- [ ] **Step 3: Implementasi `logbook_models.py`**

```python
"""
Entri logbook harian per shift untuk IGD & Rawat Inap (ARIMA).

Model yang ada di ruang lingkup shift (Bergas / Seminikal) lingkup-relative
Untuk menggunakan; memakai unitScopeIds dari akses_indikator untuk filter.
"""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models

from .akreditasi.models import UnitKerja
from pasien.models import Ruangan, Bed, KunjunganPasien  # cross-app FK

JENIS_LOGBOOK = [('IGD', 'Logbook Harian IGD'), ('RANAP', 'Logbook Harian Rawat Inap')]
SHIFTS = [('PAGI', 'Pagi (07:00-14:00)'), ('SIANG', 'Siang (14:00-21:00)'), ('MALAM', 'Malam (21:00-07:00)')]

STATUS_CHOICES = [
    ('DRAF',       'Draf'),
    ('DIISI',      'Sudah Direview Katim'),
    ('DISETUJUI',  'Disetujui Kepala Unit'),
]


class LogbookHarian(models.Model):
    """Satu logbook = satu unit/ruangan + tanggal + shift + jenis."""
    jenis   = models.CharField(max_length=6, choices=JENIS_LOGBOOK)
    unit    = models.ForeignKey(UnitKerja, on_delete=models.PROTECT, related_name='logbook_harian')
    ruangan = models.ForeignKey(Ruangan, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='logbook_harian')
    tanggal     = models.DateField()
    shift       = models.CharField(max_length=6, choices=SHIFTS)
    status      = models.CharField(max_length=12, choices=STATUS_CHOICES, default='DRAF')
    petugas     = models.ForeignKey(User, ...)   # filled at serah_terima
    petugas_nama = models.CharField(max_length=120)  # manual input
    pj_shift_nama = models.CharField(max_length=120)
    jumlah_perawat    = models.PositiveSmallIntegerField('Jumlah Perawat Jaga')
    rasio_perawat_pasien = models.CharField('Rasio (1 : N)', max_length=5)
    deskripsi_pending = models.TextField('Pemeriksaan Penunjang Masih Pending', blank=True)
    pasien_kritis_nama = models.CharField(...)
    pasien_menunggu_kamar = models.PositiveSmallIntegerField()
    ...
    class Meta:
        constraints = [models.UniqueConstraint(
            name='logbook_harian_unik', fields=['unit', 'tanggal', 'shift'])]
```

- [ ] **Step 4: Jalankan test — hijau.**
- [ ] **Step 5: Commit** `git add akreditasi/logbook_models.py akreditasi/migrations/0048* akreditasi/tests_logbook_models.py && git commit -m "feat(logbook): model serial harian per shift"`

---

### Task 2: Helper Windows & Agregasi

**Files:**
- Modify: `akreditasi/logbook_models.py`
- Test: `akreditasi/tests_logbook_models.py` (append)

**Interfaces:**
- Produces: `shift_window(tanggal, shift)` → `(awal_dt, akhir_dt)` timezone-aware Jakarta; `kunjungan_shift(jenis, unit, tanggal, shift)`; `parse_jam(x)` → `time or None` (None kalau kosong/tidak valid); `bor_pct(shift, unit)`.

- [ ] **Step 1: Test merah** — shift MALAM lintas tanggal awal/akhir; RT parse; BOR point-in-time.
- [ ] **Step 2-4: test gagal → implement → test pass.** Cos: cuidados dengan `timezone.make_aware` dan `timezone.localtime`; BOR: filter kunjungan aktif dan estime untuk rasio bed.

```python
def shift_window(tanggal, shift):
    """(awal, akhir) aware Jakarta. Shift MALAM → akhir tanggal+1."""
    awal_t = {'PAGI': time(7, 0), 'SIANG': time(14, 0), 'MALAM': time(21, 0)}[shift]
    awal_dt = timezone.make_aware(datetime.combine(tanggal, awal_t))
    if shift == 'MALAM':
        akhir_dt = timezone.make_aware(datetime.combine(tanggal + timedelta(days=1), time(7, 0)))
    else:
        akhir_dt = awal_t + timedelta(hours=7)
        akhir_dt = timezone.make_aware(datetime.combine(tanggal, akhir_t))
    return awal_dt, akhir_dt
```

- [ ] **Step 5: Commit.**

---

### Task 3: Tarik Pasien Shift (LogbookPasien snapshot)

**Files:**
- Modify: `akreditasi/logbook_models.py` — method `LogbookHarian.tarik_pasien()`
- Test: `akreditasi/tests_logbook_models.py` (append)

- [ ] **Step 1: Test merah** — kunjungan yang masuk/tanda jam di jendela masuk `LogbookPasien`, yang keluar tidak. Pasien **tanpa bed** tetap masuk baris dengan `bed=NULL` (Review Focus item 1). CPPT/`general_consent_doc` terCatat.
- [ ] **Step 2: Implement:**

```python
def tarik_pasien(self):
    awl, akl = shift_window(self.tanggal, self.shift)
    if self.jenis == 'IGD':
        qs = KunjunganPasien.objects.filter(jenis_kunjungan='IGD',
                                            tanggal_masuk__gte=awl,
                                            tanggal_masuk__lt=akl)
    else:  # RANAP — pasien yang masih dirawat di unit ini pada jendela
        qs = KunjunganPasien.objects.filter(jenis_kunjungan='RANAP',
                                            bed__ruangan=self.ruangan)
        qs = qs.filter(Q(tanggal_masuk__lt=akl) &
                       (Q(tanggal_keluar__isnull=True) | Q(tanggal_keluar__gte=awl)))
    ditarik = 0
    for k in qs:
        _, ok = LogbookPasien.objects.get_or_create(
            logbook=self, kunjungan=k, defaults={...})
        ditarik += ok
    return ditarik
```

- [ ] **Step 3: Jalankan test.**
- [ ] **Step 4: Commit.**

---

### Task 4: Checklist + Bukti (HPK / KE / SKP / K3_TLS)

**Files:**
- Modify: `akreditasi/logbook_models.py` — método `ensure_checklist()`
- Test: `akreditasi/tests_logbook_models.py` (append)

- [ ] **Step 1: Test merah** — `CHECKLIST_IGD` punya 8 kunci unik (3 HPK + 2 KE + 3 SKP), `CHECKLIST_RANAP` juga 9 kunci. `ensure_checklist()` membuat 1 row per item, idempoten.
- [ ] **Step 2: Implementasi** dengan konstanta `CHECKLIST_IGD = [('HPK1', 'A. HPK', 1, 'Edukasi Hak & Kewajiban Pasien...', 'TERLAKSANA'), ...]` (`kunci, seksi, no_urut, parameter, default_status`). Setiap row `LogbookChecklist` nullable `segel_no`, `cara_keterangan`.
- [ ] **Step 3: Commit.**

---

### Task 5: Detail View + Template

**Files:**
- Create: `akreditasi/logbook.py` (views)
- Create: `akreditasi/urls_logbook.py` (?)
- Modify: `akreditasi/urls.py` — hanya 2-3 path
- Create: `templates/akreditasi/logbook_detail.html`, `templates/akreditasi/logbook_daftar.html`
- Test: `akreditasi/tests_logbook_views.py`

**Interfaces:**
- Consumes: semua model Task 1-4; `AuditLog` (`mutu_laporan._catat` pola)
- Produces: view `logbook_daftar`, `logbook_detail`, `logbook_serah_terima`, `logbook_setujui`

- [ ] **Step 1: Test merah** — view menampilkan seksi I-IV; logbook unit lain 403; IGD/Nakes atas unit lain tidak boleh menyetujui.
- [ ] **Step 2: Implement**

```python
def _boleh_buat_logbook(user, unit):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = getattr(user, 'profile', None)
    if p is None or p.role not in ('SUPER_ADMIN', 'ADMIN_RS', 'KEPALA_UNIT', 'STAF_NAKES'):
        return False
    if p.is_unit_scoped or (p.role in ('SUPER_ADMIN', 'ADMIN_RS')):
        return True
    return bool(p.unit_kerja and unit.pk in unit_scope_ids(p.unit_kerja))
```

Sekarang view `logbook_detail` tarif pasien otomatis saat pertama diakses (jika status DRAF) + render semua seksi.
- [ ] **Step 3: Template** —火车站镜像 structure terbarukan.
- [ ] **Step 4: Commit.**

---

### Task 6: Workflow Serah Terima & Pengesahan

**Files:**
- Modify: `akreditasi/logbook.py`
- Test: `akreditasi/tests_logbook_views.py` (append)

- [ ] **Step 1: Test merah** — `logbook_serah_terima` DRAF→DIISI mengubah status & menugesha AuditLog; `logbook_setujui` STAF_NAKES 403, KEPALA_UNIT unit bukan-akar → 403 disiplinary per Task 6 spec; asesor 403.
- [ ] **Step 2: Implement views untuk aksi.**
- [ ] **Step 3: Commit.**

---

### Task 7: Rekap shift dihitung dinamis di view detail

**Files:**
- Modify: `akreditasi/logbook.py` — `konteks_rekap(logbook)`
- Test: `akreditasi/tests_logbook_views.py`

- [ ] **Step 1: Test** — 1 pasien merah (kunjungan MERAH), 1 kunjungan (trige), jumlah ranap/rujuk/pulang/DOA dari `status` dan `disposisi_tindak_lanjut`; BOR persif.
- [ ] **Step 2: Implementasi** `konteks_rekap` dan rendering di template seksi I.
- [ ] **Step 3: Commit.**

---

### Task 8: PDF Logbook (reportlab landscape)

**Files:**
- Modify: `akreditasi/logbook.py` — `logbook_pdf`
- Modify: `akreditasi/urls.py` — `logbook/<int:pk>/pdf/`
- Test: `akreditasi/tests_logbook_views.py`

- [ ] **Step 1: Test** — mengikuti pola `test_pdf` pada `tests_mutu_laporan.py` jika sudah ada, else 200 + header `Content-Type: application/pdf` (atau verifikasi via pypdf bila tersedia). Barang semua tabel (IGD dengan triage terisi, RANAP dengan bed kosong).
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit.**

---

### Task 9: Sidebar UI + Template daftar + Style

**Files:**
- Modify: `templates/includes/sidebar.html` — 1 sub-menu
- Modify: `akreditasi/urls.py` — sisa path
- Create: `templates/akreditasi/logbook_daftar.html` (final)
- Modify: `static/css/kontrol.css` (atau `static/css/logbook.css`) untuk tabel

- [ ] **Step 1: View daftar** (filter unit + tanggal + status) + template; sidebar; styling.
- [ ] **Step 2: Test smoke** — akses cepat URL list → 200, count `LogbookHarian` sama.
- [ ] **Step 3: Commit + push.**

---

### Task 10: Bantuan AI narasi logbook (Opsional — hanya jika requested)

> **Skip unless user asks.** Bila diminta, tambahkan `PANDUAN_LOGBOOK_NARASI_BAB` di ai_prompts.py + per-`K ON DETAIL` endpoint punya `ai_views.py` tidak teretapi; **pastikan konten AI tidak disembunyikan data medis pasien rahasia**, hanya tambahkan ringkasan dedupless dan checklist yang sudah diisi.
