# Dokumen Strategi QA Multi-Quarter (Q4 2026 - Q2 2027)
## Aplikasi Terpadu Manajemen Risiko & Tata Kelola Dokumen Akreditasi (ARIMA / SIK AP)

**Pemilik Dokumen:** Tim QA & Lead Engineering
**Versi:** 3.0
**Tanggal Efektif:** 02 November 2026
**Status:** Disetujui

> **Dasar versi ini.** Seluruh angka pada dokumen ini **diukur**, bukan diasumsikan: jumlah
> tes dihitung dari DiscoverRunner Django, durasi diukur dari eksekusi serial per aplikasi,
> bentuk piramida diklasifikasikan dari pemakaian Django test client per modul, dan kondisi
> gate CI dibaca dari workflow beserta riwayat commit-nya. Versi 2.0 (2026-10-04) menyebut
> "15 kasus uji" — angka itu meleset ~120× terhadap kenyataan. Dokumen ini karena itu ditulis
> ulang dari nol, bukan ditambal.

---

### 1. Executive Summary

Repositori ini sudah memiliki **1.818 tes otomatis** di 163 modul yang ditemukan DiscoverRunner
(168 berkas memuat pola `test*`, lima di antaranya bukan modul tes: `tests/__init__.py`,
`tests_utils.py`, dan `pasien/tests.py` yang kosong), tersebar pada empat
aplikasi (akreditasi 841, sdm 816, pasien 86, accounts 71, config 4), dengan 4.448 asersi.
Kualitas penulisan tes sudah wajar untuk ukuran basis kode 72.198 LOC. Masalahnya bukan
kekurangan tes.

Masalahnya ada tiga, berurutan dari yang paling mahal.

**Pertama, tidak ada satu pun gate yang menjalankan seluruh tes itu.** Workflow satu-satunya
(`security-tests.yml`) berjalan pada `push` ke `main` — dan **tidak ada branch bernama
`main`** di repo ini, baik lokal maupun di `origin`. Seluruh kode mendarat di `master`, dan
default branch `origin` adalah `master`. Akibatnya: sejak workflow itu dibuat pada 31 Oktober
2026, **belum pernah dieksekusi satu kali pun**. Suite keamanan yang oleh penulisnya
didokumentasikan "155 tes, hijau, kontrak hijau berarti sudah diperbaiki" itu adalah
kontrak yang tidak pernah diuji oleh mesin mana pun.

**Kedua, delapan tes sudah merah di `master`, termasuk satu kebocoran data nyata.** Commit
`46ba56e` (31 Okt) mengubah `dokumen_kredensial_edit` dari `get_object_or_404(...)` menjadi
`filter(...).first()` plus auto-generate. Efek sampingnya: draf milik pegawai lain tidak lagi
mengembalikan 404 — view justru membuat draf baru untuk pemanggil, melewati tiga view
(`edit`, `finalize`, `download`). Tiga tes yang menguji persis skenario ini sudah merah sejak
commit itu mendarat, dan tidak ada yang tahu karena tidak ada gate. Lima kegagalan lainnya
adalah asersi yang sudah usang terhadap perilaku yang memang diinginkan: migrasi `sdm.0015`
menyemai 23 baris `MasterProfesiPegawai` sehingga "master profesi kosong" tidak lagi benar,
satu asersi `assertNotContains` terlalu luas (katalog tindakan bersama terbawa ke halaman
pegawai lain), dan audit katalog RKK sudah tidak lagi keluar non-zero saat ada gap.

**Ketiga, umpan balik pengembang lambat.** Satu putaran penuh memakan **±17 menit serial**
karena `manage.py test --parallel` rusak (`TypeError: cannot pickle 'traceback' object`),
sehingga paralelisasi bawaan Django tidak dapat dipakai sama sekali.

Di sisi lain, aset QA terkuat justru tidak dipakai: harness `qa/` sudah membuktikan dirinya
dengan 145.000 permintaan atas 1.295 akun tanpa satu pun HTTP 500 dan tanpa pasangan flaky —
tapi berjalan lokal saja dan tidak pernah masuk CI.

Strategi v3.0 karena itu **tidak menambah volume tes** sebagai prioritas pertama. Urutannya:
(1) memperbaiki trigger CI agar gate benar-benar berjalan, (2) menyalakan gate pada suite
penuh, (3) memulihkan paralelisasi agar umpan balik turun di bawah 5 menit, (4) memulihkan
delapan kegagalan yang sudah hidup, (5) baru kemudian memperluas ke lapisan E2E dan performa.
Target akhir: *defect escape rate* < 3%, gate hijau setiap PR, durasi CI penuh < 15 menit.

---

### 2. Scope & Objectives

#### Cakupan (In-Scope):

1. **Modul Akreditasi (841 tes):** 16 Bab Standar STARKES, Matriks PDCA 7-kolom, Elemen
   Penilaian (EP) beserta sinkronisasi katalog, instrumen 2024, indikator mutu nasional (INM),
   matriks rekap KPS, FMEA/RCA, manajemen risiko, laporan mutu, dan kendali data terpadu.
2. **Modul SDM / Human Capital (816 tes):** data pegawai dan penempatan, rekrutmen, formasi,
   kinerja, K3, diklat, kredensial (RKK, STR/SIP/SIK/SPK), logbook klinis (katalog tindakan,
   jenjang profesi, rekap 36 bulan), alur intake massal, ekspor, dan storage privat.
3. **Modul Pasien (86 tes):** pendaftaran, IGD (triage, GCS, critical value), rawat jalan,
   revisi asesmen, laboratorium, consent, booking, dan object-level authorization.
4. **Modul Accounts & Kontrol (71 tes):** RBAC 10 peran, hierarki unit kerja 4-level, kontrol
   akses per kapabilitas, privilege escalation, sesi, allowed hosts, dan survey freeze.
5. **Modul Config (4 tes):** konfigurasi allowed hosts dan setelan lingkungan.
6. **Lintas-modul:** scoring otomatis kelulusan, kalkulasi rekapitulasi, unggahan berkas bukti,
   integrasi AI (DeepSeek), dan ketahanan terhadap error 500 pada seluruh 339 pola URL.

#### Di Luar Cakupan (Out-of-Scope):

- **Integrasi pihak ketiga tingkat SLA** (Supabase Storage, Railway, Vercel): diuji pada
  tingkat kontrak — payload, signature, penanganan kegagalan — bukan ketersediaan layanan.
- **Driver perangkat keras fisik** (printer thermal, scanner KTP): diverifikasi pada tingkat
  format payload (ESC/POS, PDF, struktur respons), bukan perangkat nyata.
- **Migrasi data historis pra-2026-09**: selesai dan tidak diubah; dijaga agar migrasi baru
  tetap `makemigrations --check` bersih.
- **UI/UX pixel-level**: belum ada visual regression; ditunda ke Fase 4 karena 164 template
  belum memiliki `data-testid` sehingga selector akan rapuh (lihat §6).

#### Sasaran Terukur (Objectives):

1. **Mengaktifkan gate CI yang benar-benar berjalan** pada seluruh 1.818 tes dengan status
   hijau, tidak lebih dari **2 minggu** dari tanggal efektif dokumen ini.
2. **Menurunkan durasi umpan balik PR** dari ±17 menit serial menjadi **< 5 menit** melalui
   paralelisasi yang berfungsi, dengan *parallel efficiency* > 3× pada 4 shard.
3. **Menurunkan *defect escape rate*** dari baseline belum terukur menjadi **< 3%** pada akhir
   Q1 2027 — ukuran ini hanya punya arti setelah gate aktif.
4. **Mencapai nol tes merah di `master`** pada akhir Fase 1, dan memisahkan 38 asersi
   sengaja-merah menjadi gate keamanan terpisah yang eksplisit.
5. **Memasukkan harness `qa/` ke CI terjadwal** (nightly) pada Fase 2, sehingga cakupan
   145.000 permintaan itu menghasilkan sinyal, bukan laporan lokal yang tidak dibaca.

---

### 3. Test Levels & Types

| Level Pengujian | Ruang Lingkup Validasi | Pemilik | Framework & Alat | Volume Saat Ini | Target Rasio | Frekuensi Eksekusi |
|---|---|---|---|---|---|---|
| **Unit** | Model Django, `save()`, `full_clean()`, kalkulasi skor, rekap logbook, aturan intake | Software Engineer | Django `TestCase`/`SimpleTestCase` | **536 tes (30%)** | 55–60% | Setiap commit |
| **Integrasi (view-level)** | Permintaan HTTP via test client, penegakan RBAC per view, unit scoping, alur multi-model | SE + QA | Django test client + SQLite in-memory | **1.288 tes (70%)** | 30–35% | Setiap PR |
| **E2E** | Alur kritis pengguna menyeluruh melalui peramban | QA Automation | *belum ada* | **0 tes** | 5% | Pre-deploy & nightly |
| **API Contract** | Endpoint JSON, skema respons, kode status per peran | SE | Matriks ekspektasi `qa/expectations.py` | 82 endpoint terpetakan (harness `qa/`, di luar CI) | Per endpoint aktif | Nightly |
| **Security & RBAC** | Privilege escalation, IDOR, unit scoping, sesi, token, OWASP Top 10 | QA Security | Django `TestCase` + asersi sengaja-merah | 155 tes di 13 modul; 38 asersi `self.fail()` | Modul akun & audit | Setiap build rilis |
| **Performance** | Waktu respons endpoint terpadat, akses bersamaan | DevOps/QA | *belum ada* | 0 | Endpoint terpadat | Pra-survei & bulanan |
| **Visual / A11y** | Regresi tata letak, WCAG 2.2 AA | QA/Frontend | *belum ada* | 0 | Halaman kunci | Nightly |

**Catatan penting soal level E2E.** Versi 2.0 merekomendasikan Playwright TypeScript.
Rekomendasi itu **belum diadopsi dan tidak diadopsi pada Fase 1–2**. Alasannya terukur: 164
template tidak memiliki satu pun `data-testid`, sehingga selector peramban akan menguji
struktur markup, bukan perilaku pengguna, dan setiap perubahan markup memecahkan suite.
Fase 1–2 menempuh jalur lebih murah dulu — memperluas cakupan alur kritis melalui test
client dan harness `qa/` yang sudah membuktikan dirinya — dan menunda Playwright sampai ada
kebutuhan nyata yang tidak dapat dipenuhi di lapisan HTTP.

**Catatan soal cakupan security.** Selisih 155 (yang dijanjikan gate) terhadap 38
`self.fail()` yang ditemukan bukan inkonsistensi: 16 temuan P0 sudah **diperbaiki** pada
commit `2b78c0a` (31 Okt), sehingga asersi `self.fail()` itu kini tidak pernah tercapai dan
suite hijau. Yang belum diverifikasi adalah apakah suite itu benar-benar berjalan — dan
jawabannya belum, karena workflow-nya terpasang pada branch yang tidak ada.

---

### 4. Test Pyramid Analysis

#### Kondisi Saat Ini (terukur 2026-11-02):

| Level | Jumlah Tes | Proporsi | Durasi Terukur |
|---|---|---|---|
| Unit (model/logic, tanpa test client) | 536 | 29,5% | — |
| Integrasi (view-level, dengan test client) | 1.288 | 70,5% | — |
| E2E (peramban) | 0 | 0% | — |
| **Total** | **1.818** | 100% | **±17 menit serial** |

Rincian durasi per aplikasi (eksekusi serial, SQLite in-memory):

| Aplikasi | Tes | Durasi | Rasio | Kegagalan |
|---|---|---|---|---|
| `akreditasi` | 841 | 753,4 s | 0,90 s/tes | 0 |
| `sdm` | 816 | 97,4 s | 0,12 s/tes | **8** |
| `pasien` | 86 | 94,1 s | 1,09 s/tes | 0 |
| `accounts` + `config` | 75 | 68,2 s | 0,91 s/tes | 0 |
| **Total** | **1.818** | **1.013,1 s (±16,9 menit)** | 0,56 s/tes | **8** |

Rincian delapan kegagalan tersebut, diklasifikasi agar penanganannya berbeda:

| Tes | Akar Penyebab | Sifat |
|---|---|---|
| `test_dokumen_kredensial_ui` × 3 (`edit`, `finalize`, `download`) | Commit `46ba56e` mengganti `get_object_or_404` dengan `filter().first()` + auto-generate; draf pegawai lain tidak lagi 404 | **Regresi nyata (kebocoran data)** |
| `test_empty_profession_master_does_not_block_intake` | Migrasi `sdm.0015` menyemai 23 baris `MasterProfesiPegawai`; asersi "master kosong" sudah usang | Asersi usang |
| `test_nakes_cannot_read_another_employees_logbook` | `assertNotContains` terlalu luas — katalog tindakan **bersama** ikut terbawa, bukan data pegawai lain | Asersi usang (false positive) |
| `test_audit_reports_missing_profession` | Audit RKK tidak lagi melaporkan "gap ditemukan" padahal seharusnya ya | Asersi usang |
| `test_audit_strict_exits_nonzero_on_gap` | Mode `--strict` tidak keluar non-zero saat ada gap | Asersi usang |

Yang pertama adalah bug produksi yang harus ditambal; empat sisanya adalah tes yang menguji
perilaku yang sudah tidak diinginkan. Keduanya sama-sama merah, dan keduanya sama-sama tidak
terlihat selama ini — itu inti masalahnya.

**Diagnosis bentuk: piramida pendek dengan puncak hilang dan dasar tipis.**

Bentuknya *bukan* ice cream cone terbalik — proporsi integrasi memang di atas unit, tapi
bukan karena E2E berlebihan; E2E-nya nol. Yang terjadi lebih halus:

- **Dasar tipis.** 536 tes unit untuk 72.198 LOC berarti rasio tes:sumber hanya **0,46**.
  Aturan bisnis padat (scoring akreditasi, rekap logbook, intake massal) sedang diuji lewat
  test client, artinya setiap cacat logika membutuhkan satu permintaan HTTP penuh untuk
  terungkap, bukan satu pemanggilan fungsi.
- **Puncak hilang.** Nol E2E berarti tidak ada pengujian yang membuktikan alur lintas-modul
  bekerja ketika template, URL, dan sesi disatukan. Yang menutup celah ini sekarang hanya
  harness `qa/` — dan itu berjalan manual.
- **Tidak ada yang menonton.** Ini temuan paling mahal. 1.818 tes ada, delapan merah di
  `master`, dan tidak ada gate yang mengeluh. Tes yang tidak dijalankan bernilai nol,
  terlepas dari jumlahnya.

#### Target Kondisi Ideal (akhir Q1 2027):

| Level | Jumlah Tes | Proporsi | Target Durasi |
|---|---|---|---|
| Unit | 900–1.100 | 55–60% | < 40 s |
| Integrasi (view-level) | 500–650 | 30–35% | < 90 s |
| E2E (HTTP-level, alur kritis) | 60–90 skenario | 5% | < 60 s |
| **Total** | **~1.700–1.800** | 100% | **< 5 menit (PR gate)** |

Volume total **tidak bertambah** — bahkan sedikit menurun. Yang berubah adalah komposisi:
tes validasi field dan aturan bisnis yang kini mengantar permintaan HTTP penuh diturunkan
satu level menjadi tes unit murni, dan slot yang dibebaskan dipakai untuk alur kritis
lintas-modul. Gate penuh (1.818 tes) tetap dijalankan pada merge ke `master` dan nightly,
tidak dipangkas.

#### Rencana Transisi:

1. **Salin dulu, ubah kemudian.** Sebelum menurunkan satu tes pun, gate harus hijau.
   Memindahkan tes yang sudah gagal hanya akan menyembunyikan regresi.
2. **Bekukan pertumbuhan view-level.** Tidak ada tes test-client baru untuk validasi field,
   aturan model, atau kalkulasi yang dapat diuji langsung. PR baru yang menyentuh logika
   bisnis wajib membawa tes unit.
3. **Uji dulu, jangan karantina dulu.** Pisahkan tes yang benar-benar flaky dari tes yang
   mengungkap bug nyata. Karantina tes yang menyembunyikan race condition adalah cara
   regresi lolos ke produksi (lihat §11).
4. **Jangan tambah E2E peramban di Fase 1–2.** Perluas alur kritis di lapisan HTTP lebih
   dahulu; Playwright baru dipertimbangkan setelah `data-testid` tersedia (§6).

---

### 5. Risk Assessment Matrix (5×5)

Skor = Dampak (1–5) × Peluang (1–5); 15–25 CRITICAL, 10–14 HIGH, 5–9 MEDIUM, 1–4 LOW.

| Komponen / Fitur | Dampak | Peluang | Skor | Tingkat | Strategi Pengujian |
|---|---|---|---|---|---|
| **Kontrol akses hierarki & privilege escalation** | 5 | 3 | **15** | **CRITICAL** | Automasi penuh + eksplorasi manual berkala; asersi sengaja-merah sebagai gate terpisah; pemantauan audit log |
| **Unit scoping & object-level authorization** | 5 | 3 | **15** | **CRITICAL** | Matrix testing peran × unit, boundary scoping, uji regresi lintas-pegawai |
| **Dokumen kredensial & storage privat** | 5 | 3 | **15** | **CRITICAL** | Uji cakupan pemilik draf, verifikasi SHA/size berkas, penolakan unduhan silang |
| **Logbook klinis & rekap 36 bulan** | 4 | 4 | **16** | **CRITICAL** | Unit test kalkulasi rekap, batas jendela waktu, mandiri vs supervisi |
| **Intake massal pegawai & finalisasi draf** | 4 | 3 | **12** | **HIGH** | Transaksional atomik, idempotensi `idempotency_key`, kontrol versi draf |
| **Scoring otomatis STARKES & rekap KPS** | 4 | 2 | **8** | **MEDIUM** | Regresi matematis skor, pembulatan, sinkronisasi katalog |
| **Alur klinis pasien (IGD, Rajal, Ranap)** | 4 | 2 | **8** | **MEDIUM** | Integrasi alur status kunjungan, validasi nilai kritis (GCS, EWS) |
| **Integrasi sanitasi AI DeepSeek** | 4 | 2 | **8** | **MEDIUM** | Contract test dengan mock, uji redaksi data privat pasien |
| **Ekspor (xlsx/pdf)** | 3 | 3 | **9** | **MEDIUM** | Struktur berkas dan kelengkapan kolom, bukan render visual |
| **Profil RS, master kamar, katalog tindakan** | 2 | 2 | **4** | **LOW** | Smoke test CRUD dasar |

**Temuan risiko hidup (per 2026-11-02).** Skor 15 pada baris "Dokumen kredensial" bukan
hipotetis. Commit `46ba56e` mengubah `dokumen_kredensial_edit` dari
`get_object_or_404(DrafDokumenKredensial, pegawai=pegawai, jenis=jenis)` menjadi
`filter(...).first()` diikuti auto-generate bila draf tidak ada. Efek sampingnya: draf milik
pegawai lain tidak lagi menghasilkan 404 — view justru membuat draf baru untuk pemanggil.
Tiga view (`edit`, `finalize`, `download`) terdampak, dan tes yang menguji persis skenario ini
sudah merah sejak commit itu mendarat. Karena tidak ada gate, tidak ada yang tahu. Ini alasan
paling langsung mengapa §10 menempatkan gate hijau sebagai prasyarat mutlak rilis.

---

### 6. Environment Strategy

| Environment | Tujuan | Tipe Pengujian | Data | Pemicu |
|---|---|---|---|---|
| **Local** | Umpan balik pengembang (TDD) | Unit, integrasi | SQLite in-memory, migration dimatikan (`config/control_test_settings.py`) | On save |
| **CI (GitHub Actions)** | Validasi otomatis | Unit, integrasi, security, lint, `manage.py check`, `makemigrations --check` | Ephemeral, SQLite in-memory | Pada push/PR |
| **Staging (Railway/Vercel Preview)** | Validasi pra-produksi | Harness `qa/` (matrix peran × URL), smoke E2E | Production-like (anonimisasi) | Pada merge ke `master` |
| **Production** | Pemantauan & smoke | Smoke test, health check sintetis, audit log | Live | Pada deploy |

**Catataan manajemen data.** Pengujian Django memakai `config/control_test_settings.py`: DB
in-memory, `MIGRATION_MODULES` dinonaktifkan untuk keempat aplikasi, hasher MD5, cache
LocMem, storage berkas lokal. Ini membuat eksekusi cepat, tapi punya konsekuensi yang perlu
dicatat eksplisit: **tes tidak pernah menjalankan migrasi**. Salah satu kegagalan hari ini
berasal langsung dari konseku ini — migrasi `sdm.0015` menyemai 23 baris `MasterProfesiPegawai`
di basis data pengembangan, sementara tes mengasumsikan tabel itu kosong. Ketika gate CI
menyala, setiap asumsi "tabel ini kosong" harus diverifikasi terhadap basis data uji, bukan
basis data pengembang.

**Catatan soal `data-testid`.** 164 template tidak memiliki satu pun atribut `data-testid`.
Selama atribut itu tidak ada pada template kunci, E2E peramban akan menguji struktur markup
alih-alih perilaku pengguna, dan setiap perubahan markup memecahkan suite. Karena itu
penambahan `data-testid` pada template kunci adalah prasyarat Fase 3, bukan pekerjaan
kosmetik.

---

### 7. Tool Selection Rationale

Versi 2.0 merekomendasikan `pytest-django` + `pytest-xdist` dan Playwright TypeScript.
Keduanya **tidak diadopsi** dan tetap tidak diadopsi pada Fase 1–2. Penilaian ulang
dilakukan terhadap kenyataan repo, bukan preferensi umum:

| Kriteria (bobot) | Django `manage.py test` | pytest-django + xdist | Playwright |
|---|---|---|---|
| **Sudah terpasang & terpakai** (30%) | 5 (1,50) | 1 (0,30) | 1 (0,30) |
| **Kesesuaian dengan 1.818 tes yang ada** (25%) | 5 (1,25) | 3 (0,75) | 1 (0,25) |
| **Kemudahan pemeliharaan** (20%) | 4 (0,80) | 3 (0,60) | 2 (0,40) |
| **Dukungan komunitas & CI** (15%) | 5 (0,75) | 5 (0,75) | 5 (0,75) |
| **Kecepatan eksekusi** (10%) | 2 (0,20) | 5 (0,50) | 5 (0,50) |
| **Biaya lisensi** (0%) | 5 (0) | 5 (0) | 5 (0) |
| **Total skor tertimbang** | **4,50** | **2,90** | **2,20** |

**Keputusan:** tetap pada `manage.py test` untuk Fase 1–2. Argumennya bukan preferensi,
melainkan biaya migrasi: memindahkan 1.818 tes ke pytest berarti menyentuh 163 modul sebelum
satu pun gate menyala, dan selama itu regresi tetap tidak terdeteksi. Paralelisasi diselesaikan
lebih dulu dengan `--parallel` bawaan Django (perbaikan bug pickling, atau sharding per
aplikasi di CI), yang tidak memerlukan perubahan satu pun tes.

`pytest` + `coverage` dimasukkan pada Fase 2 sebagai **pelengkap**, bukan pengganti: dipakai
mengukur cakupan baris per aplikasi dan menjalankan subset tes yang terpengaruh diff pada PR.
Playwright ditunda hingga prasyarat `data-testid` terpenuhi (§6).

---

### 8. CI Scaling Levers

Kendala sebenarnya adalah umpan balik, bukan jumlah tes. Tuas yang dipakai, berurutan dari
paling murah:

1. **Perbaiki trigger CI (paling murah, paling mahal dampaknya).** `security-tests.yml`
   berjalan pada `push` ke `main` — branch itu **tidak ada**. Seluruh kode mendarat di
   `master`, dan default branch `origin` adalah `master`. Perbaikan satu baris
   (`branches: [main]` → `branches: [master]`) membuat suite 155 tes itu benar-benar berjalan
   untuk pertama kalinya. Ini diselesaikan sebelum pekerjaan paralelisasi apa pun dimulai.
2. **Perbaiki paralelisasi.** `manage.py test --parallel 4` gagal dengan
   `TypeError: cannot pickle 'traceback' object` pada Django 6.1.2 — menghalangi paralelisasi
   bawaan sama sekali. Dua jalan keluar: memperbaiki cara traceback diserialisasi pada runner
   kustom, atau memakai **sharding per aplikasi di CI** (`akreditasi`, `sdm`, `pasien`,
   `accounts`+`config` sebagai empat job terpisasi). Yang kedua lebih dapat diandalkan karena
   tidak bergantung pada internal Django, dan keempat aplikasi sudah terpisah secara natural.
3. **Sharding per aplikasi.** Dengan empat job, waktu dinding teoritis turun dari ±17 menit
   menjadi ±13 menit (dibatasi oleh `akreditasi`, job terpanjang). Efisiensi paralel =
   jumlah durasi tes ÷ waktu dinding; target mendekati 4× tercapai hanya setelah job terpanjang
   dipecah lebih lanjut.
4. **Pecah job terpanjang.** `akreditasi` menyumbang 753 detik dari total 1.013 detik (74%).
   Tanpa memecahnya, menambah shard tidak membantu. Pecah berdasarkan direktori modul tes
   (mis. `tests_ep_*`, `tests_indikator_*`, `tests_mutu_*`, sisanya), lalu ukur ulang.
5. **Test Impact Analysis.** Jalankan hanya tes yang berkaitan dengan berkas yang berubah pada
   PR, dengan graph dependensi sederhana berbasis impor. **Suite penuh tetap wajib** pada merge
   ke `master` dan nightly, supaya tidak ada tes yang membusuk tanpa terlihat.
6. **Caching.** Cache `.venv` dan wheel antar-run. Penghematan terbesar ada di sini: setup
   lingkungan adalah biaya tetap yang muncul di setiap job dan setiap shard.
7. **Selective gating.** Gate PR menjalankan unit + integrasi + security (target < 5 menit);
   harness `qa/` penuh dan uji ekspor dijalankan nightly, bukan per PR.

**Cara mengukur payoff:** *parallel efficiency* = jumlah durasi tes ÷ waktu dinding. Nilai
rendah berarti biaya tetap (instal, build, migrasi) atau satu tes sangat panjang
(*long pole*) memakan seluruh keuntungan. Lacak juga **CI-menit-per-PR** untuk mendeteksi
paralisasi yang memotong waktu dinding tapi membengkakkan konsumsi menit.

---

### 9. Entry & Exit Criteria

#### Kriteria Masuk (Entry Criteria):

- [ ] `manage.py check` → nol issue (satu check pre-existing yang di-silence dapat diterima).
- [ ] `makemigrations --check --dry-run` → tidak ada perubahan.
- [ ] Trigger workflow menunjuk ke branch yang benar-benar ada (`master`, bukan `main`).
- [ ] Seluruh 1.818 tes telah dieksekusi setidaknya sekali di CI, dan hasilnya tercatat.
- [ ] Basis data uji terisolasi (SQLite in-memory, tidak menyentuh `db.sqlite3` atau
      `DATABASE_URL`).
- [ ] Tidak ada dependensi dengan kerentanan kritis CVE.

#### Kriteria Keluar (Exit Criteria):

- [ ] Gate PR: unit + integrasi + security hijau, durasi < 5 menit.
- [ ] Gate merge/nightly: seluruh 1.818 tes hijau, atau kegagalan terdaftar eksplisit pada
      daftar karantina beserta pemilik dan tanggal jatuh tempo.
- [ ] Nol temuan bug P0 (crash/kehilangan data) dan P1 (fitur utama macet) yang terbuka.
- [ ] Seluruh asersi sengaja-merah (`self.fail()`) berada pada gate terpisah yang statusnya
      diketahui dan terdokumentasi — bukan kegagalan senyap di suite utama.
- [ ] Waktu respons 25 endpoint utama < 800 ms (diukur di staging, bukan asumsi).
- [ ] Audit log memverifikasi tidak ada kebocoran kredensial atau data pasien polos.

---

### 10. Quality Gates & Definition of Done (DoD)

#### Gate PR (pemblok penggabungan):

1. Seluruh tes unit + integrasi + security lolos hijau.
2. Penambahan logika bisnis disertai tes unit; rasio unit terhadap total tes tidak turun.
3. `manage.py check` dan `makemigrations --check` bersih.
4. Nol peringatan linter pada berkas yang diubah.
5. Minimal satu persetujuan review Tech Lead/QA.

#### Gate Merge (menuju `master`):

6. Suite penuh (1.818 tes) dijalankan dan hijau, dengan daftar karantina eksplisit bila ada.
7. Migrasi teruji maju (*forward*); `makemigrations --check` tetap bersih.
8. Perubahan pada `accounts/` atau `sdm/views.py` memicu peninjauan keamanan wajib
   (modul ini memegang seluruh skor CRITICAL pada matriks risiko §5).

#### Gate Rilis (staging ke produksi):

9. Seluruh kriteria keluar terpenuhi.
10. Harness `qa/` dijalankan terhadap staging: nol HTTP 500, nol pasangan flaky.
11. Backup basis data terverifikasi aktif.
12. Dokumen *release notes* dan panduan pembaruan fitur disahkan, sesuai
    `docs/06_STANDAR_OPERASIONAL_UPDATE_FITUR.md`.

**Prinsip yang mengikat:** gate yang merah bukan halangan yang boleh dilewati dengan
persetujuan. Sebuah gate yang boleh dilewati bukan gate. Bila sebuah tes merah karena alasan
yang sah (mis. sengaja memamerkan kerentanan yang belum ditambal), tes itu **dipindahkan ke
suite terpisah yang eksplisit merah**, bukan dibiarkan gagal di suite utama — dengan alasan
yang sama mengapa kita tidak mematikan alarm kebakaran karena sering berbunyi.

---

### 11. Metrics & KPIs

| Metrik Kualitas | Definisi | Target Operasional | Frekuensi Evaluasi |
|---|---|---|---|
| **Status Gate CI** | Apakah suite penuh berjalan otomatis dan berapa yang hijau | 100% berjalan; ≥ 99% hijau (sisanya terkarantina eksplisit) | Setiap PR |
| **Tes Merah di `master`** | Jumlah tes yang gagal pada commit terbaru | **0** (saat ini: 8) | Harian, otomatis |
| **CI Wall-Clock Time** | Durasi gate dari push hingga status final | < 5 menit (PR), < 15 menit (penuh) | Mingguan |
| **Parallel Efficiency** | Jumlah durasi tes ÷ waktu dinding | > 3× pada 4 shard | Per perubahan pipeline |
| **Rasio Piramida** | Proporsi unit : integrasi : E2E | 55–60% : 30–35% : 5% | Bulanan |
| **Code Coverage** | Baris kode tercakup tes otomatis | ≥ 65% total, ≥ 80% modul kritis | Setiap PR (Fase 2) |
| **Flakiness Rate** | Tes gagal lalu lolos saat diulang | < 1,5% | Mingguan |
| **Defect Escape Rate** | Cacat yang baru ditemukan di produksi | < 3% dari total temuan | Per rilis |
| **MTTR** | Rata-rata waktu deteksi hingga perbaikan P0/P1 | < 3 jam (P0), < 12 jam (P1) | Per insiden |
| **Test-to-Source Ratio** | Baris tes ÷ baris sumber | ≥ 0,60 (saat ini: 0,46) | Bulanan |

**Soal *flakiness rate*.** Versi 2.0 menetapkan target < 1,5% tanpa pernah mengukurnya.
Sebelum target itu punya arti, perlu dicatat bahwa harness `qa/` sudah melaporkan **nol
pasangan flaky** atas 145.000 permintaan — jadi baseline suite HTTP jauh lebih sehat daripada
yang diasumsikan dokumen sebelumnya. Yang belum terukur justru sebaliknya: karena suite Django
tidak pernah berjalan berulang di CI, tidak ada data rerun sama sekali. Pengukuran flakiness
baru dapat dimulai setelah gate aktif, dan angka < 1,5% ditetapkan sebagai target Fase 2, bukan
klaim status saat ini.

---

### 12. Timeline & Milestones

- **Fase 1 — Fondasi & Stabilisasi (Bulan 1 / November 2026):**
  - **Memperbaiki trigger CI** dari `main` ke `master` — gate 155 tes keamanan akhirnya
    benar-benar berjalan.
  - Menyalakan gate CI pada suite penuh dengan sharding per aplikasi (§8).
  - Memperbaiki atau mengakali `--parallel` yang rusak; mengukur *parallel efficiency*.
  - Memulihkan delapan kegagalan di `sdm` menjadi hijau: menambal kebocoran draf dokumen
    kredensial lintas-pegawai, lalu memperbaiki empat asersi yang menguji perilaku yang sudah
    tidak diinginkan (§4).
  - Memisahkan 38 asersi `self.fail()` menjadi gate keamanan terpisah yang eksplisit.
  - **Kriteria selesai:** gate PR hijau, nol tes merah di `master`, durasi PR < 5 menit.

- **Fase 2 — Cakupan & Pengukuran (Bulan 2–3 / Desember 2026 – Januari 2027):**
  - Memasang `coverage` dan melaporkan cakupan per aplikasi pada setiap PR.
  - Menurunkan 150–250 tes validasi field dan aturan bisnis dari level view ke level unit.
  - Memasukkan harness `qa/` ke CI nightly terhadap staging.
  - Menambah `data-testid` pada template kunci sebagai prasyarat Fase 3.
  - **Kriteria selesai:** rasio unit ≥ 55%, cakupan total ≥ 65%, nightly `qa/` aktif.

- **Fase 3 — E2E & Karantina Otomatis (Bulan 4–5 / Februari – Maret 2027):**
  - Membentuk 60–90 skenario alur kritis lintas-modul di lapisan HTTP (bukan peramban),
    memakai `data-testid` yang sudah tersedia.
  - Menerapkan karantina otomatis dengan tanggal jatuh tempo, bukan karantina tanpa batas.
  - Mengukur *flakiness rate* dari data rerun nyata, bukan asumsi.
  - **Kriteria selesai:** 60–90 skenario alur kritis, flakiness < 1,5% terukur.

- **Fase 4 — Optimasi & Audit Berkelanjutan (Bulan 6 / April 2027):**
  - Uji performa pada endpoint terpadat (matriks PDCA, dashboard antrean, ekspor).
  - Visual regression dan audit aksesibilitas pada halaman kunci.
  - Pertimbangan Playwright hanya bila lapisan HTTP terbukti tidak memadai.
  - Tinjauan efektivitas strategi semesteran.

---

### 13. Revision History

| Versi | Tanggal | Penulis | Perubahan Utama |
|---|---|---|---|
| 1.0 | 2026-09-24 | QA Lead | Dokumen inisiasi awal SIK AP akreditasi |
| 2.0 | 2026-10-04 | Lead Engineering & QA | Ekspansi menyeluruh ke seluruh modul (Pasien, STARKES, RBAC, AI, KPS), definisi piramida uji 70/20/10, integrasi penjaminan mutu pasca-investigasi error 500 |
| 3.0 | 2026-11-02 | Lead Engineering & QA | **Penulisan ulang berbasis pengukuran.** Jumlah tes dikoreksi dari 15 menjadi 1.818 terukur (163 modul terhitung DiscoverRunner dari 168 berkas berpola `test*`; 4.448 asersi); durasi diukur ±17 menit serial; **ditemukan workflow CI terpasang pada branch `main` yang tidak ada, sehingga suite 155 tes keamanan belum pernah berjalan sekali pun**; ditemukan 8 tes merah di `master` termasuk kebocoran draf dokumen kredensial lintas-pegawai sejak commit `46ba56e`; ditemukan `--parallel` rusak; 38 asersi sengaja-merah dipetakan; keputusan stack dikoreksi — tetap `manage.py test`, Playwright ditunda sampai `data-testid` tersedia; target rasio piramida disesuaikan menjadi 55–60% unit / 30–35% integrasi / 5% E2E; seluruh KPI diberi baseline terukur atau ditandai belum terukur |

---

### Tinjauan Ulang Dokumen

Dokumen ini ditinjau **kuartalan**, atau lebih awal bila salah satu pemicu berikut terjadi:

- Area produk baru dimasukkan (modul klinis baru, integrasi pihak ketiga baru).
- Perubahan komposisi tim (QA dedicated masuk, atau pemilik modul berganti).
- Insiden besar atau kebocoran data (memicu peninjauan matriks risiko §5 segera).
- Satu atau lebih temuan cacat lolos ke produksi (memicu peninjauan gate §10).
- Perubahan pipeline CI yang menggeser waktu dinding lebih dari 2 menit.

Pemicu yang paling sering terpicu dalam enam minggu terakhir adalah yang keempat: tanpa gate,
setiap commit berisiko menjadi temuan lolos. Fase 1 dokumen ini ada untuk mematikan pemicu itu.
