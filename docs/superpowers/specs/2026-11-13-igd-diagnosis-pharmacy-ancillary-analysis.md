# Analisis Diagnosis, Tindakan, Farmasi, dan Pemeriksaan Penunjang IGD ARIMA

**Tanggal:** 13 November 2026. **Status:** analisis dan rancangan untuk review; bukan implementasi atau persetujuan deploy.
**Baseline kode:** `112a7b3357168ec53aac6cb4c6670b8bcab86f66`, branch `master`.

## 1. Sumber dan batas analisis

| Dokumen | SHA-256 | Kebutuhan utama |
|---|---|---|
| `C:/Users/cubeb/Downloads/Tambahkan diagnosa medis tindakan klinis dan obat.docx` | `606835a388b009c9d123e22e13f9f6c26f0ed02fb51d9aee1928c0adb664bf4f` | Diagnosis medis, tindakan, peresepan, medication safety, dan mode input 3S |
| `C:/Users/cubeb/Downloads/Pemeriksaan Penunjang untuk aplikasi ARima dengan alur cascading dropdown.docx` | `a42f2b704625b6ff187bce787090909dd3bb0da1c6cfe7b9614c8a6c0433c69f` | Katalog penunjang empat tingkat, multiselect, indikasi, prioritas, persiapan |

Kedua dokumen dibaca penuh, termasuk teks tabel. Referensi baris di bawah mengikuti hasil ekstraksi dokumen, bukan nomor halaman Word. Dokumen pertama mempunyai 550 baris ekstraksi, dokumen kedua 309. Tidak ada perubahan aplikasi, migrasi, master produksi, akun, atau integrasi eksternal pada pekerjaan ini.

Rancangan ini merupakan **delta atas workflow sebelas langkah yang sudah ada**, bukan proyek SIMRS baru. Plan 12 November adalah konteks implementasi historis; jangan mengulang instruksi pembuatan fondasinya. Plan `2026-11-13-igd-structured-physical-examination.md` tetap memiliki langkah 6 dan dikecualikan dari pekerjaan ini. Saat analisis berlangsung muncul file untracked `pasien/physical_exam.py` selain tiga artefak untracked awal; itu pekerjaan lain yang harus dipertahankan.

## 2. Bukti baseline: kode berbeda dari schema dan deployment

Command yang benar-benar dijalankan:

```bash
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test pasien.tests_igd_workflow_integration pasien.tests_igd_workflow_ai pasien.tests_3s_cascade pasien.tests_laboratorium klinis --keepdb --noinput
```

**Hasil: 64 tests, OK, exit 0**, waktu test Django 31.758 detik pada pengukuran awal. Pengukuran ulang sebelum handoff juga **64 tests, OK, exit 0**, waktu 30.191 detik; log akhir `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima-clinical-plan-final-baseline.log`. Runner memakai database test SQLite dan migrasi normal, bukan database operasional. Log tersimpan di `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima-clinical-plan-baseline.log`. Ini baseline terarah, bukan full regression, bukti browser, pengujian konkurensi PostgreSQL, atau bukti deployment. Terdapat RuntimeWarning datetime naive pada fixture lama.

Probe read-only database konfigurasi saat ini menghasilkan vendor **SQLite**, bukan PostgreSQL produksi. Schema lokal baru mencatat migrasi `pasien` sampai `0020_antrean_harian_counter`; kode memiliki migrasi sampai `0025_igd_result_provenance`. Tabel `pasien_igdassessmentworkflow` belum tersedia. Karena itu halaman workflow pada DB lokal ini tidak boleh dianggap siap hanya karena test DB baru lulus. Tidak ada migrasi lokal yang dijalankan dalam analisis ini.

| Master lokal | Jumlah terukur |
|---|---:|
| ICD-10 | 172 |
| ICD-9-CM | 170 |
| SDKI | 27 |
| SLKI | 20 |
| SIKI | 18 |
| Pemetaan 3S | 22 |
| Tarif tindakan kasus | 397 |

Order penunjang, resep, detail resep, dan tindakan asesmen masing-masing 0 di SQLite lokal yang diperiksa. Angka ini **bukan** inventaris produksi. Tidak dilakukan query/readback deployment atau pemeriksaan browser pada pekerjaan perencanaan ini. Cakupan master juga bukan bukti katalog nasional lengkap.

## 3. Matriks kebutuhan terhadap implementasi

| ID | Sumber | Kondisi kode yang diamati | Delta yang direncanakan |
|---|---|---|---|
| DG01 | Dok.1:5–9 | `diagnosa_masuk` dan satu `diagnosis_mode` bersama; autocomplete dan actual AI sudah ada | Daftar diagnosis terstruktur dengan utama/sekunder, mode dan provenance per item |
| DG02 | Dok.1:9 | AI mengirim istilah klinis terseleksi, triase, sebagian vital; belum konteks pemeriksaan fisik/hasil penunjang | Konteks terstruktur yang dibatasi dan bertanda sumber; tanpa mengambil identitas/free text pasien secara mentah |
| AC01 | Dok.1:11–17 | `plan_action`, `execute`, `cancel_action`, ICD9, quantity, actor/time dan billing sudah ada | UI Manual/Master/AI tindakan; lokasi/keterangan dan waktu pelaksanaan eksplisit; provenance AI |
| RX01 | Dok.1:18–25 | Resep/detail masih nama, dosis/signa teks; tidak ada master obat | Katalog empat tingkat, produk dan generik-kekuatan, komposisi, flag multipilihan, Fornas/RS |
| RX02 | Dok.1:522–530 | Signa teks dan jumlah integer; tidak ada kalkulasi unit-aware | Frekuensi/dosis/unit/rute/waktu/durasi terstruktur dan jumlah estimasi terverifikasi server |
| RX03 | Dok.1:531–535 | Alergi teks tersedia, belum engine medication safety/PPRA | Penilaian alergi, duplikasi, risk acknowledgement, PPRA berbasis kebijakan versi dan persetujuan tercatat |
| NS01 | Dok.1:536–549 | SDKI→SLKI→SIKI sudah dipetakan; mode global menyatukan seluruh komponen | Mode independen per komponen, kandidat AI sesuai SDKI/SLKI, alasan override hubungan |
| PX01 | Dok.2:1–304 | Order LAB/RADIOLOGI/EKG/LAINNYA dan hasil ada; katalog empat tingkat belum ada | Katalog kategori→instalasi→kelompok→item dan basket multiselect |
| PX02 | Dok.2:305–309 | Prioritas ada; indikasi opsional pada workflow; parameter/kondisi sampel hanya jalur legacy | Indikasi wajib saat kirim, ICD10 opsional untuk diagnosis sementara manual, persiapan terstruktur sesuai item |

### Titik reuse yang benar-benar ditemukan

- `klinis/models.py:41–68,135–201`: ICD10, ICD9, master 3S dan `Pemetaan3S`.
- `pasien/forms_igd_workflow.py:12–29`: ownership field sebelas langkah; langkah 8 menggunakan field diagnosis lama.
- `pasien/services/igd_planning.py:11–59`: validasi mode global, canonical label master, tiket AI, hubungan 3S.
- `klinis/services/ai_igd.py:15–68`: transport backend yang benar-benar memanggil AI, gate `ai_enabled` dan `ai_enable_igd`, validasi kode kandidat, pemetaan luaran/intervensi dari katalog. Bukan sekadar keyword ranking yang diberi label AI.
- `static/js/igd-clinical-controls.js:168–215`: autocomplete, tombol mapping 3S, permintaan dan penerimaan kandidat AI.
- `pasien/services/igd_actions.py:38–42,53–167,173–218`: order, plan, execute, cancel, hasil dan dispatcher transaksi dengan UUID/digest/version.
- `pasien/models.py:890–1002`: `OrderPenunjang`, `ResepElektronik`, `ResepDetail`.
- `pasien/services/igd_finalization.py:18–32`: snapshot saat ini sudah menyertakan order, CPPT dan tindakan, tetapi belum resep/daftar diagnosis baru.
- `pasien/urls.py:9–19,36–42,123–137`: route workflow dan farmasi; daftar legacy guard tidak mencakup mutator resep.
- `templates/pasien/_igd_workflow_operations.html:1–14`: panel order/hasil dan plan/execute/billing yang perlu diperluas, bukan diganti keseluruhan.

## 4. Koreksi dan keputusan spesifikasi

1. **KFA bukan master diagnosis ICD-10.** Pertahankan sistem kode terpisah: diagnosis ICD10, prosedur ICD9, produk farmasi KFA. Field dan kesiapan mapping SATUSEHAT tidak berarti integrasi nasional sudah aktif; pekerjaan ini tidak mengaktifkan outbound sync.
2. **Contoh kode 3S harus cocok dengan master.** Lokal memuat `D.0077 — Nyeri Akut`, `D.0001 — Bersihan Jalan Napas Tidak Efektif`, `L.08066 — Tingkat Nyeri`, `L.01001 — Bersihan Jalan Napas`, `I.08238 — Manajemen Nyeri`. Dokumen menamai `I.01011` sebagai “Latihan Batuk Efektif”, tetapi master lokal menamainya **Manajemen Jalan Napas**. Jangan mengganti nama master mengikuti dokumen. Perbedaan label target “menurun/meningkat” dipisahkan dari nama luaran resmi.
3. **Contoh merek bukan pemetaan produk siap impor.** Satu baris generik menggabungkan beberapa kekuatan, bentuk dan merek; pasangan harus dipecah serta diverifikasi. Flag High Alert, LASA, OOT, narkotika/psikotropika dan PPRA adalah dimensi terpisah, bukan satu enum eksklusif. Simpan sumber, versi, reviewer dan status review; tidak menetapkan produk/merek tertentu sebagai valid hanya dari contoh Word.
4. **Fornas bukan flag BPJS otomatis lolos klaim.** Keanggotaan perlu versi, periode berlaku dan restriksi; BPJS/Umum mengubah filter/estimasi, bukan memberikan persetujuan klaim. Daftar obat contoh belum membuktikan Fornas saat ini atau ketersediaan rumah sakit.
5. **Racikan dan BMHP bukan generik bermerek biasa.** Racikan memiliki komponen dan instruksi peracikan; BMHP memiliki spesifikasi dan satuan, tidak diberi signa obat wajib. Tetap tampilkan empat tingkat, tetapi gunakan label cabang yang sesuai.
6. **Kuantitas tidak selalu frekuensi × dosis × hari.** PRN, cairan, vial multidosis, tapering, racikan dan BMHP memerlukan aturan atau manual quantity dengan alasan. Jangan menyamakan mg dengan tablet atau mL dengan botol tanpa konversi master.
7. **Penunjang mempunyai panel dan varian.** CBC tidak otomatis menjadi lima tagihan; “CT Kepala polos/kontras”, laterality dan region perlu item/varian eksplisit. Baris daftar bukan hitungan final item master. Bank darah muncul di level yang tidak konsisten pada dokumen: normalisasi menjadi instalasi BDRS dengan kelompok kompatibilitas/komponen darah. “Rujukan Luar/Lainnya” harus punya cabang eksplisit, bukan dibuang karena tabel tidak merincinya.
8. **Order bukan tindakan selesai.** Memilih katalog atau menyimpan rencana tidak mengirim order atau membuat charge. EKG yang sama tidak boleh otomatis ditagih dari order penunjang sekaligus tindakan ICD9.
9. **Persetujuan PPRA merupakan workflow.** Sebutan antibiotik/lini ketiga pada contoh tidak menjadi aturan universal. Pakai kebijakan RS yang disahkan; simpan permintaan, dasar kultur/dokumen, keputusan reviewer, masa berlaku, serta penolakan. Uji bahwa dokter tidak bisa menyetujui permintaannya sendiri. Ketentuan apakah kultur saja cukup harus eksplisit di policy, bukan fallback UI.
10. **Indikasi manual tetap tersedia.** Dokumen menyebut indikasi/ICD10 wajib. Rekomendasi: indikasi teks wajib ketika order dikirim, kode ICD10 wajib hanya ketika pengguna memilih diagnosis master; diagnosis sementara manual tetap dapat memesan CITO. Jangan menjadikan pelengkapan seluruh asesmen sebagai prasyarat order darurat.

## 5. Temuan implementasi yang wajib masuk scope

Temuan berikut berasal dari pembacaan source, bukan exploit atau perjalanan browser yang dijalankan.

| Temuan | Severity | Akar masalah | Rencana perbaikan dan verifikasi |
|---|---|---|---|
| Penyelesaian resep berulang dapat menambah billing kembali | High | `pasien/views.py:820–837` membuat charge tiap POST selesai tanpa guard transisi/link item | Service transaksi, link unik detail resep→billing, replay key; uji retry dan konkurensi |
| Mutator resep hanya mensyaratkan login di definisi yang diperiksa | High | `views.py:698–718,802–807`; tidak di daftar workflow guard `urls.py:126–134` | Auth dokter/farmasi, scope per episode/depo dan state; uji nurse/admin/non-scope/direct POST |
| Resep langsung DIKIRIM dan nomor dari count+1 | High | `views.py:706–718`; draft dan kirim tidak terpisah, bentrok concurrent creation | Draft eksplisit, sequence/allocator teruji dan unique constraint, submit idempotent |
| Harga berasal dari float/client, invalid berubah 0 | High | `views.py:736–752` | Decimal dan resolver server; harga belum ditetapkan bukan gratis; reasoned override |
| AI belum memenuhi seluruh konteks dokumen | Medium | `ai_igd.py:25–39` tidak menyertakan structured physical/results dan melarang keluaran terapi | Perluas kontrak secara eksplisit untuk target diagnosis/3S/tindakan; validasi target dan kandidat |
| Satu mode memvalidasi medis dan 3S sekaligus | Medium | `igd_planning.py:13–55` | Mode/provenance terpisah; perubahan profesi sendiri tidak mengubah bagian profesi lain |
| Schema lokal tertinggal | Blocker lokal | Migration ledger sampai 0020, model workflow membutuhkan 0022+ | Verifikasi backup/target, migration plan lalu migrate pada fase implementasi; jangan fake ledger |

Jalur hasil laboratorium legacy `views.py:1959–1968` juga menulis langsung tanpa form transisi pada source tersebut. Plan penunjang mencakup penyatuan validasinya pada service yang sama. Jangan memperluas ini menjadi audit keamanan seluruh aplikasi.

## 6. Arsitektur yang direkomendasikan dan tradeoff

**Pilihan A — perluasan domain sekarang (direkomendasikan):** Django/Bootstrap/vanilla JS, master di `klinis`, transaksi episode di `pasien`, service kecil per fitur. Reuse authorization, optimistic version, idempotency, tariff resolver, signed revisions. Kelebihan: data historis dan jalur klinis tetap satu sumber. Tradeoff: migrasi additive dan adapter legacy perlu perhatian.

**Pilihan B — seluruh struktur disimpan JSON di kunjungan:** awal lebih cepat, tetapi foreign key katalog, constraint diagnosis utama, query worklist dan konsistensi billing lebih sulit. JSON hanya digunakan untuk snapshot/provenance atau metadata ber-schema, bukan menggantikan baris obat/order.

**Pilihan C — app/microservice farmasi dan penunjang baru:** isolasi lebih besar, tetapi menambah auth, sinkronisasi, deployment dan operasional sebelum kebutuhan itu terbukti. Tidak dipilih.

### Batas ownership

- `KunjunganPasien` tetap sumber episode. Proposed `DiagnosisKunjungan` menyimpan baris diagnosis; field lama merupakan proyeksi kompatibilitas yang ditulis server.
- `TindakanAsesmen` tetap sumber plan dan pelaksanaan. Tidak membuat ledger tindakan baru.
- `ResepElektronik`/`ResepDetail` tetap sumber resep; tambah master, komposisi dan penilaian risiko. Bukan membangun stok/pembelian/gudang pada scope ini.
- `OrderPenunjang` tetap worklist/result unit; satu order per item terpilih, dengan batch id, FK master dan snapshot nama/path. Panel tetap satu item order dengan komponen hasil; batch multiselect bersifat atomik.
- `BillingItem` tetap ledger tunggal. Charge obat dibuat pada penyerahan sesuai kebijakan yang disetujui; charge penunjang tidak otomatis ditambahkan oleh dropdown. Charge tindakan tetap pada execution.
- Semua writer baru dan legacy yang menyentuh domain yang sama harus melalui service yang sama; snapshot final tidak mengambil label/harga/signa dari master yang kemudian berubah.

## 7. Acceptance criteria lintas bagian

- Diagnosis utama/sekunder dan mode per item/komponen bertahan setelah reload; dua diagnosis utama ditolak secara atomik.
- Manual/master tetap bekerja ketika AI mati, timeout atau mengembalikan kode palsu. Accept AI terikat target, episode, actor, versi dan kode kandidat; saran tidak membuat keputusan atau order otomatis.
- Planned, ordered, performed, dispensed dan billed adalah state berbeda. Retry tidak menggandakan order, CPPT, resep atau billing.
- Parent dropdown berubah: child usang dibersihkan, tetapi basket berisi item lengkap yang sudah ditambahkan tidak dihapus diam-diam. POST dengan parent/child silang ditolak server.
- Resep biasa, racikan dan BMHP punya validasi sesuai jenis; semua flag multi-dimensi dan keputusan risiko tercatat. Free text allergy yang belum dipetakan ditampilkan sebagai belum terklasifikasi, bukan hasil cek negatif.
- Pemeriksaan kategori Laboratorium dan Penunjang Diagnostik lengkap tercakup sebagai katalog reviewable, termasuk rujukan luar, PA, BDRS, endoskopi/nuklir. Item tidak tersedia tidak ditawarkan sebagai layanan lokal aktif.
- Unit/profession authorization, CSRF, version conflict, sign invalidation, immutable final/addendum dan legacy data tetap terlindungi.
- Bukti penerimaan mencakup HTTP tests, browser 375/768/1366 px, negative authorization, PostgreSQL concurrency, migrasi dan readback release; bukan helper tests saja.

## 8. Keputusan review sebelum eksekusi

Default rancangan: katalog contoh masuk staging/nonaktif sampai review, AI tetap default-off, dokter menetapkan diagnosis dan mengirim order/resep, perawat menulis 3S/pelaksanaan sesuai kewenangan; farmasi menelaah/dispense melalui scope depo, bukan akses seluruh data pasien. Tidak membuat role PPRA dari role ADMIN_RS secara implisit. BPJS dan umum memakai formulary/tariff reference yang jelas; unknown price tidak menjadi 0.

Yang perlu disahkan pemilik proses: versi sumber master obat/Fornas/KFA, penanggung jawab review katalog/flag, daftar restriksi dan reviewer PPRA, aturan override alergi/duplikasi, izin pendelegasian order, cakupan worklist lintas unit/depo, dan saat pengakuan biaya obat/penunjang. Ketidaktersediaan jawaban ini tidak menghalangi pengembangan draft/catalogue tests, tetapi menghalangi aktivasi katalog klinis/aturan produksi yang bersangkutan.

## 9. Dokumen eksekusi

Plan disimpan dalam English sesuai konvensi project:

1. `../plans/2026-11-13-igd-clinical-expansion-roadmap.md` — sequencing, shared ownership dan quality gates.
2. `../plans/2026-11-13-igd-diagnosis-actions-3s.md` — diagnosis/tindakan/3S/AI.
3. `../plans/2026-11-13-igd-pharmacy-medication-safety.md` — katalog obat, resep, medication safety dan farmasi.
4. `../plans/2026-11-13-igd-ancillary-cascading-orders.md` — katalog penunjang, multiselect dan integrasi order/hasil.

Tidak termasuk: implementasi pemeriksaan fisik langkah 6, penggantian master nasional lengkap tanpa sumber, inventory/procurement, MAR/pemberian obat bedside, integrasi LIS/PACS/SATUSEHAT/BPJS live, perubahan modul RAJAL/RANAP selain compatibility domain yang disentuh, commit/push/deploy otomatis. **Do not implement, do not fix while here** untuk domain lain tersebut.
