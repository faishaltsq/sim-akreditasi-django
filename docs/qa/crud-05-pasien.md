# QA CRUD — Modul 05: Pasien (`pasien/`)

Tanggal: 2026-10-27 · DB: `db.sqlite3` lokal · Auth: `django.test.Client` + `force_login('monsiskami')` (SUPER_ADMIN)
Network guard: `unittest.mock.patch` pada `requests.get/post/put/delete/request/Session` → raise jika ada panggilan nyata.
Hasil: **tidak ada panggilan jaringan nyata** (mode SatuSehat & BPJS = `simulated`, tidak ada kredensial di `.env`).

Fixture: Pasien/Kunjungan/Ruangan/Bed dibuat sendiri, dihapus setelah uji. Sisa objek QA = 0.
Seluruh aksi yang redirect ke `pasien:kunjungan_detail` **gagal di sisi response** karena bug #1 (template rusak) walau DB tetap ter-update.

## 1. Tabel status per tombol/endpoint

| Menu/submenu | View | Method | Status | Bukti (DB delta / redirect / error) |
|---|---|---|---|---|
| Dashboard | `dashboard` | GET | 200 | len 66k |
| Master Pasien — daftar | `pasien_daftar` | GET | 200 | `?q=QA` → 200 |
| Master Pasien — detail | `pasien_detail` | GET | 200 | len 55k |
| Master Pasien — form baru | `pasien_daftar_baru` | GET | 200 | — |
| Master Pasien — **simpan** | `pasien_daftar_baru` | POST | 200 | Pasien +1, redirect `/pasien/<pk>/` |
| Master Pasien — duplikat No.RM | `pasien_daftar_baru` | POST | 200 | tetap (tidak dibuat), msg "Pasien dengan No. Rekam Medis telah ada" |
| Master Pasien — field wajib kosong | `pasien_daftar_baru` | POST | 200 | tetap, msg `Gagal: 'nama_lengkap'` (KeyError mentah) |
| Kunjungan — daftar | `kunjungan_daftar` | GET | 200 | filter status+jenis OK |
| Kunjungan — detail | `kunjungan_detail` | GET | **EXC** | `TemplateSyntaxError` endblock → 500 (bug #1) |
| Kunjungan — form baru | `kunjungan_baru` | GET | 200 | `?pasien=<pk>` OK |
| Kunjungan — **daftar pasien baru** | `kunjungan_baru` | POST | EXC | Pasien +1, Kunjungan +1; response 500 (bug #1) |
| Kunjungan — **daftar pasien lama** | `kunjungan_baru` | POST | EXC | Kunjungan +1; response 500 (bug #1) |
| Kunjungan — POST tanpa `pasien_id` | `kunjungan_baru` | POST | 200 | msg mentah `Gagal mendaftarkan kunjungan: 'pasien_id'` (bug #6) |
| CPPT — tambah | `cppt_tambah` | POST | EXC | CPPT 0→1; response 500 (bug #1) |
| Billing — tambah | `billing_tambah` | POST | EXC | BillingItem 0→1; 500 (bug #1) |
| Discharge planning | `discharge_planning_set` | POST | EXC | `aktif=True`; 500 (bug #1). GET → juga 500 (tidak redirect) |
| Discharge proses | `discharge_proses` | POST | EXC | DischargeRecord 0→1, `k.status=PULANG`; 500 (bug #1) |
| Resume PDF | `resume_pdf` | GET | 200 | `application/pdf`, 4567 byte (setelah ada discharge) |
| Resume PDF tanpa discharge | `resume_pdf` | GET | 302 | redirect detail (pesan "belum memiliki data discharge") |
| Resep — buat | `resep_buat` | POST | EXC | Resep +1, ResepDetail +2; 500 (bug #1) |
| Resep — tanpa obat | `resep_buat` | POST | EXC | rollback (resep dihapus), count tetap; 500 (bug #1) |
| Resep — proses farmasi | `resep_update_status` | POST | 200 | dispensing→DISPENSING; selesai→SELESAI + BillingItem OBAT 0→2 (Rp 27.500) |
| Resep — batal | `resep_update_status` | POST | 200 | status=BATAL |
| Resep — proses GET | `resep_update_status` | GET | 200 | redirect farmasi (no-op) |
| SatuSehat sync | `satusehat_sync_view` | GET `?format=json` | 200 | `{"success": false, "message": "Pasien belum memiliki NIK..."}` — tidak ada HTTP call |
| BPJS buat SEP | `bpjs_buat_sep_view` | GET `?format=json` | 200 | `{"success": true, "no_sep": "1000000...", "mode": "simulated"}` |
| BPJS cek peserta | `bpjs_cek_peserta_view` | GET | 200 / 400 | dengan `no_bpjs` → eligible=true; tanpa param → 400 |
| Integrasi status | `integrasi_status_view` | GET | 200 | satusehat+bpjs `mode=simulated` |
| Farmasi antrean | `farmasi_antrean` | GET | 200 | len 58k |
| Bed management | `bed_management` | GET | 200 | BOR dihitung dari bed |
| Laboratorium | `laboratorium_dashboard` | GET | 200 | len 56k |
| Order penunjang update | `order_penunjang_update` | POST | 200 | status=SELESAI, hasil tersimpan, `is_critical_value=True` |
| Pendaftaran dashboard | `pendaftaran_dashboard` | GET | 200 | len 212k |
| Pendaftaran route → IGD | `pendaftaran_route` | POST | 200 | jenis=IGD, triage=KUNING, flag=AMBULANS, redirect `/pasien/igd/` |
| Pendaftaran route → RAJAL | `pendaftaran_route` | POST | 200 | poliklinik="Poli Anak (Pediatri)", redirect rajal |
| Pendaftaran route tujuan invalid | `pendaftaran_route` | POST | 200 | msg "Pilih tujuan: IGD atau Poli Rawat Jalan." |
| Pendaftaran route GET | `pendaftaran_route` | GET | 200 | redirect pendaftaran |
| IGD dashboard | `igd_dashboard` | GET | 200 | len 545k |
| IGD TTV update | `igd_ttv_update` | POST | 200 | 120/80, nadi 88, rr 20, suhu 37.5, spo2 98, GCS tersimpan |
| IGD TTV GET | `igd_ttv_update` | GET | 200 | redirect igd (no-op) |
| Rajal dashboard | `rajal_dashboard` | GET | 200 | len 143k |
| Rajal antrean status | `rajal_antrean_status` | POST | 200 | DIPANGGIL → SEDANG_DILAYANI + `status=ASESMEN`; nilai invalid diabaikan |
| Rajal SOAP simpan | `rajal_soap_simpan` | POST | 200 | CPPT 0→1; payload kosong → msg "Harap isi minimal salah satu elemen SOAP." |
| Order penunjang buat (rajal) | `order_penunjang_buat` | POST | 200 | Order +1, BillingItem +1 (auto). Nama kosong → ditolak |
| Disposisi PULANG | `kunjungan_disposisi` | POST | 200 | status=PULANG, antrean=SELESAI, DischargeRecord dibuat |
| Disposisi PAPS | `kunjungan_disposisi` | POST | 200 | status=PULANG (APS), discharge dibuat |
| Disposisi RANAP tanpa bed | `kunjungan_disposisi` | POST | 200 | msg "Pilih Bed rawat inap terlebih dahulu.", tidak berubah |
| Disposisi RANAP + bed | `kunjungan_disposisi` | POST | — | **tidak diuji ulang**: butuh `bed_id`, bed dipakai tes booking; jalur `admit_to_ranap` tidak tercakup |
| Disposisi RUJUK_EKSTERNAL | `kunjungan_disposisi` | POST | 200 | status=RUJUK, antrean=SELESAI |
| Disposisi MENINGGAL | `kunjungan_disposisi` | POST | 200 | status=MENINGGAL, DischargeRecord kondisi MENINGGAL |
| Disposisi KONSUL_INTERNAL tanpa poli | `kunjungan_disposisi` | POST | 200 | msg "Pilih Poliklinik tujuan konsul." |
| Disposisi KONSUL_INTERNAL + poli | `kunjungan_disposisi` | POST | 200 | status=DAFTAR, antrean baru `SRF-001` |
| Disposisi aksi tak dikenal | `kunjungan_disposisi` | POST | 200 | msg "Aksi disposisi tidak dikenali." |
| Booking kamar — buat | `booking_kamar_buat` | POST | 200 | BookingKamar +1 (BOOKED), bed→DIBOOKING |
| Booking kamar — tanpa bed_id | `booking_kamar_buat` | POST | 200 | "Pilih bed / tempat tidur yang tersedia terlebih dahulu." |
| Booking kamar — bed sudah dibooking | `booking_kamar_buat` | POST | 200 | "tidak tersedia (status: Dibooking)" |
| Booking kamar — bed_id invalid | `booking_kamar_buat` | POST | 404 | get_object_or_404 |
| Booking kamar — batal | `booking_kamar_batal` | GET | 200 | booking=BATAL, bed→TERSEDIA |
| Booking kamar — check-in | `booking_kamar_checkin` | GET | EXC | booking=CHECKIN, bed=TERISI, kunjungan jadi RANAP; response 500 (bug #1) |
| General consent — simpan | `general_consent_simpan` | POST | 200 | Consent +1, `k.general_consent=True` |
| General consent — tanpa PJ/NIK | `general_consent_simpan` | POST | 200 | "Nama dan NIK Penanggung Jawab wajib diisi." |
| Cetak general consent | `cetak_general_consent` | GET | **EXC** | `FieldError: Non-relational field given in select_related: 'dpjp'` (bug #3) |
| Cetak gelang | `cetak_gelang` | GET | 200 | len 2952 |
| Cetak SEP | `cetak_sep` | GET | 200 | len 4209 |
| Cetak SPRI | `cetak_spri` | GET | 200 | len 4146 (tidak ada tombol/URL di template — hanya via redirect RANAP) |
| Cetak SKDP **tanpa** discharge | `cetak_skdp` | GET | **EXC** | `VariableDoesNotExist: obat_pulang in None` (bug #2) |
| Cetak tracer | `cetak_tracer` | GET | 200 | len 5737 |
| Cetak formulir pendaftaran | `cetak_formulir_pendaftaran` | GET | 200 | len 12295 |
| Cetak resume IGD | `cetak_resume_igd` | GET | 200 | len 6244 |
| Cetak asesmen medis IGD | `cetak_asesmen_medis_igd` | GET | 200 | len 10224 |
| Cetak permintaan lab (auto order) | `cetak_permintaan_lab` | GET | 200 | len 7502 |
| Cetak permintaan lab (order_id) | `cetak_permintaan_lab_order` | GET | 200 | hanya dipakai lewat redirect `print_after_save=1` |
| Fast-track IGD | `fast_track_igd` | POST | 200 | Pasien +1 (`RM-IGD-*`), Kunjungan +1 (IGD, MERAH) |
| Fast-track IGD GET | `fast_track_igd` | GET | 200 | redirect pendaftaran |
| Fast-track IGD usia non-angka | `fast_track_igd` | POST | **EXC** | `ValueError: invalid literal for int()` (bug #4) |
| Kunjungan batal | `kunjungan_batal` | POST | 200 | status=BATAL, nomor_antrean dikosongkan, catatan `[BATAL] ...` |
| Kunjungan batal GET | `kunjungan_batal` | GET | 200 | redirect (no-op) |
| Asesmen awal IGD | `igd_asesmen_awal_save` | POST | 200 | keadaan umum/kesadaran/TTV tersimpan |
| CPPT quick-add IGD | `igd_cppt_quick_add` | POST | 200 | CPPT 0→1; kosong → ditolak |
| Eksekusi tindakan IGD | `igd_eksekusi_tindakan` | POST | 200 | CPPT +1 dengan narasi realisasi |
| Asesmen medis IGD | `igd_asesmen_medis_save` | POST | 200 | triase KUNING (kat 3), GCS `E4V5M6 (15)`, keluhan→catatan_admisi |
| Order lab create | `order_lab_create` | POST | 200 | Order LAB +1 (`parameter_list=[]` hanya karena payload uji awal pakai key salah `parameter_list`; form asli mengirim `parameters`) |
| Order lab create + `parameters` | `order_lab_create` | POST | 200 | parameter 2 item tersimpan (HEMATOLOGI/KIMIA); `print_after_save=1` → redirect `/cetak-permintaan-lab/<order_id>/` |
| API ICD-10 | `api_icd10` | GET | 200 | `?q=demam` → 3 hasil; `q<2` → `[]` |
| API SDKI | `api_sdki` | GET | 200 | `?q=nyeri` → 2 hasil; tanpa q → 15 default |
| API cari pasien | `api_cari_pasien` | GET | 200 | `?q=QA` → results; `q` kosong → `[]` |
| API cek NIK | `api_cek_nik` | GET | 200 | ada/tidak ada → `exists` benar |
| API cek BPJS | `api_cek_bpjs` | GET | 200 / 400 | no_kartu atau nik; tanpa keduanya → 400 |
| API bed tersedia | `api_bed_tersedia` | GET | 200 | `?kelas=3` filter OK |
| API parse QR | `api_parse_qr` | POST | 200 | `{"tipe":"NIK_KTP","nik":"9999..."}`; GET → 405 |
| RBAC ASESOR (no unit) — dashboard/daftar/kunjungan baru | — | GET | 200 | `master_pasien` + `riwayat` diizinkan |
| RBAC ASESOR — igd/pendaftaran/rajal/farmasi/bed/lab | `require_patient_module` | GET | 403 | PermissionDenied sesuai matriks |
| RBAC ASESOR — kunjungan_batal/fast_track | — | POST | 403 | — |

### Tombol ADA di template tapi URL/view tidak ada (link mati)

Tidak ditemukan `{% url 'pasien:...' %}` yang gagal resolve — semua 49 nama URL yang dipakai template ada di `pasien/urls.py`.

### View ada di `urls.py` tapi TIDAK punya tombol di template

| URL name | Catatan |
|---|---|
| `booking_kamar_batal` | Tidak ada link/form di template mana pun (uji langsung GET). Bed yang sudah dibooking tidak bisa dilepas dari UI. |
| `booking_kamar_checkin` | Sama — check-in reservasi tidak punya tombol (hanya lewat URL manual). |
| `cetak_spri` | Hanya dicapai via redirect dari disposisi RANAP; tidak ada tombol langsung. |
| `api_bed_tersedia` | Endpoint JSON tanpa pemakai di template (dropdown bed dirender server-side). |
| `api_sdki` | Tanpa pemakai di template (hanya dipakai unit test). |
| `resep_update_status` | Dipakai di `farmasi_antrean.html` saja, bukan di kunjungan detail. |
| `integrasi_status` | Tanpa tombol; hanya endpoint JSON. |
| `cetak_permintaan_lab_order` | Hanya via redirect `print_after_save`. |

## 2. Daftar bug nyata

### LEVEL1 (500 / exception / CRUD tidak berfungsi)

1. **`pasien/kunjungan_detail.html` — halaman detail kunjungan 500 total.** `TemplateSyntaxError: Invalid block tag on line 1543: 'endblock'`. Ada `{% endblock %}` ganda (baris 1541 dan 1543) untuk satu `{% block content %}`. Karena **semua** aksi CRUD (CPPT, billing, discharge, resep, booking check-in, SatuSehat, kunjungan baru) redirect ke halaman ini, pengguna melihat HTTP 500 setelah setiap simpan walau data sudah masuk DB. Ini menimpa hampir seluruh modul.
2. **`templates/pasien/cetak_skdp.html:56` — cetak SKDP 500 jika belum ada DischargeRecord.** `VariableDoesNotExist: Failed lookup for key [obat_pulang] in None`. Argumen filter `|default:discharge.obat_pulang` di-resolve sebagai variabel; Django 4+ melempar `VariableDoesNotExist` saat `discharge=None`. Tombol ada di `rajal_dashboard.html:213`.
3. **`pasien/views.py:1506` (`cetak_general_consent`) — 500 `FieldError`.** `select_related(..., 'dpjp')` padahal `dpjp` adalah `CharField`, bukan FK. Tombol "Cetak A4" ada di `igd_dashboard.html:1183`.
4. **`pasien/views.py:1579` (`fast_track_igd`) — 500 `ValueError` untuk input non-angka.** `int(request.POST.get('estimasi_usia', 30) or 30)` tanpa try/except; field adalah input teks bebas.

### LEVEL2

5. **`pasien/views.py:334` — `KeyError` mentah ke pesan user.** `request.POST['pasien_id']` saat daftarkan kunjungan pasien lama; user melihat `Gagal mendaftarkan kunjungan: 'pasien_id'`. Idem `request.POST['profesi']` (baris 398, CPPT) & `request.POST['kategori']` (baris 416, billing) → pesan `Gagal: 'profesi'` / `'kategori'`.
6. **`pasien/views.py:229-248` — Kegagalan validasi tidak memberi status/form error proper.** `pasien_daftar_baru` & `kunjungan_baru` mengembalikan 200 dengan seluruh input hilang (tidak re-render nilai) dan pesan `Gagal: 'nama_lengkap'`.
7. **Matriks RBAC tidak memasukkan `rajal`/`farmasi` untuk unit IGD/lab** — bukan bug, tetapi `require_patient_module` mengembalikan 403 tanpa pesan template (halaman error default Django), dan `bed_management` memblokir ASESOR meski hanya baca. (dicatat, bukan regresi)

### LEVEL3

8. `pasien/views.py:1579` — `estimasi_usia` memakai `int()` langsung; sebaiknya input `type="number"` + validasi (sudah dilaporkan sebagai #4).
9. `kunjungan_batal` mengabaikan `GeneralConsentRawatInap`/`DischargeRecord` yang sudah dibuat — data klinis tetap ada meski kunjungan batal.
10. `booking_kamar_batal`/`checkin` tidak punya tombol → operator harus menebak URL (lihat tabel "view tanpa tombol").

## 3. Root cause file:line

| # | File:line | Sebab |
|---|---|---|
| 1 | `templates/pasien/kunjungan_detail.html:1541,1543` | `{% endblock %}` duplikat (satu `{% block content %}` di baris 8) |
| 2 | `templates/pasien/cetak_skdp.html:56` | `{{ discharge.skdp_terapi\|default:discharge.obat_pulang\|default:"..." }}` — argumen `default` di-resolve saat `discharge is None` |
| 3 | `pasien/views.py:1506` | `select_related('pasien', 'bed__ruangan', 'dpjp')` — `dpjp` CharField |
| 4 | `pasien/views.py:1579` | `int(request.POST.get('estimasi_usia', 30) or 30)` tanpa guard |
| 5 | `pasien/views.py:334,398,416` | akses `request.POST[...]` tanpa `.get` + tanpa validasi |
| 6 | `pasien/views.py:229-248`, `295-390` | `except Exception` → `messages.error` lalu render ulang tanpa bound form |

## 4. Reproduksi

Semua perintah dari root proyek, venv aktif.

```bash
# bug #1 — detail kunjungan & semua aksi yang redirect ke sana
python manage.py shell -c "
from django.test import Client; from django.contrib.auth import get_user_model
c=Client(); c.force_login(get_user_model().objects.get(username='monsiskami'))
print(c.get('/pasien/kunjungan/1/').status_code)"
# → TemplateSyntaxError Invalid block tag on line 1543: 'endblock'

# verifikasi template (tanpa HTTP)
python manage.py shell -c "
from django.template import engines
engines['django'].engine.from_string(open('templates/pasien/kunjungan_detail.html',encoding='utf-8').read())"
# hapus salah satu '{% endblock %}' di baris 1541/1543 → compile OK

# bug #2 — cetak SKDP tanpa discharge
python manage.py shell -c "
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien
p=Pasien.objects.create(no_rm='QA-SKDP-1',nama_lengkap='QA',tanggal_lahir='1990-01-01',jenis_kelamin='L')
k=KunjunganPasien.objects.create(pasien=p,no_kunjungan='QA-SKDP-K1',jenis_kunjungan='IGD',tanggal_masuk=timezone.now())
c=Client(); c.force_login(get_user_model().objects.get(username='monsiskami'))
print(c.get(f'/pasien/kunjungan/{k.pk}/cetak-skdp/').status_code)   # → VariableDoesNotExist
k.delete(); p.delete()"

# bug #3 — cetak general consent
python manage.py shell -c "
from django.test import Client; from django.contrib.auth import get_user_model
c=Client(); c.force_login(get_user_model().objects.get(username='monsiskami'))
print(c.get('/pasien/kunjungan/1/cetak-general-consent/').status_code)"   # → FieldError dpjp

# bug #4 — fast track usia non-angka
python manage.py shell -c "
from django.test import Client; from django.contrib.auth import get_user_model
c=Client(); c.force_login(get_user_model().objects.get(username='monsiskami'))
print(c.post('/pasien/fast-track-igd/',{'estimasi_usia':'abc'}).status_code)"   # → ValueError
```
Semua objek QA dibuat script dibersihkan (`Pasien.objects.filter(no_rm__startswith='QA-').delete()` dst.).
