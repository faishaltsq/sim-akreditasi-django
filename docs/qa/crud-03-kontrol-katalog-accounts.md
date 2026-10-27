# QA CRUD Modul 03 — Kontrol, Katalog, Portal Nakes/KPS, Accounts

Tanggal: 2026-10-27 · Metode: `django.test.Client` + `force_login`, DB = **copy** `db.sqlite3` di `qa/_crud03_copy.sqlite3` (dihapus setelah run).
Superuser uji: `monsiskami`. Non-admin: `staf.sdm` (STAF_NAKES), `demo.viewer` (ASESOR), `ka.ranap` (KEPALA_UNIT), `probe3` (ADMIN_RS).

## Catatan environment (bukan bug)

- `db.sqlite3` lokal punya migrasi `sdm.0043`/`sdm.0044` **belum diterapkan** (`sdm_drafdokumenkredensial` tidak ada). Akibatnya `User.delete()` migration chain meng-update kolom `created_by` (SET_NULL) ke tabel itu dan gagal `OperationalError: no such table: sdm_drafdokumenkredensial`. Uji dijalankan pada **copy DB** yang sudah `migrate`; DB asli repo tidak disentuh.

## 1. Tabel hasil uji

| Menu/submenu | View | Method | Status | Bukti (DB delta / redirect / error) |
|---|---|---|---|---|
| Kontrol hub | `kontrol_hub` `/control/` | GET | 200 | len=8794 |
| Kontrol risiko | `kontrol_risiko` `/control/risiko/` | GET | 200 | len=19606 |
| Kontrol EMR | `kontrol_emr` `/control/emr/` | GET | 200 | len=11735 |
| Kontrol dokumen | `kontrol_dokumen` `/control/dokumen/` | GET | 200 | len=12349 |
| Kontrol layanan | `kontrol_layanan` `/control/layanan/` | GET | 200 | len=6342 |
| Kontrol layanan + `?tanggal=&status=` | `kontrol_layanan` | GET | 200 | query valid & `tanggal=zzz` keduanya 200 (fallback hari ini) |
| Ringkasan AI | `kontrol_ringkasan_ai` | GET | 405 | `@require_POST` sesuai desain |
| Ringkasan AI | `kontrol_ringkasan_ai` | POST `portal=risiko` | 502 | `{"ok":false,"error":"Gagal membuat ringkasan AI."}` — gateway AI tidak terkonfigurasi di mesin uji; guard benar |
| Ringkasan AI | `kontrol_ringkasan_ai` | POST `portal=xxx` | 400 | `{"error":"Portal tidak dikenal."}` |
| Katalog daftar | `katalog_daftar` `/katalog/` | GET | 200 | len=55082 |
| Katalog pemetaan | `katalog_pemetaan` `/katalog/pemetaan/` | GET | 200 | len=144145 |
| Katalog pemetaan | `katalog_pemetaan` | POST create | 302 → `/katalog/pemetaan/` | **DB PemetaanEdisi 0→1** |
| Katalog pemetaan | `katalog_pemetaan` | POST kosong | 404 | lihat L2-1 |
| Katalog pemetaan | `katalog_pemetaan` | POST `source_item_id=abc` | 200 (redirect) | pesan "Item sumber dan target harus dipilih." — tertangani |
| Katalog validasi | `katalog_validasi` `/katalog/validasi/` | GET | 200 | len=54404 |
| Katalog pengumuman | `katalog_pengumuman` `/katalog/pengumuman/` | GET | 200 | len=53121 |
| Pencarian | `pencarian` `/pencarian/` | GET | 200 | len=52259 |
| Pencarian `?q=mutu` | `pencarian` | GET | 200 | len=78854 (hasil lintas 5 sumber) |
| Pencarian `?q=a` / `?q=%` | `pencarian` | GET | 200 | guard `MIN_QUERY_LEN=2` jalan |
| Panduan | `panduan_dokumentasi` `/panduan/` | GET | 200 | len=35528 (file docs ada) |
| Audit log | `audit_log_view` `/log/` | GET | 200 | len=164809, hanya SUPER/ADMIN_RS |
| Portal nakes (super) | `portal_nakes` `/portal-nakes/` | GET | 200 | len=68239 |
| Portal nakes (staf nakes) | `portal_nakes` | GET | 200 | len=144735 |
| Upload kredensial | `upload_kredensial_nakes` | POST `@require_POST` | 302 → `/portal-nakes/` | **DB NakesCredential 0→1** (akun dengan `sdm.Pegawai` tertaut) |
| Upload kredensial tanpa `doc_type` | idem | POST | 302 | pesan "Gagal mengunggah dokumen. Periksa form Anda." |
| Upload kredensial akun tanpa Pegawai HC | idem | POST | 302 | pesan "Akun kredensial belum memiliki identitas pegawai Human Capital." |
| Upload kredensial sebagai SUPER_ADMIN | idem | POST | 302 | ditolak: `request.user.profile` super tidak punya `sdm.Pegawai` → lihat L3-1 |
| Unduh kredensial (pemilik) | `download_kredensial_nakes` | GET | 302 → signed URL Supabase | `authorize_legacy_credential_download` OK |
| Unduh kredensial (404) | idem | GET | 404 | id tak ada |
| Hapus kredensial (pemilik, kanonis) | `delete_kredensial_nakes` | POST | 302 | objek tetap ada, versi jadi `SUPERSEDED`, pesan "Dokumen berhasil diarsipkan." (=arsip, sesuai desain) |
| Hapus kredensial (pemilik, legacy belum tertaut) | idem | POST | 302 | **DB row terhapus** |
| Hapus kredensial (super/bukan pemilik) | idem | POST | 404 | `get_object_or_404(..., user_profile=request.user.profile)` → tidak bisa hapus milik orang lain |
| Hapus kredensial via GET | idem | GET | 405 | `@require_POST` |
| Rekap KPS | `rekap_kps_unit` `/rekap-kps/` | GET | 200 (SUPER/KEPALA_UNIT), 403 (STAF/ASESOR) | len=83803 |
| Verifikasi kredensial | `verify_kredensial` | POST `status=VERIFIED` | 302 → `/rekap-kps/` | status kredensial PENDING→VERIFIED |
| Verifikasi kredensial status invalid | idem | POST `status=BOGUS` | 302 | form invalid, tidak ada 500 |
| Verifikasi KEPALA_UNIT beda unit | idem | POST | 403 JSON | "Akses ditolak: nakes bukan dari unit Anda." |
| User list | `user_list` `/accounts/users/` | GET | 200 | len=97130; filter `?role=ASESOR&q=a` 200 |
| User create (form) | `user_create` | GET | 200 | len=77470 |
| User create | `user_create` | POST valid | 302 → `/accounts/users/` | **DB User 16→17**, profil+role tersimpan |
| User create (kurang field) | `user_create` | POST minim | 200 (form error) | tidak ada user dibuat |
| User create STAF_NAKES/KEPALA_UNIT tanpa unit | `user_create` | POST | 200 (form error) | form menolak, tidak ada user dibuat |
| User edit (form + POST) | `user_edit` | GET/POST | 200 / 302 | email & first_name berubah di DB |
| User edit demote SUPER_ADMIN→ASESOR | `user_edit` | POST | 302 | `is_superuser` True→False, `is_staff` tetap True → lihat L2-4 |
| User delete | `user_delete` | POST | 302 → `/accounts/users/` | row hilang (`exists_after=False`) |
| User delete self | `user_delete` | POST | 302 | ditolak dengan pesan, akun tetap ada |
| User delete 404 | `user_delete` | POST id palsu | 404 | |
| Pusat kontrol | `admin_control_center` `/accounts/kontrol/` | GET | 200 | len=6.9 MB (semua user+unit+grid izin) |
| Update hierarki unit | `update_unit_hierarchy` | POST | 200 JSON `{"success":true}` | `order` 0→5 tersimpan |
| Update hierarki circular | idem | POST `parent_id=self` | 400 JSON | "circular dependency" |
| Update hierarki `parent_id=abc` | idem | POST | **500 / ValueError** | lihat L1-1 |
| Update hierarki unit 404 | idem | POST | 404 | |
| Update hierarki `order=x` | idem | POST | 200 | `order` tetap 0 (fallback diam-diam) → L3-3 |
| Update hierarki reparent | idem | POST parent lain | 200 | `parent_id` berubah, `level` 1→2 |
| Update izin peran | `update_role_permissions` | POST JSON | 200 `{"success":true}` | `ASESOR.can_view_pdca` True→False |
| Update izin peran SUPER_ADMIN | idem | POST JSON | 200 | `can_manage_system_settings` tetap True (LOCKOUT_SAFE_PERMS) |
| Update izin peran form-encoded | idem | POST non-JSON | **500 / AttributeError** | lihat L1-2 |
| Update izin peran field asing | idem | POST `{'zzz':true}` | 200 | diabaikan (`hasattr` guard) |
| Reset izin peran | `reset_role_permissions` | POST | 302 → `/accounts/kontrol/` | `reset_to_defaults()` jalan |
| Reset izin peran via GET | idem | GET | 405 | |
| Izin kustom user | `update_user_custom_permissions` | POST JSON | 200 | `profile.custom_permissions` terisi |
| Izin kustom user 404 | idem | POST id palsu | 404 | |
| Konfigurasi sistem | `update_system_config` | POST | 302 → `/accounts/kontrol/` | `theme_color=#123456`, `threshold_paripurna=91`, `ai_temperature=0.5` |
| Konfigurasi sistem nilai invalid | idem | POST int/float invalid | 302 | diabaikan (guard `.isdigit()` / `try`) |
| Toggle freeze | `toggle_survey_freeze` | POST | 302 | `survey_freeze_mode` False→True→False |
| Toggle freeze tanpa CSRF | idem | POST (enforce_csrf) | 403 | CSRF aktif |
| Login form | `RateLimitedLoginView` | GET | 200 | len=5315 |
| Login password salah | idem | POST | 200 | form error, tidak login |
| Rate limit login | idem | POST ×11 | 200×6 lalu **429** | `rl:login:ip:127.0.0.1 (8/8 calls in 60s)` |
| Logout | `LogoutView` | POST | 302 → `/accounts/login/` | |
| RBAC STAF_NAKES / ASESOR / KEPALA_UNIT | `/accounts/kontrol/`, `/accounts/users/`, `/accounts/users/baru/`, `/log/` | GET | 302 (redirect login) | non-SUPER tanpa izin ditolak |
| RBAC ASESOR/STAF ke POST admin | `permissions/reset`, `system/toggle-freeze`, `system/update`, `update-hierarchy` | POST | 302 | ditolak (redirect) |
| RBAC `probe3` (ADMIN_RS) | `/accounts/kontrol/`, `/accounts/users/`, `/rekap-kps/` | GET | **200** | sesuai matriks (ADMIN_RS: `can_manage_users`, `can_access_control_center`) |
| RBAC `probe3` `system/toggle-freeze` & `system/update` | idem | POST | **403 JSON** | `can_manage_system_settings=False` untuk ADMIN_RS → benar |
| RBAC `probe3` `permissions/reset` | idem | POST | 302 (sukses) | lihat L2-5 |
| RBAC `probe3` `update-hierarchy` | idem | POST | 200 JSON | sesuai `can_access_control_center` |
| RBAC katalog | `/katalog/` | GET | 200 untuk semua role | read terbuka, tulis dibatasi `require_catalogue_write` |

## 2. Bug nyata

**LEVEL1 (500 / exception)**

- **L1-1** `POST /accounts/kontrol/unit/<id>/update-hierarchy/` dengan `parent_id` non-numerik (`abc`) → `ValueError: invalid literal for int() with base 10: 'abc'` → **HTTP 500**. View memanggil `int(parent_id)` mentah setelah hanya memfilter string kosong/`'0'`.
- **L1-2** `POST /accounts/kontrol/permissions/update/` dengan body **form-encoded** (bukan JSON) → `data = request.POST`, lalu `role_data` berupa string → `AttributeError: 'str' object has no attribute 'items'` → **HTTP 500**.

**LEVEL2 (permission / CSRF / redirect)**

- **L2-1** `POST /katalog/pemetaan/` tanpa `source_item_id`/`target_item_id` → `get_object_or_404(StandardItem, pk=None)` → **404** (bukan redirect + pesan), form kehilangan input user.
- **L2-2** `reset_role_permissions` hanya dijaga `control_center_access` (=`can_access_control_center`), tidak `can_manage_system_settings`. ADMIN_RS bisa mereset seluruh matriks izin meski tombol "Konfigurasi Sistem" untuknya tersembunyi.
- **L2-3** `user_delete` hanya `@require_POST` + `admin_only`; tidak ada proteksi menghapus Super Admin terakhir / akun dengan `is_superuser=True` (selain larangan hapus diri sendiri).
- **L2-4** `user_edit` saat role diturunkan dari SUPER_ADMIN/ADMIN_RS ke role lain tidak mengembalikan `is_staff=False` (hanya `is_superuser=False`), sehingga akun tetap punya akses Django admin (`is_staff` bocor). Lihat baris `user edit demote`: `is_staff` tetap `True`.
- **L2-5** `update_role_permissions` tidak memeriksa `can_manage_system_settings`; siapa pun dengan `can_access_control_center` (mis. ADMIN_RS) dapat mengubah matriks izin semua role.

**LEVEL3 (UX / label)**

- **L3-1** `portal_nakes` boleh dibuka SUPER_ADMIN tapi `upload_kredensial_nakes` selalu gagal untuk akun tanpa `sdm.Pegawai` ("Akun kredensial belum memiliki identitas pegawai Human Capital.") — form upload tetap dirender tanpa peringatan.
- **L3-2** `kontrol_ringkasan_ai` mengembalikan 502 generik "Gagal membuat ringkasan AI."; penyebab (AI nonaktif / API key kosong) tidak dibedakan.
- **L3-3** `update_unit_hierarchy` menerima `order='x'` dengan `{"success": true}` padahal nilai jatuh ke 0 (tidak ada validasi/peringatan).
- **L3-4** `/accounts/kontrol/` merender 6.9 MB HTML (seluruh tabel user + grid izin) sekali jalan — risiko lambat pada instalasi besar.

## 3. Root cause (file:line)

| Bug | Lokasi |
|---|---|
| L1-1 | `accounts/views.py:278-280` — `new_parent = get_object_or_404(UnitKerja, id=int(parent_id))` tanpa `try/except ValueError` |
| L1-2 | `accounts/views.py:326` (view `:311`) — `for perm_field, value in role_data.items()` tanpa memastikan `role_data` dict |
| L2-1 | `akreditasi/catalogue_views.py:107-108` — `get_object_or_404(StandardItem, pk=source_item_id)` saat id kosong menghasilkan 404, bukan pesan form |
| L2-2 | `accounts/views.py:348-353` (`reset_role_permissions`) — hanya `@user_passes_test(control_center_access)`, tanpa cek `can_manage_system_settings` |
| L2-3 | `accounts/views.py:161-181` (`user_delete`) — tanpa guard akun superuser/akun terakhir |
| L2-4 | `accounts/views.py:135-137` (`user_edit`) — cabang `else` hanya `target_user.is_superuser = False` |
| L2-5 | `accounts/views.py:308-311` (`update_role_permissions`) — tanpa cek `can_manage_system_settings` |
| L3-1 | `akreditasi/views.py:1888-1912` + `sdm/services/kredensial_lama.py:51-56` |
| L3-2 | `akreditasi/kontrol_views.py:378-380` |
| L3-3 | `accounts/views.py:291` — `int(order_val) if order_val.isdigit() else 0` |
| L3-4 | `accounts/views.py:250-260` — `admin_control_center` mengambil `all_users` + seluruh `RolePermissionConfig` tanpa paginasi |

## 4. Reproduksi

```bash
# DB asli belum punya sdm.0043/0044 → pakai copy agar tidak mengubah repo
cp db.sqlite3 qa/_copy.sqlite3
cat > qa/_settings.py <<'EOF'
from config.settings import *  # noqa
import os
DATABASES['default']['NAME'] = os.path.join(BASE_DIR, 'qa', '_copy.sqlite3')
EOF
DJANGO_SETTINGS_MODULE=qa._settings .venv/Scripts/python.exe manage.py migrate
DJANGO_SETTINGS_MODULE=qa._settings .venv/Scripts/python.exe - <<'EOF'
import os, sys, django
sys.path.insert(0, os.getcwd()); os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qa._settings')
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
from akreditasi.models import UnitKerja
c = Client(); c.force_login(get_user_model().objects.get(username='monsiskami'))
print('L1-1', c.post('/accounts/kontrol/unit/1/update-hierarchy/', {'parent_id': 'abc'}).status_code)
print('L1-2', c.post('/accounts/kontrol/permissions/update/', {'ASESOR': 'x'}).status_code)
print('L2-1', c.post('/katalog/pemetaan/', {}).status_code)
unit = UnitKerja.objects.order_by('pk').first()
print('L3-3', c.post(f'/accounts/kontrol/unit/{unit.pk}/update-hierarchy/', {'order': 'x'}).content[:60])
EOF
rm -f qa/_copy.sqlite3 qa/_settings.py
```

Catatan: skrip QA di atas bersifat sementara dan dijalankan terhadap copy DB; tidak ada perubahan kode aplikasi, tidak ada migrasi baru ke `db.sqlite3`, tidak ada commit.
