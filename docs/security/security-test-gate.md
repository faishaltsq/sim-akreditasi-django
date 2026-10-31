# Security Test Gate — SIM Akreditasi RS / ARIMA

## Apa Itu Gate Ini

`.github/workflows/security-tests.yml` menjalankan suite pengujian keamanan otorisasi
pada setiap `push` ke `main` dan setiap `pull_request`. Workflow ini memakai
`python manage.py test` (Django TestCase), **bukan** pytest — tidak ada `pytest.ini`,
`pyproject.toml`, atau `setup.cfg` di repo ini, dan `pytest` tidak ada di
`requirements.txt`.

Lingkungan uji: SQLite (`config/settings.py` jatuh ke `db.sqlite3` saat `DATABASE_URL`
tidak di-set) dan `DEBUG=True` (default non-produksi). `DJANGO_DEBUG` **sengaja tidak**
di-set pada langkah test: dengan `DEBUG=False`, `config/settings.py` menyalakan
`SECURE_SSL_REDIRECT`, yang akan 301-mengalihkan setiap request HTTP biasa dari test
client dan mematahkan assertion 200/403. Test yang memang butuh `DEBUG=False` memakai
`@override_settings` secara lokal.

Tidak ada langkah seed. Perintah `seed_all_roles`, `seed_unit_hierarchy`,
`seed_hospital_type_b`, dan `seed_fase4_extended` **tidak ada** di repo ini; setiap
`TestCase` menyiapkan datanya sendiri di `setUp()`.

## Kontrak "Hijau Berarti Sudah Diperbaiki"

Suite ini **hijau**: seluruh 155 tes lulus (0 gagal, 0 error). Setiap assertion
kegagalan tetap berupa `self.fail()` dengan pesan berbahasa Indonesia yang
mendokumentasikan kerentanan; assertion itu kini tidak pernah tercapai karena
kerentanannya sudah diperbaiki di kode produksi.

**Jangan** menambahkan `continue-on-error` atau `|| true`, dan jangan melemahkan
assertion. Jalur hijau HARUS berarti kerentanan sudah diperbaiki, bukan berarti tesnya
dilewati. Bila kelak sebuah regresi muncul, tes terkait akan kembali merah dengan
sendirinya — tidak ada yang perlu diubah di workflow.

## Modul dan Cakupan

| Modul | Cakupan |
|-------|---------|
| `accounts.tests_priv_escalation` | Eskalasi hak akses vertikal: `user_create`/`user_edit`/`user_delete`, tulis `custom_permissions`, penyalahgunaan matriks izin peran. |
| `akreditasi.tests_admin_gate` | Batas `admin_required` (`_is_admin` = SUPER_ADMIN/ADMIN_RS), kontrol negatif KEPALA_UNIT/ASESOR, dan gate yang mengabaikan `RolePermissionConfig`. |
| `pasien.tests_object_authz` | IDOR data pasien lintas unit (`pasien_detail`, `kunjungan_detail`, `pasien_daftar`) dan kebocoran PII lewat API (`api_cari_pasien`, `api_cek_nik`). |
| `akreditasi.tests_session_security` | Session fixation, lockout akun `is_active=False`, flag cookie (Secure/HttpOnly/SameSite), penegakan CSRF. |
| `accounts.tests_security_owasp` | OWASP A01/A07 untuk akun: eskalasi peran SUPER_ADMIN, penulisan `custom_permissions`, flag cookie. |
| `akreditasi.tests_security_owasp` | OWASP A01 untuk unit kerja: gate `admin_required` vs STAF_NAKES/KEPALA_UNIT/ASESOR, `audit_log_view`. |
| `pasien.tests_security_owasp` | OWASP A01 untuk pasien: IDOR, kebocoran PII API, cakupan dekorator `require_patient_module`. |
| `sdm.tests.security_owasp` | OWASP A07 pada alur rekrutmen: entropi token `Pelamar`/`KonfirmasiOffering`, akses token offering. |
| `akreditasi.tests_security` | Header keamanan (CSP, Referrer-Policy, Permissions-Policy, X-Content-Type-Options), rate limiter, host-header injection, brute-force login. |
| `accounts.tests_unit_rbac` | Cakupan modul pasien per peran/unit/profesi (`get_allowed_patient_modules()`). |
| `sdm.tests.test_akses` | Kapabilitas Human Capital (`HcGrant`, `require_hc_capability`, scoping unit + descendant, masa berlaku). |
| `sdm.tests.test_private_documents` | Otorisasi unduhan dokumen privat (signed URL, sensitivitas kesehatan). |

## Menjalankan Lokal

```bash
cd "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django"
.venv/Scripts/python.exe manage.py test \
  accounts.tests_security_owasp \
  akreditasi.tests_security_owasp \
  pasien.tests_security_owasp \
  sdm.tests.security_owasp \
  akreditasi.tests_session_security \
  accounts.tests_priv_escalation \
  akreditasi.tests_admin_gate \
  pasien.tests_object_authz \
  akreditasi.tests_security \
  config.tests_allowed_hosts \
  accounts.tests_unit_rbac \
  sdm.tests.test_akses \
  sdm.tests.test_private_documents
```

Hasil terverifikasi saat ini: **155 tes dijalankan, 0 gagal, 0 error (100% PASS)** —
seluruh temuan P0 telah diperbaiki. Perintah di atas memuat 13 modul; suite penuh
(workflow) menjalankan himpunan yang sama. Catatan: angka **151** pada revisi dokumen
sebelumnya sudah usang — ia belum menghitung 4 tes `config.tests_allowed_hosts`.

Untuk melihat nama tiap tes beserta PASS/FAIL, tambahkan `--verbosity 2`. Untuk
menjalankan satu modul saja, misalnya `manage.py test pasien.tests_object_authz`.

## Artefak CI

Workflow menulis log lengkap ke `/tmp/security-tests.log` (`tee`) dan mengunggahnya
sebagai artefak `security-test-log` dengan `if: always()`, sehingga kegagalan tetap
terbaca dari halaman PR meskipun job merah. Tidak ada `--junitxml`: itu flag pytest,
bukan flag Django. `--verbosity 2` plus artefak log adalah jawaban yang jujur di sini.

## Pelacak Remediasi — Temuan P0

Rencana perbaikan terverifikasi: `docs/security/remediation-plan.md`.
Seluruh status P0-1 s.d. P0-16 saat ini **SELESAI** — kerentanan sudah diperbaiki di
kode produksi dan tes regresinya lulus. Kolom Status memakai **SELESAI**.

| ID | Temuan | Berkas Terkait | Status |
|----|--------|----------------|--------|
| P0-1 | ADMIN_RS dapat membuat akun SUPER_ADMIN via `accounts:user_create` | `accounts/views.py` | SELESAI |
| P0-2 | ADMIN_RS dapat menaikkan akun menjadi SUPER_ADMIN via `accounts:user_edit` | `accounts/views.py` | SELESAI |
| P0-3 | ADMIN_RS dapat menghapus akun SUPER_ADMIN **dan akun sesama ADMIN_RS** via `accounts:user_delete` (guard hanya menolak hapus-diri) | `accounts/views.py` | SELESAI |
| P0-4 | `custom_permissions` dapat ditulis untuk user mana pun, termasuk diri sendiri | `accounts/views.py` | SELESAI |
| P0-5 | `custom_permissions` menerima kunci izin tidak dikenal tanpa validasi | `accounts/views.py` | SELESAI |
| P0-6 | `LOCKOUT_SAFE_PERMS` dapat diubah untuk role selain SUPER_ADMIN | `accounts/views.py` | SELESAI |
| P0-7 | `can_access_control_center` dapat diberikan ke seluruh role STAF_NAKES | `accounts/views.py` | SELESAI |
| P0-8 | `admin_required` berbasis string role, mengabaikan `RolePermissionConfig` | `akreditasi/views.py` | SELESAI |
| P0-9 | Pengguna terautentikasi tanpa wewenang dialihkan ke login, bukan 403 | `akreditasi/views.py` | SELESAI |
| P0-10 | IDOR data pasien: `pasien_detail` / `kunjungan_detail` lintas unit | `pasien/views.py` | SELESAI |
| P0-11 | Enumerasi pasien: `pasien_daftar` memakai `Pasien.objects.all()` (`pasien/views.py:216`) tanpa penyaringan unit, sehingga menampilkan seluruh rumah sakit | `pasien/views.py` | SELESAI |
| P0-12 | Kebocoran PII via `pasien:api_cari_pasien` (NIK, alamat, no_hp, no_bpjs) | `pasien/views.py` | SELESAI |
| P0-13 | Kebocoran PII via `pasien:api_cek_nik` (enumerasi NIK) | `pasien/views.py` | SELESAI |
| P0-14 | `require_patient_module()` ada tetapi tidak dipasang pada view baca inti: `pasien_daftar` dan `dashboard` (modul yang benar `'pendaftaran'`, **bukan** `'master_pasien'` — `master_pasien` ada di himpunan dasar setiap profil sehingga tidak akan menolak apoteker yang diuji) | `pasien/views.py`, `pasien/decorators.py` | SELESAI |
| P0-15 | Token rekrutmen memakai `uuid.uuid4`, bukan `secrets.token_urlsafe(32)` (`Pelamar.token`, `KonfirmasiOffering.token`) | `sdm/models/rekrutmen.py` | SELESAI |
| P0-16 | `SESSION_COOKIE_SAMESITE` / `CSRF_COOKIE_SAMESITE` tidak di-set eksplisit di `settings.py`. **GAGAL pada** `akreditasi/tests_session_security.py:133` (`CookieFlagTest.test_samesite_is_explicitly_strict`), yang menuntut nilai literal `'Strict'`. Perbaikan: set `'Strict'` (bukan `'Lax'`) **di luar** blok `if not DEBUG:` — CI berjalan dengan `DEBUG=True`, sehingga nilai di dalam blok itu tidak akan terlihat oleh test. Catatan: `accounts/tests_security_owasp.py:210` juga menguji SameSite tetapi hanya menuntut `∈ {'Lax','Strict'}` dan saat ini LULUS; jangan jadikan acuan. | `config/settings.py` | SELESAI |

## Fixture Bersama

`akreditasi/tests_utils.py` menyimpan helper yang dipakai lintas suite:

- `make_user(username, role, *, unit=None, profesi='', password=..., **profile_kwargs)`
- `login(client, user, password=...)`
- `make_unit(code, name, *, level=3, parent=None, **kwargs)`
- `make_pasien(no_rm, nama, *, nik='', **kwargs)`
- `make_kunjungan(pasien, no_kunjungan, *, jenis='RANAP', **kwargs)`
- `reset_rate_limit(scope='ai')`

Test keamanan baru **harus** mengimpor dari sini alih-alih mendeklarasikan ulang
fixture. `reset_rate_limit()` penting karena rate limiter menghitung per user id dan
`TestCase` memakai ulang primary key antar test dalam satu proses, sehingga state
limiter menumpuk dan membuat test berikutnya menerima 429 alih-alih respons yang
diassert.

---
*Dokumen ini dihasilkan oleh alat analisis statis; verifikasi manual terhadap baris kode sumber diperlukan.*
