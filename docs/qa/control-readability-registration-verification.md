# Verifikasi Keterbacaan Control dan Pintu Masuk Pendaftaran EMR

## Status

**Selesai dan terverifikasi lokal.** 129 tes terfokus lulus pada database SQLite `:memory:` terisolasi, dan 40 kombinasi halaman × viewport lulus pemeriksaan computed style, overflow, dan kontras terhadap aset hasil `collectstatic`.

Belum ada commit, push, deploy, migrasi, atau seed. Tidak ada verifikasi login produksi.

## Lingkup perubahan

| Berkas | Perubahan |
|---|---|
| `akreditasi/kontrol_navigation.py` | Builder murni `registration_action()`; tanpa query, tanpa parameter unit |
| `akreditasi/kontrol_views.py` | `registration_action` diinjeksi ke `_common_context` memakai `allowed` yang sudah ada |
| `templates/akreditasi/kontrol/_layanan_unit.html` | Baris `Pendaftaran pasien` + catatan cakupan harian |
| `templates/akreditasi/kontrol/emr.html` | Layanan Unit dipindah sebelum KPI; CPPT/PPA dijelaskan; `RS-wide` → `Seluruh RS` |
| `templates/akreditasi/kontrol/{hub,risiko,dokumen}.html` | Panduan unit, kunci singkatan, dan cakupan metrik |
| `static/css/kontrol-workspace.css` | Skala tipografi 16px/1.6, label 14px, metadata 13px, baris layanan responsif |
| `akreditasi/tests_kontrol_registration.py` | Baru: kontrak builder, izin, penempatan, dan salinan penjelasan |
| `akreditasi/tests_kontrol_workspace_style.py` | Kontrak label cakupan 12px → 13px; invariant tipografi baru |

## Tes server

Perintah dan hasil sebenarnya:

```
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test \
  akreditasi.tests_kontrol_navigation akreditasi.tests_kontrol_workspace \
  akreditasi.tests_kontrol_workspace_style akreditasi.tests_kontrol_registration \
  akreditasi.tests_kontrol_dasbor akreditasi.tests_kontrol_render \
  akreditasi.tests_layanan_unit accounts.tests_unit_rbac \
  accounts.tests_sidebar_visibility pasien.tests_route_rbac --verbosity 1
```

- Hasil: `Ran 129 tests ... OK`, exit code 0.
- Baseline sebelum perubahan: `Ran 115 tests ... OK` pada suite yang sama dikurangi `tests_kontrol_registration`.
- `django check` dengan setelan yang sama: `System check identified no issues (1 silenced).`
- Interpreter: `.venv/Scripts/python.exe`, Django **6.1.1**. `requirements.txt` memuat 6.1.2; ketidaksesuaian ini belum diselesaikan dan tidak ada reinstalasi.

Cakupan izin yang diuji (fixture sintetis, unit dibuat di database test):

| Kasus | Hasil |
|---|---|
| IGD, ADMISI, PENDAFTARAN, REKAM-MEDIS (STAF) | Baris tampil; tujuan `pasien:pendaftaran_dashboard` → 200 |
| SUPER_ADMIN, ADMIN_RS, DIREKTUR, superuser | Baris tampil; tujuan → 200 |
| ADMISI dengan unit tanpa pemetaan layanan | Baris tetap tampil; pesan "tidak memiliki layanan pendaftaran pasien" dipertahankan |
| POLI-PD, LAB-BDRS, FARM, BANGSAL-DEWASA, DIREKSI | Tidak ada baris; `registration_action` None; tujuan → 403 |
| Risiko, Dokumen, Layanan, Hub | Tidak ada baris meski partial layanan dipakai bersama |
| Anonim | EMR → 302 ke login |

Penempatan diuji struktural: indeks `<section class="kontrol-layanan">` < indeks `data-service-action="pendaftaran"` < penutup section < `class="kontrol-kpis"` < `class="kontrol-ai"`. Baris pendaftaran tepat satu.

## Verifikasi render browser

Harness scratch di `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/control-readability/` (`render.py`, `measure.py`, `results.json`, screenshot). Delapan skenario dirender dari view asli memakai test client + `setup_databases`/`teardown_databases`, dengan `assert` bahwa database `:memory:`. Fixture sintetis: nama unit panjang, 25 risiko (seluruh 5×5 terisi), satu kunjungan IGD sintetis.

Pass kedua memakai aset hasil `collectstatic`: `DEBUG=False` dan `ManifestStaticFilesStorage`, sehingga HTML menunjuk `css/kontrol-workspace.d04f06799e1c.css` (nama ber-hash dari manifest), bukan berkas sumber.

Viewport: 1440×900, 1366×768, 768×1024, 390×844, 360×800 — 40 kombinasi, **0 gagal**.

Metrik yang diukur (computed style, setelah `document.fonts.ready`):

| Metrik | Ambang | Hasil |
|---|---|---|
| Overflow horizontal halaman | tidak ada | `pageOverflow=false` di semua 40 kombinasi |
| Font termuat | Inter + Manrope | `document.fonts.check` true di semua kombinasi |
| Label operasional (`.kpi-label`, `.quick-label`, `.bar-label`, `.gauge-label`) | ≥ 14px | minimum 14px |
| Teks pendukung (`.kpi-foot`, `.layanan-entry-text small`, `.kontrol-caption`, `.portal-sub`, …) | ≥ 14px | minimum 14px |
| Metadata ringkas (`.panel-hint`, `.kpi-scope`, `.layanan-date`, `.kontrol-eyebrow`, `.layanan-sub`) | ≥ 13px | minimum 13px |
| Judul panel dan seksi | ≥ 18px | 18px; judul halaman 26–40px |
| Judul baris layanan | ≥ 15px | 15px |
| Tinggi target baris layanan | ≥ 44px | 80px (desktop dan mobile) |
| Baris layanan terpotong | tidak ada | `clippedServices` kosong |
| Kontras teks normal | ≥ 4.5:1 | minimum 5.17:1 |
| Kontras sel matriks terisi | ≥ 4.5:1 | 5.17:1 pada lima latar severity (hijau, abu, kuning, oranye, merah) |

Kontras dihitung dari warna efektif: latar semi-transparan (`rgba`) dikompositkan bertingkat sampai latar opak, sehingga sel matriks tidak lagi keliru dianggap putih. Rasio minimum 5.17:1 berasal dari sel matriks; teks panel minimum 5.54:1; hub 6.27:1.

Pemeriksaan khusus baris pendaftaran (EMR berhak, semua viewport):

- `registrationCount = 1`, `registrationInsideServices = true`, `servicesBeforeKpis = true`
- `href = /pasien/pendaftaran/` tanpa query string
- Tidak ada kontrol bersarang di dalam anchor (`nested controls: 0`)
- Traversal Tab mencapai baris pendaftaran; fokus terlihat `outline: solid 3px`; label aksesibel berasal dari teks terlihat

Kasus tanpa hak: `registrationCount = 0` pada `emr-denied`, dan 0 pada seluruh halaman non-EMR.

## Aset deployment

```
collectstatic → 1 static file copied, 139 unmodified, 380 post-processed
validasi manifest → PASS css/kontrol-workspace.d04f06799e1c.css
```

Validasi memeriksa: entri manifest ada dan berkasnya ada, isi `staticfiles/css/kontrol-workspace.css` identik dengan sumber, `font: 16px/1.6` dan `.layanan-entry-registration` ada di berkas ber-hash, dan varian `.gz` (bila ada) terdekompresi identik. Perubahan `staticfiles/staticfiles.json` beserta berkas ber-hash adalah hasil `collectstatic`, bukan suntingan manual.

## Batasan

- Tes berjalan dengan migration dimatikan pada SQLite `:memory:`; ini bukan sertifikasi kesiapan migrasi PostgreSQL.
- Verifikasi browser memakai HTML yang dirender dari test client dan dibuka sebagai `file://`, bukan server hidup dengan sesi login nyata. Navigasi ke tujuan pendaftaran diverifikasi lewat Django client (HTTP 200/403), bukan klik browser end-to-end.
- Django terpasang 6.1.1, sedangkan `requirements.txt` memuat 6.1.2.
- Tidak ada verifikasi produksi, staging, atau perangkat mobile fisik.

## Catatan di luar lingkup (tidak diubah)

- Baris bed pada `_layanan_unit.html` masih tidak digating seperti toolbar klinis dan menyebut cakupan unit meski tujuannya lebih luas.
- Semantik nol-versus-strip, penanganan `?unit=` yang tidak valid, agregasi snapshot, dan siklus katalog tidak disentuh.
- Label bisnis `Unit Contoh` pada selector bersama tidak diganti.
