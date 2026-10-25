# Verifikasi Implementasi — Staff Intake v2

**Tanggal:** 2026-10-25
**Basis commit:** `f666144` (working tree dengan perubahan yang belum di-commit)
**Settings uji:** `config.control_test_settings`

## Ringkasan gate

| Gate | Perintah | Hasil |
|---|---|---|
| Suite `sdm` | `-m django test sdm` | `Ran 337 tests` — OK |
| Suite `sdm accounts` | `-m django test sdm accounts` | `Ran 368 tests` — OK |
| System check | `manage.py check` | `System check identified no issues (1 silenced)` |
| Migrasi tertunda | `makemigrations --check --dry-run` | `No changes detected` |
| Whitespace | `git diff --check` | bersih |
| Rehearsal migrasi | `migrate` pada database kosong | `0025`–`0030` apply OK |

Baseline sebelum pekerjaan ini: `291` test `sdm`, `20` test focused.

## Migrasi yang dibuat

| Nomor | Nama | Isi |
|---|---|---|
| `0026` | `add_intake_finalization_link` | `DrafInputPegawai.finalized_employee`, `finalization_key` |
| `0027` | `fix_license_validity_label` | `AlterField` label `validity_mode` (`Tanggal Berthi` → `Tanggal Berlaku`) |
| `0028` | `add_intake_attachment_staging` | model `LampiranDrafPegawai`, `ProfilPribadiPegawai.foto_profil_versi` |
| `0029` | `add_profession_master_and_sub_unit` | `Pegawai.profesi_master`, `PenempatanPegawai.unit_induk`, `atasan_langsung` |
| `0030` | `add_invitation_idempotency_and_status` | `UndanganAkunPegawai.idempotency_key`, `intended_is_active` |

`0015` tidak disentuh; label diperbaiki lewat `AlterField` di `0027`.

## Task yang selesai

- **Task 0** — `0025` di-apply lokal, baseline tercatat.
- **Task 1** — perbaikan navigasi wizard, form multipart, `expected_version`, proteksi stale-tab 409.
- **Task 2** — `finalize_staff_intake` tunggal di service, idempotent, memakai `save_assignment`.
- **Task 3** — label `Tanggal Berlaku`.
- **Task 4** — staging lampiran privat, normalisasi foto, binding saat finalisasi, route hapus lampiran, drag/drop aksesibel.
- **Task 5** — STR + banyak SIP, sub-unit, profesi master.
- **Task 6** — step 4 dengan role delegasi dan status akun, invitation post-commit.
- **Task 7** — Digital Staff Profile enam tab + endpoint avatar privat.
- **Task 8** — UI impor Excel bertahap (unggah → pratinjau → terapkan → hasil).
- **Task 9** — aktivasi akun via tautan sekali pakai.
- **Task 10** — gate penuh dan rehearsal migrasi (dokumen ini).

## Deviasi dari plan (beserta alasan)

1. **`include_descendants=True` pada fixture** `test_intake.py` dan `test_directory_enhancement`.
   Scope HC memakai unit nyata; tanpa ini penempatan ke sub-unit ditolak meski operator berhak. Fixture yang salah, bukan kode.

2. **Guard `sip_formset.is_bound`.**
   Plan menulis `if not sip_formset.is_valid()`, yang selalu gagal untuk POST tanpa management fields dan memblokir step 3 yang sah.

3. **Fixture `test_intake_uploads.py` diberi `unit_kerja` pada step 2.**
   Hardening scope staging memerlukan unit target dari draft.

4. **Tiga test route hapus lampiran ditambahkan.**
   Plan menjanjikannya dalam bentuk prosa, bukan kode.

5. **Validasi form impor memakai signature ZIP, bukan ekstensi.**
   Test client memberi nama field sebagai nama file; ekstensi adalah proksi yang salah. Cek sebenarnya ada di `preview_staff_import` (ZIP + batas ekspansi).

6. **Helper test route impor memakai `[-1]`, bukan `[-2]`.**
   Bug di helper test plan: URL berakhir dengan `/` sehingga segmen terakhir adalah UUID.

7. **Template aktivasi standalone, tidak `extends base.html`.**
   `base.html` mengasumsikan user terautentikasi dan melempar `AnonymousUser` untuk pengunjung tautan aktivasi.

8. **`_primary_unit(employee)` di service undangan.**
   `Pegawai` tidak punya `unit_kerja`; unit berasal dari penempatan aktif.

9. **`test_staff_invitation` memakai `captureOnCommitCallbacks`.**
   Pengiriman email sekarang post-commit sesuai plan; test lama mengasumsikan pengiriman sinkron.

## Yang belum dikerjakan

- **Rehearsal PostgreSQL.** Plan meminta rehearsal pada PostgreSQL karena SQLite tidak membuktikan `select_for_update` dan constraint. Database PostgreSQL lokal tidak tersedia pada sesi ini, jadi rehearsal dijalankan pada SQLite baru (membuktikan grafik migrasi apply bersih, bukan perilaku locking). Jalankan sebelum deploy:
  ```
  createdb arima_hc_rehearsal
  DATABASE_URL=postgres://localhost/arima_hc_rehearsal .venv/Scripts/python.exe manage.py migrate
  DATABASE_URL=postgres://localhost/arima_hc_rehearsal .venv/Scripts/python.exe manage.py showmigrations sdm | tail -8
  dropdb arima_hc_rehearsal
  ```
- **Verifikasi browser.** Drag/drop, unggah nyata, dan tampilan enam tab belum diuji di browser sungguhan.
- **`PUBLIC_BASE_URL` produksi.** Wajib diisi sebelum undangan dikirim; tanpa itu `_send_invitation_email` melempar `ImproperlyConfigured` dan invitation berstatus `FAILED`.
- **Commit, push, deployment.** Tidak dilakukan; menunggu instruksi terpisah.
