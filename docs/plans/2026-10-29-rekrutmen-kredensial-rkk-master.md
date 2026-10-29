# Plan: Modul Rekrutmen, Auto-Fill Kredensial, dan Master RKK Kewenangan Klinis

## Status pelaksanaan

| Bagian | Status | Bukti |
|---|---|---|
| **B — Auto-fill form kredensial** | ✅ **Selesai** | Endpoint `kredensial_pegawai_profil` (JSON), validasi STR/SIP di `PengajuanKredensialForm.clean()`, JS `hc-kredensial-autofill.js` + `hc-kredensial-portal-autofill.js`, badge & panel di form HC dan portal. Smoke test: endpoint 200, form render hook lengkap, AWAL/REKREDENSIAL diblokir saat SIP kosong, PENAMBAHAN lolos, portal 200. |
| **A — Master RKK audit & penambalan** | ✅ **Selesai** | `DOKTER_GIGI` 3 jenjang ditambahkan ke `DOKTER_JENJANG`; command `audit_katalog_rkk` (laporan + `--strict`); seed idempoten (23 profesi / 118 jenjang / 499 tindakan); test `SeedKatalogTests` + `AuditKatalogRkkTests`. |
| **C — Modul Rekrutmen 7 sub-menu** | ⏳ **Belum dikerjakan** | Masih 3 model tipis (`Lowongan`, `Lamaran`, `RiwayatSeleksi`). Lihat Fase C0–C8 di bawah. |

**Gap RKK yang tersisa** (butuh keputusan komite, bukan kode):
- Katalog butir **Dokter Gigi** dan **Dokter Spesialis** menunggu SK komite — sengaja kosong, sesuai batasan §3.
- **Apoteker** hanya 2 jenjang; dokumen master tidak merinci lebih.

---

Sumber (2026-10-29):
1. `~/Downloads/modul REKRUTMEN.docx` — spesifikasi Modul Rekrutmen & Seleksi Pegawai ARIMA, 7 sub-menu end-to-end (Manajer Lowongan → Portal Pelamar → Screening → CBT → Wawancara → MCU & Offering → Orientasi/e-File), plus dasbor pemantauan HR dan 4 fitur unggulan (audit trail KPS, talent pool, notifikasi WA/Email, transparansi).
2. `~/Downloads/Masalah pengajuan kredensial baru.docx` — permintaan perbaikan form `/human-capital/kredensial/baru/`: auto-fill Unit Kerja & Jabatan saat pegawai dipilih, auto-fetch STR/SIP dari E-File, manual override, katalog RKK dinamis per profesi/jenjang.
3. `~/Downloads/master RKK Kewenangan klinis.docx` — master 26 seksi jenjang karir + kewenangan klinis (Dokter 3 jenjang, Perawat PK I–V, Bidan BK I–V, dan 20+ profesi nakes lain) dengan status M/S/MT.

## 1. Ringkasan eksekutif: tiga permintaan, tiga tingkat kesiapan

| # | Permintaan | Kondisi repo | Sifat pekerjaan |
|---|---|---|---|
| A | **Master RKK kewenangan klinis** | **Sudah ~95% ter-seed** — 23 profesi, 115 jenjang, 499 tindakan di DB | Bukan bangun baru: audit gap, tambal 1 profesi hilang, lengkapi katalog dokter |
| B | **Auto-fill form kredensial** | **Fondasi sudah ada**, tapi form HC belum pakai | Penyambungan kecil: 1 form + 1 endpoint + 1 skrip template |
| C | **Modul Rekrutmen 7 sub-menu** | **Minimal** — 3 model tipis, 5 view CRUD dasar | Pekerjaan terbesar: 6 dari 7 sub-menu belum ada |

Urutan yang disarankan: **B → A → C**. B kecil dan langsung terasa; A hampir selesai dan menjadi prasyarat C (katalog RKK dipakai saat konversi pegawai baru); C adalah proyek multi-fase.

---

## 2. Kondisi aktual repo (fakta, bukan asumsi)

### 2.1 Yang sudah ada dan jangan dibangun ulang

| Kapabilitas | Lokasi | Catatan |
|---|---|---|
| Master profesi (`MasterProfesiPegawai`) + `keluarga` | `sdm/models/referensi.py` | 23 baris ter-seed |
| Jenjang karir (`MasterJenjangProfesi`) + `fokus_kompetensi` + `preceptor_min_urutan` | `sdm/models/katalog_rkk.py:9-35` | 115 baris ter-seed |
| Katalog tindakan RKK (`KatalogTindakan`) + tingkat `M/S/MT/T` | `sdm/models/katalog_rkk.py:38-75` | 499 baris ter-seed |
| Seed idempoten katalog RKK | `sdm/management/commands/seed_katalog_rkk.py` + `_data_katalog_rkk.py` | dry-run default, `get_or_create` |
| `Pegawai.jenjang_master` (FK nullable) | `sdm/models/pegawai.py:52` | Fase R1 plan 2026-10-27 sudah jalan |
| Filter katalog per profesi **dan** jenjang | `sdm/forms/level2_5.py:101-117` | Fase R1.4 sudah jalan |
| Profil kredensial read-only (STR/SIP dari `legal_status`) | `sdm/services/profil_kredensial.py` | Sudah menarik STR/SIP + masa kerja + unit aktif |
| Kartu profil di form kredensial | `templates/sdm/kredensial/_profil_kartu.html` | Sudah dirender di `form.html` |
| Pengajuan kredensial + RincianKewenangan + PSV + SPK + keputusan | `sdm/models/kredensial.py`, `sdm/services/kredensial.py` | Alur lengkap |
| Checklist dokumen kredensial (12 baris) | `sdm/services/syarat_kredensial.py` | `evaluate_requirements` |
| E-File dokumen + versi + masa berlaku | `sdm/models/dokumen.py` (`DokumenPegawai`/`VersiDokumen`) | PENDING/VERIFIED/REJECTED/SUPERSEDED |
| Logbook klinis (waktu, pasien_ref, kategori M/S/K, shift) + verifikasi preseptor | `sdm/models/logbook.py` | Fase 1–2 plan logbook sudah jalan |
| Orientasi (program, aktivitas, penugasan, penyelesaian) | `sdm/models/orientasi.py`, `sdm/services/orientasi.py` | Fase O1–O2 sebagian jalan |
| PDF server-side (ReportLab) | `sdm/services/dokumen_kredensial.py`, `pasien/pdf_utils.py` | Pola siap pakai ulang |
| Peristiwa audit immutable + pengingat + `hc_reminders` | `sdm/models/audit.py`, `sdm/models/pengingat.py` | Sudah dipakai lintas modul |
| Rekrutmen dasar: `Lowongan`, `Lamaran`, `RiwayatSeleksi` | `sdm/models/rekrutmen.py` | Tipis — lihat §2.3 |
| Pola permission `require_hc_capability` + `visible_units`/`visible_employees` | `sdm/views.py`, `sdm/services/akses_hc.py` | Konvensi wajib diikuti |

### 2.2 Cakupan Master RKK vs dokumen (angka nyata dari DB)

| Profesi | Kode | Keluarga | Jenjang | Tindakan | Status |
|---|---|---|---|---|---|
| Perawat | KPR | KEPERAWATAN | 5 | 32 | ✅ PK I–V lengkap |
| Bidan | BID | KEPERAWATAN | 5 | 28 | ✅ BK I–V lengkap |
| Dokter Umum | DOKTER_UMUM | MEDIS | 3 | 10 | ✅ jenjang + fokus; katalog butir terbatas |
| Dokter Spesialis | DOKTER_SP | MEDIS | 32 | 111 | ✅ per spesialisasi |
| **Dokter Gigi** | DOKTER_GIGI | MEDIS | **0** | **0** | ❌ **GAP** — di `PROFESI_TANPA_JENJANG`, tanpa jenjang & katalog |
| Radiografer | RADG | NAKES_LAIN | 4 | 20 | ✅ |
| Fisikawan Medis | FMA | NAKES_LAIN | 4 | 15 | ✅ |
| ATLM | ATLM | NAKES_LAIN | 4 | 21 | ✅ |
| PMIK | PMIK | NAKES_LAIN | 4 | 21 | ✅ |
| TTK | TTK | NAKES_LAIN | 4 | 19 | ✅ |
| Apoteker | APOTEKER | NAKES_LAIN | 2 | 8 | ⚠️ hanya 2 jenjang, dokumen master tidak merinci |
| Sanitarian | SANI | NAKES_LAIN | 4 | 19 | ✅ |
| Ahli K3RS | K3RS | NAKES_LAIN | 4 | 17 | ✅ |
| Dietisien | DIET | NAKES_LAIN | 4 | 17 | ✅ |
| Nutrisionis | NUTR | NAKES_LAIN | 4 | 16 | ✅ |
| Fisioterapis | FISIO | NAKES_LAIN | 4 | 21 | ✅ |
| Okupasi Terapis | OKT | NAKES_LAIN | 4 | 18 | ✅ |
| Terapis Wicara | WICARA | NAKES_LAIN | 4 | 18 | ✅ |
| Ortotik Prostetik | ORPRO | NAKES_LAIN | 4 | 17 | ✅ |
| Penata Anestesi | ANES | NAKES_LAIN | 4 | 20 | ✅ |
| Psikologi Klinis | PSIK | NAKES_LAIN | 4 | 19 | ✅ |
| Elektromedis | ELMD | NAKES_LAIN | 4 | 20 | ✅ |
| Tenaga Teknis TB | TB | NAKES_LAIN | 4 | 12 | ✅ |

**Total: 23 profesi / 115 jenjang / 499 tindakan.** Gap nyata hanya **Dokter Gigi** (dan Apoteker yang tipis). Catatan penting: `_data_katalog_rkk.py` sudah memuat komentar eksplisit *"katalog butir menunggu SK komite (jangan mengarang daftar tindakan)"* untuk dokter — batasan itu tetap berlaku.

### 2.3 Rekrutmen: yang ada vs yang diminta dokumen

| Sub-menu dokumen | Kondisi sekarang | Jarak |
|---|---|---|
| 1. Manajer Lowongan | `Lowongan` (unit, profesi, judul, jumlah, status) + CRUD | Tidak ada: kuota dari formasi, kualifikasi/IPK, dokumen wajib, batas usia, jalur internal/eksternal, registration window |
| 2. Portal Pelamar | **Tidak ada** | Portal publik tanpa login, form pendaftaran, e-upload, validasi dokumen, dasbor kandidat |
| 3. Seleksi Administrasi | Status `SELEKSI_ADMIN` di `Lamaran` + transisi | Tidak ada: matriks penapisan, auto-filter IPK/STR, status dokumen per-item, auto-responder |
| 4. CBT / Ujian Kompetensi | **Tidak ada** | Bank soal per profesi, mesin ujian + timer, pengacakan, auto-scoring, ranking |
| 5. Wawancara | Status `WAWANCARA` | Tidak ada: penjadwalan, undangan, digital scorecard, skor gabungan berbobot |
| 6. MCU & Offering | **Tidak ada** | Input hasil MCU (Fit/Fit with Note/Unfit), generate offering letter, e-signature |
| 7. Orientasi & e-File | `hire_application` + `start_orientation` ada | Belum ada: konversi satu klik penuh, auto-generate NIP + akun, auto-enroll orientasi |
| Dasbor Pemantauan HR | **Tidak ada** | Tabel kode lowongan/posisi/unit/kuota/pelamar/lulus per tahap/status |
| Talent Pool | **Tidak ada** | Penyimpanan pelamar berkualifikasi untuk formasi berikutnya |
| Notifikasi WA/Email | Email via `send_mail` ada; WA tidak | Gateway WA (batasan: lihat §5) |

Status transisi `Lamaran.ALLOWED_TRANSITIONS` saat ini linear: `MASUK → SELEKSI_ADMIN → TES_KOMPETENSI → WAWANCARA → DITERIMA/DITOLAK`. Tidak ada tahap MCU dan tidak ada percabangan per tahap.

### 2.4 Form kredensial: yang ada vs yang diminta

| Permintaan dokumen | Kondisi sekarang | Jarak |
|---|---|---|
| Auto-populate Unit Kerja saat pegawai dipilih | Form HC (`PengajuanKredensialForm`, `sdm/forms/level2_5.py:60`) punya `employee` + `unit_kerja` sebagai dropdown independen — **tidak terhubung** | Perlu endpoint AJAX + JS |
| Auto-populate Jabatan / Jenis Nakes | `credential_profile()` sudah menghitung `jabatan` + `profesi` + unit aktif, tapi hanya ditampilkan sebagai **kartu read-only** | Profil sudah siap; tinggal dipakai untuk mengisi form |
| Auto-fetch STR/SIP dari E-File | `credential_profile()` sudah menarik STR/SIP via `legal_status()` | Sudah ada; perlu tampilkan peringatan kadaluarsa/hilang di depan submit |
| Manual override dengan badge hijau | Tidak ada | Perlu JS + styling |
| Katalog RKK dinamis per profesi/jenjang | `RincianKewenanganForm` (`level2_5.py:84-117`) **sudah** memfilter katalog per profesi + jenjang | Sudah jalan |
| Jenis pengajuan (Awal / Re-Kredensial / Penambahan RKK) | Field `jenis` ada di model | Perlu verifikasi pilihan lengkap |

Catatan: portal self-service (`PengajuanPortalForm`, `sdm/forms/kredensial_portal.py`) sudah lebih maju — unit diambil dari penempatan, auto-initial bila hanya satu unit. Pola ini bisa diangkat ke form HC.

---

## 3. Batasan yang dijaga

1. **Jangan mengarang butir katalog RKK dokter.** Komentar di `_data_katalog_rkk.py` sudah menetapkan ini; jenjang + fokus kompetensi diisi dari dokumen, daftar tindakan menunggu SK komite.
2. **Jangan mengarang NIP, nomor surat, atau hasil tes.** NIP dari pola yang dikonfigurasi admin; nomor surat dari counter per jenis per tahun; hasil CBT dari input nyata.
3. **Jangan mengarang target/nilai kelulusan.** Passing grade, bobot skor, dan matriks durasi diambil literal dari dokumen dan disimpan di satu modul konstanta, bukan tersebar.
4. **Portal pelamar publik harus aman.** Tanpa akses ke data pegawai internal; unggahan divalidasi tipe & ukuran; tidak ada enumerasi ID yang bisa dibaca berurutan.
5. **Data pasien minimal** (aturan yang sudah berlaku di logbook) tetap berlaku bila rekrutmen menyentuh data kesehatan MCU.
6. **Notifikasi WhatsApp tidak dikerjakan** tanpa gateway eksternal — email via `send_mail` yang sudah dipakai; WA ditandai sebagai butuh keputusan pemilik proses.
7. **Ikuti konvensi repo**: `require_hc_capability` + `visible_units`/`visible_employees` untuk scoping, function-based view, ReportLab untuk PDF, `PeristiwaSDM` untuk audit.
8. **Jangan membangun DRF/React.** Repo ini server-rendered Django + Bootstrap; portal pelamar mengikuti pola yang sama.

---

## 4. Rencana kerja

### Bagian B — Auto-fill form kredensial (kecil, kerjakan lebih dulu)

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| B.1 | Endpoint `kredensial_pegawai_profil` (GET, JSON): terima `employee_id`, kembalikan unit aktif, profesi, jabatan, jenjang, STR/SIP + status kadaluarsa — pakai `credential_profile()` yang sudah ada | `sdm/views.py`, `sdm/urls.py` | Test: JSON berisi STR/SIP benar untuk pegawai ber-STR |
| B.2 | Scoping endpoint dengan `visible_employees(user)` — jangan bocorkan pegawai di luar wewenang | `sdm/views.py` | Test: pegawai unit lain → 404 |
| B.3 | JS di form HC: saat `employee` berubah → panggil endpoint → set `unit_kerja` + tampilkan badge "Auto-filled dari Data Kepegawaian" + panel STR/SIP dengan peringatan bila kosong/kadaluarsa | `templates/sdm/kredensial/form.html`, `static/js/` | Smoke: pilih pegawai → unit terisi, badge muncul |
| B.4 | Manual override: dropdown tetap editable; badge berubah jadi "Diubah manual" saat user mengubah nilai | JS | Smoke: ubah unit → badge berubah |
| B.5 | Blokir submit bila STR/SIP wajib kosong/kadaluarsa untuk jenis pengajuan yang memerlukannya, dengan pesan yang jelas (bukan silent fail) | `sdm/forms/level2_5.py` | Test: submit tanpa STR → error terarah |
| B.6 | Terapkan pola yang sama pada `PengajuanPortalForm` (badge + peringatan) | `sdm/forms/kredensial_portal.py`, template portal | Smoke: portal menampilkan badge |

### Bagian A — Master RKK: audit & penambalan

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| A.1 | Tambah jenjang **Dokter Gigi** (Umum/Spesialis/Subspesialis) dengan fokus kompetensi naratif dari dokumen; katalog butir kosong sampai SK komite | `_data_katalog_rkk.py` | `seed_katalog_rkk` idempoten; jenjang DOKTER_GIGI muncul |
| A.2 | Audit silang: setiap profesi di dokumen master RKK punya baris `MasterProfesiPegawai`; laporkan yang tidak ada | management command baru `audit_katalog_rkk` | Command melaporkan 0 profesi hilang |
| A.3 | Verifikasi status `M/S/MT` di seed cocok dengan dokumen untuk profesi yang dokumennya eksplisit (Perawat, Bidan, Radiografer, ATLM, PMIK, dsb) | `_data_katalog_rkk.py` | Laporan selisih; perbaiki yang salah |
| A.4 | Lengkapi jenjang Apoteker bila dokumen/SK menyediakan; kalau tidak, tandai eksplisit sebagai menunggu SK | `_data_katalog_rkk.py` | Komentar batasan + laporan |
| A.5 | Pastikan `preceptor_min_urutan` per profesi sesuai jenjang yang memegang kewenangan pembimbingan (PK III, BK III, Madya) | `_data_katalog_rkk.py` | Test: preseptor terpilih sesuai jenjang |

### Bagian C — Modul Rekrutmen (multi-fase)

#### Fase C0 — Fondasi model & keputusan pemilik proses (tanpa kode)

| # | Pertanyaan | Kenapa menentukan |
|---|---|---|
| C0.1 | Apakah kuota lowongan wajib terikat ke Rencana Formasi (KPS 1)? | Menentukan apakah `Lowongan` butuh FK ke formasi |
| C0.2 | Jalur internal/eksternal: satu lowongan bisa dua jalur, atau dipisah? | Menentukan skema |
| C0.3 | Bobot skor gabungan (berkas/CBT/HRD/user-komite) — angkanya dari mana? | Tanpa ini, skor gabungan tidak bisa dihitung |
| C0.4 | Passing grade CBT dan bank soal per profesi: sudah ada SK-nya? | Menentukan apakah bank soal di-seed atau diinput manual |
| C0.5 | Format offering letter & penomoran surat | Menentukan generator |
| C0.6 | Gateway WhatsApp: pakai layanan apa, atau email saja dulu? | Menentukan Fase C6 |
| C0.7 | Kebijakan retensi data pelamar yang ditolak (UU PDP) | Menentukan skema talent pool & purge |

#### Fase C1 — Manajer Lowongan (perluas yang ada)

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| C1.1 | Tambah field `Lowongan`: `jalur` (INTERNAL/EKSTERNAL), `kualifikasi_pendidikan`, `ipk_minimal`, `batas_usia`, `pengalaman_minimal`, `dokumen_wajib` (M2M ke master jenis dokumen), `tanggal_buka`, `tanggal_tutup`, `formasi_ref` (FK nullable) | `sdm/models/rekrutmen.py`, migrasi | Migrasi jalan; lowongan lama default aman |
| C1.2 | Form lowongan diperluas + validasi (tanggal tutup > buka, IPK 0–4) | `sdm/forms/rekrutmen.py` | Test: tanggal terbalik ditolak |
| C1.3 | Integrasi formasi: tarik kuota/posisi/kualifikasi dari modul Rencana Formasi bila `formasi_ref` diisi | `sdm/services/formasi.py`, form | Test: pilih formasi → kuota terisi |
| C1.4 | UI daftar lowongan: filter status/jalur/unit, kolom jumlah pelamar | template `rekrutmen/daftar.html` | Smoke: filter bekerja |

#### Fase C2 — Portal Pelamar (publik, self-service)

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| C2.1 | Model `Pelamar` (token akses unik, identitas, kontak, pendidikan, riwayat kerja, kontak darurat) — **tanpa** akun Django; akses via token di URL | `sdm/models/rekrutmen.py`, migrasi | Test: token tidak bisa ditebak; akses tanpa token ditolak |
| C2.2 | Model `BerkasPelamar` (pelamar, jenis dokumen, file, status verifikasi) — unggahan ke storage privat | model + storage | Test: file tersimpan privat, bukan di `media/` publik |
| C2.3 | Halaman publik: daftar lowongan terbuka (tanpa data internal) | view publik + template | Smoke: halaman render tanpa login |
| C2.4 | Form pendaftaran + e-upload dengan validasi tipe (PDF/JPG) & ukuran | form + template | Test: file .exe ditolak |
| C2.5 | Validasi dokumen otomatis: peringatan dini bila STR/sertifikat kadaluarsa; blokir submit bila dokumen wajib kurang | `sdm/services/rekrutmen.py` | Test: STR kadaluarsa → peringatan; dokumen kurang → tidak bisa submit |
| C2.6 | Dasbor kandidat (via token): status per tahap real-time | view + template | Smoke: status berubah setelah HR memindahkan tahap |
| C2.7 | Rate-limit & anti-abuse pada endpoint publik | middleware/view | Test: submit berulang cepat dibatasi |

#### Fase C3 — Seleksi Administrasi & Screening

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| C3.1 | Perluas `Lamaran.STATUS_CHOICES` + `ALLOWED_TRANSITIONS` sesuai alur dokumen (tambah tahap MCU; pisahkan lulus/tidak per tahap) | `sdm/models/rekrutmen.py` | Test: transisi tidak sah ditolak; alur lama tetap jalan |
| C3.2 | Model `PenilaianTahap` (lamaran, tahap, skor, catatan, penguji, waktu) — append-only | model + migrasi | Test: penilaian ganda tercatat semua |
| C3.3 | Status dokumen per-item: Valid / Perlu Klarifikasi / Tidak Lengkap | model + UI | Smoke: tandai dokumen, status berubah |
| C3.4 | Auto-filter: IPK di bawah standar atau STR kadaluarsa → saran otomatis kategori Rejected (dengan konfirmasi manusia, bukan otomatis buang) | service + UI | Test: kandidat di bawah IPK ditandai, bukan langsung ditolak |
| C3.5 | Notifikasi email penolakan otomatis (via `send_mail`) | service | Test: email terkirim sekali |
| C3.6 | UI matriks penapisan: tabel pelamar × kriteria, aksi massal | template | Smoke: aksi massal bekerja |

#### Fase C4 — CBT / Ujian Kompetensi

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| C4.1 | Model `BankSoal` (profesi, kategori, pertanyaan, pilihan, jawaban benar, bobot) + `PaketSoal` | model + migrasi | Test: soal terkait profesi benar |
| C4.2 | Model `SesiUjian` (lamaran, paket, mulai, batas waktu, status) + `JawabanUjian` | model + migrasi | Test: sesi kedaluwarsa tidak bisa dijawab |
| C4.3 | Mesin ujian: timer server-side (bukan hanya client), pengacakan soal & pilihan per sesi | service + view | Test: urutan beda antar sesi; submit setelah waktu habis ditolak |
| C4.4 | Auto-scoring + ranking per lowongan | service | Test: skor & peringkat cocok dengan jawaban |
| C4.5 | UI pengerjaan ujian (satu soal per layar, navigasi, indikator waktu) | template | Smoke: selesaikan ujian, skor muncul |
| C4.6 | Anti-cheating dasar: catat perpindahan fokus tab, satu sesi per kandidat | JS + model | Test: perpindahan fokus tercatat |

#### Fase C5 — Wawancara

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| C5.1 | Model `JadwalWawancara` (lamaran, waktu, mode luring/daring, tautan, penguji M2M) | model + migrasi | Test: jadwal bentrok terdeteksi |
| C5.2 | Undangan otomatis via email ke pelamar + penguji | service | Test: email terkirim ke semua penguji |
| C5.3 | `ScorecardWawancara` per penguji (indikator: kompetensi teknis, soft skill, ketahanan beban, integritas, AIK) | model + form | Test: skor di luar rentang ditolak |
| C5.4 | Kalkulasi skor gabungan berbobot (berkas + CBT + HRD + user/komite) — bobot dari konstanta konfigurasi | service | Test: skor gabungan cocok dengan hitungan manual |
| C5.5 | UI penguji: daftar wawancara + form scorecard | template | Smoke: penguji input skor |

#### Fase C6 — MCU & Offering Letter

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| C6.1 | Model `HasilMCU` (lamaran, tanggal, status Fit/Fit with Note/Unfit, catatan, dokumen sumber) | model + migrasi | Test: status di luar pilihan ditolak |
| C6.2 | Tahap MCU masuk ke alur transisi (C3.1) | model | Test: alur lengkap sampai DITERIMA |
| C6.3 | Generator offering letter PDF (ReportLab, kop dari `SystemConfig.kop_surat_text`, nomor dari counter) | service | Test: PDF berisi posisi, unit, komponen gaji |
| C6.4 | E-signature / konfirmasi persetujuan kandidat via token | model + view | Test: konfirmasi tercatat dengan waktu & IP |
| C6.5 | Notifikasi WA — **hanya bila C0.6 memutuskan ada gateway** | service | Test terkait |

#### Fase C7 — Orientasi & Integrasi e-File

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| C7.1 | Perluas `hire_application`: konversi satu klik — pindahkan identitas, pendidikan, berkas (ijazah/STR/SIP/sertifikat) ke `DokumenPegawai` + `VersiDokumen` | `sdm/services/rekrutmen.py` | Test: dokumen pelamar muncul di e-file pegawai baru |
| C7.2 | Auto-generate NIP dari pola yang dikonfigurasi admin (bukan dikarang) + buat akun pengguna | service | Test: NIP unik, akun tertaut ke `Pegawai` |
| C7.3 | Auto-enroll orientasi: panggil `auto_assign_orientation` (plan 2026-10-27 Fase O2) saat pegawai baru dibuat | service | Test: pegawai baru langsung punya penugasan orientasi |
| C7.4 | Isi jenjang awal pegawai baru dari profesi lowongan + katalog RKK terkait | service | Test: pegawai baru ber-jenjang sesuai lowongan |

#### Fase C8 — Dasbor, Talent Pool, Notifikasi

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| C8.1 | Dasbor pemantauan HR: kolom sesuai dokumen (kode lowongan, posisi, unit, kuota, pelamar masuk, lulus admin/CBT/wawancara/MCU, status) | view + template | Smoke: angka cocok dengan data nyata |
| C8.2 | Export rekap PDF dasbor | service | Test: PDF berisi baris yang sama dengan layar |
| C8.3 | Talent Pool: simpan pelamar berkualifikasi yang tidak terpilih; pencarian cepat saat buka formasi baru | model + UI | Test: pelamar tersimpan & bisa dipanggil ulang |
| C8.4 | Audit trail KPS: seluruh bukti seleksi (verifikasi STR/ijazah, hasil CBT, scorecard, MCU) dapat diunduh sebagai bukti audit | service + view | Test: paket bukti berisi semua dokumen tahap |
| C8.5 | Pengingat tahap menggantung via `hc_reminders` | command | Test: pengingat dibuat sekali |

---

## 5. Urutan yang disarankan

1. **Bagian B** (auto-fill kredensial) — 6 langkah kecil, langsung terasa, tidak menunggu keputusan apa pun.
2. **Bagian A** (audit & tambal RKK) — A.1 dan A.2 cepat; A.3–A.5 butuh verifikasi terhadap dokumen.
3. **Fase C0** — kumpulkan keputusan pemilik proses; tanpa ini C4/C5/C6 tidak bisa benar.
4. **Fase C1 + C3.1–C3.3** — perluas lowongan & alur transisi; fondasi untuk sisanya.
5. **Fase C2** (portal pelamar) — butuh C1 stabil; pekerjaan terbesar setelah CBT.
6. **Fase C4 + C5** — CBT dan wawancara; C5 butuh bobot dari C0.3.
7. **Fase C6 + C7** — MCU/offering dan konversi; C7 butuh Fase O2 plan orientasi.
8. **Fase C8** — dasbor & talent pool terakhir, melaporkan semuanya.

---

## 6. Yang tidak dikerjakan

- Menyalin HTML/CSS simulasi dari dokumen permintaan; tampilan mengikuti `DESIGN.md`.
- Menambah DRF/React/weasyprint (ReportLab sudah ada).
- Mengarang butir katalog RKK dokter gigi/spesialis tanpa SK komite.
- Mengarang NIP, nomor surat, bobot skor, passing grade, atau hasil tes psikologi/MCU.
- Gateway WhatsApp sebelum C0.6 diputuskan.
- LMS penuh — CBT cukup untuk seleksi, bukan platform pembelajaran.
- Mengganti alur kredensial yang sudah berjalan; auto-fill hanya menambah kenyamanan.

---

## 7. Bukti sebelum dinyatakan selesai

| Bagian | Bukti |
|---|---|
| B | Pilih pegawai di form HC → unit kerja terisi otomatis + badge muncul; STR/SIP tampil dengan status; ubah manual → badge berubah; submit tanpa STR wajib → error terarah |
| A | `seed_katalog_rkk` idempoten; `audit_katalog_rkk` melaporkan 0 profesi hilang dari dokumen; DOKTER_GIGI punya 3 jenjang |
| C1 | Lowongan dengan tanggal terbalik ditolak; pilih formasi → kuota terisi |
| C2 | Halaman publik render tanpa login; file .exe ditolak; STR kadaluarsa → peringatan; dasbor kandidat menampilkan status benar |
| C3 | Transisi tidak sah ditolak; kandidat di bawah IPK ditandai (bukan auto-buang); email penolakan terkirim sekali |
| C4 | Urutan soal beda antar sesi; submit setelah waktu habis ditolak; skor & ranking cocok dengan jawaban |
| C5 | Jadwal bentrok terdeteksi; skor gabungan cocok dengan hitungan manual |
| C6 | PDF offering berisi data benar; konfirmasi kandidat tercatat |
| C7 | Dokumen pelamar muncul di e-file pegawai baru; NIP unik; pegawai baru punya penugasan orientasi |
| C8 | Angka dasbor cocok dengan data nyata; rekap PDF sama dengan layar; paket bukti audit lengkap |
