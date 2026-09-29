# Implementation Plan: Pemetaan 16 Bab Standar STARKES Terbaru (Kepmenkes 1128/2022)

**Sumber Data**: `Berikut adalah tabel pemetaan Standar Akreditasi Rumah Sakit Terbaru.docx`
- **Total**: 16 Bab Standar, 321 Elemen Penilaian (EP), 5 Kelompok Standar Utama
- **Status Database Saat Ini**: Baru 3 Bab (TKRS, PMKP, KPS) dengan 11 EP placeholder.

---

## 1. Analisis Perubahan & Dampak

### A. Model `Category` (Pokja / Bab Akreditasi)
Tambahkan field baru pada model `Category` (`akreditasi/models.py`):
1. `kelompok` (CharField, choices):
   - `MANAJEMEN`: "Kelompok Manajemen Rumah Sakit" (6 Bab)
   - `PELAYANAN`: "Kelompok Pelayanan Berfokus pada Pasien" (7 Bab)
   - `SASARAN_KP`: "Kelompok Sasaran Keselamatan Pasien" (1 Bab)
   - `PROGNAS`: "Kelompok Program Nasional" (1 Bab)
   - `PENDIDIKAN`: "Kelompok Integrasi Pendidikan Kesehatan" (1 Bab)
2. `target_ep_count` (PositiveIntegerField): Jumlah target EP resmi STARKES (misal TKRS: 28, KPS: 23, dst.)
3. `unit_pengampu` (TextField): Unit kerja terkait & pengampu (dari kolom dokumen docx)

### B. Daftar 16 Bab Standar STARKES Lengkap

| No | Kode | Nama Bab STARKES | Kelompok | Target EP | Unit Kerja Pengampu & Terlibat |
|---|---|---|---|---|---|
| 1 | **TKRS** | Tata Kelola Rumah Sakit | Manajemen RS | 28 EP | Pemilik/Dewas, Direksi, Komite-Komite, Seluruh Kepala Instalasi |
| 2 | **KPS** | Kualifikasi & Pendidikan Staf | Manajemen RS | 23 EP | Bagian SDM, Komite Medis/Keperawatan/Nakes, Diklat |
| 3 | **MFK** | Manajemen Fasilitas & Keselamatan | Manajemen RS | 21 EP | Bagian K3RS, IPSRS, Sanitasi, Security, Seluruh Instalasi |
| 4 | **PMKP** | Peningkatan Mutu & Keselamatan Pasien | Manajemen RS | 18 EP | Komite Mutu, Sub-Komite KP, Seluruh Instalasi Pelayanan |
| 5 | **MRMIK** | Manajemen Informasi & Rekam Medis | Manajemen RS | 14 EP | Unit Rekam Medis, SIMRS/IT, Humas, Seluruh Depo Klinis |
| 6 | **PPI** | Pencegahan & Pengendalian Infeksi | Manajemen RS | 18 EP | Komite PPI, IPCN, Unit Sanitasi, CSSD, Laundry, Seluruh Unit |
| 7 | **ARK** | Akses dan Kontinuitas Pelayanan | Pelayanan Pasien | 23 EP | Admisi, IGD, Poliklinik Rajal, Ranap, ICU, Ambulans, MPP/Case Manager |
| 8 | **HPK** | Hak Pasien dan Keluarga | Pelayanan Pasien | 11 EP | Humas/Customer Service, Admisi, PPA (Dokter/Perawat), Kerohanian |
| 9 | **PP** | Pengasesan Pasien | Pelayanan Pasien | 16 EP | DPJP, Perawat, Dietisien, Apoteker, Laboratorium, Radiologi |
| 10 | **PAP** | Pelayanan dan Asuhan Pasien | Pelayanan Pasien | 19 EP | Ranap, ICU/ICCU/HCU, OK, IGD, Hemodialisa, Kemoterapi, Rehab |
| 11 | **PAB** | Pelayanan Anestesi dan Bedah | Pelayanan Pasien | 20 EP | Kamar Bedah (OK), Depo Farmasi OK, Dokter Anestesi, Bedah, PACU |
| 12 | **PKPO** | Pelayanan Kefarmasian & Penggunaan Obat | Pelayanan Pasien | 20 EP | Instalasi Farmasi (Gudang, Depo), KFT, Komite Medis/Keperawatan |
| 13 | **KE** | Komunikasi dan Edukasi | Pelayanan Pasien | 7 EP | Tim PKRS, Humas, Seluruh PPA Rajal/Ranap/Penunjang |
| 14 | **SKP** | Sasaran Keselamatan Pasien | Sasaran KP | 10 EP | Tim KPRS, Seluruh PPA (Dokter, Perawat, Bidan, Apoteker, Analis) |
| 15 | **PROGNAS** | Program Nasional (PONEK, TB, HIV, Stunting, PPRA) | Program Nasional | 26 EP | Tim PONEK, Tim TB-DOTS, Tim HIV/AIDS, Tim PPRA, Tim Stunting |
| 16 | **IPKP** | Integrasi Pendidikan Kesehatan dalam Pelayanan | Integrasi Pendidikan | 6 EP | Komite Kordik, Bagian Diklat, Unit Lahan Praktik/Pendidikan |
| **TOTAL** | **16 Bab** | | | **321 EP** | |

---

## 2. Rencana Eksekusi Bertahap (Phased Execution)

### Fase 1: Perluasan Model & Migrasi Skema
1. Modifikasi `Category` di `akreditasi/models.py`:
   - Tambahkan `KELOMPOK_CHOICES`
   - Tambahkan `kelompok`, `target_ep_count`, `unit_pengampu`
2. Jalankan `makemigrations` dan `migrate`.

### Fase 2: Seeder 16 Bab Standar STARKES & Elemen Penilaian
1. Buat management command: `seed_starkes_16_bab.py`:
   - Upsert 16 Category lengkap beserta kelompok, nama resmi, target EP, dan deskripsi unit pengampu.
   - Seed seluruh sub-standar dan 321 Elemen Penilaian (EP) dengan kode standar baku STARKES (misal `TKRS 1 EP 1`, `PKPO 1 EP 1`, `SKP 1 EP 1`, dst.) sehingga matriks PDCA langsung memiliki basis data 321 EP nyata.
   - Link default QualityRecord (score=0, status=PLAN) untuk setiap EP agar matriks PDCA langsung interaktif.
2. Buat data migration otomatis agar seeder berjalan saat deploy di production Railway.

### Fase 3: Pemetaan Otomatis Unit Kerja Pengampu (`standar_terkait`)
1. Sinkronisasi `UnitKerja.standar_terkait` dengan 16 bab STARKES:
   - **FARM (Instalasi Farmasi)**: PKPO (20 EP), MFK, PPI, KPS, TKRS
   - **LAB-BDRS**: PP, PPI, MFK, TKRS, KPS
   - **RAD-IMAGING**: PP, MFK, TKRS, KPS
   - **IGD**: ARK, PAP, SKP, MFK, PPI
   - **IBS (Bedah)**: PAB, PAP, SKP, PPI, MFK
   - **INTENSIF (ICU)**: PAP, SKP, PPI, MFK
   - **REKAM-MEDIS**: MRMIK, HPK, ARK
   - **SUB-IPSRS & SUB-KESLING**: MFK, PPI
   - **KMKP (Mutu & KP)**: PMKP, SKP, TKRS
   - **BAG-SDM & BAG-DIKLIT**: KPS, IPKP, TKRS
   - **PROGNAS / TIM-PONEK**: PROGNAS
2. Kepala unit masing-masing otomatis mendapatkan sidebar dan matriks PDCA khusus sesuai bab tanggung jawabnya.

### Fase 4: Pembaruan UI & Dashboard
1. **Sidebar Navigation**:
   - Tampilkan 16 Bab dikelompokkan berdasarkan 5 accordion Kelompok Standar (Manajemen, Pelayanan, SKP, Prognas, IPKP) untuk Super Admin/Direksi.
   - Untuk user Kepala Unit (`is_unit_scoped`), sidebar tetap accordion ringkas bab terkait unitnya.
2. **Dashboard RS**:
   - Tampilkan rekap per Kelompok Standar (progress %, badge akreditasi per kelompok).
   - Progress bar keseluruhan RS: kalkulasi dari 321 EP.
3. **Matriks PDCA**:
   - Tab navigasi Pokja dikelompokkan atau diberi badge kelompok standar agar tidak menumpuk 16 tombol mendatar.
4. **Rekap / Cetak PDF**:
   - Rekapitulasi per 16 Bab dengan breakdown target vs riil EP.

### Fase 5: Tambah Unit Kerja & Akun Demo L4
1. **Unit Kerja Baru (Level 4)** — pilih 6 unit L4 strategis merepresentasikan semua kelompok standar:
   | Kode | Nama | Induk (L3) | Standar Terkait |
   |---|---|---|---|
   | `DEPO-RAJAL` | Depo Farmasi Rawat Jalan | FARM | PKPO, PPI, MFK |
   | `PATKLIN` | Unit Patologi Klinik & Mikrobiologi | LAB-BDRS | PP, PPI, MFK |
   | `RUANG-OK` | Unit Kamar Operasi (OK) | IBS | PAB, PAP, SKP, PPI, MFK |
   | `RUANG-PRIA` | Ruang Perawatan Pria | BANGSAL-DEWASA | PAP, HPK, SKP, PPI |
   | `ADMISI` | Unit Pendaftaran & Admission | REKAM-MEDIS | ARK, HPK, MRMIK |
   | `CSSD` | Instalasi CSSD & Laundry | CSSD-JENAZAH | PPI, MFK |

2. **Akun Demo Khusus RS Monsiskami** — 1 akun level `ADMIN_RS` tanpa pembatasan unit, khusus demonstrasi ke pimpinan/tim mutu/asesor:
   | Username | Nama | Role | Unit | Password |
   |---|---|---|---|---|
   | `demo.monsiskami` | Demo RS Monsiskami | ADMIN_RS | — (akses seluruh RS) | `Demo@2024` |
   > Catatan: akun ini **tidak `is_unit_scoped`** — bisa lihat seluruh 16 bab, semua matriks PDCA, semua unit kerja, laporan PDF. Tidak bisa akses Tab Sistem & Log (eksklusif `SUPER_ADMIN`).

3. **Akun Demo (unit-scoped) Baru** — 8 akun mencakup L3 dan L4:
   | Username | Nama | Role | Unit | Password |
   |---|---|---|---|---|
   | `ka.depo.rajal` | Ka. Depo Farmasi Rawat Jalan | KEPALA_UNIT | DEPO-RAJAL (L4) | Unit@1234 |
   | `ka.laboratorium` | Ka. Laboratorium | KEPALA_UNIT | LAB-BDRS (L3) | Unit@1234 |
   | `ka.kamar.operasi` | Ka. Kamar Operasi | KEPALA_UNIT | RUANG-OK (L4) | Unit@1234 |
   | `ka.ranap` | Ka. Rawat Inap Dewasa | KEPALA_UNIT | BANGSAL-DEWASA (L3) | Unit@1234 |
   | `ka.rekam.medis` | Ka. Rekam Medis | KEPALA_UNIT | REKAM-MEDIS (L3) | Unit@1234 |
   | `ka.cssd` | Ka. CSSD & Laundry | KEPALA_UNIT | CSSD (L4) | Unit@1234 |
   | `koordinator.mutu` | Koordinator Mutu & KP | KOORDINATOR | KMKP (L2) | Unit@1234 |
   | `staf.sdm` | Staf SDM & Diklat | STAF | BAG-SDM (L3) | Unit@1234 |

---

## 3. Langkah Verifikasi
1. Jalankan `python manage.py check` & `test`.
2. Verifikasi 16 Category terdaftar di DB dengan total 321 EP.
3. Verifikasi role `SUPER_ADMIN` melihat 16 Bab dikelompokkan 5 Kelompok Standar di sidebar dan matriks.
4. Verifikasi role unit-scoped (misal `ka.farmasi`) hanya melihat bab farmasi (PKPO, MFK, PPI, KPS, TKRS).
5. Push & Deploy ke Railway, verifikasi production smoke test.
