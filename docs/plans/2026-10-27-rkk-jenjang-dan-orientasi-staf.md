# Plan tambahan: Master RKK jenjang karir & Modul Orientasi Staf (KPS 4 & KPS 8)

Sumber (2026-10-27):

1. `~/Downloads/master RKK Kewenangan klinis.docx` — 26 seksi: RKK dokter (3 jenjang) + 23 profesi nakes lain, keperawatan PK I–V, kebidanan BK I–V. Per jenjang: Fokus Kompetensi, Daftar Kewenangan Klinis, Status di Sistem (M/S/MT, Mitra Bestari, hak preseptor).
2. `~/Downloads/Bab Modul Orientasi Staf.docx` — spesifikasi modul orientasi STARKES KPS 4 & KPS 8: alur auto-assign → orientasi umum/khusus → post-test (lulus ≥ 80) → sertifikat otomatis → arsip e-File Folder D; matriks durasi per kelompok staf; TOR 1 (umum) & TOR 2 (khusus) yang harus bisa dicetak dari sistem; dashboard monitoring + reminder.

## 1. Apa yang sudah ada (jangan bangun ulang)

| Kapabilitas | Status | Lokasi |
|---|---|---|
| Master profesi + jenjang + katalog tindakan RKK | Ada, 19 profesi / 273 baris tindakan dari dokumen lama | `sdm/models/katalog_rkk.py`, seed `sdm/management/commands/_data_katalog_rkk.py` |
| Filter katalog logbook per profesi | Ada (fallback profesi saat tanpa SPK, baru diperbaiki) | `sdm/forms/logbook.py` |
| Pengajuan kredensial + RincianKewenangan + SPK | Ada | `sdm/models/kredensial.py:125,216` |
| Model orientasi (program, aktivitas, penugasan, penyelesaian, progress %) | Ada | `sdm/models/orientasi.py` |
| `start_orientation` + penyelesaian aktivitas + audit | Ada, manual | `sdm/services/rekrutmen.py:344` |
| Hook orientasi dari rekrutmen | Ada satu titik panggil | `sdm/services/rekrutmen.py:357` |
| Model diklat + evaluasi lulus/tidak + sertifikat bernomor | Ada (untuk diklat, bukan orientasi) | `sdm/models/diklat.py`, `sdm/services/kinerja.py:254` |
| PDF server-side (ReportLab) | Ada, pola siap dipakai ulang | `sdm/services/dokumen_kredensial.py` (render_pdf), `pasien/pdf_utils.py` |
| Arsip dokumen privat + versi + hash | Ada | `DokumenPegawai`/`VersiDokumen`, `sdm/storage.py` |
| Verifikasi logbook oleh preseptor | Ada, baru selesai (Fase 2 plan sebelumnya) | `VerifikasiLogbook`, `sdm/services/logbook.py` |
| Peristiwa audit immutable + pengingat SDM + command `hc_reminders` | Ada | `sdm/models/audit.py`, `sdm/models/pengingat.py` |
| Katalog tindakan otomatis tersaring di portal self-service | Sebagian — per **profesi**, belum per **jenjang** | `sdm/forms/logbook.py`, `sdm/services/dokumen_kredensial.py` |

## 2. Temuan dari dokumen baru

### 2.1 RKK: jenjang karir adalah kunci saring, bukan profesi saja

Dokumen menegaskan: *"Saat user nakes memilih kategori profesinya di Sub-Menu 2, sistem akan otomatis menyaring daftar Katalog RKK dan Skema Supervisi/Mandiri sesuai jenjang karir."*

Masalahnya: `Pegawai` **tidak punya kolom jenjang** (hanya `profesi_master`). Akibatnya:

- Dropdown katalog saat ini menampilkan seluruh tindakan lintas jenjang satu profesi (PK I ikut melihat kewenangan PK IV).
- RincianKewenangan pada pengajuan kredensial tidak bisa divalidasi terhadap jenjang pengaju.

### 2.2 RKK dokter masih naratif, tanpa katalog butir

Seed sekarang menaruh `DOKTER_UMUM`/`DOKTER_SP` di `PROFESI_TANPA_JENJANG` (katalog kosong). Dokumen baru memberi naratif jenjang (Umum → Spesialis → Subspesialis/Konsultan, rujukan SKDI 4A, Mitra Bestari) tapi **tidak memberi daftar tindakan butir-per-butir**. Batasan lama tetap: jangan mengarang daftar tindakan. Yang bisa dilakukan: simpan jenjang + fokus kompetensi sebagai master data, katalog dokter tetap menunggu input komite.

### 2.3 "Status di Sistem" membawa data preseptor

PK III, BK III, Madya (semua profesi teknis) eksplisit memegang **kewenangan pembimbingan/supervisi**; Utama/Konsultan masuk Mitra Bestari. Ini menjawab **Fase 0.2 plan sebelumnya** (siapa preseptor sah): resolusi preseptor bisa dibaurkan dari jenjang, tanpa tabel baru per unit.

### 2.4 Orientasi: alur wajib otomatis, TOR harus tercetak dari sistem

Yang diminta dokumen dan belum ada sama sekali:

| Permintaan | Kondisi sekarang |
|---|---|
| Jenis program UMUM vs KHUSUS + matriks durasi per kelompok staf (medis/ners/nakes lain/non-klinis) | `ProgramOrientasi` hanya punya `unit_kerja` (null = umum) dan `berlaku_hari` global |
| Auto-assign matriks saat pegawai baru/mutasi | `start_orientation` manual; hook rekrutmen cuma satu titik, intake tidak memicu |
| Post-test terpadu, passing grade 80, remedial bila gagal | Tidak ada model asesmen orientasi; `EvaluasiDiklat` milik diklat |
| Sertifikat orientasi + lembar verifikasi kompetensi auto-generate → e-File Folder D | Tidak ada; `SertifikatDiklat` tanpa PDF, tidak menaut ke arsip pegawai |
| TOR 1 & TOR 2 otomatis muncul pada perencanaan, bisa diedit & diekspor PDF | Tidak ada |
| Dashboard monitoring orientasi (filter unit/status, export rekap PDF) | `orientasi_list` sederhana, belum ada filter/export |
| Reminder ke preceptor | `PengingatSDM` + `hc_reminders` ada, belum menyentuh orientasi |
| Logbook harian masa orientasi (supervisi preseptor) | Logbook + VerifikasiLogbook sudah ada dari Fase 1–2; tinggal menautkan ke penugasan orientasi |

## 3. Batasan yang dijaga

1. Jangan mengarang butir katalog RKK dokter; jenjang & fokus kompetensi diisi, daftar tindakan menunggu SK komite.
2. Passing grade 80, durasi matriks, dan kelompok staf diambil literal dari dokumen; kalau berubah, ubah di satu tempat (konstanta/konfigurasi), bukan tersebar.
3. Sertifikat hanya terbit setelah penilaian lulus — pola yang sama dengan `issue_certificate` diklat.
4. TOR yang dicetak berisi data program yang benar (aktivitas, PJ, durasi); bagian biaya/anggaran hanya templated kosong bila data tidak ada di sistem.
5. Reminder email boleh via `send_mail` yang sudah ada; WhatsApp butuh gateway eksternal — **tidak dikerjakan** di plan ini.
6. Arsip "Folder D" dipetakan ke `DokumenPegawai`+`VersiDokumen` yang sudah ada (private storage), bukan kebutuhan storage baru.
7. Menu nakes tetap hanya melihat data milik sendiri (aturan Fase 5 plan sebelumnya).

## 4. Rencana kerja

### Fase R1 — Jenjang karir pada Pegawai (fondasi)

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| R1.1 | Tambah `fokus_kompetensi` (text) & `preceptor_min_urutan` (int, default 3) di `MasterJenjangProfesi`; migrasi | `sdm/models/katalog_rkk.py` | migrasi jalan |
| R1.2 | Tambah `jenjang_master` FK nullable di `Pegawai`; admin HC bisa set lewat form pegawai | `sdm/models/pegawai.py`, form/admin | test: set & baca balik |
| R1.3 | Seed jenjang dokter (Umum/Spesialis/Subspesialis-Konsultan) + fokus kompetensi naratif dari dokumen; katalog butir = kosong (menunggu komite) | `_data_katalog_rkk.py` | seed idempoten, report berubah |
| R1.4 | Filter katalog logbook & portal kredensial per `jenjang_master` bila terisi, fallback profesi bila kosong | `sdm/forms/logbook.py`, layanan kredensial | test: PK I tidak melihat tindakan PK IV |
| R1.5 | RincianKewenangan divalidasi: butir yang diajukan harus milik jenjang pegawai | `sdm/services/kredensial.py` | test: butir lintas jenjang ditolak |

### Fase R2 — Resolusi preseptor dari jenjang (menuntup Fase 0.2 lama)

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| R2.1 | Service `eligible_preceptors(unit)`: pegawai aktif di unit dengan `jenjang_master.urutan >= preceptor_min_urutan`, ATAU pemegang grant `can_review_hc_credentials` | `sdm/services/logbook.py` | test: PK II ditolak, PK III lolos |
| R2.2 | Pakai resolver ini di `verify_entry` (mengganti cek grant-only saat ini bila penyelesai cocok) | `sdm/services/logbook.py` | test: preseptor jenjang cukup tanpa grant HC bisa memverifikasi |
| R2.3 | Antrean verifikasi menampilkan kandidat preseptor unit | template verifikasi | smoke: nama muncul |

### Fase O1 — Jenis orientasi & matriks baku

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| O1.1 | `jenis` (UMUM/KHUSUS) + `kelompok_staf` (MEDIS/KEPERAWATAN/NAKES_LAIN/NON_KLINIS) + `durasi_hari` di `ProgramOrientasi`; konstanta matriks durasi dokumen (3 hari umum; khusus 56/90/28/14 hari) di satu modul konfigurasi | `sdm/models/orientasi.py`, `sdm/services/orientasi.py` (isi real) | migrasi + test konstanta |
| O1.2 | Seed program baku: Orientasi Umum (aktivitas: visi-misi/bylaws, PMKP & SKP 1–6 + pelaporan IKP, PPI, K3RS & code darurat, BHD) dan Orientasi Khusus per kelompok staf (izin VAHA/ORMA sistem: handover SBAR, alat medis, logbook; medis: RKK/SPK, CPPT, clinical pathway; nakes lain: SOP profesi; non-klinis: layanan & RME) | management command seed baru | seed idempoten; 2 program + aktivitas muncul |

### Fase O2 — Auto-assign orientasi

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| O2.1 | `auto_assign_orientation(employee, *, actor, unit_kerja)`: pilih program UMUM + program KHUSUS irisan (unit tujuan & kelompok staf); buat 1 penugasan per program; idempoten (jangan dobel bila sudah BERJALAN untuk jenis+unit yang sama) | `sdm/services/orientasi.py` | test: pegawai baru dapat 2 penugasan; panggil ulang tidak dobel |
| O2.2 | Panggil dari finalisasi intake pegawai baru & dari perubahan penempatan (mutasi) | `sdm/services/intake.py`, `sdm/services/penempatan.py` | test: finalize intake memicu penugasan |
| O2.3 | Tenggat dihitung dari `durasi_hari` program, bukan `berlaku_hari` global | service | test |

### Fase O3 — Asesmen & remedial

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| O3.1 | Model `AsesmenOrientasi` (penugasan, nilai 0–100, lulus? ≥ 80, percobaan ke-n, penguji, waktu, catatan) append-only per percobaan | `sdm/models/orientasi.py`, migrasi | test: nilai 79.9 gagal, 80 lulus |
| O3.2 | View HC input nilai (capability `can_manage_hc_orientation`); gagal → status penugasan tetap BERJALAN + flag remedial + perpanjang tenggat satu siklus | views + service | test: remedial menambah tenggat, percobaan 2 tercatat |
| O3.3 | Lulus semua program (umum + khusus, aktivitas wajib selesai, asesmen lulus) → status penugasan SELESAI + PeristiwaSDM | service | test: status berubah otomatis saat prasyarat penuh |

### Fase O4 — Sertifikat, TOR, arsip e-File

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| O4.1 | Generator PDF sertifikat orientasi (ReportLab, kop `SystemConfig.kop_surat_text`, nomor `ORI/{tahun}/{urut}`); hanya untuk penugasan lulus | `sdm/services/orientasi.py` | test: PDF berisi nama & nomor; lulus-syarat ditegakkan |
| O4.2 | Simpan hasil sebagai `DokumenPegawai` (jenis sertifikat orientasi) + `VersiDokumen` — arsip e-File otomatis | service | test: dokumen muncul di e-file pegawai |
| O4.3 | TOR 1 & TOR 2 PDF dari data program (aktivitas, PJ, durasi, struktur laporan); bagian biaya dicetak sebagai templat kosong bila tidak ada anggaran | service + template | test: PDF memuat nama program & aktivitas |
| O4.4 | Tombol di UI orientasi: unduh sertifikat (per penugasan) & unduh TOR (per program) | views + templates | smoke: unduh PDF 200 |

### Fase O5 — Dashboard & reminder

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| O5.1 | Dashboard orientasi: kolom sesuai mockup dokumen (NIP, nama, profesi/unit, mulai, umum, khusus, preseptor, status, aksi), filter unit & status (IN-PROGRESS/COMPLETED/WARNING remedi) | views + template baru | render 200 dengan 3 status |
| O5.2 | Export rekap PDF dashboard | service (reuse generator) | test: PDF berisi baris yang sama |
| O5.3 | `hc_reminders` menambah pengingat: penugasan orientasi mendekati/lewat tenggat → pegawai + preseptor (email via `send_mail` yang sudah terpakai; PengingatSDM tercatat) | `sdm/management/commands/hc_reminders.py` | test: pengingat dibuat sekali |
| O5.4 | Tautan logbook orientasi: penugasan KHUSUS menampilkan ringkasan entri logbook + verifikasi preseptor selama masa orientasi | template detail orientasi | smoke: angka cocok dengan logbook |

## 5. Urutan yang disarankan

1. **R1** dulu — `jenjang_master` adalah fondasi filter RKK & validasi pengajuan; perubahan kecil, dampaknya ke seluruh alur kredensial.
2. **R2** — menuntut utang Fase 0.2 plan sebelumnya dengan data yang kini tersedia.
3. **O1, O2** — struktur + auto-assign; langsung terlihat saat ada pegawai baru.
4. **O3, O4** — asesmen, sertifikat, TOR (butuh O1/O2 stabil).
5. **O5** — dashboard & reminder terakhir, melaporkan semuanya.

## 6. Yang tidak dikerjakan

- LMS penuh / bank soal online — asesmen cukup input nilai oleh penguji.
- Gateway WhatsApp — email saja dulu.
- Modul anggaran/biaya TOR — angka biaya tetap luar sistem, PDF hanya templat.
- Daftar tindakan katalog dokter — menunggu SK komite (Fase 0.1 plan lama masih terbuka).
- Mengganti alur kredensial yang sudah berjalan; jenjang hanya menambah filter.

## 7. Bukti sebelum dinyatakan selesai

| Fase | Bukti |
|---|---|
| R1 | Pegawai PK I: dropdown logbook tidak memuat tindakan PK IV; pegawai tanpa jenjang berperilaku seperti sekarang |
| R2 | PK II mencoba verifikasi → ditolak; PK III → lolos; tercatat di `PeristiwaSDM` |
| O1 | Seed menghasilkan program umum + 4 khusus dengan aktivitas baku, idempoten |
| O2 | Finalisasi intake 1 pegawai baru → 2 penugasan orientasi dengan tenggat dari matriks; panggil ulang tidak dobel |
| O3 | Nilai 80 → penugasan berjalan ke SELESAI bila aktivitas wajib penuh; nilai 70 → remedial, tenggat bertambah, percobaan ke-2 tercatat |
| O4 | Sertifikat & TOR terunduh PDF; sertifikat masuk e-file pegawai; syarat lulus memblokir sertifikat dini |
| O5 | Dashboard menampilkan 3 status dengan filter; rekap PDF cocok dengan layar; reminder terbuat sekali per penugasan |
