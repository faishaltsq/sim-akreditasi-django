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

### Struktur Hierarki 3 Tingkat:
- **Level 1 (Pimpinan / Pemilik / Dewas / Direksi Utama):** Unit tingkat teratas tanpa induk (*parent*).
- **Level 2 (Direktorat / Komite / SPI / Bidang):** Unit koordinasi dan penunjang langsung di bawah Direksi.
- **Level 3 (Instalasi / KSM / Ruangan / Depo Pelayanan):** Unit kerja operasional tempat pelaksanaan SPO dan pelayanan pasien.

---

### Cara Menambahkan Sub-Unit Kerja di Bawah Level Tertentu:

#### ⚡ Cara Cepat (Rekomendasi — Melalui Pohon Struktur):
1. Buka menu **Unit Kerja** &rarr; **Pohon Hierarki** (`/unit/hierarki/`).
2. Temukan unit induk yang ingin ditambahkan anaknya (misal: ingin menambah depo baru di bawah *Instalasi Farmasi* atau ruang perawatan baru di bawah *Rawat Inap*).
3. Klik tombol hijau **`+ Tambah Sub-Unit (L2)`** atau **`+ Tambah Sub-Unit (L3)`** yang terletak tepat di baris unit tersebut.
4. Modal cepat akan terbuka dengan **Induk Unit Kerja otomatis terisi**:
   - Sistem secara cerdas menghitung tingkatan target (misal: jika induk Level 2, maka unit baru otomatis Level 3).
   - Masukkan **Nama Unit Kerja** (misal: "Depo Farmasi IGD").
   - Masukkan **Kode Unit** (misal: "DEPO-IGD").
   - Masukkan **Penanggung Jawab (PIC)** & **Keterangan**.
5. Klik **Simpan Unit Kerja**. Unit baru langsung muncul di bawah induknya dalam pohon organisasi!

#### 📝 Cara Manual (Melalui Form Unit Kerja):
1. Buka menu **Unit Kerja** &rarr; **Tambah Unit** (`/unit/`).
2. Pada dropdown **Induk Unit Kerja**:
   - Jika dikosongkan &rarr; Unit otomatis tersimpan sebagai **Level 1** (Puncak).
   - Jika memilih unit Level 1 &rarr; Unit otomatis tersimpan sebagai **Level 2**.
   - Jika memilih unit Level 2 &rarr; Unit otomatis tersimpan sebagai **Level 3**.
3. Klik **Simpan Unit Kerja**.

---

### Fitur Pencarian & Filter Tingkat Unit:
Di halaman `/unit/hierarki/`, pengguna dapat:
- Mengetik kode/nama unit di kolom pencarian **🔍 Cari unit...** untuk menemukan unit secara instan tanpa reload halaman.
- Mengklik tombol filter **Semua / L1 / L2 / L3** untuk memfilter pohon berdasarkan tingkat hierarki.

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
