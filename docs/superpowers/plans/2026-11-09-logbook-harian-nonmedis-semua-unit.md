# Logbook Harian Non-Medis (Semua Unit Kerja) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modul Logbook Harian untuk **semua unit kerja non-medis** (pendaftaran/admisi, rekam medis, keuangan, administrasi, dan unit penunjang lain). Setiap karyawan/pegawai mengisi logbook harian yang terhubung ke Fokus EP akreditasi (autolink ke `StandardItem`), dilengkapi checklist kepatuhan SOP, uraian aktivitas/layanan, identifikasi risiko + mitigasi, dan lampiran bukti berkas. Dilengkapi tabel rekapitulasi (filter unit + periode), status kelengkapan, dan unduh PDF sebagai bukti audit.

**Why a new module (not extending `LogbookHarian`):** The existing `LogbookHarian` (`akreditasi/logbook_models.py`) is hard-wired to **medis/IGD & Ranap**: it rekeys its Section-I figures from `KunjunganPasien` (EMR), carries SBAR serah-terima, nurse-to-patient ratios, and IGD/RANAP-only checklist sections (HPK/KE/SKP). A non-medis logbook has none of those — instead it is **per-pegawai** (not per-unit-per-shift), has **general compliance checklist** (SOP, validasi data, target harian), **activity narrative + risk analysis**, and **EP evidence attachment**. Forcing this into `LogbookHarian` would contaminate a reviewed, tested model with nullable-everywhere fields and two incompatible rekap semantics. A sibling model module keeps the medis logbook intact and the non-medis logbook honest.

**Architecture:** New model module `akreditasi/logbook_nonmedis_models.py` with tables: `LogbookNonMedis` (one entry = one pegawai + one date + one unit), `ChecklistNonMedis` (compliance items per entry, seeded from a per-unit/global template), `BuktiNonMedis` (evidence file). A separate view module `akreditasi/logbook_nonmedis.py` mirrors the `logbook.py` / `mutu_laporan.py` conventions (local RBAC helpers, `AuditLog` on every POST, `_catat`). Fokus EP "autolink" resolves against `StandardItem` (code TKRS/MFK/HPK/etc.) scoped by the entry's unit via `UnitKerja.standar_terkait`, with free-text fallback.

**Tech Stack:** Django 5 (SQLite dev / Postgres prod), reportlab (PDF portrait), Django messages framework, template `{% include %}`.

**Spec:** `docs/qa/analisis-logbook-nonmedis-<date>.md` (analisis docx + pemetaan model + keputusan desain).

## Global Constraints

- Komentar, label, help_text, dan pesan UI **Bahasa Indonesia**; file plan ini **English**.
- JANGAN menambah logika ke `akreditasi/views.py` — gunakan modul `akreditasi/logbook_nonmedis.py`.
- JANGAN menyentuh `akreditasi/logbook_models.py` atau `akreditasi/logbook.py` (modul medis) — modul non-medis berdiri sendiri.
- Ikuti pola `mutu_laporan.py` / `logbook.py`: helper izin lokal, guard `_cek`-persis-dengan-redirect, `AuditLog` DI SETIAP aksi POST.
- Semua DateTime **aware** — `django.utils.timezone.localtime`, `TIME_ZONE='Asia/Jakarta'`, `USE_TZ=True`.
- Migration baru `akreditasi/0058_logbook_nonmedis` (nomor dicek `ls akreditasi/migrations/` sebelum `makemigrations`; angka di plan ini adalah placeholder — angka final tercantum di blok status eksekusi).
- Kredensial/API key jangan pernah masuk ke file.
- Setiap Task: unit test merah → implement → hijau → commit.
- File upload lewat `validate_uploaded_file` + `sanitize_filename` (`akreditasi/file_security.py`) — sama persis dengan `logbook_unggah_bukti`.

## Role & Scope Rules

- **Pelaksana/pegawai** (`STAF_NAKES`, `KEPALA_UNIT`, dan role unit-scoped lain) mengisi logbook **unit kerja mereka** (subtree sendiri).
- **Admin/role lingkup RS** (`SUPER_ADMIN`, `ADMIN_RS`, `KOORDINATOR_POKJA`, `ASESOR`) melihat seluruh rumah sakit; `ASESOR` read-only.
- Unit non-medis vs medis tidak perlu hard-flag: **semua unit aktif** boleh mengisi logbook non-medis, karena checklist-nya generik (SOP/validasi/target) dan berlaku untuk admisi, rekam medis, keuangan, dst. Filter "Unit Kerja" cukup membedakan tampilan.
- "Semua unit kerja, karyawan muncul" → daftar pegawai yang muncul sebagai pelaksana diambil dari `sdm.Pegawai` yang aktif + `PenempatanPegawai` (unit placement), fallback ke `request.user` profile.

## Fokus EP Autolink

- `UnitKerja.standar_terkait` (JSONField) sudah menyimpan pemetaan `{"PKPO": ["PKPO 1", ...]}`; dipakai untuk menyaring kandidat EP.
- EP diambil dari `StandardItem` (code unik per `Category`), framework aktif via `active_framework()`.
- Entry menyimpan `fokus_ep` FK ke `StandardItem` (nullable) + `fokus_ep_teks` free-text (untuk kode EP yang belum ada di katalog).

---

### Task 1: Model + Checklist Template (logbook_nonmedis_models.py)

**Files:**
- Create: `akreditasi/logbook_nonmedis_models.py`
- Create: `akreditasi/migrations/0049_logbook_nonmedis.py` (via `makemigrations`)
- Test: `akreditasi/tests_logbook_nonmedis_models.py`

**Interfaces:**
- Consumes: `UnitKerja`, `StandardItem`, `Category` (`akreditasi.models`), `Pegawai`, `PenempatanPegawai` (`sdm.models`)
- Produces: `LogbookNonMedis`, `ChecklistNonMedis`, `BuktiNonMedis`, `CHECKLIST_UMUM` template, `checklist_template()` helper.

**Model shape:**

```python
class LogbookNonMedis(models.Model):
    unit = FK(UnitKerja, PROTECT, related_name='logbook_nonmedis')
    pegawai = FK('sdm.Pegawai', SET_NULL, null=True, related_name='logbook_nonmedis')
    pelaksana_nama = CharField(150, blank=True)          # fallback manual
    tanggal = DateField()                                  # hari dinas
    shift = CharField(6, choices=SHIFT_CHOICES, blank=True)  # reuse PAGI/SIANG/MALAM
    fokus_ep = FK(StandardItem, SET_NULL, null=True, related_name='logbook_nonmedis')
    fokus_ep_teks = CharField(120, blank=True)             # free-text EP fallback
    uraian_aktivitas = TextField(blank=True)
    risiko_identifikasi = TextField(blank=True)
    risiko_mitigasi = TextField(blank=True)
    target_harian = CharField(250, blank=True)             # ketercapaian target
    status = CharField(12, choices=STATUS_CHOICES, default='DRAF')
    dibuat_oleh = FK(settings.AUTH_USER_MODEL, SET_NULL, null=True)
    disetujui_oleh = FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, related_name=...)
    disetujui_pada = DateTimeField(null=True)
    created_at / updated_at
    Meta: ordering ['-tanggal']; UniqueConstraint(unit, pegawai, tanggal) name='logbook_nonmedis_unik_harian'

class ChecklistNonMedis(models.Model):
    logbook = FK(LogbookNonMedis, CASCADE, related_name='checklist')
    kunci = CharField(40)
    parameter = CharField(250)
    status = CharField(12, choices=TERLAKSANA/TIDAK/NA, default='TERLAKSANA')
    keterangan = TextField(blank=True)
    no_urut = PositiveSmallInteger(default=1)
    Meta: ordering ['no_urut']; UniqueConstraint(logbook, kunci)

class BuktiNonMedis(models.Model):
    logbook = FK(LogbookNonMedis, CASCADE, related_name='bukti')
    judul = CharField(200)
    berkas = FileField(upload_to=_path_bukti_nonmedis)
    ukuran = CharField(20, blank=True)
    diunggah_oleh = FK(AUTH_USER_MODEL, SET_NULL, null=True)
    created_at
```

- `CHECKLIST_UMUM` (template generik, bisa diperluas per unit di Task 4):
  1. `SOP` — Kesesuaian Prosedur Layanan dengan SOP
  2. `VALIDASI` — Validasi Data / Identifikasi Pasien / Pengunjung
  3. `TARGET` — Evaluasi Ketercapaian Target Harian

- `LogbookNonMedis.ensure_checklist()` idempoten (get_or_create per `kunci`).

- [ ] Step 1: Tulis test model gagal (ImportError).
- [ ] Step 2: Jalankan — harus `ModuleNotFoundError`.
- [ ] Step 3: Implement `logbook_nonmedis_models.py`.
- [ ] Step 4: Jalankan test — hijau.
- [ ] Step 5: Commit.

---

### Task 2: Fokus EP Autolink Helper

**Files:**
- Modify: `akreditasi/logbook_nonmedis_models.py` (helper) atau modul service kecil `akreditasi/services_logbook_nonmedis.py`
- Test: `akreditasi/tests_logbook_nonmedis_models.py` (append)

**Interfaces:**
- Produces: `ep_kandidat(unit)` → QuerySet `StandardItem` yang relevan untuk unit (dari `standar_terkait` JSONField + framework aktif), `resolve_fokus_ep(kode)` → StandardItem or None.

- [ ] Step 1: Test merah — unit dengan `standar_terkait={"TKRS": ["TKRS 1"]}` mengembalikan EP TKRS milik framework aktif; unit tanpa pemetaan mengembalikan empty; `resolve_fokus_ep('MFK 1')` menemukan EP, kode tak dikenal → None.
- [ ] Step 2: Implement (parse JSON, filter `Category.code` + `StandardItem.sub_standard`/`code` via `active_framework()`).
- [ ] Step 3: Test hijau.
- [ ] Step 4: Commit.

---

### Task 3: View Daftar + Buat (logbook_nonmedis.py)

**Files:**
- Create: `akreditasi/logbook_nonmedis.py`
- Modify: `akreditasi/urls.py` — tambah path
- Create: `templates/akreditasi/logbook_nonmedis_daftar.html`, `templates/akreditasi/logbook_nonmedis_form.html`
- Test: `akreditasi/tests_logbook_nonmedis_views.py`

**Interfaces:**
- Consumes: Task 1 model; `akses_indikator.unit_scope_ids`, `_profil`-style helper
- Produces: `logbook_nonmedis_daftar`, `logbook_nonmedis_buat`

- [ ] Step 1: Test merah — daftar menampilkan entry unit sendiri; unit lain tidak terlihat (unit-scoped); admin melihat semua; asesor read-only.
- [ ] Step 2: Implement RBAC (reuse pola `_logbook_scoped`, `_unit_pilihan`, `_catat`).
- [ ] Step 3: Test hijau.
- [ ] Step 4: Commit.

---

### Task 4: View Detail + Checklist + Risiko + Bukti

**Files:**
- Modify: `akreditasi/logbook_nonmedis.py`
- Create: `templates/akreditasi/logbook_nonmedis_detail.html`
- Test: `akreditasi/tests_logbook_nonmedis_views.py` (append)

**Interfaces:**
- Produces: `logbook_nonmedis_detail`, `logbook_nonmedis_simpan_checklist`, `logbook_nonmedis_simpan_narasi`, `logbook_nonmedis_unggah_bukti`

- [ ] Step 1: Test merah — detail render 4 seksi (identitas, checklist, uraian+risiko, lampiran); simpan checklist validasi status; unggah bukti validasi ekstensi (tolak `.exe`); narasi+risiko tersimpan.
- [ ] Step 2: Implement (ensure_checklist saat DRAF, validasi upload `validate_uploaded_file`, `_catat`).
- [ ] Step 3: Test hijau.
- [ ] Step 4: Commit.

---

### Task 5: Pengesahan + Kunci (DRAF → DISETUJUI)

**Files:**
- Modify: `akreditasi/logbook_nonmedis.py`
- Test: `akreditasi/tests_logbook_nonmedis_views.py` (append)

- [ ] Step 1: Test merah — `logbook_nonmedis_setujui`: STAF_NAKES 403, KEPALA_UNIT unit lain 403, KEPALA_UNIT unit sendiri ok, `AuditLog` tercipta.
- [ ] Step 2: Implement (guard `boleh_ubah`/`terkunci`, mirip `logbook_setujui`).
- [ ] Step 3: Test hijau.
- [ ] Step 4: Commit.

---

### Task 6: PDF Bukti Audit (reportlab portrait)

**Files:**
- Modify: `akreditasi/logbook_nonmedis.py` — `logbook_nonmedis_pdf`
- Modify: `akreditasi/urls.py`
- Test: `akreditasi/tests_logbook_nonmedis_views.py` (append)

- [ ] Step 1: Test — 200 + `Content-Type: application/pdf`; body memuat unit, tanggal, fokus EP, checklist, uraian, risiko.
- [ ] Step 2: Implement (reportlab portrait, pola `logbook_pdf`).
- [ ] Step 3: Test hijau.
- [ ] Step 4: Commit.

---

### Task 7: Sidebar + Filter Rekapitulasi

**Files:**
- Modify: `templates/includes/sidebar.html` — 1 sub-menu "Logbook Non-Medis"
- Modify: `akreditasi/logbook_nonmedis.py` — filter unit + periode + cari
- Modify: `templates/akreditasi/logbook_nonmedis_daftar.html` (final, tabel rekap)
- Modify: `static/css/...` (atau reuse class tabel existing)

- [ ] Step 1: Filter unit (Semua Unit), filter periode (Bulan Ini/Bulan Lalu/Semua), cari teks; kolom No/Hari-Tanggal/Jam/Fokus EP/Status Checklist & Risiko/Lampiran/Aksi (👁️✏️🗑️📥PDF).
- [ ] Step 2: Smoke test — akses URL daftar → 200, count konsisten.
- [ ] Step 3: Commit + push.

---

## Status Eksekusi (2026-11-09)

### Done (semua task terverifikasi, 24 test hijau)

- **Task 1 — Model + checklist** (`akreditasi/logbook_nonmedis_models.py`): `LogbookNonMedis`, `ChecklistNonMedis`, `BuktiNonMedis`, `CHECKLIST_UMUM` (SOP/Validasi/Target), `ensure_checklist()` idempoten. Migrasi `0058_logbook_nonmedis` + merge `0059` (graph punya cabang leaf paralel dari `0043_alter_insiden...`, di-resolve dengan `makemigrations --merge`). 5 test model.
- **Task 2 — Autolink Fokus EP**: `ep_kandidat(unit)` (parse `standar_terkait` JSONField) + `resolve_fokus_ep(kode)` (framework aktif). 4 test.
- **Task 3 — Daftar & buat**: `logbook_nonmedis_daftar` (filter unit/periode/cari), `logbook_nonmedis_buat`, RBAC unit-scoped (`_unit_pilihan`, `_scoped`, `_cek`). 5 test.
- **Task 4 — Detail + checklist + risiko + bukti**: `logbook_nonmedis_detail`, `_simpan_checklist`, `_simpan_narasi`, `_unggah_bukti` (validasi `validate_uploaded_file` + `sanitize_filename`). 7 test.
- **Task 5 — Pengesahan**: `logbook_nonmedis_setujui` (DRAF→DISETUJUI, kepala unit/admin, `AuditLog`). 4 test (3 setujui + 1 pdf).
- **Task 6 — PDF**: `logbook_nonmedis_pdf` (reportlab portrait, checklist/uraian/risiko/bukti). Verifikasi `Content-Type: application/pdf`.
- **Task 7 — Sidebar**: entry "Logbook Non-Medis" di seksi "Mutu dan kinerja".

**Smoke test** (shell Django, client force_login ADMIN_RS): `/logbook-nonmedis/` → 200, `/logbook-nonmedis/buat/` → 200.

### Not done, needs live environment

- Migrasi `0058` & `0059` sudah diterapkan ke DB dev (`python manage.py migrate akreditasi`), tapi **belum** di environment produksi/deploy. Per konvensi proyek, migrasi tidak auto-jalan di deploy — jalankan `python manage.py migrate akreditasi` di target deploy setelah push.
- Belum `git push` (menunggu instruksi operator).

### Skipped on purpose

- Task "AI narasi" tidak ada di plan ini (modul medis punya Task 10 opsional; modul non-medis tidak membutuhkannya).

### Deviasi dari plan

- Angka migrasi `0049` (placeholder) → final `0058` + merge `0059` karena nomor `0044`–`0057` sudah terpakai dan graph punya cabang leaf paralel.
- `Pegawai` tidak punya `unit_kerja` langsung — penempatan via `PenempatanPegawai`; fixture test memakai `Pegawai.objects.create` tanpa unit. Dropdown pelaksana mengambil `Pegawai` aktif tanpa filter unit (semua karyawan muncul, sesuai judul docx "semua unit kerja, karyawan muncul").
