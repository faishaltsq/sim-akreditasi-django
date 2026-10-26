# Pemeriksaan STARKES 2024 pada Database Produksi ARIMA

**Tanggal pemeriksaan:** 24 Oktober 2026.  
**Web diperiksa:** https://sim-akreditasi-django.vercel.app/  
**Database remote yang diperiksa:** proyek Supabase `sim-akreditasi`, ref `gwaeuzbbdawbekrmrvfd`.  
**Metode:** HTTP publik, query SELECT katalog remote, perbandingan digest kode+teks per bab terhadap hasil parser PDF, dan pemeriksaan teks asli pada halaman contoh. Tidak ada perubahan database, impor, migrasi, atau deployment.

## Kesimpulan

**Database produksi sudah mengaktifkan STARKES 2024, tetapi hasil ekstraksi belum sepenuhnya utuh dan bersih sesuai PDF.**

Framework aktif ID 5 bernama `STARKES Edisi 2024 / KMK HK.01.07/MENKES/1596/2024`, versi `2024`, dengan 16 bab dan 794 EP. Kode serta teks 794 EP yang tersimpan cocok dengan hasil parser saat ini untuk file PDF pengguna di seluruh 16 bab. Kecocokan dengan parser tidak membuktikan parser mengekstrak seluruh sumber secara benar.

Ini berbeda dari database SQLite lokal yang diperiksa saat penyusunan rencana. Pernyataan sebelumnya tentang katalog lokal yang belum beralih ke 2024 tidak menggambarkan keadaan database produksi.

## Sumber pembanding

- File: `C:/Users/cubeb/Downloads/starkes 2024.pdf`.
- Identitas: KMK HK.01.07/MENKES/1596/2024 tentang Standar Akreditasi Rumah Sakit.
- Jumlah halaman: 356, sesuai pembacaan sumber sebelumnya dalam sesi ini.
- SHA-256 diverifikasi ulang: `22d2247e6a2b272789141536ca4539f99ebb825ad6c7bfe61106d065aa453116`.
- Parser: fungsi `parse_pdf` dan `_extract_ep_items` dari `akreditasi/management/commands/import_instrumen_2024.py`; dijalankan sebagai fungsi ekstraksi saja, tanpa memuat model/settings atau menjalankan impor.

## Katalog aktif — perbandingan seluruh bab

Digest dibentuk dari daftar kode EP terurut dan hash teks deskripsi, kemudian dibandingkan dengan digest yang dihitung langsung oleh PostgreSQL. Pemeriksaan ini tidak hanya membandingkan jumlah baris.

| Bab | EP remote aktif | Cocok dengan hasil parser PDF |
|---|---:|---|
| TKRS | 71 | Ya |
| KPS | 78 | Ya |
| MFK | 68 | Ya |
| PMKP | 45 | Ya |
| MRMIK | 51 | Ya |
| PPI | 60 | Ya |
| AKP | 67 | Ya |
| HPK | 39 | Ya |
| PP | 56 | Ya |
| PAP | 46 | Ya |
| PAB | 37 | Ya |
| PKPO | 53 | Ya |
| KE | 25 | Ya |
| SKP | 27 | Ya |
| PROGNAS | 48 | Ya |
| PPK | 23 | Ya |
| **Total** | **794** | **16 bab cocok** |

Arsip framework ID 4 tidak aktif dan masih memiliki 1.024 EP. Total seluruh EP aktif+arsip adalah 1.818. Angka arsip tidak boleh dicampur ke denominator katalog aktif. Pemeriksaan ini tidak mengklaim bahwa halaman setelah login sudah diuji terhadap pencampuran tersebut.

## Ketidaksesuaian yang ditemukan

### 1. Teks EP terpotong

Terdapat 27 deskripsi katalog aktif yang panjangnya tepat pada batas parser 300 karakter. Contoh yang dikonfirmasi terhadap teks PDF:

- **KPS 10 EP c** pada database berhenti di bagian `elektrokardiogram `.
- **PDF halaman 68** masih melanjutkan kalimat dengan `(EKG), elektroensefalogram (EEG), elektromiogram (EMG), serta pemeriksaan lain yang serupa.`

Akar penyebab: parser memakai pemotongan `[:300]` pada deskripsi. Teks lengkap harus disimpan; pemendekan hanya untuk preview UI.

### 2. Uraian bab berikutnya ikut menjadi deskripsi EP

- **AKP 6 EP d** pada database memasukkan `2. Hak Pasien dan Keterlibatan Keluarga (HPK) Gambara...` setelah kalimat ketentuan transportasi.
- **PDF halaman 228** menunjukkan bagian tersebut adalah judul dan gambaran umum bab HPK, bukan lanjutan EP transportasi.
- Contoh remote lain: **HPK 4.2 EP b** ikut memuat pengantar bab Pengkajian Pasien, dan **KE 7 EP b** ikut memuat pengantar Kelompok Sasaran Keselamatan Pasien.

Akar penyebab: batas akhir blok ekstraksi belum memisahkan setiap judul/bagian berikutnya secara andal.

### 3. Kebutuhan bukti RDWOS belum terisi menyeluruh

Katalog aktif hanya mempunyai dua `EvidenceReq`, pada:

- `PMKP 11 EP f`: R.
- `SKP 6.1 EP 3`: D.

Artinya data standar/EP sudah dipasang, tetapi panduan kebutuhan bukti tidak dapat disebut lengkap. PDF KMK standar dan dokumen instrumen survei adalah sumber berbeda; pengayaan RDWOS harus berasal dari instrumen survei yang ditinjau, bukan menebak jenis bukti dari huruf yang muncul di narasi KMK.

### 4. Label publik belum diperbarui

HTTP GET web mengarah ke halaman login yang berhasil dimuat. Halaman login masih menampilkan `STANDAR STARKES 2026 — RS TIPE B`, bukan identitas edisi 2024. Tahun target/survei dan edisi instrumen seharusnya ditampilkan terpisah.

## Batas verifikasi UI

Halaman internal memerlukan login. Pemeriksaan browser memakai profil tersimpan terhalang karena profil Brave sedang terkunci; browser pengguna tidak ditutup. Koneksi metadata deployment Vercel juga belum tersedia. Karena itu tidak ada klaim tentang tampilan halaman internal, commit deployment aktif, atau verifikasi end-to-end setelah login. Katalog aktif dan contoh ketidaksesuaian di atas berasal dari SELECT langsung pada database remote proyek `sim-akreditasi`, bukan snapshot SQLite lokal.

## Tindak lanjut yang sesuai

1. Pertahankan framework 2024 aktif dan arsip lama; jangan menjalankan impor ulang destruktif atau mereset skor.
2. Perbaiki ekstraksi teks penuh dan batas antar-EP/bab; tinjau perbedaan terhadap PDF sebelum pembaruan data.
3. Susun artefak sumber terversi dan lakukan pembaruan deskripsi terkontrol dengan menjaga PK, skor, catatan, dan tautan bukti.
4. Lengkapi RDWOS dari instrumen survei yang sesuai, dengan provenance dan review pemilik akreditasi.
5. Pisahkan label `Edisi instrumen: 2024` dari tahun target akreditasi; verifikasi halaman internal ketika sesi browser tersedia.

**Status akhir:** sudah beralih ke katalog 2024 di database produksi; belum tepat menyatakan seluruh isi sudah bersih, lengkap, dan sepenuhnya sesuai PDF.
