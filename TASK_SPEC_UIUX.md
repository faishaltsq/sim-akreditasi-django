# Spesifikasi UI/UX: SIK AP - Sistem Manajemen Dokumen Akreditasi Rumah Sakit

## 1. Tinjauan Umum & Tujuan
Membangun antarmuka web dashboard admin untuk mengelola dokumen dan skor akreditasi rumah sakit berdasarkan siklus PDCA (Plan-Do-Check-Action). Fokus utama adalah kemudahan penggunaan, kejelasan status kepatuhan, dan efisiensi dalam menghubungkan Elemen Penilaian (EP) dengan bukti dokumen fisik.

## 2. Pengguna & Persona
Admin RS/Koordinator Akreditasi: Pengguna utama. Membutuhkan visibilitas tingkat tinggi (dashboard) dan kemampuan untuk menugaskan, mengunggah, dan memverifikasi dokumen.

## 3. Arsitektur Informasi & Navigasi (Sidebar)
Menu navigasi harus dikelompokkan secara logis.
- **Dashboard Utama**: (Ikon: Chart/Home) Ringkasan status PDCA.
- **Modul Akreditasi (Inti)**:
  - **Ringkasan PDCA**: (Ikon: Cycle/Checklist) Halaman matriks utama.
  - **Elemen Penilaian (EP)**: Daftar terperinci semua EP, dapat difilter berdasarkan Bab/Pokja.
  - **Dokumen Bukti (RDWOS)**: Repositori semua dokumen yang diunggah.
- **Manajemen Data**:
  - **Pokja & Standar**: Manajemen struktur akreditasi.
  - **Unit Kerja**: Daftar unit di RS.
  - **Pengguna**: Manajemen user admin/editor.
- **Laporan**:
  - **Analisis Capaian**: Laporan grafik dan matriks.
  - **Ekspor Data**: (Ikon: Download) Halaman untuk mengunduh Excel/PDF.
- **Pengaturan**:
  - **Profil RS**: Data rumah sakit.
  - **Log Sistem**: Audit trail.

## 4. Desain Halaman Utama (Dashboard)
Halaman ini harus memberikan jawaban instan atas pertanyaan: "Seberapa siap kita?"
- **Judul Halaman**: "Dashboard Akreditasi - [Nama RS]"
- **Header**: Logo RS (kiri), Judul Aplikasi (tengah), Profil Admin & Logout (kanan).
- **Metric Ribbon (KPI Bar)**:
  - Box 1: Capaian Rata-rata: Angka besar (misal: 86.5%) dengan progress bar hijau.
  - Box 2: Total Dokumen: Jumlah dokumen terunggah vs total target (misal: 152/180).
  - Box 3: Evaluasi PDCA: Persentase EP yang sudah masuk tahap Check/Action (misal: 78%).
  - Box 4: Anggaran RKA: Total Anggaran (Rp 1.25 M) dengan rincian Biaya & Non-Biaya.
- **Grafik Inti (Pie Chart)**: "Status Kepatuhan EP" (%). Tampilkan persentase: Tercapai (Hijau), Dalam Proses (Kuning), Belum Ada Bukti (Merah).
- **Tabel "Aktivitas Terkini"**: 5 dokumen yang baru diunggah atau diubah statusnya, beserta nama pengunggah dan waktu.

## 5. Halaman Inti: Matriks PDCA (Detail Per Pokja)
Ini adalah halaman paling kritis untuk dioptimalkan UI/UX-nya.
- **Filter & Kontrol**:
  - Dropdown "Pilih Pokja/Bab": Misal: TKRS.
  - Dropdown "Pilih Standar": Misal: TKRS 1.
  - Tombol: "Tambah Bukti Baru" (Hijau), "Ekspor PDF/Excel" (Biru).
- **Matriks Utama (Tabel 7 Kolom)**:
  - Kolom 1: Nomor EP (misal: TKRS 1.1.1)
  - Kolom 2: Elemen Penilaian (Teks lengkap EP)
  - Kolom 3 (Plan): Analisis Risiko/Regulasi.
  - Kolom 4 (Do): Implementasi/SOP/Kebijakan.
  - Kolom 5 (Check): Evaluasi Pelaksanaan/RDWOS.
  - Kolom 6 (Action): Tindak Lanjut/RTL.
  - Kolom 7 (Skor): Dropdown (10, 5, 0) dengan warna latar (Hijau, Kuning, Merah).
- **Interaksi Tabel**:
  - Setiap sel di kolom 3-6 harus dapat diklik untuk mengedit atau menambahkan teks.
  - Setiap sel di kolom 3-6 harus memiliki ikon "Upload/Link Dokumen" (Clip/Upload).
  - Ketika ikon diklik, muncul modal/pop-up "Manajemen Bukti" (lihat #6).
  - **Perubahan Skor (Quick Scoring)**: Dropdown skor harus langsung menyimpan data (AJAX) tanpa reload halaman. Tampilkan indikator "Saving..." kecil di dekat dropdown saat diubah.
  - **Badge RDWOS**: Di dalam sel kolom 3-6, beri badge kecil jika ada dokumen terkait (misal: "1 Dokumen" atau "RDWOS Terkait").

## 6. Modal/Pop-up: Manajemen Bukti Dokumen
Modal ini muncul ketika ikon "Upload/Link Dokumen" diklik.
- **Header Modal**: "Bukti Dokumen untuk: [Nama EP]"
- **Tab Navigation**:
  - **Tab 1: Upload Baru**:
    - Input File (Drag & Drop area).
    - Input Nama Dokumen.
    - Input Tanggal Berlaku.
    - Tombol: "Simpan & Link"
  - **Tab 2: Pilih dari Repositori**:
    - Daftar semua dokumen yang sudah ada di sistem (Searchable).
    - Ceklis dokumen yang ingin ditautkan ke EP ini.
    - Tombol: "Link Dokumen Terpilih"
  - **Tab 3: Daftar Terlink**:
    - Tabel kecil berisi daftar dokumen yang sudah tertaut ke EP ini.
    - Tombol "Unlink" (X).

## 7. Desain Tabel Elemen Penilaian (List View)
Alternatif tampilan untuk melihat EP.
- **Filter**: Bab, Standar, Unit Kerja Terkait.
- **Tabel**: Kolom: EP ID, Deskripsi EP, Unit PJ, Status Dokumen (badge), Skor (badge), Terakhir Diperbarui.
- **Aksi**: Ikon Edit, Ikon Detail.

## 8. Spesifikasi Visual & Branding
- **Warna**:
  - Primary: Biru Rumah Sakit (Professional Healthcare Blue).
  - Success: Hijau cerah (untuk kepatuhan 100% / Dokumen Lengkap).
  - Warning: Oranye (untuk kepatuhan 5% / Dokumen Sebagian).
  - Danger: Merah (untuk kepatuhan 0% / Belum Ada Dokumen).
  - Neutral: Abu-abu (untuk background dan teks).
- **Font**: Font sans-serif yang modern dan mudah dibaca (misal: Inter, Roboto, atau Open Sans). Ukuran font harus nyaman untuk membaca data padat di layar.
- **Ikon**: Gunakan set ikon modern (misal: FontAwesome 6, Bootstrap Icons, atau Google Material Icons) yang intuitif. Contoh: Ikon PDCA harus terlihat seperti siklus.
- **Responsif**: Sistem harus bekerja dengan baik di desktop dan tablet.

## Daftar Periksa untuk Designer/AI Agent:
- [ ] Apakah Metric Ribbon di Dashboard sudah mencakup Capaian, Dokumen, Evaluasi, dan Anggaran?
- [ ] Apakah Matriks PDCA memiliki 7 kolom yang jelas?
- [ ] Apakah dropdown skor 10/5/0 mudah diakses dan cepat diubah?
- [ ] Apakah ikon upload dokumen ada di setiap kolom Plan/Do/Check/Action?
- [ ] Apakah Modal Manajemen Bukti memungkinkan upload baru dan pemilihan dokumen lama?
- [ ] Apakah warna status (Hijau/Kuning/Merah) konsisten digunakan di seluruh sistem (Skor dan Badge)?
- [ ] Apakah navigasi sidebar mudah digunakan untuk berpindah antar Pokja/Bab?
