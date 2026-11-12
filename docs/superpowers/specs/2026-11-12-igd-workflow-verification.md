# Verifikasi Implementasi Alur IGD 11 Langkah

**Status: implementasi dan verifikasi lokal selesai. Rilis production belum diminta/dijalankan.**

Plan: `../plans/2026-11-12-perbaikan-alur-asesmen-awal-igd.md`.
Evidence permanen: `../evidence/igd-workflow/`.

## Identitas artefak

- Branch: `master`, perubahan belum di-commit.
- Base commit: `36aa2900c1d0d3d174acfdabede1c09a6b7174b1`.
- Fingerprint SHA-256 sumber: `9677bd5950d43f6083132110038642f98f977b7ae87620458d216c1f3f1863da`.
- Manifest `verification.json` memuat hash 45 file sumber yang berubah; fingerprint ini bukan SHA commit atau bukti deployment.
- Database pengujian terisolasi/sintetis. Tidak ada migrasi atau penulisan data pasien production.

## Traceability kebutuhan

| Kebutuhan | Implementasi | Bukti |
|---|---|---|
| R01 — identitas dan penjamin | Header identitas, penjamin dari admisi; penjamin tidak dapat diganti melalui patch klinis; acuan tarif server-side | Tes mass assignment, preservasi billing, browser dua kunjungan |
| R02 — triase/ABCDE | ATS, ESI, WARNA eksplisit; kategori, warna dan kematian tidak disamakan; cara datang/ABCDE tersimpan | Tes kategori 5 dan sistem historis, browser simpan triase |
| R03 — anamnesis/alergi | Riwayat dan skrining alergi per episode, tanpa menyimpulkan blank sebagai tidak ada alergi | Tes round-trip dan browser simpan/buka kembali |
| R04 — TTV awal | Batas nilai, GCS, nyeri nol, timestamp/recorder; koreksi menambah observasi tertaut | Tes validasi/append/proyeksi; browser GCS, nol, koreksi |
| R05 — biopsikososial/skrining | Field psikososial/spiritual/hambatan edukasi, jawaban Morse/MST; jawaban parsial tidak menghasilkan skor lengkap | Tes klinis/hardening, browser kalkulasi dan reload |
| R06 — fisik/lokalis/anatomi | Input organ, lokalis, penanda FRONT/BACK dengan jenis/label/koordinat tervalidasi | Browser klik/tambah/edit/hapus/reload; marker tercetak pada resume |
| R07 — penunjang | Order eksplisit LAB/RADIOLOGI/EKG/LAINNYA, hasil/critical value berprovenance, lampiran terproteksi | Tes idempotensi/scope/upload, browser order pending → hasil dan unduh |
| R08 — diagnosis/rencana | Manual, katalog Master/3S dan adapter AI terpisah; ticket AI terikat episode/pengguna/versi | Tes penerimaan AI bermock yang mempertahankan bagian manual; browser Manual/Master dan AI nonaktif |
| R09 — pelaksanaan | Rencana tidak menagih; pelaksanaan menautkan petugas, CPPT dan billing sekali; tarif tidak diketahui tidak dijadikan nol | Tes integrasi dan audit tarif; browser dokter/perawat; race PostgreSQL |
| R10 — evaluasi | Kondisi akhir, respon terapi dan observasi EVALUATION, terpisah dari INITIAL | Browser nadi awal/koreksi tetap terpisah dari nadi evaluasi |
| R11 — finalisasi/disposisi | Persetujuan medis/keperawatan, konfirmasi outcome, snapshot final, addendum dan resume | Browser delapan outcome, revisi/cetak, penolakan writer lama; tes transfer dan rollback |

Penjamin yang sudah dipakai episode tidak dikoreksi atau direpricing diam-diam oleh workflow ini. Koreksi administratif/penjamin memerlukan proses admisi dan tinjauan keuangan tersendiri; tidak ada perubahan biaya historis otomatis.

## Hasil pengujian

| Gate | Hasil aktual | Lingkup |
|---|---|---|
| Regresi lintas aplikasi | 1.383 tes, 874,286 detik, OK, exit 0 | `klinis pasien akreditasi accounts`; sebelum dua tambahan lokal audit tarif/pintasan dashboard |
| Regresi klinis akhir | 400 tes, 232,668 detik, OK, exit 0 | `klinis pasien`; mencakup kedua tambahan lokal tersebut |
| Workflow akhir | 96 tes, 9,753 detik, OK, exit 0 | Delapan modul workflow; juga menguji fixture media tanpa path mesin yang di-hardcode |
| Browser | 48 pengukuran layout lulus; delapan outcome; tanpa page error | Chromium, 375/768/1366px, fixture/session/CSRF nyata pada server lokal |
| PostgreSQL | Lima race lulus; nol migrasi tertunda | PostgreSQL17 disposable, dua koneksi independen |
| Static assets | Source = collected = hashed = gzip | Kedua file JavaScript, target manifest dicatat dalam `verification.json` |
| Pemeriksaan statis | Django check, migration drift, JavaScript syntax dan diff check lulus | Tidak ada perubahan model yang belum memiliki migrasi; satu system-check historis tetap disilence oleh konfigurasi proyek |

Run di atas saling overlap dan **tidak dijumlahkan** menjadi total tes unik. File log lengkap berada di scratch; ringkasan terstruktur disimpan permanen dalam `verification.json`. Hash sumber mengidentifikasi delivery terakhir, bukan mengklaim seluruh run historis terjadi pada hash yang sama. Perubahan JavaScript terakhir diverifikasi melalui smoke browser dan perbandingan byte aset.

### Browser: perilaku yang dijalankan

- Navigasi sebelas langkah pada ketiga lebar; tidak ada nested form, overflow horizontal, atau action bar menutupi field.
- Keyboard Tab ke tombol simpan; save/reload, isolasi dua kunjungan, kegagalan jaringan/retry dan penolakan versi stale.
- GCS dan nyeri nol; koreksi observasi append-only; hasil Morse/MST tetap ada setelah reload.
- Penanda anatomi ditambah melalui diagram, diedit, dihapus dan dibuka kembali; text alternative tersedia.
- Order pending, hasil tercatat, upload dan download lampiran dengan session/CSRF nyata.
- Manual dan Master dengan pemetaan SDKI → SLKI → SIKI; AI nonaktif tidak menghalangi pekerjaan.
- Rencana medis dan keperawatan; satu tagihan untuk tarif yang diketahui dan tidak ada tarif keperawatan fiktif; CPPT oleh profesi terautentikasi.
- Persetujuan dokter dan perawat; isian resume belum dikirim tidak hilang ketika menandatangani; finalisasi tanpa persetujuan ditolak.
- Pulang, final dokumen tanpa discharge (`NONE`), RANAP, konsultasi poli, transfer layanan poli, rujukan eksternal, meninggal dan PAPS.
- Finalisasi diikuti addendum menjadi revisi 2; PDF menampilkan marker dan addendum; endpoint lama edit/hapus/TTV menolak penimpaan.
- Viewer dan admin tanpa profesi klinis dapat membaca tetapi direct-sign ditolak; pengguna unit lain ditolak; anonymous diarahkan ke login. Dokter/perawat positif memakai akun non-superuser.
- Smoke tambahan: input `datetime-local` WIB tetap terisi dan tidak berubah setelah dua kali simpan; pintasan dashboard menuju langkah 7/9/11, bukan modal writer lama.

Seluruh outcome diuji fungsional pada desktop. Pengukuran responsif terpisah meliputi seluruh sebelas langkah dan halaman operasi berisi data; ini bukan klaim pengujian setiap kombinasi perangkat fisik/outcome. Beberapa outcome memakai API draft untuk menyiapkan kasus sintetis, lalu persetujuan/finalisasi dijalankan lewat kontrol browser sebenarnya. Penangkapan respons operasi memakai pass-through Playwright ke server yang sama, bukan respons domain palsu. Probe dilanjutkan setelah memperbaiki dua masalah harness: body respons yang dibaca setelah navigasi, dan disclosure alasan pengecualian yang belum dibuka.

### PostgreSQL

`postgresql.json` merekam hasil dua koneksi untuk:

1. Draft pertama simultan: satu tersimpan, satu stale, satu workflow.
2. Request ID order sama: satu order, satu replay.
3. Request pelaksanaan sama: satu CPPT dan satu billing.
4. Request finalisasi sama: satu revisi final dan satu replay.
5. Dua pasien memperebutkan bed sama: satu transfer berhasil, transaksi lainnya ditolak tanpa revisi/penempatan kedua.

Rantai migrasi penuh akhirnya diterapkan tanpa melewati `RunPython`. Hambatan seed lama diperbaiki pada tiga penggunaan inserted ID: PostgreSQL memakai `RETURNING id`, SQLite tetap memakai `lastrowid`. Kegagalan awal dan probe schema-only pada batch fondasi bukan bukti final; hasil final menggantikannya. Probe PostgreSQL diulang setelah tambahan audit tarif.

## Temuan yang diperbaiki

| Finding | Severity | Root cause | Perbaikan dan bukti |
|---|---|---|---|
| Pembatalan rencana lintas profesi | High | Cancel belum memeriksa execution team | Pemeriksaan dokter/perawat sejajar dengan plan/execute; tes penolakan nurse terhadap rencana medis |
| Form JSON ditolak saat simpan | Medium | Hidden helper `initial-*` Django ikut masuk payload klinis | Serializer hanya mengirim field aktual, bukan helper initial; browser skrining/anatomi lulus |
| Nilai tanggal/jam hilang setelah save | Medium | ISO datetime berzona ditugaskan langsung ke `datetime-local` | Normalisasi ke representasi WIB yang diterima input; dua save mempertahankan nilai |
| Diagram melebar pada 768px | Medium | Min-content fieldset dan grid dua kolom terlalu lebar | Fieldset dapat menyusut, diagram satu kolom pada tablet; geometry pass |
| Riwayat tarif tidak menyimpan nilai lama | Medium | Audit operasi hanya berisi jenis aksi/versi | Audit perubahan menyimpan before/after, penjamin/quantity/acuan dan alasan; tes integrasi akhir |
| Pintasan dashboard memakai writer lama | Medium | CPPT/order/disposisi masih menuju modal lama ketika rollout aktif | Pintasan aktif menuju langkah terkait; regresi Django dan smoke browser |
| Bootstrap PostgreSQL gagal | Medium | Seeder menganggap `lastrowid` selalu inserted PK | `RETURNING id` untuk PostgreSQL pada ketiga lokasi; migrasi penuh dan race lulus |

## Batas rilis dan rollback

- Workflow dan AI tetap **default-off pada kode**. Tidak ada klaim nilai environment production saat ini diperiksa.
- AI positif diuji dengan transport/provider bermock dan validasi katalog/ticket nyata. Provider live, kuota, kredensial dan persetujuan data klinis eksternal belum diuji/diaktifkan.
- Persetujuan adalah atribusi akun/profesi aplikasi; tidak ada klaim integrasi sertifikat tanda tangan elektronik eksternal.
- Alur rujuk mengubah state lokal. Tidak ada klaim SISRUTE/LIS/SATUSEHAT menerima data.
- Tidak ada commit, push, deploy atau migrasi primary/production dari pekerjaan ini.
- Rilis yang disetujui terpisah harus meliputi backup, penerapan dan baca-balik migrasi additive, aset manifest, deployment/SHA/alias, serta smoke production.
- Rollback menyembunyikan UI melalui gate tetapi mempertahankan guard writer, observasi dan snapshot. Jangan merilis ulang versi lama yang dapat melewati guard atau menghapus tabel baru.

## Artefak

- `../evidence/igd-workflow/verification.json`
- `../evidence/igd-workflow/browser.json`
- `../evidence/igd-workflow/postgresql.json`
- `../evidence/igd-workflow/anatomy-375.png`, `anatomy-768.png`, `anatomy-1366.png`
- `../evidence/igd-workflow/resume-synthetic.pdf`
