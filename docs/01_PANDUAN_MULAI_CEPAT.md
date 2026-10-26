# 🚀 Panduan Mulai Cepat (Quickstart)
### *SIM Akreditasi RS MonsisKami*

---

## 1. Akses Sistem
Buka peramban internet (Google Chrome, Mozilla Firefox, atau Microsoft Edge) dan ketik alamat:
👉 **[https://sim-akreditasi-django.vercel.app](https://sim-akreditasi-django.vercel.app)**

Halaman login resmi **RS MonsisKami** akan tampil dengan nuansa warna Putih & Hijau Teal (#0d9488).

---

## 2. Akun Demo Berdasarkan Peran (Role-Based Access)

Sistem telah dilengkapi dengan 13 jenis akun percontohan sesuai struktur tata kelola rumah sakit tipe B:

| No | Username | Role / Jabatan | Peruntukan & Hak Akses Utama | Password Standar |
|:--:|---|---|---|---|
| 1 | `admin` | **Super Administrator** | Akses penuh ke seluruh fitur, setting RS & data master | `admin123` |
| 2 | `admin.mutu` | **Admin Mutu / Komite Mutu** | Monitoring matriks PDCA, laporan risiko & scoring RS | `Mutu@1234` |
| 3 | `koord.tkrs` | **Koordinator Pokja TKRS** | Mengelola dokumen & EP Pokja Tata Kelola RS | `Tkrs@1234` |
| 4 | `koord.pmkp` | **Koordinator Pokja PMKP** | Mengelola dokumen Mutu & Keselamatan Pasien | `Pmkp@1234` |
| 5 | `koord.kps` | **Koordinator Pokja KPS** | Mengelola Kualifikasi & Pendidikan Staf (Nakes) | `Kps@1234` |
| 6 | `ka.ranap` | **Kepala Ruang Rawat Inap** | Mengisi risiko unit, verifikasi regulasi internal rawat inap | `Ranap@1234` |
| 7 | `ka.farmasi` | **Kepala Instalasi Farmasi** | Mengelola bukti regulasi obat LASA, high alert & risiko depo | `Farmasi@1234` |
| 8 | `ka.lab` | **Kepala Laboratorium** | Mengunggah bukti PMI/PME & kalibrasi alat lab | `Lab@1234` |
| 9 | `perawat.igd` | **Perawat Pelaksana (IGD)** | *Smart Redirect* ke Portal Portofolio Nakes (STR, SIP, SIK) | `Perawat@1234` |
| 10 | `dokter.spesialis` | **Dokter Spesialis (KSM)** | *Smart Redirect* ke Portal Nakes (SPK, RKK, Ijazah) | `Dokter@1234` |
| 11 | `apoteker.farmasi` | **Apoteker Klinis** | *Smart Redirect* ke Portal Nakes & bukti kredensial | `Apoteker@1234` |
| 12 | `analis.lab` | **Analis Kesehatan** | *Smart Redirect* ke Portal Nakes & sertifikat kompetensi | `Analis@1234` |
| 13 | `asesor.kars` | **Asesor / Surveior KARS** | Hak baca/review matriks PDCA & pemberian skor simulasi | `Asesor@1234` |

> 🔒 **Catatan Keamanan:** Untuk penggunaan riil pegawai rumah sakit, kata sandi wajib segera diperbarui melalui menu **Profil Saya** di sudut kanan atas.

---

## 3. Fitur Smart Redirect (Kenyamanan Pengguna)
- Jika staf login dengan role **Tenaga Kesehatan (Dokter, Perawat, Bidan, Apoteker, Analis)**, sistem akan secara otomatis mengarahkan layar langsung ke **Portal Portofolio Nakes** (`/portal-nakes/`), sehingga staf tidak bingung mencari menu upload berkas STR/SIP mereka.
- Jika pengguna login sebagai **Direksi, Koordinator Pokja, atau Admin**, layar langsung menampilkan **Dashboard Eksekutif** dengan rangkuman capaian RS MonsisKami.

---

## 4. Navigasi Antarmuka (Sidebar)
Sidebar kiri dikelompokkan per tugas, bukan per modul teknis:

- **Dashboard:** satu angka kesiapan (capaian rata-rata), distribusi EP tercapai / dalam proses / belum ada bukti, lalu capaian per pokja diurutkan dari yang terendah. Pohon struktur organisasi tidak lagi ada di sini; gunakan menu **Hierarki unit**.
- **Akreditasi:** Matriks PDCA, Elemen Penilaian, Dokumen Bukti, dan daftar 16 bab STARKES yang bisa dicari.
- **Risiko dan insiden:** daftar risiko, input risiko, Perencanaan (Plan), Pelaksanaan (Do), Monitoring dan evaluasi, Laporan PDCA lengkap, Laporan manajemen risiko, FMEA dan RCA, register insiden, lapor insiden.
- **Mutu dan kinerja:** Indikator mutu, Laporan Mutu, Logbook harian.
- **Laporan:** Auto-scoring, Rekap capaian, Ekspor Excel.
- **Data induk dan Pengaturan:** Pokja dan standar, unit kerja, hierarki unit, pengguna, profil RS, log sistem.

Setiap item menu memakai nama pendek satu baris. Keterangan panjang muncul sebagai tooltip saat kursor berhenti di atas item.
