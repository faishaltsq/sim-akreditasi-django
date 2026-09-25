# 🛡️ Manajemen Risiko & Pelaporan Insiden Keselamatan Pasien
### *SIM Akreditasi RS MonsisKami — Risk Register 5×5 & Lapor Insiden Anonim*

---

## Modul 1: Manajemen Risiko Unit Kerja (Risk Register 5×5)

### Apa Tujuannya?
Mengidentifikasi, menganalisis, dan memitigasi seluruh potensi risiko di unit kerja rumah sakit (Klinis, Operasional, Finansial, Fasilitas/K3RS, IT, Reputasi) menggunakan standar **Matriks 5×5 Kemenkes/KARS**.

### Cara Input Risiko Baru:
1. Masuk ke menu **Manajemen Risiko → Tambah Risiko Baru** (`/risiko/baru/`).
2. Isi formulir:
   - **Unit Kerja:** Pilih unit kerja anda (misal: Instalasi Farmasi, IGD, ICU, dll).
   - **Kategori Risiko:** Klinis / Operasional / Finansial / Fasilitas-K3RS / IT / Reputasi.
   - **Deskripsi Kejadian / Potensi Risiko:** Jelaskan kejadian risiko yang mungkin timbul.
   - **Penyebab (Root Cause):** Apa yang menyebabkan risiko ini berpotensi terjadi?
   - **Dampak (Severity 1–5):** Geser slider dampak:
     - 1 = Tidak Signifikan
     - 2 = Minor
     - 3 = Moderat
     - 4 = Mayor
     - 5 = Katastropik
   - **Probabilitas (Likelihood 1–5):** Geser slider peluang kejadian:
     - 1 = Sangat Jarang
     - 2 = Jarang
     - 3 = Mungkin
     - 4 = Sering
     - 5 = Sangat Sering
3. **Skor Matriks Terhitung Otomatis:**
   ```
   Skor Risiko = Dampak × Probabilitas (Nilai 1 sampai 25)
   ```
   - 🟩 **Rendah (1–3)**: Penanganan rutin di tingkat staf
   - 🟦 **Sedang (4–9)**: Pengawasan oleh Kepala Unit
   - 🟨 **Tinggi (10–14)**: Memerlukan Rencana Tindakan Tertulis
   - 🟥 **Ekstrem (15–25)**: Perhatian langsung Direksi & Komite Mutu
4. Isi **Rencana Pengendalian (Plan):** Tindakan pencegahan yang akan dilakukan.
5. Klik **Simpan Risiko**.

---

## Modul 2: Evaluasi Residual Risk & PDCA Risiko

Setelah rencana mitigasi diterapkan, unit kerja melakukan **evaluasi risiko residual**:

1. Masuk ke **Manajemen Risiko → Daftar Risiko** (`/risiko/`).
2. Klik tombol **🔍 Detail & Evaluasi** pada baris risiko yang ingin dievaluasi.
3. Klik tab **Evaluasi & Residual Risk**.
4. Masukkan:
   - **Dampak Residual (1–5)** dan **Probabilitas Residual (1–5)** setelah mitigasi berjalan.
   - **Catatan Evaluasi / Bukti Perbaikan.**
   - **Status:** Direncanakan / Sedang Dijalankan / Efektif / Ditutup.
5. Klik **Simpan Evaluasi**.

---

## Modul 3: Pelaporan Insiden Keselamatan Pasien (Anonim)

### Prinsip "Just Culture" & Non-Punitive
Sistem mendukung **budaya keselamatan non-menghukum**. Siapapun staf di RS MonsisKami (perawat, dokter, farmasi, cleaning service, administrasi) dapat melaporkan insiden tanpa rasa takut karena **kolom identitas pelapor bersifat opsional (dapat dikosongkan/anonim)**.

### Jenis Insiden:

| Jenis Insiden | Singkatan | Definisi | Contoh |
|---|:---:|---|---|
| **Kejadian Nyaris Celaka** | **KNC** | Terjadi kesalahan, tapi belum sampai mengenai pasien | Salah ambil obat di farmasi, tapi ketahuan saat double-check sebelum diberikan |
| **Kejadian Tidak Cedera** | **KTC** | Sudah mengenai pasien, tetapi tidak timbul cedera | Pasien diberi obat yang salah, tapi obat tersebut bukan racun & pasien tidak ada efek samping |
| **Kondisi Potensial Cedera** | **KPC** | Kondisi yang sangat berpotensi menimbulkan cedera | Bed rails tempat tidur patah, lantai licin tanpa penanda |
| **Kejadian Tidak Diharapkan** | **KTD** | Insiden yang mengakibatkan cedera pada pasien | Pasien jatuh dari tempat tidur hingga memar |
| **Kejadian Sentinel** | **Sentinel** | Kejadian yang mengakibatkan kematian atau cedera permanen | Operasi salah sisi organ, kematian pasien yang tidak terduga |

### Cara Melaporkan Insiden:
1. Buka menu **Pelaporan Insiden** (`/insiden/lapor/`).
2. Isi formulir:
   - **Tanggal & Waktu Kejadian**
   - **Unit Tempat Kejadian**
   - **Jenis Insiden:** KNC / KTC / KPC / KTD / Sentinel
   - **Deskripsi Kronologi Kejadian Singkat**
   - **Tindakan Awal yang Sudah Dilakukan**
   - **Tingkat Keparahan (Severity Scale):** Derajat 1 s.d. 5
   - *(Opsional)* Nama Pelapor & No HP — **Kosongkan jika ingin melapor secara anonim!**
3. Klik **Kirim Laporan Insiden**.
4. Laporan langsung masuk ke dashboard **Komite Mutu & Keselamatan Pasien (KMKP)** untuk ditindaklanjuti dengan investigasi sederhana atau Root Cause Analysis (RCA).
