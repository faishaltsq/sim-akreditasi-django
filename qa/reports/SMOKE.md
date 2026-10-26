# Laporan Smoke Testing — 1.295 Akun

**Tanggal:** 2026-10-23
**Fase:** Smoke (Tahap 1 dari 4)
**Endpoint:** 70 URL GET tanpa parameter, tanpa side effect
**Sumber data:** `qa/shards/smoke/shard0.json` … `shard12.json`

---

## 1. Ringkasan

| Metrik | Nilai |
|---|---|
| Akun diuji | **1.295 / 1.295** |
| Shard | 13 / 13 |
| Request | 90.650 |
| HTTP 500 | **0** |
| Exception | **0** |
| Durasi total | ~42 menit (2 batch) |
| Throughput | ~36 req/s agregat |

**Gate: LULUS.** Tidak ada satu pun akun yang gagal login, dan tidak ada satu pun halaman yang menghasilkan 500.

---

## 2. Distribusi Status

| Status | Jumlah | Porsi | Makna |
|---|---|---|---|
| 200 | 61.023 | 67,3% | halaman terender |
| 403 | 16.867 | 18,6% | ditolak sesuai hak akses |
| 302 | 6.285 | 6,9% | redirect (login wall / non-admin) |
| 405 | 3.885 | 4,3% | endpoint POST-only diprobe GET |
| 400 | 2.590 | 2,9% | endpoint butuh parameter wajib |
| **500** | **0** | **0%** | — |

Tidak ada 404. Ini penting: 404 akan berarti ada route yang saya uji tapi tidak terdaftar, dan itu akan membuat cakupan tes menipu.

---

## 3. Per Tingkatan Akun

| Role | Akun | 200 | 403 | 302 | 400 | 405 |
|---|---|---|---|---|---|---|
| SUPER_ADMIN | 218 | 13.734 | 218 | 218 | 436 | 654 |
| ADMIN_RS | 218 | 13.734 | 218 | 218 | 436 | 654 |
| KOORDINATOR_POKJA | 216 | 8.550 | 3.965 | 1.525 | 432 | 648 |
| KEPALA_UNIT | 211 | 8.560 | 3.666 | 1.489 | 422 | 633 |
| STAF_NAKES | 214 | 8.253 | 4.361 | 1.296 | 428 | 642 |
| ASESOR | 218 | 8.192 | 4.439 | 1.539 | 436 | 654 |

SUPER_ADMIN dan ADMIN_RS identik karena keduanya lolos semua guard modul (SUPER_ADMIN lewat `is_superuser` short-circuit, ADMIN_RS lewat `can_access_control_center`). 218 × 70 = 15.260 request per role; angka 403 sebesar 218 untuk keduanya = tepat 1 endpoint yang menolak mereka, yaitu `/human-capital/k3/` (butuh grant `hc_health_read` eksplisit).

---

## 4. Temuan

### F-2 — Unit RAJAL/RANAP/DEPO terkunci dari modulnya sendiri

**Severity:** High
**Akun terdampak:** 30 (di 6 unit)
**Repro:**

```bash
.venv/Scripts/python.exe -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
U=get_user_model()
u=U.objects.get(username='ka.rajal')
c=Client(); c.force_login(u)
print('allowed:', u.profile.get_allowed_patient_modules())
print('/pasien/rajal/ ->', c.get('/pasien/rajal/').status_code)
"
```

**Expected:** Kepala Unit `RAJAL` mendapat `rajal` di `get_allowed_patient_modules()` → HTTP 200
**Actual:** `{'master_pasien', 'riwayat'}` → HTTP **403**

**Akar masalah:** `accounts/models.py:266-279` mencocokkan substring `'IRJ'`, `'POLI'`, `'BANGSAL'`, `'INTENSIF'`, `'RUANG'`, `'ADMISI'`, `'PENDAFTARAN'`, `'REKAM-MEDIS'` — tetapi tidak `'RAJAL'` maupun `'RANAP'`. Unit dengan kode tersebut tidak pernah cocok dengan cabang mana pun dan jatuh ke default `{'master_pasien', 'riwayat'}`.

**Unit terdampak:**

| Unit | Akun | Modul yang seharusnya |
|---|---|---|
| RAJAL | 4 | rajal |
| RANAP | 3 | ranap |
| SEK-RAJAL-RANAP | 8 | rajal + ranap |
| DEPO-RANAP-IGD | 8 | ranap + igd |
| DEPO-RAJAL | 3 | rajal |
| DEPO-BEDAH-INTENSIF | 4 | ranap |

**Catatan:** 6 dari 30 akun adalah role ASESOR dan KOORDINATOR_POKJA yang memang bukan staf operasional unit — untuk mereka 403 adalah perilaku wajar. Yang benar-benar salah adalah 24 akun KEPALA_UNIT dan STAF_NAKES.

**Bukti:** `qa/shards/smoke/shard*.json`, field `findings`

---

### F-3 — Modul Human Capital tertutup untuk 4 dari 6 role

**Severity:** Medium (desain, bukan bug)
**Akun terdampak:** 876
**Status:** sudah diketahui sebelum QA; dicatat sekali, tidak dilaporkan per akun

`/human-capital/*` mengembalikan 403 untuk KOORDINATOR_POKJA, KEPALA_UNIT, STAF_NAKES, dan ASESOR karena `RolePermissionConfig.can_view_hc` hanya `True` untuk ADMIN_RS (SUPER_ADMIN lolos lewat `is_superuser` short-circuit di `has_permission()`).

Ini konsekuensi konfigurasi, bukan cacat kode. Keputusan membuka akses ada di operator lewat Pusat Kontrol.

---

### F-1 — `ValidationError` tidak diimpor — SUDAH DIPERBAIKI, bukan temuan aktif

**Severity:** ~~High~~ → **tidak berlaku**
**Status:** **sudah diperbaiki** di commit `3c3565d` (2026-10-23 16:42), sebelum QA dijalankan

Saat plan QA disusun, `akreditasi/views.py:5` hanya mengimpor `PermissionDenied`, sementara baris ~1992 menangkap `ValidationError`. Itu akan menghasilkan 500 setiap kali `review_legacy_credential` menolak.

**Verifikasi ulang saat eksekusi:** kondisi itu sudah tidak ada.

```bash
$ grep -n "from django.core.exceptions" akreditasi/views.py
6:from django.core.exceptions import PermissionDenied, ValidationError

$ .venv/Scripts/python.exe manage.py test sdm.tests.test_legacy_credentials --keepdb
Ran 26 tests in 6.596s
OK
```

Diuji juga lewat jalur nyata dengan kredensial id=3 (status `EXPIRED`) sebagai ADMIN_RS:

```
POST /rekap-kps/verifikasi/3/  ->  302
status setelah rollback: EXPIRED  (tidak berubah)
```

302 berarti kode masuk ke blok `except (PermissionDenied, ValidationError)` dan menangani penolakan dengan benar — bukan 500.

**Kesimpulan:** F-1 dicabut dari daftar temuan. Catatan untuk plan QA: rencana yang disusun sebelum repo bergerak harus memverifikasi ulang temuannya saat eksekusi, karena commit `3c3565d` dan `673690d` masuk di antara penyusunan plan dan eksekusi.

---

## 5. Anomali yang perlu diperhatikan

**403 SUPER_ADMIN = 218.** SUPER_ADMIN seharusnya tidak pernah ditolak. Setelah ditelusuri, semuanya berasal dari `/human-capital/k3/` yang memanggil `require_hc_capability(user, 'hc_health_read')`. Fungsi `_active_grants()` di `sdm/akses.py:16-21` melewati `has_permission()` untuk kapabilitas berawalan `hc_health_`, tetapi tetap mensyaratkan baris `HcGrant` yang eksplisit. Karena seed tidak membuat grant kesehatan kerja (memang disengaja), SUPER_ADMIN pun ditolak.

Ini **bukan bug** — desainnya memang begitu ("health data uses explicit grants even when has_permission() returns True"). Tapi perlu dicatat: satu-satunya cara membuka `/human-capital/k3/` adalah memberi grant `hc_health_read` manual, termasuk untuk SUPER_ADMIN.

---

## 6. Yang belum diuji di fase ini

- Jalur tulis (POST) — masuk fase regression tulis dengan rollback
- Assertion isi halaman — masuk fase sanity
- Endpoint berparameter (`<int:pk>`, `<uuid:id>`) — 158 route, butuh data fixture per unit
- Deteksi flaky — masuk fase regression baca (2× run)
