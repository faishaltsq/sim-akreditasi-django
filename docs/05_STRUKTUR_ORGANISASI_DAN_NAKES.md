# 🏢 Struktur Organisasi RS Tipe B & Portal Nakes
### *SIM Akreditasi RS MonsisKami — 65 Unit Kerja, 14 KSM, dan Portofolio Kredensial Nakes*

---

## 1. Struktur Organisasi RS MonsisKami (Visualisasi Pohon)

Di **Dashboard** utama, Anda dapat melihat **Pohon Struktur Organisasi** yang menampilkan hierarki 4 level seluruh unit kerja RS MonsisKami Tipe B:

### Hierarki Organisasi:

```
PEMILIK RS
  └── DEWAN PENGAWAS (DEWAS)
        ├── Sekretariat Dewas
        ├── Sub Komite Audit Operasional
        └── Sub Komite Audit Medis
  └── DIREKTUR UTAMA
        ├── SATUAN PENGAWAS INTERNAL (SPI)
        ├── KOMITE-KOMITE RS
        │     ├── Komite Medis
        │     ├── Komite Keperawatan
        │     ├── Komite Mutu (PMKP)
        │     ├── Komite PPI
        │     ├── Komite Etik & Hukum
        │     └── Komite Farmasi & Terapi
        ├── DIREKTORAT MEDIS
        │     ├── IGD
        │     ├── Rawat Jalan
        │     ├── Rawat Inap
        │     ├── ICU / HCU
        │     ├── NICU / PICU
        │     ├── Kamar Operasi / Bedah Sentral
        │     ├── Hemodialisis
        │     ├── Rehabilitasi Medik
        │     └── 14 Kelompok Staf Medis (KSM):
        │           KSM Penyakit Dalam, Bedah, Anak, Obsgin, Anestesi,
        │           Saraf, Jantung, Mata, THT, Kulit, Ortopedi,
        │           Paru, Radiologi, Patologi Klinik
        ├── DIREKTORAT KEPERAWATAN
        │     └── Bidang Keperawatan & Kebidanan
        ├── DIREKTORAT PENUNJANG & UMUM
        │     ├── Instalasi Farmasi
        │     ├── Laboratorium
        │     ├── Radiologi
        │     ├── Gizi
        │     ├── CSSD / Sterilisasi
        │     ├── Rekam Medik
        │     ├── SIMRS / IT
        │     ├── Laundry & Linen
        │     ├── IPSRS
        │     ├── Ambulans / Transportasi
        │     └── Kesling & K3RS
        ├── DIREKTORAT KEUANGAN & SDM
        │     ├── Keuangan & Akuntansi
        │     ├── SDM / Kepegawaian
        │     ├── Humas & Pemasaran
        │     └── Pengadaan / Logistik
        └── PENDIDIKAN & PENELITIAN (DIKLIT)
              ├── Diklat Staf / SDM
              └── Penelitian & Pengembangan
```

Total **65 Unit Kerja** yang terdaftar dan aktif di database production.

---

## 2. Cara Melihat & Mengelola Unit Kerja

### Daftar Unit Kerja:
1. Buka menu **Unit Kerja** → **Daftar Unit** (`/unit/`).
2. Tabel menampilkan Kode Unit, Nama, Level Hierarki, dan Unit Induk.
3. Klik **Nama Unit** untuk melihat detil unit dan EP terkait pokja.

### Pohon Hierarki:
1. Buka menu **Unit Kerja** → **Pohon Hierarki** (`/unit/hierarki/`).
2. Tampilkan seluruh struktur dalam format *tree view* interaktif.

---

## 3. Portal Portofolio Nakes (Tenaga Kesehatan)

### Tujuan:
Portal ini menyediakan tempat bagi setiap tenaga kesehatan (Dokter, Perawat, Bidan, Apoteker, Analis, dll.) untuk mengunggah dan mengelola berkas kredensial profesional mereka, seperti yang diwajibkan Pokja **KPS (Kualifikasi dan Pendidikan Staf)**.

### Jenis Berkas yang Dikelola:

| Berkas | Singkatan | Keterangan |
|---|---|---|
| **Surat Tanda Registrasi** | STR | Bukti registrasi profesi dari Konsil Kedokteran / Tenaga Kesehatan |
| **Surat Izin Praktik** | SIP | Izin praktik di fasilitas kesehatan tertentu |
| **Surat Izin Kerja** | SIK | Izin kerja bagi nakes non-dokter (Perawat, Bidan, dll.) |
| **Surat Penugasan Klinis** | SPK | Penugasan klinis oleh Direktur RS berdasarkan kewenangan |
| **Rincian Kewenangan Klinis** | RKK | Daftar tindakan medis yang dapat dilakukan oleh nakes |
| **Ijazah** | — | Bukti pendidikan terakhir profesi |
| **Sertifikat Kompetensi** | — | Bukti pelatihan (BLS, ACLS, ATLS, PPI, K3RS, dll.) |

### Cara Upload Berkas Portofolio:
1. Login dengan akun Nakes (misal: `perawat.igd`). Sistem otomatis mengarahkan ke **/portal-nakes/**.
2. Di portal, klik **Upload Berkas** untuk setiap jenis dokumen (STR, SIP, Ijazah, Sertifikat, dll.).
3. Pilih jenis berkas, unggah file (PDF/JPG/PNG), dan isi nomor serta tanggal berlaku.
4. Berkas akan tersimpan di Supabase Cloud Storage dan tercatat di rekap kelengkapan unit kerja.

### Rekap Kelengkapan Staf per Unit:
- Admin/Koordinator dapat membuka menu **Rekap KPS** (`/rekap-kps/`) untuk melihat status kelengkapan berkas seluruh nakes per unit kerja.
