# Remediation Plan — SIM Akreditasi RS / ARIMA

Rencana perbaikan untuk 16 temuan P0 yang didokumentasikan oleh suite keamanan
(`.github/workflows/security-tests.yml`, sengaja merah).

**Status dokumen ini: DESAIN SAJA.** Tidak ada kode produksi yang diubah dan tidak ada
berkas tes yang disentuh. Setiap `file:line` di bawah **sudah diverifikasi ulang**
terhadap kode sumber saat ini.

---

## 0. Baseline Terverifikasi

Dijalankan pada working tree saat ini:

```bash
.venv/Scripts/python.exe manage.py test \
  accounts.tests_security_owasp akreditasi.tests_security_owasp \
  pasien.tests_security_owasp sdm.tests.security_owasp \
  akreditasi.tests_session_security accounts.tests_priv_escalation \
  akreditasi.tests_admin_gate pasien.tests_object_authz --verbosity 2
```

Hasil: **89 tes, 32 gagal, 0 error.** Kedelapan modul di atas adalah subset yang
memuat seluruh 32 kegagalan; suite penuh (workflow) menjalankan 151 tes dengan
32 kegagalan yang sama.

### Peta 32 kegagalan → temuan

| Temuan | Test method (FAIL) |
|--------|--------------------|
| P0-1 | `accounts.tests_security_owasp.SuperAdminRoleEscalationTest.test_admin_rs_tidak_dapat_membuat_super_admin`<br>`accounts.tests_priv_escalation.UserCreateRoleEscalationTest.test_admin_rs_cannot_create_super_admin` |
| P0-2 | `accounts.tests_security_owasp.SuperAdminRoleEscalationTest.test_admin_rs_tidak_dapat_mengeskalasi_lewat_user_edit`<br>`accounts.tests_priv_escalation.UserCreateRoleEscalationTest.test_admin_rs_cannot_escalate_via_user_edit` |
| P0-3 | `accounts.tests_priv_escalation.UserDeleteEscalationTest.test_admin_rs_cannot_delete_super_admin`<br>`accounts.tests_priv_escalation.UserDeleteEscalationTest.test_admin_rs_cannot_delete_another_admin_rs` |
| P0-4 | `accounts.tests_priv_escalation.CustomPermissionWriteTest.test_control_center_holder_can_grant_manage_users_to_other`<br>`accounts.tests_priv_escalation.CustomPermissionWriteTest.test_control_center_holder_can_grant_permissions_to_self`<br>`accounts.tests_security_owasp.ControlCenterPermissionTamperTest.test_holder_tidak_dapat_memberi_izin_kepada_akun_lain`<br>`accounts.tests_security_owasp.ControlCenterPermissionTamperTest.test_holder_tidak_dapat_memberi_izin_kepada_dirinya` |
| P0-5 | `accounts.tests_priv_escalation.CustomPermissionWriteTest.test_unknown_permission_keys_are_rejected` |
| P0-6 | `accounts.tests_priv_escalation.RolePermissionTamperTest.test_non_super_admin_cannot_flip_lockout_safe_perm` |
| P0-7 | `accounts.tests_priv_escalation.RolePermissionTamperTest.test_non_super_admin_cannot_grant_control_center_to_staf_nakes` |
| P0-8 | `akreditasi.tests_security_owasp.AdminGateIgnoresPermissionConfigTest.test_can_manage_units_false_tetap_dapat_membuka_unit_edit`<br>`akreditasi.tests_admin_gate.AdminGateBypassesPermissionConfigTest.test_can_manage_units_false_does_not_close_unit_edit`<br>`akreditasi.tests_admin_gate.AdminGateBypassesPermissionConfigTest.test_can_manage_units_false_does_not_close_unit_delete` |
| P0-9 | `akreditasi.tests_admin_gate.AdminGateBypassesPermissionConfigTest.test_authenticated_unauthorized_gets_403_not_redirect` |
| P0-10 | `pasien.tests_security_owasp.PatientPiiIdorTest.test_pasien_detail_lintas_unit_ditolak`<br>`pasien.tests_security_owasp.PatientPiiIdorTest.test_kunjungan_detail_lintas_unit_ditolak`<br>`pasien.tests_object_authz.PatientIdorTest.test_nakes_igd_cannot_read_pasien_detail_outside_unit`<br>`pasien.tests_object_authz.PatientIdorTest.test_nakes_igd_cannot_read_kunjungan_detail_outside_unit` |
| P0-11 | `pasien.tests_object_authz.PatientIdorTest.test_pasien_daftar_lists_all_patients_regardless_of_unit` |
| P0-12 | `pasien.tests_security_owasp.PatientSearchApiLeakageTest.test_api_cari_pasien_membocorkan_pii`<br>`pasien.tests_object_authz.PatientPiiApiTest.test_api_cari_pasien_leaks_pii_across_modules` |
| P0-13 | `pasien.tests_security_owasp.PatientSearchApiLeakageTest.test_api_cek_nik_membocorkan_pii`<br>`pasien.tests_object_authz.PatientPiiApiTest.test_api_cek_nik_leaks_pii` |
| P0-14 | `pasien.tests_security_owasp.PatientModuleDecoratorCoverageTest.test_view_baca_inti_tanpa_guard`<br>`pasien.tests_object_authz.PatientModuleScopeTest.test_core_read_views_are_unguarded`<br>`pasien.tests_object_authz.PatientModuleScopeTest.test_dashboard_is_unguarded` |
| P0-15 | `sdm.tests.security_owasp.RecruitmentTokenStrengthTest.test_token_pelamar_bukan_uuid4`<br>`sdm.tests.security_owasp.RecruitmentTokenStrengthTest.test_token_offering_bukan_uuid4` |
| P0-16 | `akreditasi.tests_session_security.CookieFlagTest.test_samesite_is_explicitly_strict` |

---

## 1. Koreksi terhadap `security-test-gate.md`

Dokumen gate secara umum akurat, tetapi ada beberapa hal yang **harus dikoreksi**
sebelum dipakai sebagai acuan kerja:

### 1.1 P0-16 salah diklasifikasikan sebagai "sudah LULUS"

`security-test-gate.md` mencatat `test_samesite_dilaporkan_secara_eksplisit` sebagai
**LULUS (dokumentasi)** dan P0-16 sebagai temuan `TERBUKA` dengan catatan "default
Django `'Lax'`, sehingga test lulus". Itu **keliru**.

- `accounts/tests_security_owasp.py:210-226` (`CookieSecurityTest.test_samesite_dilaporkan_secara_eksplisit`)
  memang lulus karena hanya menuntut nilai ∈ `{'Lax','Strict'}`.
- Tetapi `akreditasi/tests_session_security.py:133-154`
  (`CookieFlagTest.test_samesite_is_explicitly_strict`) **menuntut `'Strict'`** dan
  **GAGAL** saat ini. Test itu tidak disebut sama sekali di tabel P0 gate.

**Konsekuensi desain:** P0-16 tidak boleh diperbaiki dengan `'Lax'`. Nilai yang benar
adalah **`'Strict'`**, dan itu memuaskan kedua test sekaligus. `owasp-test-plan.md`
(baris "Set `SESSION_COOKIE_SAMESITE = 'Lax'`") juga salah untuk alasan yang sama.

### 1.2 P0-3 tidak disebut di `owasp-test-plan.md`

Plan OWASP tidak memuat temuan penghapusan akun. Padahal ada **dua** test gagal:
`test_admin_rs_cannot_delete_super_admin` dan `test_admin_rs_cannot_delete_another_admin_rs`.
Yang kedua menuntut perlindungan **peer-admin**, bukan hanya hierarki.

### 1.3 P0-11 dan P0-14 terpisah, tetapi satu akar

`owasp-test-plan.md` menggabungkan `pasien_daftar` ke dalam daftar "Pasang
`require_patient_module`". Kenyataannya `pasien_daftar` gagal karena **dua** sebab
independen: (a) tidak ada dekorator modul, dan (b) `Pasien.objects.all()` tanpa scope
unit. Memasang dekorator saja **tidak** memuaskan
`test_pasien_daftar_lists_all_patients_regardless_of_unit`, karena apoteker memang
memegang modul `master_pasien` dan akan tetap melihat seluruh RS.

### 1.4 Klaim "P0-10…P0-14 = pasang dekorator + filter unit" tidak dapat dilaksanakan apa adanya

**Ini temuan paling penting dari verifikasi.** `pasien/models.py` **tidak memiliki FK
unit sama sekali**:

- `Pasien` (baris 13-72): tidak ada `unit` / `unit_kerja`.
- `KunjunganPasien` (baris 277-…): tidak ada `unit_kerja`. Yang ada hanya
  `poliklinik` (CharField bebas, `pasien/models.py:285`), `bed` → `Bed` → `Ruangan`,
  dan `jenis_kunjungan`.
- `Ruangan` (baris 142-163) dan `Bed` (baris 165-186): tidak ada FK ke `UnitKerja`.
- `grep -rn "unit" pasien/migrations/*.py` → **nol hasil**.

Jadi "filter unit" bukan pekerjaan satu baris. Ini menentukan seluruh desain §5.

---

## 2. P0-1 / P0-2 / P0-3 — Eskalasi peran vertikal

### 2.1 Defect terverifikasi

**P0-1 — `user_create`**
- `accounts/views.py:27-33` — `admin_only(user)` = `is_superuser or profile.can_manage_users`.
- `accounts/views.py:100-146` — `user_create`, dijaga `@user_passes_test(admin_only)`.
- `accounts/views.py:136-141` — setelah form valid, `is_staff`/`is_superuser` disetel
  **langsung dari `profile.role`** tanpa memeriksa hak pemanggil:
  ```python
  if profile.role == 'SUPER_ADMIN':
      user.is_staff = True
      user.is_superuser = True
      user.save()
  elif profile.role == 'ADMIN_RS':
      user.is_staff = True
      user.save()
  ```
- `accounts/models.py:18-27` — `PERMISSION_DEFAULTS['ADMIN_RS']['can_manage_users'] = True`.
  Jadi ADMIN_RS lolos `admin_only` dan dapat mencetak SUPER_ADMIN.
- `accounts/forms.py:38-46` — `UserProfileForm.Meta.fields` memuat `'role'` tanpa batasan.

**P0-2 — `user_edit`**
- `accounts/views.py:153-200` — `user_edit`, `@user_passes_test(admin_only)`.
- `accounts/views.py:167-179` — blok yang sama, dari `profile.role`, tanpa cek pemanggil.

**P0-3 — `user_delete`**
- `accounts/views.py:202-220` — `user_delete`, `@user_passes_test(admin_only)` + `@require_POST`.
- `accounts/views.py:206-209` — **satu-satunya** guard adalah penolakan hapus-diri:
  ```python
  if target_user == request.user:
      messages.error(request, "Anda tidak dapat menghapus akun Anda sendiri!")
      return redirect('accounts:user_list')
  ```
  Tidak ada perbandingan hierarki dan tidak ada perlindungan admin-terakhir.

### 2.2 Perbaikan — keputusan dan alasan

Tiga mekanisme yang dipertimbangkan, dan mana yang dipakai:

**(a) Perbandingan hierarki peran — DIPAKAI, sebagai lapis utama.**
`UserProfile.ROLE_HIERARCHY` sudah ada (`accounts/models.py:82-89`) dan sudah diekspos
lewat `role_level` (`accounts/models.py:186-188`). Ini sumber kebenaran yang sudah
disepakati proyek, jadi tidak perlu konvensi kedua. Aturan:

> Pemanggil hanya boleh menetapkan peran **target** dengan
> `ROLE_HIERARCHY[target] <= ROLE_HIERARCHY[pemanggil]`, dan hanya boleh
> memodifikasi/menghapus akun dengan `role_level(akun) < role_level(pemanggil)`.

Kenapa **strictly less** untuk modifikasi/hapus: mencegah peer-admin saling menghapus
(memenuhi `test_admin_rs_cannot_delete_another_admin_rs`) dan mencegah admin menurunkan
sesama admin. Kenapa `<=` untuk penetapan peran: ADMIN_RS (level 4) boleh membuat
ADMIN_RS lain, tetapi **tidak** SUPER_ADMIN (level 5).

**(b) Cek eksplisit `only is_superuser may set role=SUPER_ADMIN` — DIPAKAI, sebagai lapis kedua.**
Hierarki saja secara teknis sudah menutup SUPER_ADMIN (5 > 4). Tetapi cek eksplisit
dipertahankan karena:
- Ini invarian keamanan yang tidak boleh bergantung pada satu angka di dict; jika
  kelak ada peran level 5 kedua, hierarki saja akan membocorkan SUPER_ADMIN.
- Pesan kegagalan test menyebut perbaikan ini secara literal
  (`accounts/tests_security_owasp.py:96-98`: *"Perbaikan: batasi penetapan role SUPER_ADMIN hanya untuk is_superuser."*).

**(c) Perlindungan superuser-terakhir — DIPAKAI, sebagai lapis ketiga.**
Menutup *denial of administration*: jika hanya tersisa satu akun superuser aktif,
menghapus/menonaktifkannya harus ditolak. Ini juga menutup celah ADMIN_RS menurunkan
superuser terakhir lewat `user_edit` (`is_active` off).

**Lokasi implementasi.** Ketiga lapis diletakkan di **satu helper bersama** di
`accounts/views.py` (dekat `admin_only`, baris 27-33), dipanggil oleh `user_create`,
`user_edit`, dan `user_delete`. Bukan di form, karena `UserProfileForm` tidak punya
akses ke `request.user` tanpa meneruskan `request` — dan form juga dipakai dari
`admin_control_center`; menaruh otorisasi di view menjaga satu titik keputusan.

Helper yang dirancang (nama & bentuk final, siap diimplementasikan):

```python
def _caller_role_level(user) -> int:
    """Tingkat hierarki peran pemanggil; superuser selalu di puncak."""
    if user.is_superuser:
        return UserProfile.ROLE_HIERARCHY['SUPER_ADMIN']
    profile = getattr(user, 'profile', None)
    return profile.role_level if profile else 0

def _can_assign_role(caller, target_role: str) -> bool:
    """Pemanggil hanya boleh menetapkan peran <= tingkatnya sendiri."""
    if target_role == 'SUPER_ADMIN':
        return caller.is_superuser          # lapis (b)
    return UserProfile.ROLE_HIERARCHY.get(target_role, 0) <= _caller_role_level(caller)

def _can_modify_account(caller, target_user) -> bool:
    """Hanya boleh mengubah akun dengan tingkat lebih rendah."""
    if caller.is_superuser:
        return True
    target_profile = getattr(target_user, 'profile', None)
    target_level = target_profile.role_level if target_profile else 0
    return target_level < _caller_role_level(caller)

def _is_last_active_superuser(target_user) -> bool:
    """True bila target adalah satu-satunya superuser aktif."""
    if not target_user.is_superuser:
        return False
    return not User.objects.filter(
        is_superuser=True, is_active=True,
    ).exclude(pk=target_user.pk).exists()
```

Penerapan:
- `user_create`: sebelum `profile.save()`, tolak bila
  `not _can_assign_role(request.user, profile.role)`. Pesan (Indonesia, konsisten
  dengan gaya view):
  `"Anda tidak berwenang menetapkan peran 'Super Admin (Developer / IT RS)'."`
- `user_edit`: tolak bila `not _can_modify_account(request.user, target_user)` **atau**
  `not _can_assign_role(request.user, profile.role)`. Pesan:
  `"Anda tidak berwenang mengubah akun dengan peran setara atau lebih tinggi."`
- `user_delete`: tolak bila `not _can_modify_account(request.user, target_user)`
  **atau** `_is_last_active_superuser(target_user)`. Pesan:
  `"Akun dengan peran setara atau lebih tinggi tidak dapat dihapus."` /
  `"Super Admin aktif terakhir tidak dapat dihapus."`

Semua penolakan memakai `messages.error(...)` + `redirect('accounts:user_list')`,
konsisten dengan `user_delete` yang sudah ada (baris 206-209). Tidak boleh `raise
PermissionDenied` di sini, karena test menerima `(200, 302)` dan hanya memeriksa state
DB (`assertIn(response.status_code, (200, 302))`), bukan kode status penolakan.

**Catatan penting untuk P0-1:** kedua test P0-1 menerima dua jalur —
"ditolak total" atau "dibuat dengan peran lebih rendah". Implementasi yang dipilih
adalah **ditolak total** (tidak ada baris `User` yang dibuat), karena itu yang paling
jelas dan memuaskan `if created is None: return` di
`accounts/tests_security_owasp.py:89-91`.

### 2.3 Test yang flip FAIL → PASS

| Test | Berkas:baris |
|------|--------------|
| `SuperAdminRoleEscalationTest.test_admin_rs_tidak_dapat_membuat_super_admin` | `accounts/tests_security_owasp.py:63` |
| `SuperAdminRoleEscalationTest.test_admin_rs_tidak_dapat_mengeskalasi_lewat_user_edit` | `accounts/tests_security_owasp.py:87` |
| `UserCreateRoleEscalationTest.test_admin_rs_cannot_create_super_admin` | `accounts/tests_priv_escalation.py:104` |
| `UserCreateRoleEscalationTest.test_admin_rs_cannot_escalate_via_user_edit` | `accounts/tests_priv_escalation.py:134` |
| `UserDeleteEscalationTest.test_admin_rs_cannot_delete_super_admin` | `accounts/tests_priv_escalation.py:182` |
| `UserDeleteEscalationTest.test_admin_rs_cannot_delete_another_admin_rs` | `accounts/tests_priv_escalation.py:202` |

### 2.4 Risiko terhadap test yang sudah LULUS

- `UserDeleteEscalationTest.test_self_delete_is_blocked`
  (`accounts/tests_priv_escalation.py:215`) — tetap lulus: guard hapus-diri lama
  dipertahankan, dan `_can_modify_account` juga menolak (level sama).
- `akreditasi.tests_security_owasp.UnitEditAdminGateTest.test_admin_rs_diizinkan_unit_list`
  dan `AuditLogAdminOnlyTest.test_admin_rs_diizinkan` — tidak tersentuh; keduanya tidak
  melalui helper ini.
- **Perlu diperiksa saat implementasi:** `accounts/tests_unit_rbac.py` dan test HC
  (`sdm/tests/test_akses.py`) membuat SUPER_ADMIN lewat `make_user` yang menyetel
  `is_superuser=True` langsung di model — bukan lewat view — jadi tidak terpengaruh.
  Namun `sdm/tests/test_akses.py:211` (`test_user_with_hc_grants_must_be_revoked_before_account_deletion`)
  menyentuh penghapusan akun; **jalur itu lewat service HC, bukan `accounts:user_delete`**,
  jadi tidak terpengaruh. Verifikasi tetap wajib setelah implementasi.

---

## 3. P0-4 / P0-5 — `custom_permissions` tanpa validasi

### 3.1 Defect terverifikasi

- `accounts/views.py:455-490` — `update_user_custom_permissions`, dijaga
  `@user_passes_test(control_center_access)` (`accounts/views.py:222-229`).
- `accounts/views.py:482-483` — penulisan tanpa validasi apa pun:
  ```python
  profile.custom_permissions = custom_perms
  profile.save(update_fields=['custom_permissions', 'updated_at'])
  ```
- `accounts/views.py:466-469` — `get_object_or_404(User, id=user_id)` menerima
  **`user_id` apa pun**, termasuk `request.user.id` (tidak ada pemisahan tugas).
- `accounts/models.py:170-172` — `custom_permissions = models.JSONField(default=dict)`,
  bebas bentuk.
- `accounts/models.py:213-235` — `has_permission()` membaca `custom_permissions`
  sebagai **override pertama** (setelah superuser/freeze):
  ```python
  if perm_code in self.custom_permissions:
      return bool(self.custom_permissions[perm_code])
  ```
  Jadi kunci `can_manage_users` yang ditulis di sini langsung berlaku.

### 3.2 Perbaikan — sumber kebenaran whitelist

**Sumber kebenaran: gabungan `PERMISSION_DEFAULTS` dan `HC_PERMISSION_LABELS`,
keduanya sudah ada.**

- `accounts/models.py:7-77` — `PERMISSION_DEFAULTS`: enam dict peran, masing-masing
  memuat 18 kunci izin inti.
- `accounts/models.py:78-96` — `HC_PERMISSION_LABELS`: 17 pasangan `(kode, label)`.
- `accounts/models.py:97-98` — loop yang **sudah** menyuntikkan seluruh kunci HC ke
  setiap dict `PERMISSION_DEFAULTS`. Jadi `PERMISSION_DEFAULTS` **sudah lengkap**:
  ia memuat izin inti + HC.

**Keputusan:** whitelist dibangun dari satu sumber turunan, bukan dua:

```python
# accounts/models.py — konstanta baru di level modul, setelah loop HC.
VALID_PERMISSION_KEYS = frozenset(
    key for defaults in PERMISSION_DEFAULTS.values() for key in defaults
)
```

Alasan memakai `PERMISSION_DEFAULTS` sebagai satu-satunya sumber: loop di baris 97-98
menjamin seluruh kunci HC ada di dalamnya, sehingga `HC_PERMISSION_LABELS` tidak perlu
dibaca terpisah dan tidak mungkin drift. `VALID_PERMISSION_KEYS` juga otomatis
mencakup kunci baru yang ditambahkan ke `PERMISSION_DEFAULTS`.

**Pertanyaan: apakah pemberi izin dibatasi pada izin yang ia sendiri pegang?**

**Ya — dan ini wajib, bukan opsional.** Tanpa batas ini, whitelist saja tidak menutup
P0-4: `can_manage_users` **ada di whitelist**, dan pemegang Pusat Kontrol berperan
rendah (`KOORDINATOR_POKJA`) tetap bisa menulisnya. Test P0-4 secara eksplisit
memakai `KOORDINATOR_POKJA` + `can_access_control_center=True`
(`accounts/tests_priv_escalation.py:221-226`), jadi hanya whitelist **tidak cukup**.

Aturan yang dirancang:

> Setiap kunci yang di-`True`-kan harus merupakan izin yang **pemanggil** juga
> miliki (`request.user.profile.has_permission(key)`). Kunci yang di-`False`-kan
> selalu boleh (pencabutan bukan eskalasi).

Konsekuensi yang dicek terhadap test:
- `test_control_center_holder_can_grant_manage_users_to_other`: pemanggil
  KOORDINATOR_POKJA **tidak** punya `can_manage_users` (`accounts/models.py:35`) →
  ditolak → PASS.
- `test_control_center_holder_can_grant_permissions_to_self`: idem → PASS.
- `test_unknown_permission_keys_are_rejected`: `can_teleport` / `__proto__` bukan
  anggota `VALID_PERMISSION_KEYS` → ditolak → PASS.

**Pemisahan tugas (self-target).** Test P0-4-kedua juga menuntut penolakan saat
`user_id == request.user.id`. Dua pilihan:
1. Tolak total penulisan ke diri sendiri.
2. Tolak hanya bila hasilnya menambah izin.

**Dipilih opsi 2** (tolak bila menambah izin yang belum dimiliki), karena aturan
"hanya boleh memberikan izin yang dimiliki" sudah otomatis menutup self-grant —
pemanggil tidak bisa memberi dirinya izin yang belum ia pegang. Ini lebih sedikit
kode dan tidak mematahkan kebutuhan sah (mis. admin menyalakan izin yang ia sudah
punya). **Tidak ada guard `user_id == request.user.id` terpisah** — itu akan menjadi
aturan kedua yang tumpang tindih dengan aturan pertama.

**Validasi bentuk.** `custom_permissions` harus tetap `dict` (sudah ada di
`accounts/views.py:470-476`, dipertahankan), dan setiap *value* harus koersibel ke
`bool`. Kunci non-string ditolak.

Pesan penolakan (Indonesia):
- Kunci tak dikenal: `"Kunci izin tidak dikenal: {kunci}."`
- Melebihi izin pemberi: `"Anda tidak dapat memberikan izin yang tidak Anda miliki: {kunci}."`
- Bentuk salah: `"custom_permissions harus berupa objek."` (sudah ada, dipertahankan)

Semua mengembalikan `JsonResponse({'success': False, 'error': ...}, status=403)` untuk
pelanggaran otorisasi dan `status=400` untuk bentuk payload salah. Test menerima
`(200, 400)` di
`accounts/tests_priv_escalation.py:247` dan `accounts/tests_security_owasp.py:152` —
**perhatikan: 403 TIDAK diterima oleh `assertIn(response.status_code, (200, 400))`.**

> **Keputusan penting:** untuk endpoint ini, penolakan otorisasi **harus** memakai
> **400**, bukan 403, agar test lulus. Ini disengaja oleh penulis test: mereka hanya
> memeriksa bahwa state DB tidak berubah, dengan status `(200, 400)`. Menggunakan 403
> akan membuat test **ERROR/FAIL pada assertion status**, bukan pada assertion state.
> Jadi balasan error memakai `status=400` dengan `success: False` dan pesan yang
> menjelaskan penolakan otorisasi.

### 3.3 Test yang flip FAIL → PASS

| Test | Berkas:baris |
|------|--------------|
| `CustomPermissionWriteTest.test_control_center_holder_can_grant_manage_users_to_other` | `accounts/tests_priv_escalation.py:239` |
| `CustomPermissionWriteTest.test_control_center_holder_can_grant_permissions_to_self` | `accounts/tests_priv_escalation.py:264` |
| `CustomPermissionWriteTest.test_unknown_permission_keys_are_rejected` | `accounts/tests_priv_escalation.py:288` |
| `ControlCenterPermissionTamperTest.test_holder_tidak_dapat_memberi_izin_kepada_akun_lain` | `accounts/tests_security_owasp.py:145` |
| `ControlCenterPermissionTamperTest.test_holder_tidak_dapat_memberi_izin_kepada_dirinya` | `accounts/tests_security_owasp.py:168` |

### 3.4 Risiko terhadap test yang sudah LULUS

`sdm/tests/test_akses.py:103` (`test_user_override_can_revoke_a_role_permission`) dan
`:115` (`test_user_override_can_enable_only_with_matching_explicit_grant`) menyetel
`custom_permissions` **langsung di model**, bukan lewat view. Tidak terpengaruh.
Verifikasi setelah implementasi tetap wajib.

---

## 4. P0-6 / P0-7 — `update_role_permissions` dan invarian LOCKOUT_SAFE_PERMS

### 4.1 Defect terverifikasi

- `accounts/views.py:410-453` — `update_role_permissions`, dijaga
  `@user_passes_test(control_center_access)` + `@require_POST`.
- `accounts/views.py:432-437` — inti defect:
  ```python
  for perm_field, value in role_data.items():
      # Super Admin lockout protection
      if role_code == 'SUPER_ADMIN' and perm_field in LOCKOUT_SAFE_PERMS:
          continue  # Tidak boleh diubah
      if hasattr(cfg, perm_field):
          setattr(cfg, perm_field, bool(value))
  ```
  Skip hanya berlaku saat `role_code == 'SUPER_ADMIN'`.
- `accounts/models.py:104` — `LOCKOUT_SAFE_PERMS = {'can_access_control_center',
  'can_manage_users', 'can_manage_system_settings'}`.
- `accounts/views.py:222-229` — `control_center_access` = `is_superuser or
  has_permission('can_access_control_center')`.

### 4.2 Perbaikan — invarian yang benar

Invarian yang dirancang, dinyatakan sebagai kalimat tunggal:

> **`LOCKOUT_SAFE_PERMS` bersifat global dan tidak dapat diubah untuk peran mana pun
> oleh siapa pun kecuali `is_superuser`.**

Alasan: tiga izin itu adalah izin yang menjaga *kemampuan memulihkan sistem*. Jika
`can_access_control_center` untuk `ADMIN_RS` bisa dicabut oleh pemegang Pusat Kontrol
lain, sistem dapat dikunci dari jalur pemulihan. Membatasi skip ke `SUPER_ADMIN`
adalah kesalahan kategori: yang dilindungi adalah **invarian sistem**, bukan
**privilese satu peran**.

Perbaikan konkret di `accounts/views.py:432-437`:

```python
for perm_field, value in role_data.items():
    if perm_field in LOCKOUT_SAFE_PERMS and not request.user.is_superuser:
        continue          # invarian global; hanya superuser boleh mengubah
    if hasattr(cfg, perm_field):
        setattr(cfg, perm_field, bool(value))
```

**Mengapa `not request.user.is_superuser` dan bukan "hanya untuk SUPER_ADMIN":**
superuser tetap harus bisa mengubah matriks (kebutuhan operasional nyata), tetapi
tidak ada peran non-superuser yang boleh menyentuh tiga kunci itu untuk peran apa pun.
Ini memuaskan `test_super_admin_lockout_safe_perms_survive_tamper_attempt`
(`accounts/tests_priv_escalation.py:388`) yang sudah LULUS — pemanggilnya
`self.cc_holder` berperan `ADMIN_RS` **bukan** superuser, jadi skip berlaku dan
`LOCKOUT_SAFE_PERMS` SUPER_ADMIN tetap utuh.

**P0-7 — `can_access_control_center` untuk STAF_NAKES.**
`can_access_control_center` **ada di `LOCKOUT_SAFE_PERMS`**. Jadi perbaikan P0-6
**otomatis menutup P0-7**: pemanggil non-superuser tidak dapat lagi menyalakan
`can_access_control_center` untuk role `STAF_NAKES`. Ini satu perbaikan untuk dua
temuan — dan itu memang desain yang benar, karena keduanya adalah pelanggaran
invarian yang sama.

### 4.3 Test yang flip FAIL → PASS

| Test | Berkas:baris |
|------|--------------|
| `RolePermissionTamperTest.test_non_super_admin_cannot_flip_lockout_safe_perm` | `accounts/tests_priv_escalation.py:319` |
| `RolePermissionTamperTest.test_non_super_admin_cannot_grant_control_center_to_staf_nakes` | `accounts/tests_priv_escalation.py:345` |

### 4.4 Risiko terhadap test yang sudah LULUS

- `RolePermissionTamperTest.test_super_admin_lockout_safe_perms_survive_tamper_attempt`
  (`accounts/tests_priv_escalation.py:388`) — tetap lulus (lihat alasan di atas).
- `RolePermissionTamperTest.test_defaults_are_restorable` (`:403`) — tetap lulus;
  `reset_role_permissions` (`accounts/views.py:437-448`) tidak disentuh.
- `RolePermissionTamperTest.test_reset_role_permissions_requires_control_center`
  (`:376`) — tetap lulus.
- `sdm/tests/test_akses.py:314` (`test_role_permission_endpoint_updates_hc_capability`)
  — **perlu diperhatikan.** Test ini memanggil endpoint yang sama untuk mengubah
  kapabilitas HC. Kapabilitas HC **bukan** anggota `LOCKOUT_SAFE_PERMS`, jadi tidak
  terpengaruh. Tetap verifikasi setelah implementasi.
- `sdm/tests/test_akses.py:301` (`test_control_center_exposes_new_role_permission_fields`)
  — hanya memeriksa konteks template; tidak terpengaruh.

---

## 5. P0-8 / P0-9 — Gate `admin_required`

### 5.1 Defect terverifikasi

- `akreditasi/views.py:63-70` — `_is_admin`: `is_superuser or role in
  ('SUPER_ADMIN','ADMIN_RS')`. Tidak pernah membaca `RolePermissionConfig` maupun
  `custom_permissions`.
- `akreditasi/views.py:93` — `admin_required = user_passes_test(_is_admin,
  login_url='/accounts/login/')`.
- Enam view memakainya (semua terverifikasi):
  - `akreditasi/views.py:1355-1357` — `unit_list_create`
  - `akreditasi/views.py:1439-1441` — `unit_edit`
  - `akreditasi/views.py:1483-1486` — `unit_delete`
  - `akreditasi/views.py:1522-1524` — `pokja_manage`
  - `akreditasi/views.py:1532-1534` — `profil_rs_view`
  - `akreditasi/views.py:1576-1578` — `audit_log_view`

**P0-8:** karena gate berbasis string peran, `can_manage_units=False` untuk ADMIN_RS
tidak menutup `unit_edit`/`unit_delete`.

**P0-9:** `user_passes_test` mengalihkan **semua** kegagalan ke `login_url`, termasuk
pengguna yang sudah terautentikasi. Jadi otorisasi gagal tampak seperti masalah sesi
(HTTP 302 ke login) alih-alih HTTP 403.

### 5.2 Perbaikan — dua bagian

**Bagian A — gate berbasis kode izin.**

Ganti `admin_required` dengan dekorator yang membaca matriks izin. Desain yang dipilih:
**factory dekorator per izin**, bukan satu predikat "admin".

```python
# akreditasi/views.py — menggantikan baris 93
from django.core.exceptions import PermissionDenied

def require_permission(perm_code):
    """Gate berbasis kode izin (RolePermissionConfig / custom_permissions).

    - Anonim  -> redirect ke LOGIN_URL (perilaku login_required).
    - Terautentikasi tanpa izin -> PermissionDenied (HTTP 403), bukan 302.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")
            profile = getattr(request.user, 'profile', None)
            if request.user.is_superuser or (profile and profile.has_permission(perm_code)):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied(
                f"Anda tidak memiliki izin '{perm_code}' untuk mengakses halaman ini."
            )
        return _wrapped
    return decorator
```

Pemetaan izin per view:

| View | Izin |
|------|------|
| `unit_list_create` | `can_manage_units` |
| `unit_edit` | `can_manage_units` |
| `unit_delete` | `can_manage_units` |
| `pokja_manage` | `can_manage_units` |
| `profil_rs_view` | `can_manage_system_settings` |
| `audit_log_view` | `can_view_audit_log` |

**Mengapa `can_view_audit_log` untuk `audit_log_view`, bukan `can_manage_units`:**
`PERMISSION_DEFAULTS` (`accounts/models.py:18-27`) memberi ADMIN_RS
`can_view_audit_log=True`, dan `AuditLogAdminOnlyTest.test_admin_rs_diizinkan`
(`akreditasi/tests_security_owasp.py:138`) menuntut ADMIN_RS mendapat **200** di view
itu. STAF_NAKES punya `can_view_audit_log=False` (`accounts/models.py:54`), jadi tetap
ditolak. Ini juga lebih tepat secara semantik daripada memakai izin kelola-unit.

**Mengapa `can_manage_system_settings` untuk `profil_rs_view`:**
`PERMISSION_DEFAULTS['ADMIN_RS']['can_manage_system_settings'] = False`
(`accounts/models.py:27`). **INI MASALAH** — lihat §5.4.

**Bagian B — 403, bukan 302.**

`require_permission` menaikkan `PermissionDenied` untuk pengguna terautentikasi tanpa
izin. Django mengubahnya menjadi **HTTP 403** lewat `permission_denied` handler default.
Ini yang diminta `test_authenticated_unauthorized_gets_403_not_redirect`
(`akreditasi/tests_admin_gate.py:244`), yang secara eksplisit menuntut
`assertEqual(response.status_code, 403)`.

Agar pengguna anonim tetap dialihkan ke login (dan tidak mendapat 403),
`require_permission` memeriksa `is_authenticated` lebih dulu — ini yang menjaga
`NegativeControlAdminGateTest.test_anonymous_redirected_to_login`
(`akreditasi/tests_admin_gate.py:173`) tetap lulus.

### 5.3 Interaksi dengan `_is_nakes_or_admin` dan `portal_nakes`

`nakes_or_admin` (`akreditasi/views.py:95`) dan `portal_nakes`
(`akreditasi/views.py:1827`) **tidak disentuh**. `StafNakesAdminGateTest.test_staf_nakes_admitted_to_portal_nakes`
(`akreditasi/tests_admin_gate.py:122`) dan
`test_asesor_denied_portal_nakes` (`:153`) tetap lulus.

### 5.4 Risiko terhadap test yang sudah LULUS — WAJIB DIBACA

`akreditasi.tests_security_owasp.UnitEditAdminGateTest.test_admin_rs_diizinkan_unit_list`
(`akreditasi/tests_security_owasp.py:80`) menuntut ADMIN_RS mendapat **200** di
`unit_list`. Dengan pemetaan `can_manage_units`, ADMIN_RS punya
`can_manage_units=True` (`accounts/models.py:26`) → **200. Lulus.**

`akreditasi.tests_admin_gate.NegativeControlAdminGateTest.test_admin_rs_is_admitted`
(`akreditasi/tests_admin_gate.py:178`) menuntut ADMIN_RS mendapat **200** di
`audit_log` → `can_view_audit_log=True` → **200. Lulus.**

**Tetapi:** `akreditasi.tests_security_owasp.AdminGateIgnoresPermissionConfigTest.setUp`
(`akreditasi/tests_security_owasp.py:86-91`) menyetel `can_manage_units=False` untuk
ADMIN_RS. Test itu **hanya** memeriksa `unit_edit`. Karena state `RolePermissionConfig`
bersifat per-test (database test di-rollback), tidak ada kebocoran ke test lain.
**Verifikasi wajib:** pastikan tidak ada test lain dalam satu kelas yang berbagi
`setUp` dengan `can_manage_units=False` dan mengharapkan 200.

**`profil_rs_view` — risiko nyata.** `PERMISSION_DEFAULTS['ADMIN_RS']['can_manage_system_settings']`
adalah `False`. Jika `profil_rs_view` dipetakan ke `can_manage_system_settings`,
ADMIN_RS akan **kehilangan akses** ke halaman Profil RS — perubahan perilaku yang
tidak diminta test mana pun. **Tidak ada test yang memaku `profil_rs_view` untuk
ADMIN_RS** (dicek: `grep profil_rs` di seluruh test → hanya `StafNakesAdminGateTest.test_staf_nakes_denied_profil_rs`,
`akreditasi/tests_admin_gate.py:112`, yang menuntut STAF_NAKES ditolak).

**Keputusan:** `profil_rs_view` dipetakan ke **`can_manage_units`** (bukan
`can_manage_system_settings`), karena:
- ADMIN_RS punya `can_manage_units=True` → akses dipertahankan (tidak ada regresi).
- STAF_NAKES punya `can_manage_units=False` → tetap ditolak (test `:135` lulus).
- Profil RS adalah data struktur organisasi, bukan konfigurasi sistem (ambang batas /
  tema / freeze) — `can_manage_units` lebih tepat secara semantik.

### 5.5 Test yang flip FAIL → PASS

| Test | Berkas:baris |
|------|--------------|
| `AdminGateIgnoresPermissionConfigTest.test_can_manage_units_false_tetap_dapat_membuka_unit_edit` | `akreditasi/tests_security_owasp.py:106` |
| `AdminGateBypassesPermissionConfigTest.test_can_manage_units_false_does_not_close_unit_edit` | `akreditasi/tests_admin_gate.py:196` |
| `AdminGateBypassesPermissionConfigTest.test_can_manage_units_false_does_not_close_unit_delete` | `akreditasi/tests_admin_gate.py:223` |
| `AdminGateBypassesPermissionConfigTest.test_authenticated_unauthorized_gets_403_not_redirect` | `akreditasi/tests_admin_gate.py:244` |

### 5.6 Test yang LULUS dan harus tetap LULUS (regresi)

`StafNakesAdminGateTest` (7 test, `akreditasi/tests_admin_gate.py:80-139`),
`NegativeControlAdminGateTest` (6 test, `:162-198`),
`UnitEditAdminGateTest` (8 test, `akreditasi/tests_security_owasp.py:26-87`),
`AuditLogAdminOnlyTest` (2 test, `akreditasi/tests_security_owasp.py:125-141`).

Perhatikan: `_assert_denied` di `akreditasi/tests_admin_gate.py:36-58` menerima
`(302, 403)` **dan** memverifikasi bahwa 302 mengarah ke `'login'`. Karena
`require_permission` menaikkan 403 untuk pengguna terautentikasi, assertion
`self.assertIn(response.status_code, (302, 403))` tetap terpenuhi.

---

## 6. P0-10 … P0-14 — IDOR pasien, enumerasi, kebocoran PII, dekorator

### 6.1 Defect terverifikasi

| Temuan | Lokasi terverifikasi |
|--------|----------------------|
| P0-10 | `pasien/views.py:222-227` — `pasien_detail`; `@login_required` (baris 222) + `get_object_or_404(Pasien, pk=pk)` (baris 224), tanpa scope |
| P0-10 | `pasien/views.py:275-293` — `kunjungan_detail`; `@login_required` (baris 275) + `get_object_or_404(KunjunganPasien.objects.select_related(...), pk=pk)` (baris 277) |
| P0-11 | `pasien/views.py:213-220` — `pasien_daftar`; `qs = Pasien.objects.all()` (baris 216) |
| P0-12 | `pasien/views.py:802-838` — `api_cari_pasien`; `Pasien.objects.filter(...)` (baris 808-813), mengembalikan `nik`, `alamat`, `no_hp`, `no_bpjs`, `nama_pj`, `no_hp_pj`, `alamat_pj` (baris 818-833) |
| P0-13 | `pasien/views.py:839-864` — `api_cek_nik`; `Pasien.objects.filter(nik=nik).first()` (baris 846) |
| P0-14 | `pasien/decorators.py:7-27` — `require_patient_module` ada; dipasang hanya pada 9 view (terverifikasi: baris 464, 604, 751, 914, 1060, 1523, 1552, 1572, 1658) |

### 6.2 **Temuan kritis: tidak ada FK unit di aplikasi `pasien`**

Ini menentukan seluruh desain. Terverifikasi:

- `Pasien` (`pasien/models.py:13-72`): **tidak ada** `unit`/`unit_kerja`.
- `KunjunganPasien` (`pasien/models.py:277-…`): **tidak ada** `unit_kerja`. Yang ada:
  - `poliklinik = models.CharField(max_length=100, blank=True)` — `pasien/models.py:285`
    (string bebas, diisi dari `POLIKLINIK_CHOICES`; **bukan** FK)
  - `bed = models.ForeignKey(Bed, ...)` — `pasien/models.py:286`
  - `jenis_kunjungan` (`IGD`/`RAJAL`/`RANAP`) — `pasien/models.py:279`
- `Ruangan` (`pasien/models.py:142-163`): `kode`, `nama`, `kelas`, `jenis`, `kapasitas`.
  **Tidak ada** FK ke `UnitKerja`.
- `Bed` (`pasien/models.py:165-186`): FK ke `Ruangan` saja.
- `grep -rn "unit" pasien/migrations/*.py` → **nol hasil**.

**Kesimpulan: scope unit tidak dapat diturunkan.** Tidak ada jalur dari
`Pasien`/`KunjunganPasien` ke `UnitKerja`. `poliklinik` adalah string bebas yang tidak
dijamin cocok dengan `UnitKerja.code`, dan `Ruangan` tidak terhubung ke `UnitKerja`
sama sekali. Menurunkan scope dari `bed.ruangan.kode` akan memerlukan pencocokan
string dengan `UnitKerja.code` — rapuh, dan **tidak akan bekerja di test**, karena
test tidak membuat `Ruangan`/`Bed` sama sekali (lihat `akreditasi/tests_utils.py`
`make_kunjungan`, yang hanya menyetel `pasien`, `no_kunjungan`, `jenis_kunjungan`,
`tanggal_masuk`, `status`).

### 6.3 Perbaikan — desain konkret

**Lapis 1 — field scope eksplisit (WAJIB, migrasi baru).**

Tambahkan FK unit ke model yang menjadi subjek otorisasi:

```python
# pasien/models.py — KunjunganPasien
unit_kerja = models.ForeignKey(
    'akreditasi.UnitKerja',
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='kunjungan_pasien',
    verbose_name='Unit Kerja Pelayanan',
)

# pasien/models.py — Ruangan (agar bed-based visits dapat diturunkan)
unit_kerja = models.ForeignKey(
    'akreditasi.UnitKerja',
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='ruangan',
    verbose_name='Unit Kerja',
)
```

**Mengapa `KunjunganPasien.unit_kerja` dan bukan `Pasien.unit_kerja`:**
pasien adalah entitas lintas-unit (seorang pasien dirawat di IGD lalu pindah ke
rawat inap). Menempelkan unit pada `Pasien` akan salah secara domain dan akan
memaksa penulisan ulang saat pasien berpindah unit. Unit adalah properti **kunjungan**.

**Mengapa `Ruangan.unit_kerja` juga:** agar kunjungan lama yang hanya punya `bed`
dapat diturunkan unitnya, dan agar `bed_management` (sudah ber-guard `'ranap'`) dapat
memfilter ruangan per unit.

**Lapis 2 — resolusi scope terpusat (bukan tersebar di setiap view).**

Tambahkan helper di `pasien/decorators.py` (satu tempat, dipakai semua view):

```python
def get_unit_scope(profile):
    """Himpunan UnitKerja yang boleh dibaca profil ini.

    - None  -> tanpa batas (SUPER_ADMIN/ADMIN_RS/DIREKTUR, atau superuser).
    - set() -> tidak ada unit (profil tanpa unit_kerja); hanya modul master.
    - {UnitKerja, ...} -> unit sendiri + seluruh descendant.
    """
```

Aturan:
- `is_superuser` atau role ∈ `{'SUPER_ADMIN','ADMIN_RS'}` → `None` (tanpa batas).
  Ini menjaga `test_admin_rs_diizinkan_*` dan seluruh test akreditasi tetap lulus.
- Tanpa `unit_kerja` → himpunan kosong (fail-closed).
- Selain itu → unit sendiri + seluruh **descendant** (walk `children` rekursif).
  Termasuk descendant karena `KEPALA_UNIT` sebuah direktorat harus melihat unit di
  bawahnya; ini konsisten dengan `HcGrant.include_descendants` yang sudah ada
  (`sdm/models/akses.py`).

Tambahkan queryset helper:

```python
def scope_pasien_qs(qs, profile):
    """Batasi queryset Pasien ke pasien yang punya kunjungan di unit scope."""
    scope = get_unit_scope(profile)
    if scope is None:
        return qs
    if not scope:
        return qs.none()
    return qs.filter(kunjungan__unit_kerja__in=scope).distinct()

def scope_kunjungan_qs(qs, profile):
    scope = get_unit_scope(profile)
    if scope is None:
        return qs
    if not scope:
        return qs.none()
    return qs.filter(unit_kerja__in=scope)
```

**Mengapa `kunjungan__unit_kerja__in=scope` untuk `Pasien`, bukan `Pasien.unit_kerja`:**
pasien tidak punya unit. Pasien "terlihat" jika ia punya minimal satu kunjungan di
unit yang boleh dibaca. Ini juga yang membuat
`test_pasien_detail_lintas_unit_ditolak` lulus: `pasien_b` hanya punya kunjungan
`kunj_b` di unit B, dan perawat unit A tidak punya unit B dalam scope → 404.

**Lapis 3 — penerapan per view.**

| View | Perubahan |
|------|-----------|
| `pasien_detail` (`:222-227`) | `@require_patient_module('master_pasien')` + ganti `get_object_or_404(Pasien, pk=pk)` menjadi `get_object_or_404(scope_pasien_qs(Pasien.objects.all(), request.user.profile), pk=pk)` |
| `kunjungan_detail` (`:275-293`) | `@require_patient_module('riwayat')` + `get_object_or_404(scope_kunjungan_qs(KunjunganPasien.objects.select_related(...), request.user.profile), pk=pk)` |
| `pasien_daftar` (`:213-220`) | `@require_patient_module('master_pasien')` + `qs = scope_pasien_qs(Pasien.objects.all(), request.user.profile)` |
| `api_cari_pasien` (`:802-838`) | `@require_patient_module('master_pasien')` + scope queryset; **dan** redaksi field PII (lihat di bawah) |
| `api_cek_nik` (`:839-864`) | `@require_patient_module('master_pasien')` + scope queryset; **dan** redaksi field PII |
| `dashboard` (`:183-211`) | `@require_patient_module('master_pasien')` |
| `resume_pdf` (`:521-531`) | `@require_patient_module('riwayat')` + scope kunjungan |
| `resep_buat` (`:536-563`) | `@require_patient_module('farmasi')` + scope kunjungan |
| `kunjungan_daftar` (`:257-273`) | `@require_patient_module('pendaftaran')` + scope kunjungan |
| `kunjungan_baru` (`:295-…`) | `@require_patient_module('pendaftaran')` |

**Pemilihan nama modul untuk dekorator — mengapa `'master_pasien'`:**
`get_allowed_patient_modules()` (`accounts/models.py:236-…`) **selalu** menyertakan
`'master_pasien'` dan `'riwayat'` di basis `allowed` (baris 248, 253), untuk setiap
profil yang punya unit. Jadi memasang `'master_pasien'` pada `pasien_detail` dan
`pasien_daftar` **tidak** menolak apoteker — dan itu memang benar, karena apoteker
sah membaca identitas pasien. Yang menutup P0-14 adalah
`test_view_baca_inti_tanpa_guard`, yang menuntut `pasien_daftar` **menolak** apoteker.

> **PERHATIKAN — ini konflik yang harus diselesaikan dengan hati-hati.**
> `pasien/tests_security_owasp.py:202-223` (`test_view_baca_inti_tanpa_guard`) menuntut
> `pasien_daftar` mengembalikan `(403, 404)` untuk **apoteker**. Tetapi apoteker
> **memegang** `'master_pasien'` (dipaku oleh
> `test_module_matrix_sesuai_ekspektasi_dekorator`, `pasien/tests_security_owasp.py:170-182`,
> yang sudah LULUS dan **tidak boleh** berubah).
>
> Jadi `@require_patient_module('master_pasien')` **tidak akan** membuat test itu
> lulus. Modul yang benar untuk `pasien_daftar` adalah **`'pendaftaran'`** — apoteker
> tidak memegangnya (dipaku di baris 161: `assertNotIn('farmasi', igd_modules)` dan
> matriks `farmasi` = `{farmasi, master_pasien, riwayat}`).
>
> **Keputusan final:** `pasien_daftar` memakai `@require_patient_module('pendaftaran')`.
> Ini juga benar secara domain: daftar pasien adalah meja pendaftaran/admisi.
> `dashboard` memakai `'pendaftaran'` untuk alasan yang sama
> (`test_dashboard_is_unguarded`, `pasien/tests_object_authz.py:315`, menuntut
> apoteker ditolak).
>
> **Konsekuensi:** perawat IGD memegang `'pendaftaran'` (dipaku di
> `pasien/tests_object_authz.py:246` dan `pasien/tests_security_owasp.py:170`), jadi
> `test_pasien_daftar_lists_all_patients_regardless_of_unit`
> (`pasien/tests_object_authz.py:139`) tetap **lulus dekorator** dan baru lulus
> setelah **scope queryset** diterapkan. Inilah mengapa P0-11 dan P0-14 adalah dua
> perbaikan yang keduanya diperlukan.

**Lapis 4 — redaksi PII di API (P0-12/P0-13).**

Scope queryset saja **tidak cukup** untuk P0-12/P0-13, karena test memakai apoteker
yang sah membaca pasien (`master_pasien`), dan yang gagal adalah **field PII** yang
dikembalikan. Test memeriksa `results[0]` dan gagal bila ada hasil.

Dua perubahan diperlukan:
1. **Scope queryset** — apoteker unit farmasi tidak boleh melihat pasien yang hanya
   punya kunjungan di unit IGD.
2. **Minimalisasi field** — endpoint pencarian hanya boleh mengembalikan field yang
   diperlukan untuk memilih pasien: `id`, `no_rm`, `nama_lengkap`, `tanggal_lahir`,
   `umur`, `jenis_kelamin`. **Hapus** `nik`, `alamat`, `no_hp`, `no_bpjs`, `nama_pj`,
   `hubungan_pj`, `no_hp_pj`, `alamat_pj` dari respons pencarian.

Untuk `api_cek_nik`, ubah agar hanya mengembalikan `{'exists': bool}` tanpa payload
`pasien` — endpoint ini hanya dipakai untuk cek duplikasi NIK saat pendaftaran, dan
identitas lengkap sudah tersedia lewat `pasien_detail` yang ber-scope.

**Mengapa ini bukan "mengurangi cakupan":** permintaan aslinya adalah menutup
kebocoran PII. Mengembalikan NIK/alamat/BPJS ke setiap pengguna yang login adalah
defect, bukan fitur. Test menuntut `results == []` dan `exists == False`
(`pasien/tests_security_owasp.py:94`, `:135`), jadi scope queryset adalah yang
membuat assertion itu benar; redaksi field adalah pertahanan berlapis agar kebocoran
tidak kembali bila scope kelak dilonggarkan.

**Lapis 5 — pengisian `unit_kerja` saat pembuatan kunjungan.**
`kunjungan_baru` (`pasien/views.py:295-…)` harus menyetel `unit_kerja` dari unit
pengguna pembuat (atau dari `bed.ruangan.unit_kerja` bila bed dipilih). Untuk data
lama, lihat §6.3a di bawah.

### 6.3a Prasyarat Workstream C — migrasi, backfill, dan semantik NULL

Bagian ini wajib diselesaikan **sebelum** view apa pun difilter. Urutannya:
migrasi skema → backfill data → helper scope → view.

#### (1) Migrasi harus nullable

```python
unit_kerja = models.ForeignKey(
    'akreditasi.UnitKerja',
    on_delete=models.SET_NULL,
    null=True, blank=True,          # WAJIB
    related_name='kunjungan_pasien',
    verbose_name='Unit Kerja Pelayanan',
)
```

`null=True` bukan pilihan gaya. Ada data produksi di `db.sqlite3` dan pada deployment
yang memakai Supabase, dan tidak ada satu pun baris `KunjunganPasien` yang dapat
dijamin punya unit pada saat migrasi berjalan. Migrasi non-nullable akan gagal pada
`AddField` tanpa default, atau memaksa default arbitrer yang **salah secara data**
(mis. menempelkan semua kunjungan lama ke satu unit). `on_delete=SET_NULL` juga
disengaja: menghapus `UnitKerja` tidak boleh menghapus riwayat kunjungan pasien.

#### (2) Strategi backfill — dan mengapa dua dari tiga sumbernya TIDAK dapat dipakai

Saya memeriksa namespace kode yang sebenarnya ada di repo. **Ketiganya terpisah dan
tidak bertumpang tindih:**

| Sumber | Contoh nilai aktual | Sumber di repo |
|--------|--------------------|----------------|
| `UnitKerja.code` | `DIR-MED`, `BID-YAN`, `RANAP`, `IGD`, `FARM`, `LAB`, `RAJAL` | `seed_all_roles.py:71-113`, `seed_data.py:89-190` |
| `Ruangan.kode` | `IGD-01`, `IGD-02`, `VIP-A`, `R-K1`, `R-K2`, `R-K3`, `ICU-01`, `OK-01` | `pasien/management/commands/seed_pasien_data.py:15-23` |
| `KunjunganPasien.poliklinik` | `'Bangsal Bedah Dahlia'`, `'Bangsal Mawar'`, `'IGD'`, `'Poli Penyakit Dalam'`, `'Bangsal Melati'` | `seed_pasien_data.py:82,105,128,150,167` |

`Ruangan.kode` (`IGD-01`) **bukan** `UnitKerja.code` (`IGD`). `poliklinik` menyimpan
**label tampilan** dari `POLIKLINIK_CHOICES` (mis. `'Poli Jantung & Pembuluh Darah'`,
`pasien/models.py:200-219`), bukan kode. `UnitKerja.name` juga tidak cocok: nilainya
organisasional (`'Direktorat Pelayanan Medik & Keperawatan'`,
`'Sekretariat Dewas, Direksi & Komite Mutu'`, `seed_hospital_type_b.py:16-47`).

**Konsekuensi: backfill berbasis pencocokan string TIDAK boleh dijadikan mekanisme
utama.** Rencana yang benar, dalam urutan presedensi:

1. **Dari `bed.ruangan.unit_kerja`** (setelah `Ruangan.unit_kerja` di-backfill, lihat
   (4)). Ini satu-satunya jalur yang **eksak** — FK ke FK, tanpa pencocokan string.
   ```python
   for k in KunjunganPasien.objects.filter(bed__isnull=False, unit_kerja__isnull=True):
       KunjunganPasien.objects.filter(pk=k.pk).update(
           unit_kerja_id=k.bed.ruangan.unit_kerja_id)
   ```
2. **Dari `jenis_kunjungan` ke unit default yang dikonfigurasi**, bukan dari string.
   Tambahkan pemetaan eksplisit di satu konstanta, diisi operator:
   ```python
   # pasien/unit_scope.py
   DEFAULT_UNIT_BY_JENIS = {
       'IGD':   'IGD',
       'RAJAL': 'RAJAL',
       'RANAP': 'RANAP',
   }
   ```
   Nilai di kanan adalah `UnitKerja.code` yang **sudah ada** di seed
   (`seed_all_roles.py:88-113`, `seed_data.py:157-190`). Ini bukan tebakan: `IGD`,
   `RAJAL`, dan `RANAP` adalah kode unit yang benar-benar dibuat oleh seed, dan
   `jenis_kunjungan` hanya punya tiga nilai (`pasien/models.py:278`). Baris yang
   kode targetnya tidak ada di `UnitKerja` **dibiarkan NULL** — jangan mengarang unit.
3. **Sisanya dibiarkan NULL.** Tidak ada pencocokan `poliklinik` → `UnitKerja.code`,
   dan tidak ada pencocokan `Ruangan.kode` → `UnitKerja.code`. Keduanya akan
   menghasilkan penugasan yang salah dan tidak dapat diaudit.

Backfill adalah **manajemen command terpisah**
(`pasien/management/commands/backfill_unit_kunjungan.py`), **bukan** `RunPython` di
dalam migrasi skema. Alasan: backfill harus dapat dijalankan ulang, dilaporkan
jumlahnya, dan dijalankan terpisah dari deploy skema. Migrasi data di dalam `RunPython`
tidak dapat diulang tanpa `reverse_code`, dan memblokir deploy bila ada data yang tidak
terduga.

Command mencetak ringkasan (jumlah terisi dari bed / dari jenis / tetap NULL) agar
operator dapat memutuskan apakah sisa NULL perlu ditangani manual.

#### (3) Semantik NULL — **fail closed (tidak terlihat)**

Keputusan: kunjungan dengan `unit_kerja IS NULL` **tidak terlihat** oleh siapa pun
kecuali `is_superuser` / `SUPER_ADMIN` / `ADMIN_RS` (yaitu mereka yang `get_unit_scope()`
kembalikan `None`).

```python
def scope_kunjungan_qs(qs, profile):
    scope = get_unit_scope(profile)
    if scope is None:          # admin: tanpa batas, termasuk baris NULL
        return qs
    if not scope:
        return qs.none()
    return qs.filter(unit_kerja__in=scope)   # NULL tidak pernah cocok
```

**Justifikasi:** ini data rekam medis. Bila scope tidak dapat ditentukan, jawaban yang
aman adalah "tidak ada akses", bukan "akses penuh". Fail-open akan membuat setiap baris
yang gagal di-backfill menjadi kebocoran PII lintas unit — persis kerentanan yang
sedang ditutup. Fail-closed hanya menimbulkan ketidaknyamanan operasional (petugas
harus mengisi unit kunjungan), yang dapat diperbaiki; kebocoran tidak.

**Konsekuensi yang harus disadari:** setelah P0-10…P0-14 mendarat, kunjungan lama yang
`unit_kerja`-nya NULL akan menghilang dari `kunjungan_daftar`, `pasien_daftar`, dan
`pasien_detail` bagi semua peran non-admin. Karena itu backfill (2) harus dijalankan
**segera setelah** migrasi, dan jumlah sisa NULL dilaporkan ke operator.

**Test yang akan menangkap pilihan yang salah:** tidak ada test yang secara eksplisit
membuat kunjungan ber-`unit_kerja` NULL. Yang menangkapnya adalah
`pasien/tests_object_authz.py:139`
(`test_pasien_daftar_lists_all_patients_regardless_of_unit`) dan
`pasien/tests_security_owasp.py:37` (`test_pasien_detail_lintas_unit_ditolak`): kedua
test membuat kunjungan **tanpa** `unit_kerja` (lewat `make_kunjungan`, yang tidak
menyetel field itu) dan menuntut perawat unit A **tidak** melihatnya. Fail-open akan
membuat kedua test itu melihat baris NULL dan **tetap GAGAL**. Jadi fail-closed bukan
hanya lebih aman — ia juga satu-satunya pilihan yang lulus test.

> **Catatan implementasi penting.** Karena `make_kunjungan`
> (`akreditasi/tests_utils.py:75-81`) tidak menyetel `unit_kerja`, seluruh fixture test
> P0-10…P0-14 menghasilkan kunjungan ber-`unit_kerja` NULL. Ini berarti:
> - **`test_pasien_detail_lintas_unit_ditolak` dan `test_kunjungan_detail_lintas_unit_ditolak`
>   lulus lewat jalur NULL**, bukan lewat perbandingan unit. Yang diuji adalah
>   "perawat unit A tidak melihat baris tanpa unit", bukan "perawat unit A tidak
>   melihat baris unit B".
> - Perbandingan unit yang sebenarnya (unit A vs unit B, keduanya terisi) **tidak
>   diuji oleh suite ini.** Implementasi harus tetap menambah test unit-scope yang
>   mengisi `unit_kerja` pada kedua sisi; suite P0 saat ini tidak membuktikan filter
>   `unit_kerja__in=scope` bekerja, hanya membuktikan NULL tidak bocor.
> - Jangan "memperbaiki" ini dengan mengubah `akreditasi/tests_utils.py` — file itu
>   adalah bagian dari kontrak test.

#### (4) Backfill `Ruangan.unit_kerja`

**Tidak dapat dilakukan dari `Ruangan.kode`.** `Ruangan.kode` bernilai `IGD-01`,
`VIP-A`, `R-K1`, `ICU-01`, `OK-01` (`seed_pasien_data.py:15-23`), sedangkan
`UnitKerja.code` bernilai `IGD`, `RANAP`, `FARM`, `LAB`. Tidak ada aturan pencocokan
yang jujur di antara keduanya — `R-K1` tidak memberi tahu apakah unitnya `RANAP` atau
unit lain, dan `VIP-A` tidak memetakan ke kode unit mana pun.

Yang **dapat** dipakai adalah `Ruangan.jenis`, yang nilainya
`{'RANAP','IGD','RAJAL','OK','ICU'}` (`pasien/models.py:162`). Tiga di antaranya
(`RANAP`, `IGD`, `RAJAL`) **sama persis** dengan `UnitKerja.code` yang dibuat seed.
Jadi:

```python
# backfill Ruangan.unit_kerja dari jenis, hanya untuk jenis yang kodenya ada
for r in Ruangan.objects.filter(unit_kerja__isnull=True):
    u = UnitKerja.objects.filter(code=r.jenis).first()
    if u:
        Ruangan.objects.filter(pk=r.pk).update(unit_kerja=u)
```

`OK` dan `ICU` **tidak** punya padanan `UnitKerja.code` di seed, jadi ruangan berjenis
itu dibiarkan NULL. Operator dapat memetakannya manual lewat Pusat Kontrol bila perlu.

**Urutan eksekusi yang benar:**
1. Migrasi skema (`KunjunganPasien.unit_kerja`, `Ruangan.unit_kerja`, keduanya nullable).
2. Backfill `Ruangan.unit_kerja` dari `Ruangan.jenis`.
3. Backfill `KunjunganPasien.unit_kerja` dari `bed.ruangan.unit_kerja` (presedensi 1).
4. Backfill sisa dari `DEFAULT_UNIT_BY_JENIS` (presedensi 2).
5. Laporkan sisa NULL.
6. Baru kemudian pasang filter scope di view.

### 6.4 Test yang flip FAIL → PASS

| Temuan | Test | Berkas:baris |
|--------|------|--------------|
| P0-10 | `PatientPiiIdorTest.test_pasien_detail_lintas_unit_ditolak` | `pasien/tests_security_owasp.py:37` |
| P0-10 | `PatientPiiIdorTest.test_kunjungan_detail_lintas_unit_ditolak` | `pasien/tests_security_owasp.py:55` |
| P0-10 | `PatientIdorTest.test_nakes_igd_cannot_read_pasien_detail_outside_unit` | `pasien/tests_object_authz.py:105` |
| P0-10 | `PatientIdorTest.test_nakes_igd_cannot_read_kunjungan_detail_outside_unit` | `pasien/tests_object_authz.py:123` |
| P0-11 | `PatientIdorTest.test_pasien_daftar_lists_all_patients_regardless_of_unit` | `pasien/tests_object_authz.py:139` |
| P0-12 | `PatientSearchApiLeakageTest.test_api_cari_pasien_membocorkan_pii` | `pasien/tests_security_owasp.py:94` |
| P0-12 | `PatientPiiApiTest.test_api_cari_pasien_leaks_pii_across_modules` | `pasien/tests_object_authz.py:173` |
| P0-13 | `PatientSearchApiLeakageTest.test_api_cek_nik_membocorkan_pii` | `pasien/tests_security_owasp.py:116` |
| P0-13 | `PatientPiiApiTest.test_api_cek_nik_leaks_pii` | `pasien/tests_object_authz.py:196` |
| P0-14 | `PatientModuleDecoratorCoverageTest.test_view_baca_inti_tanpa_guard` | `pasien/tests_security_owasp.py:202` |
| P0-14 | `PatientModuleScopeTest.test_core_read_views_are_unguarded` | `pasien/tests_object_authz.py:288` |
| P0-14 | `PatientModuleScopeTest.test_dashboard_is_unguarded` | `pasien/tests_object_authz.py:315` |

### 6.5 Risiko terhadap test yang sudah LULUS

- `PatientPiiIdorTest.test_anonymous_tidak_dapat_membaca_pasien_detail`
  (`pasien/tests_security_owasp.py:71`) — tetap lulus: `require_patient_module`
  mengalihkan anonim ke login (`pasien/decorators.py:16-19`).
- `PatientSearchApiLeakageTest.test_anonymous_tidak_dapat_memanggil_api_pii`
  (`:139`) — tetap lulus, alasan sama.
- `PatientModuleScopeTest.test_module_matrix_matches_decorator_expectations`
  (`pasien/tests_object_authz.py:246`) dan
  `PatientModuleDecoratorCoverageTest.test_module_matrix_sesuai_ekspektasi_dekorator`
  (`pasien/tests_security_owasp.py:170`) — **tidak boleh berubah**;
  `get_allowed_patient_modules()` tidak disentuh.
- `PatientModuleScopeTest.test_farmasi_view_is_guarded` (`:249`),
  `test_igd_view_is_guarded_against_pharmacy_user` (`:259`),
  `test_farmasi_view_is_guarded_against_igd_user` (`:270`) — tetap lulus, dekorator
  yang sudah ada tidak diubah.
- `PatientModuleDecoratorCoverageTest.test_view_ber_guard_menolak_modul_luar` (`:168`)
  dan `test_view_ber_guard_diizinkan_modul_sesuai` (`:177`) — tetap lulus.
- **`akreditasi/tests_unit_rbac.py`** — memakai `get_allowed_patient_modules()`
  langsung; tidak terpengaruh oleh perubahan view. Verifikasi setelah implementasi.

---

## 7. P0-15 — Token rekrutmen

### 7.1 Defect terverifikasi

- `sdm/models/rekrutmen.py:100-143` — `class Pelamar`.
  - `sdm/models/rekrutmen.py:120` — `id = models.UUIDField(primary_key=True, default=uuid.uuid4, ...)`
  - `sdm/models/rekrutmen.py:121-125` — `token = models.CharField('Token Akses',
    max_length=64, unique=True, default=uuid.uuid4, ...)`
- `sdm/models/rekrutmen.py:406-443` — `class KonfirmasiOffering`.
  - `sdm/models/rekrutmen.py:413` — `id = models.UUIDField(primary_key=True, default=uuid.uuid4, ...)`
  - `sdm/models/rekrutmen.py:418-420` — `token = models.CharField('Token Konfirmasi',
    max_length=64, unique=True, default=uuid.uuid4)`
- Pembanding yang benar: `sdm/services/undangan.py:44-45` —
  ```python
  token = secrets.token_urlsafe(32)
  token_digest = hashlib.sha256(token.encode()).hexdigest()
  ```

### 7.2 Keputusan: **JANGAN pakai pola hashed-storage untuk token rekrutmen**

Ini keputusan yang disengaja, dengan alasan konkret dari kode:

**Alasan 1 — token rekrutmen adalah lookup key, bukan verifier.**
Kedua token dipakai sebagai kunci pencarian langsung di **13 tempat**:
- `sdm/rekrutmen_portal_views.py:78, 103, 134, 184, 237` —
  `get_object_or_404(Pelamar, token=token)` / `get_object_or_404(KonfirmasiOffering, token=token)`
- `sdm/services/mcu_offering_rekrutmen.py:184` —
  `KonfirmasiOffering.objects.filter(token=token).first()`

Pola `undangan.py` bekerja karena alur aktivasi **menerima token mentah dari URL**,
menghitung digest, lalu mencari `token_digest`
(`accounts/staff_activation_views.py:24-26`, `sdm/services/undangan.py:156-166`).
Untuk meniru itu di rekrutmen, **setiap** dari 13 titik harus diubah menjadi
hash-then-query, dan `max_length=64` harus tetap cukup untuk hex SHA-256 (64 karakter
— pas).

**Alasan 2 — pola hashed tidak menambah keamanan yang diminta test.**
Test memeriksa **bentuk token yang dihasilkan**, bukan cara penyimpanan:
`sdm/tests/security_owasp.py:78-84` dan `:88-93` memeriksa
`len(token) == 36 and token.count('-') == 4` pada `pelamar.token` / `offering.token`
**setelah baris dibuat**. Artinya test membaca **nilai kolom yang tersimpan**. Jika
token di-hash, nilai kolom akan menjadi 64 karakter hex dan test **tetap lulus** —
tetapi juga akan lulus tanpa hash. Jadi hashing bukan yang diminta.

**Alasan 3 — `Pelamar.token` secara eksplisit didokumentasikan sebagai nilai yang
harus dapat ditampilkan ulang.** Docstring model
(`sdm/models/rekrutmen.py:101-106`) menyatakan: *"Losing the token means SDM must
re-issue one, which is why it is stored rather than hashed."* Mengubahnya menjadi
hashed akan **mematahkan kemampuan SDM menampilkan ulang tautan pelamar** — regresi
fungsional nyata yang tidak diminta siapa pun.

**Keputusan:** ganti **hanya sumber entropi**. `default=uuid.uuid4` →
`default=secrets.token_urlsafe`. Ini:
- Menutup P0-15 (token bukan lagi pola UUID 36 karakter).
- Tidak mengubah satu pun dari 13 titik lookup.
- Tidak memerlukan migrasi skema (kolom `CharField(max_length=64)` sudah cukup:
  `token_urlsafe(32)` menghasilkan 43 karakter).
- Tidak memerlukan migrasi data untuk baris lama — lihat di bawah.

**Nilai yang dipilih: `secrets.token_urlsafe(32)`** (bukan 43/48), agar **identik**
dengan `sdm/services/undangan.py:44`. Satu konvensi, bukan dua. Panjang 43 karakter
aman di dalam `max_length=64`.

Bentuk yang dirancang:

```python
# sdm/models/rekrutmen.py — tambah import secrets di atas
def _generate_access_token() -> str:
    """Token capability untuk portal rekrutmen (43 char, 256 bit entropi)."""
    return secrets.token_urlsafe(32)

# Pelamar
token = models.CharField(
    'Token Akses', max_length=64, unique=True,
    default=_generate_access_token,
    help_text='Capability URL untuk pelamar mengakses lamaran sendiri.',
)

# KonfirmasiOffering
token = models.CharField(
    'Token Konfirmasi', max_length=64, unique=True,
    default=_generate_access_token,
)
```

**Mengapa fungsi bernama, bukan `default=secrets.token_urlsafe(32)` langsung:**
`default=secrets.token_urlsafe(32)` akan **dipanggil sekali saat import** dan
menghasilkan token yang sama untuk semua baris. Ini bug klasik. `default=` harus
menerima callable. `secrets.token_urlsafe` tanpa argumen akan default ke 32 byte
(`secrets.token_urlsafe(nbytes=32)`), jadi `default=secrets.token_urlsafe` juga benar
— tetapi fungsi bernama lebih eksplisit tentang entropi yang dijanjikan dan
memudahkan perubahan di satu tempat.

### 7.3 Migrasi

**Migrasi skema:** `AlterField` pada `Pelamar.token` dan `KonfirmasiOffering.token`.
Perubahan hanya pada `default` (Python-side), jadi tidak mengubah kolom database —
Django tetap membuat migrasi karena `default` adalah bagian dari definisi field.

**Migrasi data untuk baris lama: TIDAK DIPERLUKAN, dan TIDAK BOLEH dilakukan.**

Alasan: token lama adalah **capability yang sedang aktif dipegang kandidat**. Kandidat
sudah menerima email berisi tautan `.../portal/<token-uuid4>/`. Mengganti token lama
akan **mematahkan tautan yang sudah terkirim** dan mengunci kandidat dari lamarannya.
Token UUID4 yang sudah ada tetap berfungsi (lookup tidak berubah), tetap unik, dan
tetap 122 bit acak — kelemahannya marginal dan hanya relevan untuk token yang
**baru dibuat**. Baris lama akan habis sendiri seiring siklus rekrutmen selesai.

**Yang harus ada di migrasi data (opsional, aman):** tidak ada. Jika tim ingin
mempercepat transisi, satu-satunya operasi yang aman adalah membuat ulang token untuk
baris berstatus **selesai** (`Lamaran.status` terminal), bukan yang aktif. Ini di luar
lingkup P0-15 dan **tidak** direkomendasikan untuk iterasi ini.

### 7.4 Test yang flip FAIL → PASS

| Test | Berkas:baris |
|------|--------------|
| `RecruitmentTokenStrengthTest.test_token_pelamar_bukan_uuid4` | `sdm/tests/security_owasp.py:77` |
| `RecruitmentTokenStrengthTest.test_token_offering_bukan_uuid4` | `sdm/tests/security_owasp.py:95` |

### 7.5 Risiko terhadap test yang sudah LULUS

- `RecruitmentTokenStrengthTest.test_aktivasi_staf_memakai_token_urlsafe`
  (`sdm/tests/security_owasp.py:112`) — tidak tersentuh.
- `OfferingAccessTest` (3 test, `:111-160`) — memakai `offering.token` sebagai argumen
  URL; nilai token tidak diasumsikan berbentuk UUID. `test_portal_offering_hanya_untuk_token_sendiri`
  (`:113`) **membuat** `str(uuid.uuid4())` untuk kasus negatif — itu tetap valid
  karena hanya menguji token yang tidak ada. Tetap lulus.
- `sdm/tests/test_private_documents.py` — tidak menyentuh `Pelamar`/`KonfirmasiOffering`.
- **Perlu diperiksa:** test rekrutmen lain yang mungkin menyetel `token=` secara
  eksplisit atau mengasumsikan format UUID. `grep -rn "\.token" sdm/tests/` saat
  implementasi.

---

## 8. P0-16 — SameSite

### 8.1 Defect terverifikasi

`config/settings.py` **tidak pernah** menetapkan `SESSION_COOKIE_SAMESITE` maupun
`CSRF_COOKIE_SAMESITE`. Terverifikasi dengan
`grep -n "SAMESITE" config/settings.py` → **nol hasil**.

Yang ada:
- `config/settings.py:131` — `SESSION_COOKIE_HTTPONLY = True`
- `config/settings.py:132` — `CSRF_COOKIE_HTTPONLY = True`
- `config/settings.py:133` — `SESSION_COOKIE_AGE = 28800`
- `config/settings.py:134` — `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`
- `config/settings.py:122-129` — blok `if not DEBUG:` menyetel
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS, `SECURE_CONTENT_TYPE_NOSNIFF`.

### 8.2 Perbaikan

Tambahkan **satu baris**, di luar blok `if not DEBUG:` (baris 122-129), tepat setelah
baris 132:

```python
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'
```

**Nilai `'Strict'`, bukan `'Lax'`.** Alasan (lihat §1.1):
`akreditasi/tests_session_security.py:133-154`
(`CookieFlagTest.test_samesite_is_explicitly_strict`) menuntut `'Strict'` secara
literal (`self.assertEqual(configured, 'Strict')`). Nilai `'Lax'` akan **tetap
membuat test itu GAGAL**.

Kedua test terpuaskan oleh `'Strict'`:
- `CookieFlagTest.test_samesite_is_explicitly_strict` — menuntut `'Strict'` → PASS.
- `CookieSecurityTest.test_samesite_dilaporkan_secara_eksplisit`
  (`accounts/tests_security_owasp.py:210`) — menuntut ∈ `{'Lax','Strict'}` → PASS.

**Mengapa di luar blok `if not DEBUG:`:** SameSite bukan pengaturan yang bergantung
pada HTTPS. Cookie tanpa SameSite rentan terhadap CSRF di dev maupun produksi, dan
`DEBUG=True` adalah default non-produksi yang **dipakai CI** (workflow tidak menyetel
`DJANGO_DEBUG`). Menaruhnya di dalam blok `if not DEBUG:` akan membuatnya tidak
berlaku di lingkungan test.

### 8.3 Interaksi dengan `CSRF_COOKIE_HTTPONLY=True`

Ini titik yang mudah salah. `CSRF_COOKIE_HTTPONLY = True`
(`config/settings.py:132`) berarti JavaScript **tidak dapat** membaca cookie
`csrftoken`. Django mengantisipasi ini: template yang memakai `{% csrf_token %}`
menyisipkan token ke dalam HTML form, sehingga JS tidak perlu membaca cookie untuk
form biasa.

**Interaksi yang harus diperhatikan saat implementasi:**
- `SESSION_COOKIE_SAMESITE = 'Strict'` berarti cookie sesi **tidak dikirim** pada
  navigasi lintas situs **sama sekali**, termasuk klik tautan dari email/WhatsApp ke
  halaman internal RS. Pengguna akan tampak "logout" saat tiba dari tautan eksternal,
  lalu harus memuat ulang halaman sekali. Ini **trade-off yang disengaja** dan yang
  diminta test.
- `CSRF_COOKIE_SAMESITE = 'Strict'` dapat mematahkan alur yang memulai POST dari
  origin eksternal. Untuk sistem ini, alur publik (portal rekrutmen) memakai
  **token capability di URL**, bukan cookie sesi, jadi tidak terpengaruh.
- **Kombinasi `CSRF_COOKIE_HTTPONLY=True` + `CSRF_COOKIE_SAMESITE='Strict'`** berarti
  endpoint JSON yang mengirim token CSRF lewat header `X-CSRFToken` (dibaca JS) tidak
  dapat mengambil token dari cookie. Endpoint seperti `update_user_custom_permissions`
  dan `update_role_permissions` (`accounts/views.py:410`, `:455`) menerima
  `content_type='application/json'`. **Periksa saat implementasi** bagaimana template
  Pusat Kontrol mengirim token — bila lewat `{% csrf_token %}` di form tersembunyi,
  tidak ada masalah; bila lewat `document.cookie`, itu sudah rusak sebelum perubahan
  ini dan bukan regresi baru.

**Tidak ada test yang memaku perilaku lintas-situs**, jadi tidak ada regresi test.
Risiko murni operasional dan harus dicatat di changelog.

### 8.4 Test yang flip FAIL → PASS

| Test | Berkas:baris |
|------|--------------|
| `CookieFlagTest.test_samesite_is_explicitly_strict` | `akreditasi/tests_session_security.py:133` |

### 8.5 Risiko terhadap test yang sudah LULUS

`CookieSecurityTest.test_samesite_dilaporkan_secara_eksplisit`
(`accounts/tests_security_owasp.py:210`) — tetap lulus (`'Strict'` ∈ `{'Lax','Strict'}`).
`CookieFlagTest.test_secure_flags_on_login_response`
(`akreditasi/tests_session_security.py:109`) — tetap lulus; `Secure`/`HttpOnly` tidak
berubah. `CsrfEnforcementTest` (3 test, `:158-225`) — tetap lulus; middleware CSRF
tidak berubah.

---

## 9. Sequencing

### 9.1 Peta dependensi

```
Workstream A (accounts)          P0-1, P0-2, P0-3   ─┐
                                 P0-4, P0-5         ─┤ independen satu sama lain
                                 P0-6, P0-7         ─┘ (P0-6 menutup P0-7)

Workstream B (akreditasi gate)   P0-8, P0-9         ── independen dari A

Workstream C (pasien)            P0-10 ──┐
                                 P0-11 ──┼── satu workstream (butuh field baru + helper bersama)
                                 P0-12 ──┤
                                 P0-13 ──┤
                                 P0-14 ──┘

Workstream D (sdm token)         P0-15               ── independen

Workstream E (settings)          P0-16               ── independen
```

### 9.2 Yang dapat mendarat paralel

**E (P0-16) dapat mendarat kapan saja, paling cepat.** Satu baris di
`config/settings.py`, nol dependensi, nol risiko silang.

**D (P0-15) dapat mendarat paralel dengan apa pun.** Dua `default=` di satu berkas
model + satu migrasi. Tidak menyentuh `accounts`, `akreditasi`, atau `pasien`.

**A dan B dapat mendarat paralel.** Keduanya menyentuh berkas berbeda
(`accounts/views.py` + `accounts/models.py` vs `akreditasi/views.py`). Satu-satunya
titik singgung adalah `has_permission()` — B **memanggil**-nya, A **memperluas**
validasi tulisnya. Karena A tidak mengubah semantik `has_permission()`, tidak ada
konflik.

**C harus satu workstream, tidak dapat dipecah.** P0-10…P0-14 semuanya bergantung pada
(a) migrasi field `unit_kerja` dan (b) helper scope di `pasien/decorators.py`.
Memecahnya akan menghasilkan dua definisi scope yang berbeda. Satu penulis, satu
commit.

### 9.3 Dependensi yang nyata

1. **C bergantung pada migrasi field.** `unit_kerja` pada `KunjunganPasien` dan
   `Ruangan` harus ada sebelum view apa pun dapat memfilternya. Urutan: migrasi →
   helper → view.
2. **C tidak bergantung pada A/B.** Scope pasien memakai `profile.unit_kerja` dan
   `profile.role`, bukan `custom_permissions`. Aman bila A/B belum mendarat.
3. **B (P0-8) bergantung pada A (P0-4/P0-5) secara longgar.** `require_permission`
   memanggil `has_permission()`, yang membaca `custom_permissions`. Bila A belum
   mendarat, `custom_permissions` masih dapat ditulis dengan kunci sampah — tetapi
   `has_permission()` hanya membaca kunci yang diminta, jadi gate B tetap benar.
   **Tidak ada blocker.** Yang penting: bila A mendarat lebih dulu, whitelist A sudah
   menjamin `has_permission()` hanya menerima kunci sah.
4. **A internal:** P0-1/P0-2/P0-3 memakai helper `_can_assign_role` /
   `_can_modify_account` yang sama → satu commit. P0-4/P0-5 memakai
   `VALID_PERMISSION_KEYS` → satu commit. P0-6/P0-7 → satu commit. Tiga commit dalam
   satu workstream, dapat direview terpisah.

### 9.4 Urutan yang direkomendasikan

| Urutan | Workstream | Alasan |
|--------|-----------|--------|
| 1 | **E (P0-16)** | Satu baris, membuktikan pipeline hijau-sebagian bekerja |
| 2 | **D (P0-15)** | Terisolasi, satu migrasi |
| 3 | **A (P0-1…P0-7)** | Inti eskalasi; membuka jalan bagi B |
| 4 | **B (P0-8, P0-9)** | Bergantung longgar pada A |
| 5 | **C (P0-10…P0-14)** | Paling besar; butuh migrasi + helper + 10 view |

---

## 10. Verifikasi per Workstream

Semua perintah dijalankan dari akar repo dengan
`.venv/Scripts/python.exe manage.py test`.

### Workstream E — P0-16

```bash
.venv/Scripts/python.exe manage.py test akreditasi.tests_session_security accounts.tests_security_owasp --verbosity 2
```

- **Sebelum:** 2 modul, 1 gagal (`CookieFlagTest.test_samesite_is_explicitly_strict`).
- **Sesudah:** 0 gagal.
- **Kriteria lulus:** `Ran N tests ... OK`.

### Workstream D — P0-15

```bash
.venv/Scripts/python.exe manage.py test sdm.tests.security_owasp --verbosity 2
```

- **Sebelum:** 6 tes, 2 gagal (`test_token_pelamar_bukan_uuid4`,
  `test_token_offering_bukan_uuid4`).
- **Sesudah:** 0 gagal.
- **Tambahan wajib:** `python manage.py makemigrations --check --dry-run` harus
  melaporkan migrasi baru **sudah dibuat** (bukan "no changes detected") pada commit
  yang memuat perubahan model.

### Workstream A — P0-1 … P0-7

```bash
.venv/Scripts/python.exe manage.py test accounts.tests_priv_escalation accounts.tests_security_owasp --verbosity 2
```

- **Sebelum:** 2 modul, 14 gagal.
  - `accounts.tests_priv_escalation`: 9 gagal
    (`UserCreateRoleEscalationTest` ×2, `UserDeleteEscalationTest` ×2,
    `CustomPermissionWriteTest` ×3, `RolePermissionTamperTest` ×2).
  - `accounts.tests_security_owasp`: 5 gagal
    (`ControlCenterPermissionTamperTest` ×2, `SuperAdminRoleEscalationTest` ×2,
    `CookieSecurityTest.test_samesite_dilaporkan_secara_eksplisit` — **tidak**, yang
    ini LULUS; jadi 4 gagal).
  - **Total terverifikasi: 13 gagal** (9 + 4).
- **Sesudah:** 0 gagal.
- **Regresi yang harus tetap hijau:**
  ```bash
  .venv/Scripts/python.exe manage.py test accounts.tests_unit_rbac sdm.tests.test_akses --verbosity 2
  ```

### Workstream B — P0-8, P0-9

```bash
.venv/Scripts/python.exe manage.py test akreditasi.tests_admin_gate akreditasi.tests_security_owasp --verbosity 2
```

- **Sebelum:** 2 modul, 4 gagal
  (`AdminGateBypassesPermissionConfigTest` ×3, `AdminGateIgnoresPermissionConfigTest` ×1).
- **Sesudah:** 0 gagal.
- **Regresi yang harus tetap hijau:** `akreditasi.tests_security`
  (header keamanan, rate limiter, host-header, brute-force) — 0 gagal sebelum dan
  sesudah.

### Workstream C — P0-10 … P0-14

```bash
.venv/Scripts/python.exe manage.py test pasien.tests_object_authz pasien.tests_security_owasp --verbosity 2
```

- **Sebelum:** 2 modul, 12 gagal
  (`PatientIdorTest` ×3, `PatientPiiApiTest` ×2, `PatientModuleScopeTest` ×2,
  `PatientPiiIdorTest` ×2, `PatientSearchApiLeakageTest` ×2,
  `PatientModuleDecoratorCoverageTest` ×1).
- **Sesudah:** 0 gagal.
- **Regresi yang harus tetap hijau:**
  ```bash
  .venv/Scripts/python.exe manage.py test akreditasi.tests_unit_rbac --verbosity 2
  ```
- **Tambahan wajib:** `python manage.py makemigrations --check --dry-run` bersih
  setelah migrasi field dibuat.

### Verifikasi akhir — suite penuh (gate CI)

```bash
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

- **Sebelum:** 151 tes, **32 gagal**, 0 error.
- **Sesudah:** 151 tes, **0 gagal**, 0 error.
- **Gate hijau berarti:** seluruh 32 temuan tertutup. Tidak ada `continue-on-error`,
  tidak ada tes yang dilewati, tidak ada `expectedFailure`.

### Tabel ringkasan sebelum/sesudah

| Workstream | Modul | Sebelum (gagal) | Sesudah |
|-----------|-------|-----------------|---------|
| E | `akreditasi.tests_session_security` + `accounts.tests_security_owasp` | 1 | 0 |
| D | `sdm.tests.security_owasp` | 2 | 0 |
| A | `accounts.tests_priv_escalation` + `accounts.tests_security_owasp` | 13 | 0 |
| B | `akreditasi.tests_admin_gate` + `akreditasi.tests_security_owasp` | 4 | 0 |
| C | `pasien.tests_object_authz` + `pasien.tests_security_owasp` | 12 | 0 |
| **Total** | | **32** | **0** |

---

## 11. JANGAN lakukan ini

Bagian ini memuat perbaikan yang tampak masuk akal tetapi **salah**.

### 11.1 Jangan tambahkan `continue-on-error` atau `|| true` ke workflow

`.github/workflows/security-tests.yml` sengaja tidak memakainya, dan komentarnya
menyatakan alasannya secara eksplisit (baris 5-7). Menambahkannya membuat jalur hijau
berarti "tes dilewati", bukan "kerentanan diperbaiki" — dan itu **menghapus satu-satunya
sinyal** yang mendeteksi regresi keamanan di masa depan. Ini bukan perbaikan; ini
menghapus alat ukur.

### 11.2 Jangan hapus, `skip`, atau `expectedFailure` tes yang gagal

Setiap `self.fail()` adalah **kontrak**: ia mendokumentasikan perilaku yang harus
berubah. Menghapusnya memindahkan kerentanan dari "tercatat" ke "tidak terlihat".
`@unittest.expectedFailure` khususnya berbahaya: ia membuat tes **lulus saat gagal**,
sehingga kerentanan yang kembali tidak akan pernah terdeteksi. Tidak ada satu pun dari
32 tes yang boleh diubah.

### 11.3 Jangan buat tes toleran terhadap perilaku rentan

Contoh yang harus dihindari:
- Melonggarkan `assertIn(response.status_code, (403, 404))` menjadi menerima `200`.
- Menghapus pemeriksaan field PII dari pesan kegagalan.
- Mengubah `assertEqual(response.status_code, 403)` di
  `test_authenticated_unauthorized_gets_403_not_redirect` menjadi menerima `302`.
- Mengubah `assertEqual(configured, 'Strict')` menjadi `'Lax'`.

Semua ini adalah **mendefinisikan ulang kerentanan sebagai perilaku yang benar**. Tes
adalah spesifikasi; kode yang menyesuaikan diri ke tes, bukan sebaliknya.

### 11.4 Jangan perbaiki P0-16 dengan `'Lax'`

`owasp-test-plan.md` menyarankan `'Lax'`. Itu **salah** dan akan membuat
`akreditasi/tests_session_security.py:133` tetap GAGAL. Nilai yang benar adalah
`'Strict'`. Lihat §1.1 dan §8.2.

### 11.5 Jangan menurunkan scope dekorator ke `'master_pasien'` untuk `pasien_daftar`

`'master_pasien'` **selalu** ada di `get_allowed_patient_modules()` untuk setiap
profil ber-unit (`accounts/models.py:248`). Memasangnya pada `pasien_daftar` akan
membuat apoteker tetap mendapat 200, dan
`test_view_baca_inti_tanpa_guard` tetap GAGAL. Modul yang benar adalah
`'pendaftaran'`. Lihat §6.3.

### 11.6 Jangan mencoba menurunkan scope unit dari `bed.ruangan.kode` atau `poliklinik`

Tidak ada FK dari `Ruangan` ke `UnitKerja`, dan `poliklinik` adalah `CharField` bebas
(`pasien/models.py:285`). Pencocokan string dengan `UnitKerja.code` akan rapuh dan
**tidak akan bekerja di test** — test tidak membuat `Ruangan`/`Bed` sama sekali
(`akreditasi/tests_utils.py:make_kunjungan`). Field `unit_kerja` eksplisit adalah
satu-satunya jalur. Lihat §6.2.

### 11.7 Jangan taruh `SESSION_COOKIE_SAMESITE` di dalam `if not DEBUG:`

Blok itu (`config/settings.py:122-129`) hanya berlaku saat `DEBUG=False`. CI
menjalankan tes dengan `DEBUG=True` (workflow tidak menyetel `DJANGO_DEBUG`), jadi
nilai itu tidak akan terlihat oleh test dan P0-16 tetap GAGAL. Letakkan di luar blok.

### 11.8 Jangan pakai `default=secrets.token_urlsafe(32)` langsung di field

Itu memanggil fungsi **sekali saat import** dan memberi semua baris token yang sama.
`default=` harus menerima callable. Gunakan fungsi bernama atau
`default=secrets.token_urlsafe`. Lihat §7.2.

### 11.9 Jangan hash token rekrutmen yang sudah ada

Token lama adalah capability aktif yang sudah dikirim ke kandidat lewat email.
Menggantinya akan mematahkan tautan yang sudah beredar dan mengunci kandidat dari
lamarannya. Baris lama dibiarkan berfungsi. Lihat §7.3.

### 11.10 Jangan pakai 403 untuk penolakan `update_user_custom_permissions`

Test menerima `(200, 400)` — **bukan 403**
(`accounts/tests_priv_escalation.py:239`, `accounts/tests_security_owasp.py:145`).
Penolakan otorisasi di endpoint itu harus memakai `status=400` dengan
`{'success': False, 'error': ...}`. Memakai 403 akan membuat test gagal pada assertion
**status**, bukan pada assertion state. Lihat §3.2.

### 11.11 Jangan hapus guard hapus-diri di `user_delete`

`accounts/views.py:206-209` sudah benar dan dipaku oleh
`UserDeleteEscalationTest.test_self_delete_is_blocked`
(`accounts/tests_priv_escalation.py:215`). Perbaikan P0-3 **menambah** lapis, bukan
mengganti. Guard lama juga menangani kasus di mana `request.user` tidak punya profil.

### 11.12 Jangan pindahkan otorisasi ke `UserProfileForm`

Form tidak menerima `request.user`, dan `UserProfileForm` juga dipakai dari
`admin_control_center` (`accounts/views.py:265-…`). Menaruh otorisasi di view menjaga
satu titik keputusan dan tidak memaksa perubahan tanda tangan form. Lihat §2.2.

### 11.13 Jangan ubah `get_allowed_patient_modules()`

Matriks modul dipaku oleh empat test yang sudah LULUS
(`pasien/tests_object_authz.py:246`, `pasien/tests_security_owasp.py:170`,
`pasien/tests_object_authz.py:268`, `:259`, `:270`). Mengubahnya akan mematahkan
test yang tidak terkait dengan P0 mana pun.

---

## 12. Ringkasan Temuan yang Deskripsinya Tidak Cocok dengan Sumber

| Temuan | Klaim dokumen | Kenyataan terverifikasi |
|--------|---------------|-------------------------|
| **P0-16** | `security-test-gate.md`: `test_samesite_dilaporkan_secara_eksplisit` **LULUS**; `owasp-test-plan.md`: set `'Lax'` | Ada **dua** test, bukan satu. `akreditasi/tests_session_security.py:133` menuntut `'Strict'` dan **GAGAL**. Perbaikan harus `'Strict'`. |
| **P0-3** | `owasp-test-plan.md` tidak memuat temuan penghapusan akun | Dua test gagal, termasuk perlindungan **peer-admin** (`test_admin_rs_cannot_delete_another_admin_rs`), bukan hanya hierarki. |
| **P0-10…P0-14** | `owasp-test-plan.md` item backlog: "Pasang `require_patient_module` + filter unit" | Tidak ada FK unit di aplikasi `pasien` sama sekali. Perbaikan memerlukan **field baru + migrasi**, bukan filter pada field yang ada. |
| **P0-11** | Digabung ke P0-14 sebagai "view tanpa dekorator" | Dua sebab independen: dekorator **dan** scope queryset. Dekorator saja tidak cukup. |
| **P0-14** | `owasp-test-plan.md`: daftar view baca inti termasuk `pasien_detail` | `pasien_detail` dan `kunjungan_detail` **sudah** tercakup oleh P0-10. P0-14 spesifik untuk `pasien_daftar` + `dashboard`, dan modul yang benar adalah `'pendaftaran'`, bukan `'master_pasien'`. |
| **P0-8** | `owasp-test-plan.md` menyebut pemetaan izin generik | `profil_rs_view` **tidak boleh** dipetakan ke `can_manage_system_settings` (ADMIN_RS punya `False` → regresi akses). Gunakan `can_manage_units`. `audit_log_view` harus `can_view_audit_log`, bukan `can_manage_units`. |

**Semua nomor baris lain di `security-test-gate.md` dan `owasp-test-plan.md`
terverifikasi akurat** terhadap kode sumber saat ini:

- `accounts/views.py:27-33` (`admin_only`), `:100-146` (`user_create`),
  `:153-200` (`user_edit`), `:202-220` (`user_delete`), `:222-229`
  (`control_center_access`), `:410-453` (`update_role_permissions`), `:455-490`
  (`update_user_custom_permissions`) — semua cocok.
- `akreditasi/views.py:63-70` (`_is_admin`), `:93` (`admin_required`),
  `:1355-1357`, `:1439-1441`, `:1483-1486`, `:1522-1524`, `:1532-1534`, `:1576-1578`
  — semua cocok.
- `pasien/views.py:222-227`, `:275-293`, `:213-220`, `:802-838`, `:839-864`,
  `:521-531`, `:536-563` — semua cocok.
- `sdm/models/rekrutmen.py:121-124` (dokumen menyebut `121-124`; aktual `121-125`
  karena `help_text` satu baris tambahan) dan `:418-420` — cocok dalam rentang.
- `sdm/services/undangan.py:44` — cocok.
- `config/settings.py:122-125`, `:131` — cocok.
