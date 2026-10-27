# QA CRUD — Modul Risiko / Insiden / Indikator Mutu / Laporan Mutu / Logbook

Tanggal: 2026-10-27 · DB: `db.sqlite3` lokal · User: `monsiskami` (superuser) · skrip throwaway: `.qa_tmp/qa_02_*.py`
Perintah: `PYTHONPATH=. .venv/Scripts/python.exe .qa_tmp/qa_02_risiko_mutu.py` (lalu `qa_02_neg.py`, `qa_02_logbook.py`)

## 1. Status per tombol CRUD

| Menu/submenu | View | Method | Status | Bukti (DB delta / redirect / error) |
|---|---|---|---|---|
| Risiko · Daftar risiko | `risiko_daftar` | GET | 200 | render OK |
| Risiko · Input risiko | `risiko_input` | GET | 200 | form render |
| Risiko · Input risiko (simpan) | `risiko_input` | POST | 302 | RisikoUnit 51→52, redirect `/risiko/52/` |
| Risiko · Detail | `risiko_detail` | GET | 200 | render OK |
| Risiko · Edit (form) | `risiko_edit` | GET | 200 | prefill OK |
| Risiko · Edit (simpan) | `risiko_edit` | POST | 302 | `jenis_risiko` & `dampak` berubah di DB |
| Risiko · Evaluasi (form) | `risiko_evaluasi` | GET | 200 | render OK |
| Risiko · Evaluasi (simpan) | `risiko_evaluasi` | POST | 302 | `rpn_residual=8`, `status=EVALUASI` |
| Risiko · Hapus (konfirmasi) | `risiko_hapus` | GET | 200 | halaman konfirmasi |
| Risiko · Hapus (eksekusi) | `risiko_hapus` | POST | 302 | RisikoUnit 52→51 |
| Risiko · Perencanaan unit | `risiko_perencanaan_unit` | GET | 200 | `/risiko/perencanaan/` & `/156/` |
| Risiko · Pelaksanaan unit | `risiko_pelaksanaan_unit` | GET | 200 | `/risiko/pelaksanaan/` & `/156/` |
| Risiko · Monitoring-Evaluasi | `risiko_monitoring_evaluasi` | GET | 200 | `/` & `/156/` |
| Risiko · FMEA-RCA | `risiko_fmea_rca` | GET | 200 | render OK |
| Risiko · Laporan | `risiko_laporan` | GET | 200 | `/` & `/156/` |
| Risiko · Laporan Lengkap | `risiko_laporan_lengkap_unit` | GET | 200 | `/` & `/156/` |
| Risiko · Dok. Perencanaan single | `risiko_perencanaan_dokumen` | GET | 200 | render OK |
| Risiko · Dok. Pelaksanaan single | `risiko_pelaksanaan_dokumen` | GET | 200 | render OK |
| Risiko · Laporan Lengkap single | `risiko_laporan_lengkap` | GET | 200 | render OK |
| Risiko · Export CSV perencanaan | `risiko_perencanaan_export_csv` | GET | **500** | `?unit=abc` → `ValueError` (lihat BUG-01); normal = 200 |
| Risiko · Export CSV pelaksanaan | `risiko_pelaksanaan_export_csv` | GET | **500** | `?unit=abc` → `ValueError` (BUG-02); normal = 200 |
| Risiko · Export CSV monev | `risiko_monev_export_csv` | GET | **500** | `?unit=abc` → `ValueError` (BUG-03); normal = 200 |
| Risiko · API indikator-by-unit | `api_indikator_by_unit` | GET | 200 | JSON `{"indikator":[...]}`; `?unit=abc` → 200 (fallback diam-diam) |
| Insiden · Daftar | `insiden_daftar` | GET | 200 | render OK |
| Insiden · Lapor (form) | `insiden_lapor` | GET | 200 | render OK |
| Insiden · Lapor (kirim) | `insiden_lapor` | POST | 302 | InsidenKeselamatan 5→6 |
| Insiden · Detail | `insiden_detail` | GET | 200 | render OK |
| Insiden · Update status | `insiden_update_status` | POST | 302 | `status=INVESTIGASI`, `rca_dilakukan=True` |
| Indikator · Dashboard | `indikator_dashboard` | GET | 200 | render OK |
| Indikator · Matriks INM | `indikator_inm_matrix` | GET | 200 | render OK — **tak ada tombol/link di template mana pun** (BUG-05) |
| Indikator · Tambah (form) | `indikator_tambah` | GET | 200 | render OK |
| Indikator · Tambah (simpan) | `indikator_tambah` | POST | 302 | IndikatorMutu 51→52 |
| Indikator · Detail | `indikator_detail` | GET | 200 | render OK |
| Indikator · Edit (simpan) | `indikator_edit` | POST | 302 | `nama_indikator` berubah |
| Indikator · Input capaian | `indikator_input_capaian` | POST | 302 | CatatanIndikator 0→1 |
| Indikator · API tren | `api_indikator_tren` | GET | 200 | JSON keys `kode,nama,...,labels` |
| Indikator · API komparasi | `api_indikator_komparasi_unit` | GET | 200 | JSON `jenis,bulan,tahun,items`; `?tahun=abc` → **500** (BUG-04) |
| Laporan Mutu · Daftar | `laporan_mutu_daftar` | GET | 200 | render OK |
| Laporan Mutu · Buat (form) | `laporan_mutu_create` | GET | 200 | render OK |
| Laporan Mutu · Buat (simpan) | `laporan_mutu_create` | POST | 302 | LaporanMutu 0→1 + 51 baris snapshot |
| Laporan Mutu · Detail | `laporan_mutu_detail` | GET | 200 | render OK |
| Laporan Mutu · Analisis (per baris) | `laporan_mutu_simpan_analisis` | POST | 302 | `baris.analisis` tersimpan |
| Laporan Mutu · Analisis (massal) | `laporan_mutu_simpan_analisis` | POST | 302 | `analisis_<pk>` tersimpan |
| Laporan Mutu · Tarik MONEV | `laporan_mutu_tarik_monev` | POST | 302 | redirect + pesan info/warning |
| Laporan Mutu · Simpan seksi | `laporan_mutu_simpan_seksi` | POST | 302 | LaporanMutuSeksi 0→8 |
| Laporan Mutu · Verifikasi | `laporan_mutu_verifikasi` | POST | 302 | DRAF→DIVERIFIKASI |
| Laporan Mutu · Setujui L3 | `laporan_mutu_setujui` | POST | 302 | DIVERIFIKASI→DISETUJUI |
| Laporan Mutu · Setujui L2 | `laporan_mutu_setujui` | POST | 302 | DISETUJUI→TERBIT |
| Laporan Mutu · Regenerasi | `laporan_mutu_regenerasi` | POST | 302 | DRAF: 51 baris; TERBIT: ditolak + pesan |
| Laporan Mutu · Cetak | `laporan_mutu_cetak` | GET | 200 | text/html |
| Laporan Mutu · PDF | `laporan_mutu_pdf` | GET | 200 | application/pdf |
| Logbook · Daftar | `logbook_daftar` | GET | 200 | render OK |
| Logbook · Buat (form) | `logbook_buat` | GET | 200 | render OK |
| Logbook · Buat (simpan) | `logbook_buat` | POST | 302 | LogbookHarian 0→1 |
| Logbook · Detail | `logbook_detail` | GET | 200 | auto `tarik_pasien()` + `ensure_checklist()` (9 butir) |
| Logbook · Simpan pasien | `logbook_simpan_pasien` | POST | 302 | **tidak terverifikasi**: 0 baris pasien auto-tarik untuk unit 156/tanggal uji |
| Logbook · Simpan checklist | `logbook_simpan_checklist` | POST | 302 | status→`TERLAKSANA`, keterangan tersimpan |
| Logbook · Simpan narasi | `logbook_simpan_narasi` | POST | 302 | DRAF: tersimpan; DISETUJUI: 403 (terkunci) |
| Logbook · Kejadian | `logbook_simpan_kejadian` | POST | 302 | LogbookKejadian 1, InsidenKeselamatan 5→6 (sync) |
| Logbook · Bukti (upload) | `logbook_unggah_bukti` | POST | 302 | LogbookBukti 1; `.exe` ditolak (tetap 1) |
| Logbook · Serah terima | `logbook_serah_terima` | POST | 302 | DRAF→DIISI; tanpa `ttd_perawat` tetap DRAF |
| Logbook · Setujui | `logbook_setujui` | POST | 302 | DIISI→DISETUJUI; tanpa `ttd_kepala_ruang` tetap DIISI |
| Logbook · PDF | `logbook_pdf` | GET | 200 | application/pdf (4.6 KB) |

Negatif/pengamanan yang lolos: anonim → 302 login (semua 8 URL); CSRF enforced → 403; GET pada view `@require_POST` → 405 (13 endpoint); id tidak ada → 404 (6 URL); duplikat periode LaporanMutu ditolak (count tetap 1); ASESOR `/logbook/buat/` → 403.

## 2. Bug nyata

**LEVEL1**
- **BUG-01** `/risiko/perencanaan/export-csv/?unit=abc` → 500 `ValueError: Field 'id' expected a number but got 'abc'`.
- **BUG-02** `/risiko/pelaksanaan/export-csv/?unit=abc` → 500 (sama).
- **BUG-03** `/risiko/monitoring-evaluasi/export-csv/?unit=abc` → 500 (sama).
- **BUG-04** `/indikator-mutu/api/komparasi-unit/?tahun=abc` → 500 `ValueError: invalid literal for int() with base 10: 'abc'`.
- **BUG-05** `/risiko/laporan/?tahun=abc` → 500 `ValueError: Field 'tahun' expected a number but got 'abc'`.
- **BUG-06** `/risiko/fmea-rca/?unit=abc` → 500 `ValueError: Field 'id' expected a number but got 'abc'`.

**LEVEL2**
- **BUG-07** RBAC Risiko tidak ada sama sekali: ASESOR (`demo.viewer`, unit_scope False) dapat **mengedit** dan **menghapus** `RisikoUnit` milik unit lain (dibuktikan: edit 302 mengubah `jenis_risiko`, delete 302 menghapus baris pk=29). Semua role (ASESOR/STAF_NAKES/KEPALA_UNIT/ADMIN_RS) mendapat 200 pada `/risiko/`, `/risiko/baru/`, `/risiko/<id>/edit/`, `/risiko/<id>/hapus/`.
- **BUG-08** `indikator_inm_matrix` ada di `urls.py` + view + template `indikator_inm_matrix.html` tapi **tidak ada tautan tombol/menu di template mana pun** (hanya dirujuk `tests_smoke_render.py`).
- **BUG-09** `logbook_simpan_pasien` tak punya bukti jalan: untuk unit 156 tanggal uji, `tarik_pasien()` menghasilkan 0 baris sehingga loop tidak pernah dieksekusi; tombol tidak bisa diuji end-to-end tanpa data EMR yang cocok.

**LEVEL3**
- **BUG-10** Pesan error form Risiko/Insiden/Indikator menampilkan `repr(dict)` / `KeyError`: "Gagal menyimpan: {'periode': [...]}" dan "Gagal menyimpan: 'dampak'" — bukan bahasa manusia.
- **BUG-11** `api_indikator_by_unit?unit=abc` mengembalikan 200 dengan daftar indikator (bukan 400), sehingga filter unit gagal secara diam-diam.
- **BUG-12** `logbook_unggah_bukti` menampilkan ukuran `0 KB` untuk berkas <1 KB karena pembulatan `size/1024`.

## 3. Root cause (file:line)

- BUG-01 `akreditasi/risiko_views.py:1780` — `get_object_or_404(UnitKerja, pk=unit_id)` dengan `unit_id` string mentah.
- BUG-02 `akreditasi/risiko_views.py:1936` — pola sama.
- BUG-03 `akreditasi/risiko_views.py:1122` — `qs.filter(unit_id=unit_id)` tanpa `int()`/validasi.
- BUG-04 `akreditasi/indikator_views.py:873` — `int(request.GET.get('tahun', 2026))` tanpa `try`.
- BUG-05 `akreditasi/risiko_views.py:1274` — `qs.filter(tahun=tahun)` (tahun = string GET).
- BUG-06 `akreditasi/risiko_views.py:1560` dan `:1566` — `qs.filter(unit_id=unit_id)` string mentah.
- BUG-07 `akreditasi/risiko_views.py:238,330,516,592,734` — hanya `@login_required`, tanpa cek role/scope unit (bandingkan `risiko_perencanaan_dokumen:1620` yang punya cek `is_unit_scoped`).
- BUG-08 `akreditasi/urls.py:116` (route ada) + `templates/akreditasi/indikator_dashboard.html` (tanpa `{% url 'akreditasi:indikator_inm_matrix' %}`); `templates/includes/sidebar.html` juga tanpa entri.
- BUG-10 `akreditasi/risiko_views.py:508` (`messages.error(request, f'Gagal menyimpan: {e}')` dengan `e` ValidationError), `akreditasi/risiko_views.py:1517` (insiden), `akreditasi/indikator_views.py:720`.
- BUG-11 `akreditasi/risiko_views.py:172-236` — param `unit` diabaikan bila non-numerik tanpa sinyal error.

## 4. Reproduksi

```bash
# bug 500 query param (BUG-01..06)
PYTHONPATH=. .venv/Scripts/python.exe -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
c=Client(); c.force_login(get_user_model().objects.get(username='monsiskami'))
for u in ['/risiko/perencanaan/export-csv/?unit=abc','/risiko/pelaksanaan/export-csv/?unit=abc',
          '/risiko/monitoring-evaluasi/export-csv/?unit=abc','/indikator-mutu/api/komparasi-unit/?tahun=abc',
          '/risiko/laporan/?tahun=abc','/risiko/fmea-rca/?unit=abc']:
    c.get(u)   # raises ValueError
"

# BUG-07 RBAC (ASESOR menghapus risiko unit lain)
PYTHONPATH=. .venv/Scripts/python.exe -c "
import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
c=Client(); c.force_login(get_user_model().objects.get(username='demo.viewer'))
print(c.get('/risiko/29/edit/').status_code)   # 200 — seharusnya 403
"
```
