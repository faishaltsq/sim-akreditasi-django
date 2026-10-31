# OWASP Top 10 Security Test Plan — SIM Akreditasi RS / ARIMA

## Ringkasan Proyek

Django 6.1.2, session-cookie auth saja (tanpa DRF/JWT/OAuth), tidak ada MFA, tidak ada reset password flow. RBAC dengan 6 peran; resolusi izin di `UserProfile.has_permission()`.

Kontribusi: `sdm.akses.require_hc_capability` + `HcGrant` (user, kapabilitas, unit_kerja, include_descendants, valid_from/until) — subsistem yang paling ketat.

**Lingkup Baru**: `pasien/` views yang terekspos (IDOR + mass PII), RBAC `STAF_NAKES` yang terlalu lebar, eskalasi izin `user_create/user_edit`, header CSRF yang hilang di API JSON, hadiah cookie SameSite hilang, server error stack trace terbuka di JSON, token aktivasi yang lemah, tidak ada rate limit di login/AI.

**Status Semua**: **VERIFIED** (membaca kode sumber asli untuk masing-masing.)

---

## A. Lightweight Threat Model for THIS system

### Aset (Data Sensitif & Funcional)

- **Pasien PII**: NIK, nama lengkap, alamat, nomor BPJS, nomor telepon, data diagnosa, billing, resep obat.
- **Dokumen Kredensial Nakes**: STR/SIP, sertifikat pelatihan, hasil MCU, foto, metadata scan.
- **Audit & Konfigurasi**: matriks izin peran, unit kerja hierarchy, konfigurasi sistem (ambang batas KPS, tema, survey freeze), log akses.
- **Bagian AI/DeepSeek**: token API mentah, template prompt, jawaban model.

### Aktor

- **Internet anonim**: Rekrutmen publik (token), brute force login, probing IDOR.
- **User terautentikasi low-priv**: Staf Nakes unit-scoped (dapat akses limited pasien & nakes).
- **Unit-scoped KEPALA_UNIT**: Hanya unitnya sendiri. `STAF_NAKES` **tidak** naik hierarki ke `audit_log_view`/`unit_list_create` — keduanya dijaga `admin_required` yang menolaknya (lihat `akreditasi/views.py:63-70`).
- **ADMIN_RS / KOORDINATOR_POKJA**: Dapat manage unit & users tetapi dibatasi oleh `can_manage_units` dan `can_manage_users`.
- **SUPER_ADMIN**: Pengembang/IT RS, privilege penuh di seluruh sistem.
- **Kandidat rekrutmen**: Token-based, tanpa akun, dapat upload dokumen, lihat lamaran sendiri, akses ujian & offering letter.
- **Insider (malicious staff)**: Akses ke PII pasien, kredensial nakes, dapat memodifikasi matriks izin.

### Batasan Kepercayaan

- **Boundary Publik**: Rekrutmen portal (tanpa login) — token sebagai capability, penyimpanan file ke Supabase (private bucket).
- **Boundary Sesi-Cookie**: Session login cookie saja; tanpa JWT/refresh token.
- **Boundary Scope Unit**: `UserProfile.get_allowed_patient_modules()` gates modulo ‘master_pasien’, ‘pendaftaran’, ‘igd’, ‘rajal’, ‘ranap’, ‘farmasi’, ‘laboratorium’, ‘riwayat’.
- **Boundary Capability HC**: `HcGrant` + `require_hc_capability` enforce kapabilitas per unit, termasuk descendant inclusion opsional.
- **Boundary Control Center**: `/accounts/kontrol/` end points require `can_access_control_center` + role ikut bermain.

### Inventarisasi Permukaan Attack

| App / View | File:Line | Mengapa Rentan | Kekuatan Eksploitasi |
|------------|----------|------------------|--------------------|
| `pasien/pasien_detail/<pk>` | pasien/views.py:223 | `get_object_or_404(Pasien, pk=pk)` tanpa filter unit | IDOR → siapapun yang login dapat membaca PII pasien di seluruh RS |
| `pasien/kunjungan_detail/<pk>` | pasien/views.py:276 | Sama, tanpa pemeriksaan `KunjunganPasien.unit_kerja` | Akses data klinis lintas unit (billing, CPPT, resep) |
| `pasien/api_cari_pasien` | pasien/views.py:803 | `Pasien.objects.all()` with global search | Enumeration NIK/alamat/no_hp + data PII mentah |
| `pasien/api_cek_nik` | pasien/views.py:840 | `Pasien.objects.filter(nik=nik)` tanpa unit | Pencarian NIK anonim (hanya login) → kebocoran PII |
| `pasien/resume_pdf/<kunjungan_pk>` | pasien/views.py:522 | Tidak ada `require_patient_module` | Download resume medis pasien dari luar unit |
| `pasien/resep_buat/<kunjungan_pk>` | pasien/views.py:537 | `_can_modify_ep`? Tidak ada (hanya `login_required`) | Membuat resep dari luar unit scope |
| `akreditasi/unit_list_create` | akreditasi/views.py:1357 | `@admin_required`; `_is_admin` (views.py:63-70) = `is_superuser or role in ('SUPER_ADMIN','ADMIN_RS')` — STAF_NAKES **tidak** termasuk | **TIDAK rentan ke STAF_NAKES.** Yang benar-benar bocor: `admin_required` hanya berbasis string peran, tidak pernah membaca `RolePermissionConfig` atau `UserProfile.custom_permissions`, sehingga mencabut `can_manage_units` di Pusat Kontrol tidak menutup unit_edit/unit_delete |
| `akreditasi/profil_rs_view` | akreditasi/views.py:1534 | `@admin_required` | Sama: role-string based, bukan permission-based |
| `akreditasi/audit_log_view` | akreditasi/views.py:1578 | `@admin_required` | Akses log audit penuh untuk ADMIN_RS; STAF_NAKES ditolak 403 |
| `accounts/user_create` | accounts/views.py:100 | `@user_passes_test(admin_only)`; `admin_only` = `is_superuser or can_manage_users` | ADMIN_RS (`can_manage_users`) dapat membuat SUPER_ADMIN (self-escalation) |
| `accounts/user_edit` | accounts/views.py:153 | `@user_passes_test(admin_only)` | ADMIN_RS dapat mengubah profil SUPER_ADMIN → eskalasi / demosi |
| `accounts/update_user_custom_permissions` | accounts/views.py:455 | `@user_passes_test(control_center_access)` | Siapa pun dengan control center (termasuk KOORDINATOR_POKJA) dapat menulis custom JSON untuk *user_id mana pun*, termasuk dirinya sendiri |
| `accounts/update_role_permissions` | accounts/views.py:410 | `@user_passes_test(control_center_access)` | Non-superuser control center holder dapat memodifikasi matriks peran kecuali `LOCKOUT_SAFE_PERMS` untuk SUPER_ADMIN |
| `accounts/staff_activation_views.activate` | accounts/staff_activation_views.py:33 | Token SHA256 digest hanya, tanpa randomness atau expiry validation? | Token aktivasi reuse / brute force (tetapi expiry 72 jam) |
| `sdm/rekrutmen_portal_views.portal_offering/<token>` | sdm/rekrutmen_portal_views.py:195 | `KonfirmasiOffering.objects.get(token=token)` + tidak ada `require_hc_capability` untuk download | Siapa pun dengan token dapat mengunduh surat penawaran (meskipun token adalah UUID acak) |
| `akreditasi/views.quick_score/<record_id>` | akreditasi/views.py:795 | `@editor_required` (hanya `p.can_edit`) | `can_edit_pdca` boolean dari role/permission; `STAF_NAKES` tidak punya; tetapi `admin_required` *bukan* cek `can_edit` |
| `akreditasi/views.inline_edit_pdca/<record_id>` | akreditasi/views.py:839 | Sama dengan `quick_score` |

**Catatan**: Sudah diamankan setelah membaca kode sumber asli:
- `akreditasi/views.verify_kredensial` (K-2) memiliki IDOR guard untuk KEPALA_UNIT.
- `akreditasi/views.quick_score` dan `inline_edit_pdca` terlindungi oleh `_can_modify_ep` (termasuk unit-scoped pokja + sub_standard).
- `akreditasi/unit_list_create`/`unit_edit`/`unit_delete`/`pokja_manage`/`audit_log_view`/`profil_rs_view` menolak STAF_NAKES dan ASESOR (`_is_admin` = SUPER_ADMIN/ADMIN_RS saja). Karena `admin_required` memakai `user_passes_test`, penolakannya berupa pengalihan ke login (HTTP 302), bukan 403 — termasuk untuk pengguna yang sudah terautentikasi.
- Login brute-force sudah dibatasi 8/60s oleh `RateLimitedLoginView` + `rate_limit(scope='login')`, dibuktikan `akreditasi/tests_security.py::LoginBruteForceProtectionTest`.
- Akun `is_active=False` **memang** terkunci: `ModelBackend.user_can_authenticate()` menolaknya saat login, dan `auth.get_user()` → `ModelBackend.get_user()` mengembalikan `None` pada setiap request, sehingga sesi lama pun mati.

**Rentan (terverifikasi):**
- Token rekrutmen (`Pelamar.token`, `KonfirmasiOffering.token`) memakai `default=uuid.uuid4` — 122 bit acak versi-4, bukan `secrets.token_urlsafe(32)` seperti alur aktivasi staf (`sdm/services/undangan.py:44`).

---

## B. OWASP Top 10 (2021) Mapping for THIS system

| OWASP A01 | A02 | A03 | A04 | A05 | A06 | A07 | A08 | A09 | A10 |
|-----------|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| **Broken Access Control** | **Cryptographic Failures** | **Injection** | **Insecure Design** | **Security Misconfiguration** | **Vulnerable & Outdated Components** | **Identification & Authentication Failures** | **Software Supply Chain** | **Security Logging & Monitoring Failures** | **Server-Side Request Forgery** |
| **IDOR** di pasien_detail / kunjungan_detail / api_cari_pasien / api_cek_nik (A01) |
| **Session fixation** / is_active=False lockout / SameSite hilang (A07) |
| **Rate limiting** hilang di login & endpoint AI (A07) |
| **CSRF protection hilang** di POST JSON views (A08) |
| **Error stack traces** di JsonResponse (A03) |
| **File upload MIME / ekstensi** tidak divalidasi (A03) |
| **Token aktivasi lemah** (uuid4, tidak ada secrets) (A07) |
| **Password reset flow hilang** (A07) |
| **Weak password policy** (default Django, tidak ada validasi tambahan) (A07) |
| **Depedensi URL admin default `/admin/`** (A05) |

**Test Cases Baru** (untuk skema OWASP ini):
1. **A01**: Unit-scoped patient read (pasien_detail, kunjungan_detail, api_cari_pasien) → 403 untuk unit lain.
2. **A02**: Pengamanan cookie (Secure, HttpOnly, SameSite) + pemeriksaan is_active di activation flow.
3. **A03**: Validasi ekstensi/MIME upload file + limit ukuran.
4. **A04**: Desain (role hierarchy, policy survey freeze) — validate `_is_admin` / `_is_manager_role` tidak termasuk STAF_NAKES.
5. **A05**: Headers keamanan (CSP, HSTS, X-Frame-Options, X-Content-Type-Options) — sudah diuji.
6. **A06**: Komponen ketinggalan jaman — CVE patching (dependency-audit.md).
7. **A07**: Rate limiting login + endpoint AI (DeepSeek).
8. **A08**: CSRF token di endpoint JSON (require POST + CsrfViewMiddleware). Gunakan `require_POST` + `csrf_exempt` hanya di tempat yang benar.
9. **A09**: Pencatatan audit untuk perubahan izin, rekrutmen token usage, download private dokumen HC (sudah ada di AuditLog).
10. **A10**: SSRF tidak relevan (tidak ada permintaan URL user-controlled).

**Existing tests already cover**:
- SecurityHeadersTest (CSP, Referrer, Permissions, X-Content-Type-Options)
- RateLimiterTest (login + last-hop XFF).
- AllowedHostsTest (host-header injection).
- LoginBruteForceProtectionTest (login brute force).
- Unit-scoped RBAC di pasien/tests_object_authz.py, akreditasi/tests_admin_gate.py, dsb.
- Unit-scoped RBAC rekrutmen portal (test_token_palsu_tidak_membocorkan_lamaran, test_token_hanya_melihat_lamaran_sendiri).
- Staff activation token tests di accounts/tests_staff_activation.py.
- HC access tests di sdm/tests/test_akses.py, sdm/tests/test_private_documents.py.

---

## C. Concrete test file layout

**Alasan penempatan**:
- `accounts/` → PrivEsc, HC RBAC, activation, user permissions.
- `akreditasi/` → EP (QualityRecord), unit CRUD, katalog, risiko, insiden, logbook, portal AI.
- `pasien/` → Manajemen pasien, billing, resep, integrasi BPJS/SatuSehat.
- `sdm/` → Human Capital (rekrutmen, orientasi,/mc_u, offering, dokumen pribadi).
- `config/` → Pengujian allowed hosts, QA harness, CI runner.

**File names & TestCase classes**:

### 1. `accounts/tests_security_owasp.py` (BARU)
- `class SuperAdminRoleEscalationTest` — ADMIN_RS POST ke `accounts:user_create`/`user_edit` dengan `role='SUPER_ADMIN'`; GAGAL bila `is_superuser=True`.
- `class ControlCenterPermissionTamperTest` — `update_user_custom_permissions` menulis `{'can_manage_users': True}` ke akun low-priv dan ke dirinya sendiri; GAGAL bila tersimpan.
- `class CookieSecurityTest` — `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SECURE` (DEBUG off), nilai `SESSION_COOKIE_SAMESITE`, dan lockout `is_active=False` (LULUS).

### 2. `akreditasi/tests_security_owasp.py` (BARU)
- `class UnitEditAdminGateTest` — STAF_NAKES/KEPALA_UNIT/ASESOR ditolak pada unit_list/unit_edit/unit_delete/pokja_manage/audit_log; ADMIN_RS 200 (LULUS, memaku batas).
- `class AdminGateIgnoresPermissionConfigTest` — `can_manage_units=False` untuk ADMIN_RS di `RolePermissionConfig`, `unit_edit` tetap tembus (GAGAL, mendokumentasikan gate berbasis string peran).
- `class AuditLogAdminOnlyTest` — `audit_log_view` 200 untuk ADMIN_RS, ditolak untuk STAF_NAKES (LULUS).

### 3. `pasien/tests_security_owasp.py` (BARU)
- `class PatientPiiIdorTest` — dua unit, dua pasien; STAF_NAKES unit A GET `pasien_detail`/`kunjungan_detail` milik unit B; GAGAL bila 200.
- `class PatientSearchApiLeakageTest` — `api_cari_pasien`/`api_cek_nik` mengembalikan NIK/no_rm/alamat/no_hp/no_bpjs lintas scope; GAGAL bila bocor.
- `class PatientModuleDecoratorCoverageTest` — satu view ber-guard (403 untuk modul di luar `get_allowed_patient_modules()`) dan satu view tanpa guard (GAGAL bila lintas unit dapat diakses).

### 4. `sdm/tests/security_owasp.py` (BARU)
- `class RecruitmentTokenStrengthTest` — `Pelamar.token`/`KonfirmasiOffering.token` default; GAGAL bila `uuid.uuid4` (bandingkan `secrets.token_urlsafe(32)` di `sdm/services/undangan.py`).
- `class OfferingAccessTest` — token offering hanya memetakan ke satu `KonfirmasiOffering`; pemegang token lain tidak dapat membaca/mengunduh offering orang lain.

### 5. `config/tests_allowed_hosts.py` (EXISTING) → already covers A05.

**Proyek mengikuti konvensi `tests_*.py`**; file baru diberi awalan `tests_security_owasp.py` untuk membedakannya dari suite keamanan yang sudah ada (`tests_security.py`, `tests_unit_rbac.py`).

---

## D. Fixture strategy

**Shared test helper** di `akreditasi/tests_utils.py`:
- `reset_rate_limit(scope)` — membersihkan cache rate limiter.
- `_make_user` dengan role/unit/profil yang sesuai.
- `_login` helper.

**Implementasi:**
- Gunakan `_make_user` di setiap file test baru; perpanjang `UserProfileForm` & `UserCreateForm` dengan data unit & role yang tepat.
- Unit hierarchy: buat root `UnitKerja` (`Direktorat Layanan`), child `Unit Klinis`, descendant lain (IGD, RAJAL, RANAP, FARMASI, LAB).
- Staf Nakes per unit dengan `profesi` (`PERAWAT`, `APOTEKER`, `ANALIS_LAB`).
- Pasien & kunjungan: gunakan `_make_pasien` / `_make_kunjungan` dari `pasien/tests_object_authz.py` (diimpor).
- Rekrutmen token: buat `Pelamar`/`KonfirmasiOffering` lewat model default (token diisi `uuid.uuid4`), lalu baca `instance.token` untuk URL. Test entropi membandingkan sumber default dengan `secrets.token_urlsafe(32)`.

**Fixture reuse**: per kelas test gunakan `setUpTestData` statis (membuat unit, peran, pengguna) untuk mengurangi waktu test; gunakan instance `TestCase` yang sudah ada dari suite keamanan yang sudah ada sebagai base.

---

## E. CI integration

Repo menjalankan test dengan `manage.py test` (Django TestCase; tidak ada pytest.ini/pyproject/setup.cfg dan `pytest` tidak ada di `requirements.txt`). Tidak ada perintah seed khusus di CI: setiap `TestCase` menyiapkan datanya sendiri, dan `config/settings.py` otomatis memakai SQLite bila `DATABASE_URL` tidak di-set — Django membuat DB test sementara `test_*.sqlite3` lalu menghapusnya. `qa/settings_qa.py` adalah setelan harness QA (`python -m qa.runner`), **bukan** modul settings Django; jangan dipakai sebagai `DJANGO_SETTINGS_MODULE`.

**Workflow GitHub Actions** (`.github/workflows/security-tests.yml`) — sudah ada di repo dan mengikuti gaya `hc-reminders.yml`:

```yaml
name: Security Tests
on:
  push:
    branches: [main]
  pull_request:
concurrency:
  group: security-tests-${{ github.ref }}
  cancel-in-progress: true
jobs:
  security:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    env:
      DJANGO_SECRET_KEY: ci-only-security-suite-key-not-for-production
      PUBLIC_BASE_URL: http://localhost:8000
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run security tests
        env:
          DJANGO_DEBUG: 'False'
          DJANGO_SECRET_KEY: ci-only-security-suite-key-not-for-production
        run: |
          python manage.py test \
            accounts.tests_security_owasp \
            akreditasi.tests_security_owasp \
            pasien.tests_security_owasp \
            sdm.tests.security_owasp \
            --verbosity 2
```

**Catatan**:
- `manage.py test` memakai `django.test.TestCase`; tidak ada langkah `migrate`/`seed` manual karena runner test Django membuat skema dari migrasi dan tiap `TestCase` menyiapkan datanya sendiri.
- `--verbosity 2` mencetak nama tiap test beserta PASS/FAIL sehingga kegagalan yang mendokumentasikan kerentanan langsung terlihat di log CI.
- Jalur cepat lokal: `.venv/Scripts/python.exe manage.py test accounts.tests_security_owasp akreditasi.tests_security_owasp pasien.tests_security_owasp sdm.tests.security_owasp`

---

## F. Prioritized execution order & expected results

### Hasil eksekusi aktual (terverifikasi)

Perintah: `.venv/Scripts/python.exe manage.py test accounts.tests_security_owasp akreditasi.tests_security_owasp pasien.tests_security_owasp sdm.tests.security_owasp`

```
Ran 36 tests in 47.9s
FAILED (failures=12)
```

- **36 test**, **12 GAGAL** (semuanya `self.fail()` yang mendokumentasikan kerentanan nyata), **24 LULUS**, **0 ERROR**.
- Setiap test berakhir PASS atau FAIL dengan assertion eksplisit; tidak ada import/URL/field yang salah.

Rincian per suite:

| Suite | Jumlah | GAGAL (kerentanan) | LULUS |
|-------|--------|--------------------|-------|
| `accounts.tests_security_owasp` | 9 | 4 | 5 |
| `akreditasi.tests_security_owasp` | 11 | 1 | 10 |
| `pasien.tests_security_owasp` | 10 | 5 | 5 |
| `sdm.tests.security_owasp` | 6 | 2 | 4 |

### P0 — kerentanan akses & autentikasi (implementasi pertama)

| Test | Expected | Evidence |
|------|----------|----------|
| `pasien.PatientPiiIdorTest.test_pasien_detail_lintas_unit_ditolak` | **GAGAL** | `pasien/views.py:223-226` hanya `@login_required` + `get_object_or_404(Pasien, pk=pk)`, tanpa filter unit |
| `pasien.PatientPiiIdorTest.test_kunjungan_detail_lintas_unit_ditolak` | **GAGAL** | `pasien/views.py:276-277`, tanpa cek `KunjunganPasien.unit` |
| `pasien.PatientSearchApiLeakageTest.test_api_cari_pasien_membocorkan_pii` | **GAGAL** | `pasien/views.py:803-838` mengembalikan nik/no_rm/alamat/no_hp/no_bpjs lintas unit |
| `pasien.PatientSearchApiLeakageTest.test_api_cek_nik_membocorkan_pii` | **GAGAL** | `pasien/views.py:840-864`, `Pasien.objects.filter(nik=nik).first()` tanpa scope |
| `pasien.PatientModuleDecoratorCoverageTest.test_view_baca_inti_tanpa_guard` | **GAGAL** | `require_patient_module` tidak dipasang pada `pasien_daftar`; apoteker tembus 200 |
| `accounts.SuperAdminRoleEscalationTest.test_admin_rs_tidak_dapat_membuat_super_admin` | **GAGAL** | `accounts/views.py:100-146`: `admin_only` = `can_manage_users`; form menerima `role='SUPER_ADMIN'` → `is_superuser=True` |
| `accounts.SuperAdminRoleEscalationTest.test_admin_rs_tidak_dapat_mengeskalasi_lewat_user_edit` | **GAGAL** | `accounts/views.py:153-200`: `user_edit` menyetel `is_superuser` dari `profile.role` |
| `accounts.ControlCenterPermissionTamperTest.test_holder_tidak_dapat_memberi_izin_kepada_akun_lain` | **GAGAL** | `accounts/views.py:455-490`: `custom_permissions` JSONField ditulis apa adanya untuk `user_id` mana pun |
| `accounts.ControlCenterPermissionTamperTest.test_holder_tidak_dapat_memberi_izin_kepada_dirinya` | **GAGAL** | tidak ada pemisahan tugas: pemanggil dapat menargetkan `user_id` sendiri |
| `sdm.RecruitmentTokenStrengthTest.test_token_pelamar_bukan_uuid4` | **GAGAL** | `sdm/models/rekrutmen.py:121-124` `default=uuid.uuid4` vs `sdm/services/undangan.py:44` `secrets.token_urlsafe(32)` |
| `sdm.RecruitmentTokenStrengthTest.test_token_offering_bukan_uuid4` | **GAGAL** | `sdm/models/rekrutmen.py:418-420` `default=uuid.uuid4` |
| `akreditasi.AdminGateIgnoresPermissionConfigTest.test_can_manage_units_false_tetap_dapat_membuka_unit_edit` | **GAGAL** | `admin_required` berbasis string peran, mengabaikan `RolePermissionConfig` |

### P1 — batas RBAC yang harus dipaku (PASS) and one yang bocor (FAIL)

| Test | Expected | Evidence |
|------|----------|----------|
| `akreditasi.UnitEditAdminGateTest.test_staf_nakes_ditolak_*` (unit_list/unit_edit/unit_delete/pokja_manage) | **LULUS** | `_is_admin` (`akreditasi/views.py:63-70`) hanya SUPER_ADMIN/ADMIN_RS |
| `akreditasi.UnitEditAdminGateTest.test_kepala_unit_ditolak_unit_edit` | **LULUS** | idem |
| `akreditasi.UnitEditAdminGateTest.test_asesor_ditolak_audit_log` | **LULUS** | idem |
| `akreditasi.UnitEditAdminGateTest.test_admin_rs_diizinkan_unit_list` | **LULUS** | ADMIN_RS ∈ `_is_admin` |
| `akreditasi.AuditLogAdminOnlyTest.test_staf_nakes_ditolak` | **LULUS** | `akreditasi/views.py:1578` |
| `akreditasi.AuditLogAdminOnlyTest.test_admin_rs_diizinkan` | **LULUS** | idem |
| `akreditasi.AdminGateIgnoresPermissionConfigTest.test_can_manage_units_false_tetap_tembus` | **GAGAL** | `admin_required` tidak membaca `RolePermissionConfig`, jadi mencabut `can_manage_units` tidak menutup `unit_edit` |
| `accounts.CookieSecurityTest.test_akun_nonaktif_tidak_dapat_login` | **LULUS** | `ModelBackend.user_can_authenticate()` menolak akun nonaktif saat login |
| `accounts.CookieSecurityTest.test_sesi_akun_nonaktif_dimatikan` | **LULUS** | `auth.get_user()` → `ModelBackend.get_user()` mengembalikan `None` tiap request |
| `accounts.CookieSecurityTest.test_session_cookie_httponly` | **LULUS** | `config/settings.py:131` |
| `accounts.CookieSecurityTest.test_session_cookie_secure_saat_debug_off` | **LULUS** | `config/settings.py:122-125` |
| `accounts.CookieSecurityTest.test_samesite_dilaporkan_secara_eksplisit` | **LULUS** (dokumentasi) | `SESSION_COOKIE_SAMESITE` tidak di-set eksplisit, tetapi Django default-nya `'Lax'`, sehingga test lulus; komentar menandai bahwa nilai bergantung pada default framework dan sebaiknya di-set eksplisit |

### P2 — kelengkapan (backlog)

- `pasien.PatientModuleDecoratorCoverageTest` — memaku view mana yang membawa `require_patient_module` dan mana yang tidak.
- `pasien.PatientFileUploadTest` — validasi ekstensi/MIME/ukuran upload bukti (`akreditasi/file_security.py`).
- `sdm.OfferingAccessTest` — token offering hanya memetakan ke satu `KonfirmasiOffering`; pemegang token lain tidak dapat membaca/mengunduh offering orang lain.

### Ekspektasi Hasil Test

- **PASS**: suite keamanan lama (`akreditary/tests_security.py`, `accounts/tests_unit_rbac.py`, `pasien/tests_object_authz.py`, `akreditasi/tests_admin_gate.py`, `accounts/tests_priv_escalation.py`) tidak berubah dan tetap hijau.
- **BARU**: setiap test di suite `*_owasp.py` berakhir PASS atau FAIL dengan assertion kerentanan eksplisit — **tidak boleh ERROR** (import gagal, URL salah, field salah).
- **CI**: `manage.py test` mengembalikan non-zero bila ada FAIL, sehingga kerentanan yang terdokumentasi memblokir merge sampai diperbaiki atau test dipindahkan ke daftar `expectedFailure` setelah perbaikan.

### Item backlog untuk pelaksanaan

- Pasang `require_patient_module` + filter unit pada `pasien_detail`, `kunjungan_detail`, `resume_pdf`, `api_cari_pasien`, `api_cek_nik`, `pasien_daftar`.
- Batasi penetapan `role='SUPER_ADMIN'` di `user_create`/`user_edit` hanya untuk `is_superuser`.
- Validasi kunci izin di `update_user_custom_permissions` (whitelist) dan tolak pemberian yang melebihi izin pemberi.
- Jadikan `admin_required` permission-based (baca `RolePermissionConfig`/`custom_permissions`) agar mencabut `can_manage_units` benar-benar menutup unit CRUD.
- Ganti `default=uuid.uuid4` pada `Pelamar.token`/`KonfirmasiOffering.token` dengan `secrets.token_urlsafe(32)`.
- Set `SESSION_COOKIE_SAMESITE = 'Lax'` (atau `'Strict'`) secara eksplisit di `config/settings.py`.
- Tambah validasi ekstensi/MIME/ukuran pada jalur upload bukti.

---

*Dokumen ini dihasilkan oleh alat analisis statis; verifikasi manual terhadap baris kode sumber diperlukan.*
