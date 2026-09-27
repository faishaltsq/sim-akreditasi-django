# 📘 Panduan Lengkap: Pusat Kontrol Sistem & Manajemen Akses
### SIM Akreditasi RS (SIK AP — Standar STARKES KARS)
**Versi:** 2.0 (Edisi 2026) &bull; **Target Pengguna:** Super Admin, Admin RS, dan Tim Manajemen TI/Mutu

---

## 📑 Daftar Isi
1. [Tentang Pusat Kontrol Sistem](#1-tentang-pusat-kontrol-sistem)
2. [Hak Akses & Tingkatan Wewenang (Tab-Level Permission)](#2-hak-akses--tingkatan-wewenang)
3. [Panduan Operasional Tiap Tab:](#3-panduan-operasional-tiap-tab)
   - [Tab 1: Hierarki & Unit Organisasi (N-Level & Reparenting)](#tab-1-hierarki--unit-organisasi)
   - [Tab 2: Matriks Hak Akses Peran Dinamis (Role Permission Matrix)](#tab-2-matriks-hak-akses-peran-dinamis)
   - [Tab 3: Kustomisasi Akses Pengguna (User Overrides)](#tab-3-kustomisasi-akses-pengguna)
   - [Tab 4: Standar & Ambang Batas Akreditasi (Passing Grade, RDWOS, Risiko)](#tab-4-standar--ambang-batas-akreditasi)
   - [Tab 5: Branding, Tema & Mode Kunci Survei (Freeze Mode)](#tab-5-branding-tema--mode-kunci-survei)
4. [Tabel Referensi 18 Modul Izin Sistem](#4-tabel-referensi-18-modul-izin-sistem)
5. [Protokol Keamanan & Perlindungan Lockout](#5-protokol-keamanan--perlindungan-lockout)
6. [Audit Trail & Rekaman Perubahan](#6-audit-trail--rekaman-perubahan)
7. [Tanya Jawab (FAQ) & Penyelesaian Masalah](#7-tanya-jawab-faq--penyelesaian-masalah)

---

## 1. Tentang Pusat Kontrol Sistem

**Pusat Kontrol Sistem** (`/accounts/kontrol/`) adalah modul terpusat bagi Administrator untuk mengkustomisasi seluruh parameter operasional rumah sakit secara independen tanpa perlu mengubah baris kode atau melakukan *deployment* ulang.

### Mengapa Menu Ini Dibuat?
- **Kebutuhan Dinamis Tiap Rumah Sakit:** Tiap rumah sakit memiliki struktur organisasi, batas toleransi risiko, dan kebijakan unggah berkas yang berbeda-beda.
- **Kepatuhan Standar KARS 2026:** Standar akreditasi menuntut kejelasan wewenang (kredensial staf), struktur unit yang terlacak, dan transparansi penilaian EP.
- **Kesiapan Menghadapi Survei:** Tersedia fitur proteksi khusus untuk membekukan perubahan data saat tim surveior akreditasi hadir di rumah sakit.

---

## 2. Hak Akses & Tingkatan Wewenang

Secara default, menu ini **eksklusif** dan hanya dapat diakses oleh peran tertentu:

| Peran Akun | Hak Akses Menu | Tab yang Dapat Dikelola |
|---|---|---|
| **SUPER_ADMIN** (`admin`) | Penuh (5 Tab) | Seluruh 5 Tab: Hierarki, Matriks Izin, User Override, Ambang Batas, Branding & Freeze Mode |
| **ADMIN_RS** (`admin.rs`) | Terbatas (3 Tab) | Tab 1 (Hierarki Unit), Tab 2 (Matriks Izin), Tab 3 (User Override). Tab 4 & 5 terkunci |
| **Role Lain** (Direktur, Asesor, Staf) | Tidak Ada | Menu tidak tampil di sidebar; akses langsung URL diblokir otomatis |

> **Catatan Fleksibilitas:** Super Admin dapat memberikan izin akses menu ini ke pengguna tertentu di luar peran admin dengan mengaktifkan toggle `can_access_control_center` di Tab 3 (User Overrides).

---

## 3. Panduan Operasional Tiap Tab

### Tab 1: Hierarki & Unit Organisasi
Tab ini digunakan untuk mengelola seluruh struktur unit kerja rumah sakit mulai dari tingkatan puncak (Pimpinan) hingga unit pelaksana terkecil (Depo/Ruangan).

#### Fitur Utama:
1. **Dukungan N-Level Tanpa Batas:**
   - Sistem tidak membatasi tingkat hierarki (bisa sampai Level 4, 5, atau lebih dalam sesuai kompleksitas rumah sakit).
   - Level dihitung otomatis oleh sistem berdasarkan posisi induk (*parent*): Level = Level Induk + 1.
2. **Reparenting Interaktif:**
   - Memindahkan sub-unit dari satu atap direktorat/bagian ke bagian lain semudah memilih nama induk baru di dropdown *Induk Unit (Parent)*.
   - Dilengkapi algoritma proteksi *Anti-Circular Dependency* (unit tidak dapat dijadikan anak dari dirinya sendiri atau sub-unitnya).
3. **Pengaturan Tipe & Klasifikasi Unit:**
   - Pilihan: *Pimpinan / Dewas*, *Direktorat / Bidang*, *Komite RS*, *SPI*, *Bagian / Sub-Bag*, *Instalasi*, *KSM Spesialis*, *Ruangan Pelayanan*, *Depo / Satelit*, dan *Lainnya*.
4. **Urutan Tampilan (*Sort Order*):**
   - Atur angka urutan untuk menentukan posisi kemunculan unit di sidebar, dropdown formulir, dan halaman pohon hierarki.
   - Unit dengan angka lebih kecil tampil lebih atas. Jika semua unit memiliki angka urutan yang sama (misal semua `0`), sistem akan menampilkan unit berdasarkan urutan ID database (kapan pertama kali dibuat).
   - **Tips:** Gunakan kelipatan 10 (misal `10`, `20`, `30`) agar mudah menyisipkan unit baru di antara unit yang sudah ada tanpa perlu mengubah angka urutan seluruh unit.
5. **Toggle Aktif / Arsip:**
   - Unit yang dinonaktifkan tidak akan muncul pada dropdown formulir baru, namun riwayat data lamanya tetap tersimpan aman.

#### Langkah Mengubah Hierarki Unit:
1. Masuk ke **Pusat Kontrol Sistem** &rarr; Buka **Tab 1 (Hierarki & Unit Organisasi)**.
2. Gunakan kolom pencarian di pojok kanan atas untuk menemukan unit yang ingin diubah.
3. Ubah kolom yang diinginkan (Tipe Unit, Induk Parent, Nomor Urut, atau Status Aktif).
4. Klik tombol **Simpan** pada baris unit tersebut. Sistem akan memvalidasi dan memperbarui level secara instan.

---

### Tab 2: Matriks Hak Akses Peran Dinamis (Role Permission Matrix)
Tab ini menyediakan kisi-kisi matriks antara **6 Peran Standar** dengan **18 Modul Izin Sistem**.

#### 6 Peran Standar Sistem:
1. `SUPER_ADMIN` — Administrator Utama Sistem
2. `ADMIN_RS` — Administrator Operasional Rumah Sakit
3. `DIREKTUR` — Pimpinan Tertinggi & Dewan Pengawas
4. `KOORDINATOR_POKJA` — Ketua Pokja STARKES
5. `KEPALA_UNIT` — Kepala Instalasi / Ruangan / KSM
6. `STAF_NAKES` — Staf Medis, Perawat, Nakes, dan Administrasi

#### Cara Kerja:
- Setiap saklar (*switch toggle*) mewakili izin khusus (misal: *Beri Skor EP*, *Hapus Dokumen Bukti*, *Investigasi Insiden*).
- Cukup aktifkan atau matikan saklar pada kolom peran yang dituju.
- Setelah selesai mengatur kisi-kisi, klik tombol hijau **Simpan Seluruh Matriks Izin** di pojok kanan atas.
- **Tombol Reset ke Standar KARS:** Jika konfigurasi izin tidak sengaja bermasalah, klik tombol merah *Reset ke Standar KARS* untuk mengembalikan seluruh matriks ke formula default KARS.

---

### Tab 3: Kustomisasi Akses Pengguna (User Overrides)
Digunakan ketika seorang staf membutuhkan wewenang tambahan khusus di luar standar perannya tanpa perlu menaikkan pangkat/peran globalnya di sistem.

*Contoh Kasus:*
- Seorang staf perawat (`STAF_NAKES`) ditunjuk menjadi Sekretaris Akreditasi, sehingga membutuhkan izin unggah bukti RDWOS dan verifikasi KPS.
- Tanpa fitur ini, admin harus mengubah perannya menjadi `ADMIN_RS` (terlalu berisiko).
- Dengan **User Overrides**, admin cukup memberi centang tambahan pada staf tersebut.

#### Langkah Menetapkan Override Pengguna:
1. Buka **Tab 3 (Kustomisasi Akses Pengguna)**.
2. Cari nama staf melalui kolom pencarian.
3. Klik tombol **Atur Akses Kustom** di sebelah kanan nama pengguna.
4. Modal popup akan terbuka menampilkan 18 izin modular. Centang izin yang ingin diberikan secara khusus kepada staf tersebut.
5. Klik **Simpan Hak Akses Kustom**.
6. Pengguna tersebut langsung memiliki hak akses baru pada saat memuat ulang halaman.

---

### Tab 4: Standar & Ambang Batas Akreditasi
*(Khusus Super Admin)*

Tab ini menampung parameter kuantitatif yang digunakan oleh mesin kalkulasi sistem:

1. **Ambang Batas Nilai Kelulusan Akreditasi (Passing Grade %):**
   - **Paripurna (Bintang 5 / A):** Default `80%`.
   - **Utama (Bintang 4 / B):** Default `60%`.
   - **Madya (Bintang 3 / C):** Default `40%`.
   - **Dasar (Bintang 2 / D):** Default `20%`.
   - *Catatan:* Perubahan nilai ini langsung mengubah kalkulasi predikat di modul Auto-Scoring dan badge pada Matriks PDCA.
2. **Kebijakan Berkas Bukti RDWOS:**
   - **Maksimal Ukuran Berkas:** Default `25 MB` (dapat diubah antara 1–100 MB).
   - **Ekstensi yang Diizinkan:** Default `pdf,docx,xlsx,pptx,jpg,jpeg,png`.
3. **Peringatan Masa Berlaku Kredensial Nakes (KPS):**
   - Jangka waktu (hari) sebelum STR/SIP habis masa berlaku untuk memicu peringatan kuning di Portal Nakes dan Rekap KPS (Default: `60 hari`).
4. **Batas Skor Matriks Risiko 5×5:**
   - Ambang batas pengelompokan tingkat risiko inheren & residual:
     - **Sangat Tinggi:** Skor &ge; `20` (Merah Tua)
     - **Tinggi:** Skor &ge; `12` (Oranye)
     - **Sedang:** Skor &ge; `5` (Kuning)
     - **Rendah:** Skor &ge; `1` (Hijau)

---

### Tab 5: Branding, Tema & Mode Kunci Survei
*(Khusus Super Admin)*

#### A. Mode Kunci Survei Akreditasi (Freeze Mode)
- **Tujuan:** Melindungi data saat surveior akreditasi (KARS/LAFI/LAM-KPRS) sedang berada di rumah sakit untuk melakukan telusur dokumen dan simulasi lapangan.
- **Cara Kerja:**
  - Saat tombol merah **Kunci Sistem Sekarang (Mode Survei)** ditekan, banner peringatan kuning besar akan tampil di seluruh layar pengguna.
  - Seluruh pengguna non-Super Admin otomatis diubah ke status **Read-Only (Baca Saja)**.
  - Percobaan mengedit skor EP, mengunggah/menghapus file bukti, atau mengubah profil risiko akan otomatis diblokir sistem.
  - Untuk membuka kembali setelah survei selesai, Super Admin cukup menekan tombol **Buka Kunci Sistem**.

#### B. Tema Warna & Kop Surat
- **Tema Aksen Antarmuka:** Pilihan palette warna (Teal Medis RS MonsisKami, Hospital Royal Blue, Emerald Green Health, atau Dark Navy Slate).
- **Kop Surat Dokumen Cetak:** Kolom teks untuk mengatur kop surat resmi rumah sakit (nama yayasan, alamat, nomor telepon, izin operasional) yang akan tampil otomatis saat mencetak laporan atau matriks PDCA via peramban (`Ctrl + P`).

---

## 4. Tabel Referensi 18 Modul Izin Sistem

| No | Kode Izin (`field_name`) | Label Modul | Fungsi & Wewenang yang Diatur |
|---|---|---|---|
| 1 | `can_view_pdca` | Lihat Matriks PDCA | Mengakses dan membaca halaman Matriks PDCA & daftar EP |
| 2 | `can_edit_pdca` | Ubah PDCA & Rencana Aksi | Mengisi baseline, target mutu, PIC, anggaran, dan evaluasi |
| 3 | `can_score_ep` | Beri Skor EP (0 / 5 / 10) | Memberikan skor self-assessment pemenuhan elemen penilaian |
| 4 | `can_view_rdwos` | Akses Dokumen RDWOS | Mengunduh dan melihat berkas bukti Regulasi, Dokumen, Wawancara, Observasi, Simulasi |
| 5 | `can_upload_rdwos` | Unggah Berkas Bukti | Mengunggah dokumen bukti baru ke server |
| 6 | `can_delete_rdwos` | Hapus Berkas Bukti | Menghapus dokumen bukti yang telah terunggah |
| 7 | `can_view_risiko` | Lihat Register Risiko | Membaca daftar profil risiko unit dan peta risiko 5×5 |
| 8 | `can_manage_risiko` | Kelola & Mitigasi Risiko | Membuat risiko baru, menentukan skor probabilitas/dampak, rencana mitigasi |
| 9 | `can_lapor_insiden` | Lapor Insiden Keselamatan | Mengisi formulir pelaporan insiden keselamatan (KNC/KTD/Sentinel) |
| 10 | `can_investigate_insiden` | Investigasi & Grading Insiden | Mengubah hasil grading risiko insiden dan investigasi RCA/5-Why |
| 11 | `can_view_scoring` | Akses Auto-Scoring & Prediksi | Melihat kalkulasi prediksi kelulusan dan persentase kelengkapan |
| 12 | `can_export_reports` | Ekspor Dokumen & Excel | Mengunduh rekap akreditasi dalam format spreadsheet Excel |
| 13 | `can_manage_units` | Manajemen Unit Kerja | Menambah atau mengedit data unit kerja rumah sakit |
| 14 | `can_manage_users` | Manajemen Akun Pengguna | Membuat akun baru, mengatur peran, mereset password staf |
| 15 | `can_verify_kps` | Verifikasi KPS Nakes | Menyetujui/memvalidasi dokumen STR, SIP, dan SPK/RKK staf |
| 16 | `can_view_audit_log` | Lihat Log Audit Sistem | Mengakses riwayat audit jejak aktivitas sistem |
| 17 | `can_access_control_center` | Akses Pusat Kontrol | Masuk ke menu `/accounts/kontrol/` |
| 18 | `can_manage_system_settings` | Kelola Kebijakan Sistem | Mengubah ambang batas kelulusan, tema, dan Mode Freeze Survei |

---

## 5. Protokol Keamanan & Perlindungan Lockout

Untuk mencegah kesalahan konfigurasi fatal yang dapat mengunci sistem (*system lockout*):

1. **Proteksi Wewenang Super Admin (*Lockout Guard*):**
   - Izin `can_access_control_center`, `can_manage_users`, dan `can_manage_system_settings` pada kolom `SUPER_ADMIN` diproteksi permanen (*disabled checkbox*) di antarmuka dan divalidasi ketat pada backend. Super Admin tidak dapat secara tidak sengaja mencabut hak akses dirinya sendiri.
2. **Validasi Anti-Circular Reparenting Unit:**
   - Sistem memeriksa pohon silsilah unit saat memindahkan induk. Jika Unit A dipilih menjadi anak dari Unit B, padahal Unit B adalah anak dari Unit A, transaksi otomatis ditolak demi mencegah *infinite loop* pada query database.
3. **Penyimpanan Override JSON Terisolasi:**
   - Izin kustom staf disimpan dalam format `custom_permissions` terisolasi pada profil masing-masing pengguna. Jika peran staf tersebut diubah di masa depan, sistem tetap memprioritaskan keamanan berbasis peran.

---

## 6. Audit Trail & Rekaman Perubahan

Setiap aksi perubahan pada Pusat Kontrol Sistem otomatis dicatat ke dalam database riwayat aktivitas (`AuditLog`):
- **Waktu Transaksi:** Tanggal dan jam presisi (WIB).
- **Pelaku:** Username dan alamat IP admin yang melakukan perubahan.
- **Jenis Operasi:** Pembaruan Hierarki Unit, Perubahan Matriks Izin, Penetapan User Override, atau Pembaruan Ambang Batas.
- **Riwayat Data:** Membandingkan nilai lama (*before*) dan nilai baru (*after*).

Riwayat ini dapat ditinjau kapan saja melalui menu **Pengaturan &rarr; Log Sistem**.

---

## 7. Tanya Jawab (FAQ) & Penyelesaian Masalah

#### Q: Mengapa setelah mengubah izin peran, staf terkait belum merasakan perubahannya?
> **Jawab:** Perubahan izin peran berlaku seketika. Namun, jika peramban staf masih menyimpan cache sesi lama, minta staf melakukan *Refresh* halaman (`Ctrl + F5`) atau melakukan *Logout* dan *Login* kembali.

#### Q: Bagaimana cara membatalkan izin kustom seorang pengguna agar kembali mengikuti standar perannya?
> **Jawab:** Buka **Tab 3**, klik **Atur Akses Kustom** pada pengguna tersebut, hilangkan semua tanda centang, lalu klik **Simpan**. Status akan kembali menjadi *"Mengikuti Peran"*.

#### Q: Apakah mengaktifkan Mode Kunci Survei akan menghalangi Super Admin untuk memperbaiki kesalahan ketik mendesak saat survei?
> **Jawab:** Tidak. Super Admin tetap memiliki akses tulis (*write permission*) penuh bahkan saat Mode Kunci Survei aktif. Pembatasan hanya berlaku untuk peran selain Super Admin.

---

*Dokumen ini diterbitkan oleh Tim Pengembang SIM Akreditasi RS MonsisKami sebagai panduan resmi tata kelola administrasi sistem.*
