# Laporan Temuan — QA Fleet 1.295 Akun ARIMA

**Tanggal:** 2026-10-23
**Cakupan:** 219 unit kerja × 6 tingkatan role = 1.314 kombinasi, 1.295 akun seed
**Fase:** Smoke, API, Sanity, Regression baca, Regression tulis

---

## Ringkasan Eksekusi

| Fase | Akun | Request | HTTP 500 | Temuan | Gate |
|---|---|---|---|---|---|
| Smoke | 1.295 | 90.650 | 0 | 2 | LULUS |
| API | 1.295 | 33.670 | 0 | 0 | LULUS |
| Sanity | 1.295 | 15.540 | 0 | 0 | LULUS |
| Regression baca | 39 (sampel) | 5.460 | 0 | 0 (0 flaky) | LULUS |
| Regression tulis | 11 kasus | 11 | 0 | 0 | LULUS |
| **Total** | | **145.331** | **0** | **2** | |

Tidak ada satu pun HTTP 500 di seluruh 145.331 request. Tidak ada exception yang lolos ke handler Django.

---

## Temuan Aktif

### F-2 — Unit RAJAL/RANAP/DEPO terkunci dari modulnya sendiri

**Severity:** High
**Akun terdampak:** 24 (dari 30 yang terdeteksi; 6 sisanya role non-operasional yang 403-nya wajar)
**Unit terdampak:** 6

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
print('allowed:', sorted(u.profile.get_allowed_patient_modules()))
print('/pasien/rajal/ ->', c.get('/pasien/rajal/').status_code)
"
```

**Expected:** `{'master_pasien', 'rajal', 'riwayat'}` → HTTP 200
**Actual:** `{'master_pasien', 'riwayat'}` → HTTP **403**

**Akar masalah:** `accounts/models.py:251-279`. Fungsi `get_allowed_patient_modules()` mencocokkan substring pada kode unit:

```python
if any('IRJ' in c or 'POLI' in c for c in all_codes):   # rajal
if any('IRIN' in c or 'BANGSAL' in c or 'INTENSIF' in c or 'RUANG' in c for c in all_codes):  # ranap
```

Kode unit `RAJAL` dan `RANAP` tidak mengandung token mana pun di atas, sehingga jatuh ke `return allowed` (default `{'master_pasien', 'riwayat'}`). Unit `SEK-RAJAL-RANAP` juga tidak cocok karena hanya diperiksa `IRJ`/`POLI`, bukan `RAJAL`.

**Unit terdampak:**

| Unit | Akun terdampak | Modul yang seharusnya |
|---|---|---|
| RAJAL | 4 | rajal |
| RANAP | 3 | ranap |
| SEK-RAJAL-RANAP | 8 | rajal + ranap |
| DEPO-RANAP-IGD | 8 | ranap + igd |
| DEPO-RAJAL | 3 | rajal |
| DEPO-BEDAH-INTENSIF | 4 | ranap |

**Bukti:** `qa/shards/smoke/shard*.json` → `findings`; `qa/reports/smoke_findings.json`

**Catatan perbaikan:** tambahkan `'RAJAL'` dan `'RANAP'` ke daftar token, atau lebih aman ganti pencocokan substring menjadi pemetaan eksplisit kode→modul (lihat `qa/expectations.py:EXPECTED_MODULE_BY_UNIT` yang sudah memuat pemetaan yang benar).

---

### F-3 — Modul Human Capital tertutup untuk 4 dari 6 role

**Severity:** Medium (keputusan konfigurasi, bukan cacat kode)
**Akun terdampak:** 876

`/human-capital/*` mengembalikan 403 untuk KOORDINATOR_POKJA, KEPALA_UNIT, STAF_NAKES, dan ASESOR. Penyebab: `RolePermissionConfig.can_view_hc` hanya `True` untuk `ADMIN_RS`; `SUPER_ADMIN` lolos lewat short-circuit `is_superuser` di `has_permission()`.

**Repro:**

```bash
.venv/Scripts/python.exe -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
U=get_user_model()
for un in ['sa.igd','admin.igd','ka.igd','pokja.igd','asesor.igd']:
    u=U.objects.get(username=un); c=Client(); c.force_login(u)
    print('%-12s %-18s /human-capital/ -> %s' % (un, u.profile.role, c.get('/human-capital/').status_code))
"
```

**Actual:**
```
sa.igd       SUPER_ADMIN        200
admin.igd    ADMIN_RS           200
ka.igd       KEPALA_UNIT        403
pokja.igd    KOORDINATOR_POKJA  403
asesor.igd   ASESOR             403
```

**Keputusan yang dibutuhkan:** apakah Kepala Unit seharusnya bisa membuka modul HC untuk unitnya sendiri? Kalau ya, aktifkan `can_view_hc` untuk `KEPALA_UNIT` lewat Pusat Kontrol — tapi itu akan membuka seluruh 219 akun KEPALA_UNIT sekaligus, jadi perlu diputuskan bersama cakupan grant-nya.

---

## Temuan yang Dicabut

### ~~F-1 — `ValidationError` tidak diimpor~~

**Dicabut.** Sudah diperbaiki di commit `3c3565d` (2026-10-23 16:42), sebelum QA dijalankan. Diverifikasi ulang:

```
akreditasi/views.py:6: from django.core.exceptions import PermissionDenied, ValidationError
manage.py test sdm.tests.test_legacy_credentials → Ran 26 tests, OK
POST /rekap-kps/verifikasi/3/ (ADMIN_RS, kredensial EXPIRED) → 302, bukan 500
```

**Pelajaran:** plan QA disusun pukul ~19:00 dan menyebut F-1 sebagai bug aktif, padahal commit perbaikan masuk pukul 16:42. Rencana yang disusun sebelum repo bergerak wajib memverifikasi ulang temuannya saat eksekusi. Tiga commit masuk di antara penyusunan plan dan eksekusi: `3c3565d`, `673690d`, `aabddb7`.

---

## Observasi Non-Temuan

### O-1 — SUPER_ADMIN ditolak di `/human-capital/k3/` (218 akun)

`/human-capital/k3/` memanggil `require_hc_capability(user, 'hc_health_read')`. Di `sdm/akses.py:16-21`, kapabilitas berawalan `hc_health_` sengaja melewati `has_permission()` tetapi tetap mensyaratkan baris `HcGrant` eksplisit. Seed tidak membuat grant kesehatan kerja — dan memang tidak seharusnya.

**Ini desain yang benar**, bukan bug: data kesehatan kerja tidak boleh terbuka hanya karena seseorang admin. Tapi perlu diketahui operator: membuka `/human-capital/k3/` menuntut grant `hc_health_read` manual, termasuk untuk SUPER_ADMIN.

### O-2 — Urutan validasi `/ai/*` tidak konsisten

`/ai/test-connection/` mengembalikan 403 untuk ASESOR (cek izin dulu), sementara `/ai/mitigasi-risiko/` mengembalikan 400 untuk akun yang sama (cek body dulu). Bukan bug, tapi menyulitkan debugging.

### O-3 — `quick_score` menelan exception jadi 500 generik

`akreditasi/views.py:754` memakai `except Exception as e:` lalu mengembalikan `{"error": "Terjadi kesalahan internal."}` dengan status 500. Body form-encoded (bukan JSON) memicu ini:

```
POST /ep/record/1/quick-score/  (form-encoded)  → 500 {"success": false, "error": "Terjadi kesalahan internal."}
POST /ep/record/1/quick-score/  (JSON {"score":5}) → 200
```

Bukan bug fatal — endpoint memang didokumentasikan sebagai JSON — tapi `except Exception` menyembunyikan penyebab sebenarnya (`JSONDecodeError`) dari log operator. Lebih baik menangkap `JSONDecodeError` secara spesifik dan mengembalikan 400.

---

## Matriks Ekspektasi per Role (terverifikasi)

23 dari 70 endpoint memberi status berbeda antar role. Ini yang membuat ekspektasi global tidak bisa dipakai:

| Endpoint | SUPER_ADMIN | ADMIN_RS | KEPALA_UNIT | KOORD_POKJA | ASESOR | STAF_NAKES |
|---|---|---|---|---|---|---|
| `/accounts/kontrol/` | 200 | 200 | 302 | 302 | 302 | 302 |
| `/accounts/users/` | 200 | 200 | 302 | 302 | 302 | 302 |
| `/human-capital/*` (10 URL) | 200 | 200 | 403 | 403 | 403 | 403 |
| `/indikator-mutu/matriks-inm/` | 200 | 200 | 200 | 200 | 403 | 403 |
| `/log/` | 200 | 200 | 302 | 302 | 302 | 302 |
| `/pasien/farmasi/` | 200 | 200 | 403 | 403 | 403 | 403 |
| `/pasien/laboratorium/` | 200 | 200 | 403 | 403 | 403 | 403 |
| `/pasien/rajal/` | 200 | 200 | 403 | 403 | 403 | 403 |
| `/pokja/` | 200 | 200 | 302 | 302 | 302 | 302 |
| `/portal-nakes/` | 200 | 200 | 302 | 302 | 302 | 200 |
| `/profil/` | 200 | 200 | 302 | 302 | 302 | 302 |
| `/rekap-kps/` | 200 | 200 | 200 | 403 | 403 | 403 |
| `/rekap/` | 200 | 200 | 200 | 200 | 403 | 403 |
| `/unit/` | 200 | 200 | 302 | 302 | 302 | 302 |

---

## Rekomendasi Urutan Perbaikan

1. **F-2** — 24 akun kehilangan akses ke modul unitnya sendiri. Perbaikan satu fungsi, dampak langsung ke operasional harian.
2. **O-3** — `except Exception` di `quick_score` menyembunyikan error nyata. Perbaikan kecil, mempermudah debugging.
3. **F-3** — butuh keputusan produk dulu, bukan perbaikan kode.
