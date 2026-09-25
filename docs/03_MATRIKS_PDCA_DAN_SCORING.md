# 📊 Matriks PDCA & Auto-Scoring Akreditasi KARS
### *SIM Akreditasi RS MonsisKami — Panduan Operasional Matriks 7 Kolom STARKES*

---

## Apa Itu Matriks PDCA?

**Matriks PDCA** adalah inti dari sistem pencatatan akreditasi. Setiap Elemen Penilaian (EP) dikelola melalui siklus **Plan → Do → Check → Action** yang memenuhi standar evaluasi KARS dan Kemenkes.

Tampilan matriks memiliki **7 Kolom Utama**:

| Kolom | Nama | Fungsi |
|:---:|---|---|
| 1 | **EP / Kode** | Kode dan deskripsi Elemen Penilaian dari standar STARKES |
| 2 | **PLAN (Regulasi & Rencana)** | Kebijakan, SPO, dan Rencana Kerja Anggaran (RKA) |
| 3 | **DO (Pelaksanaan)** | Bukti pelaksanaan kegiatan/program di unit kerja |
| 4 | **CHECK (Pemantauan)** | Hasil audit, monitoring, dan capaian indikator mutu |
| 5 | **ACTION (Tindak Lanjut)** | Rencana perbaikan (CPAR / RTL / RTM) berdasarkan temuan |
| 6 | **Bukti RDWOS** | Upload berkas regulasi, dokumen, foto, video, laporan |
| 7 | **Skor EP** | Penilaian 0 / 5 / 10 untuk setiap EP (Tercapai/Sebagian/Tidak) |

---

## Cara Mengisi Matriks PDCA

### Melalui Tabel Utama:
1. Buka menu **Matriks PDCA** dari sidebar kiri.
2. Pilih **Pokja** dari dropdown (misal: PMKP, TKRS, MFK, KPS, dst).
3. Pilih **Standar** dalam pokja tersebut.
4. Kolom PLAN / DO / CHECK / ACTION dapat langsung diklik untuk mengedit teks secara **inline (tanpa berpindah halaman)**.
5. Kolom **Skor EP** memiliki dropdown dengan pilihan:
   - `10` → **Tercapai Penuh** (Skor 10)
   - `5` → **Tercapai Sebagian** (Skor 5)
   - `0` → **Tidak Tercapai** (Skor 0)
6. Sistem menyimpan perubahan secara otomatis via AJAX (tanpa perlu klik "Simpan" manual).

---

## Auto-Scoring: Simulasi Nilai Akreditasi KARS

### Akses Auto-Scoring:
- Buka menu **Rekap → Auto-Scoring** di sidebar kiri.

### Cara Membaca Hasil Auto-Scoring:

Setiap Pokja dihitung dengan formula:

```
Skor Kepatuhan (%) = (Total skor EP yang terisi) ÷ (Skor maksimal mungkin) × 100%
```

Kategori hasil berdasarkan standar KARS:

| Kategori | Ambang Batas | Ikon |
|---|:---:|---|
| ⭐⭐⭐⭐ **Paripurna** | ≥ 80% | Status akreditasi tertinggi |
| ⭐⭐⭐ **Utama** | ≥ 60% | Status akreditasi utama |
| ⭐⭐ **Madya** | ≥ 40% | Status akreditasi madya |
| ⭐ **Dasar** | ≥ 20% | Status akreditasi dasar |
| ❌ **Tidak Terakreditasi** | < 20% | Belum memenuhi syarat minimum |

> 🎯 **Tips:** Pokja dengan skor rendah ditampilkan di atas daftar sehingga bisa diprioritaskan pengisian dokumennya.

---

## Cetak Dokumen Akreditasi (PDF Resmi)

Dokumen cetak akreditasi resmi ber-kop **RS MonsisKami** dapat dihasilkan dengan cara:

1. Buka menu **Rekap → Cetak Dokumen** di sidebar kiri, **ATAU** klik tombol 🖨️ **Cetak** dari halaman Auto-Scoring.
2. Pilih **Pokja** yang ingin dicetak.
3. Klik tombol **🖨️ Cetak Dokumen Resmi**.
4. Browser akan membuka tampilan cetak — Pilih **Simpan sebagai PDF** atau kirim langsung ke printer.

Dokumen cetak otomatis menampilkan:
- Kop RS MonsisKami (Nama RS, Tipe, Tahun Akreditasi)
- Tabel Elemen Penilaian beserta Skor dan Status (✅ / ⚠️ / ❌)
- Tanggal & Waktu Cetak Otomatis
- Halaman bersih tanpa sidebar / menu (otomatis via CSS `@media print`)
