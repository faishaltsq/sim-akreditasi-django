# Verifikasi Integrated Control Workspace

## Status

**Implementasi lokal selesai melalui worker `eg/elf/deepseek-v4.1-flash`.** Delta spesifikasi dinyatakan PASS dan review kualitas APPROVED, tanpa temuan Critical/Important yang tersisa. Belum ada staging, commit, push, deploy, atau verifikasi login produksi untuk pekerjaan ini.

**Regresi aplikasi keseluruhan belum hijau:** 1.018 tes dijalankan pada database terisolasi dan 5 tes di luar modul perubahan ini gagal. Rincian ada di bawah; laporan ini bukan klaim bahwa seluruh aplikasi siap rilis.

## Perubahan

- Masthead gradient navy–indigo sesuai palet ARIMA, permukaan data putih, font Inter/Manrope lokal, grid kartu dua kolom desktop dan satu kolom mobile.
- Ilustrasi rumah sakit, backdrop dekoratif, glow kartu, blur topbar, dan permintaan Google Fonts pada shell kontrol dihapus.
- Navigasi bersama Ringkasan/Risiko/EMR/Dokumen; Human Capital tampil hanya melalui predikat grant yang sama dengan kartu hub.
- Toolbar akses langsung berada sebelum KPI, tanpa perantara halaman utama aplikasi. Unit ter-resolve dipertahankan hanya pada tujuan yang mendukung filter tersebut.
- Pintasan EMR mengikuti pemetaan layanan dan entitlement profil; unit administratif tidak diberi tautan klinis generik.
- Rekap/scoring hanya diiklankan kepada role yang diterima guard tujuan. Human Capital tetap membuka workspace HC yang sudah ada.
- Angka, null-versus-zero, pemetaan layanan, endpoint AI, dan rumus snapshot tidak diubah oleh pekerjaan UI ini.

Berkas utama:

- `akreditasi/kontrol_navigation.py`
- `akreditasi/kontrol_views.py`
- `templates/akreditasi/kontrol/base_kontrol.html`
- `templates/akreditasi/kontrol/{hub,risiko,emr,dokumen}.html`
- `templates/akreditasi/kontrol/{_portal_nav,_module_actions,_portal_header}.html`
- `static/css/kontrol-workspace.css`
- `static/css/kontrol.css` — hanya penghapusan deklarasi blur lama.
- `config/control_test_settings.py` dan tes kontrol terkait.

## Temuan review yang ditutup

| Temuan | Perbaikan | Verifikasi |
|---|---|---|
| Header mobile menyisakan ruang kosong 207–269px; aksi utama jatuh di bawah fold | Reset flex-basis heading group pada layout column | Sisa ruang terukur 0px; seluruh aksi primer berada dalam viewport yang diuji |
| Label cakupan aksi 10px | Menjadi 12px dengan line-height 1.35 | Invariant CSS dan render browser lulus |
| Angka matriks putih pada warna tingkat risiko kurang kontras | Foreground gelap `#06121F`; warna severity dipertahankan | 125 pemeriksaan sel terisi; rasio minimum 5.157:1 |
| Parameter `tahun` Laporan Mutu diabaikan tujuan | Parameter dihapus dari kedua pintasan laporan | Tes URL exact-path/query lulus |
| Ikon kartu risiko tidak tersedia di Bootstrap Icons | Menggunakan `bi-shield-check` | Tes render dan inspeksi screenshot |
| Assertion rute/unit berbasis substring rapuh | Parse path dan query untuk assertion terkait | Suite terfokus lulus |

Probe kontras awal memiliki cacat harness: alpha ikut dijumlahkan sebagai komponen luminance keempat sehingga menghasilkan NaN. Harness diperbaiki, gate menolak nilai nonfinite, dan cacat kontras produk kemudian direproduksi serta diperbaiki sebelum verifikasi final. Angka di atas berasal dari probe yang sudah diperbaiki, bukan hasil NaN.

## Gate yang lulus

### Tes terfokus

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_navigation akreditasi.tests_kontrol_workspace akreditasi.tests_kontrol_workspace_style akreditasi.tests_kontrol_dasbor akreditasi.tests_kontrol_render akreditasi.tests_layanan_unit --verbosity 1
```

Hasil controller: **92 tests, OK**. Database SQLite `:memory:`; migrasi app lokal dinonaktifkan. Ini menguji perilaku UI/navigasi, bukan kesiapan migrasi historis PostgreSQL.

Gate budget cache hangat yang sudah ada untuk hub/EMR tetap <=12 query. Reviewer juga menjalankan probe query terpisah; tidak ada perubahan budget untuk menyembunyikan regresi.

### Render dan browser

- 9 kasus: hub tanpa/dengan HC, risiko, EMR poli/IGD/bed/unit administratif, dokumen, dan layanan.
- 5 ukuran: 1440×900, 1366×768, 768×1024, 390×844, 360×800.
- **45 render browser**, tanpa page error, overflow halaman, label yang terpotong menurut probe, target aksi <44px, nested control pada kartu, atau backdrop dekoratif tersisa.
- Satu main dan h1 per halaman; tab aktif tepat; skip-link menerima fokus pertama dan memindahkan fokus ke main.
- **13 GET tujuan operasional mengembalikan 200**, termasuk HC. Ini menghitung pemeriksaan tautan dari sumber masing-masing, bukan 13 URL unik; Laporan Mutu sengaja diperiksa dari dua portal.
- Seluruh 25 sel matriks diberi data fixture dan diukur pada 5 viewport: 125 pemeriksaan kontras valid, minimum 5.157:1.
- Screenshot desktop dan mobile akhir diperiksa secara visual. Native select tetap menyingkat nama unit fixture yang sangat panjang pada layar sempit; nilai option lengkap tetap tersedia pada kontrol asli.

Batas bukti: HTML berasal dari view Django test-client yang terautentikasi pada fixture SQLite sementara, lalu dimuat dengan aset sumber asli untuk geometri komponen. Ini **bukan sesi login produksi**, bukan uji E2E browser seluruh aplikasi, dan bukan sertifikasi WCAG menyeluruh.

Perubahan katalog paralel menambahkan kebutuhan katalog terpasang pada halaman dokumen/rekap. Renderer awal yang belum membuat Framework sempat menerima 403. Harness kemudian membuat Framework ACTIVE **hanya di SQLite sementara**, tanpa mengubah sumber/model/katalog aktif/produksi; kedua tujuan kembali 200. Guard aplikasi tidak dilonggarkan.

### Aset deployment

`collectstatic` dijalankan dengan storage produksi tetapi koneksi DB diganti SQLite `:memory:` sebelum inisialisasi Django. Tidak ada migrasi atau koneksi database produksi yang diperlukan.

Manifest menunjuk ke:

- `css/kontrol.1710b56b40d2.css`
- `css/kontrol-workspace.9eefe145ddc7.css`

Aset plaintext sesuai sumber; aset hashed sesuai transformasi URL font oleh Django; file font hashed ada; gzip terdekompresi identik dengan plaintext masing-masing. Normalisasi path Windows dan tanda kutip URL pada checker diperbaiki setelah membandingkan diff aktual hasil post-processing.

Delta mapping manifest terbatas pada dua stylesheet tersebut. `git diff --check` lulus. Peringatan LF/CRLF dari Git bukan kegagalan whitespace atau perubahan konten admin asset.

## Regresi aplikasi luas: belum hijau

Command controller dijalankan melalui scratch runner yang memaksakan SQLite `:memory:` dan MEDIA_ROOT sementara:

```bash
.venv/Scripts/python.exe C:/Users/cubeb/AppData/Local/hermes/cache/scratch/control-elf/run_full_suite.py
```

Runner mengeksekusi `django test akreditasi accounts pasien sdm --verbosity 1` dengan `config.control_test_settings`.

Hasil aktual: **1.018 tests, FAILED (failures=5)**.

| Modul | Kegagalan teramati |
|---|---|
| `tests_import_buku_risiko` | Idempotensi: jumlah record pertama/kedua berbeda |
| `tests_pencarian` | Label pencarian EP yang diharapkan tidak ditemukan |
| `tests_perencanaan_risiko` | Nama unit yang diharapkan tidak ada pada laporan |
| `tests_sidebar_uid` | ID kelompok sidebar dari fixture/seed yang diharapkan tidak ditemukan |
| `tests_smoke_render` | Profil pengguna fixture tidak ada pada satu halaman dan reverse URL laporan tanpa unit pada halaman lain |

Tidak ada kegagalan pada 92 tes fitur kontrol. Kelima kegagalan luas dicatat apa adanya, tanpa mengklaim semuanya sudah dibuktikan pre-existing melalui baseline bersih. Berkas terkait dan pekerjaan catalogue/model paralel tidak diubah untuk membuat gate ini hijau.

## Adjudikasi minor review

Tujuh catatan opsional tidak menghalangi approval: tautan bed pada partial layanan lama belum mengikuti entitlement toolbar baru; assertion substring lain di satu tes; lock query-budget tambahan untuk tiga halaman; pemakaian helper manager privat lintas modul; metadata accent yang kini tidak dipakai; guard untuk penggunaan partial header di portal yang belum didukung; dan robustness lookup jika konfigurasi portal/poli diperluas.

Catatan lama dicatat sebagai follow-up di luar perubahan ini. Refactor helper lintas aplikasi, perubahan partial layanan yang tidak menjadi target, fallback konfigurasi hipotetis, dan ekspansi halaman HC tidak dilakukan hanya untuk menutup nit review. Kontrak konfigurasi yang dipakai sekarang tetap teruji.

## Artefak bukti

Sertifikat mesin: `docs/qa/integrated-control-workspace-verification.json`.

Scratch root:
`C:/Users/cubeb/AppData/Local/hermes/cache/scratch/control-elf/`

- `visual/browser-results.json`
- `visual/render-results.json`
- `visual/hub-hc-1440-full.png`
- `visual/risiko-390-fold.png`
- `visual/dokumen-390-full.png`
- `backend-spec-review.md`
- `ui-spec-review-findings.md`
- `quality-review.md`
- `full-suite.log`

Beberapa proses reviewer/fixer mencapai batas iterasi dan tidak menulis report atau menjalankan GREEN terakhir. Output lengkap tetap dikembalikan pada stdout; controller menyimpan laporan dan menjalankan gate independen. Exit code proses tersebut tidak disamakan dengan sukses verifikasi. Rute model utama tidak diubah; semua worker memakai rute ELF yang dipin setelah endpoint CLI diperbaiki.

## Pemisahan pekerjaan paralel

Selain baseline seed/STARKES/HC yang sudah kotor, selama verifikasi muncul perubahan paralel pada `akreditasi/catalogue.py`, `akreditasi/models.py`, `akreditasi/views.py`, migrasi normalisasi lifecycle, dan `templates/akreditasi/ep_list.html`. Berkas-berkas tersebut tidak dimiliki, ditimpa, di-stage, atau di-commit oleh pekerjaan Integrated Control ini. Working tree keseluruhan tidak dinyatakan bersih.
