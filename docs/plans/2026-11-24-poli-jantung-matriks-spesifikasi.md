# Matriks Spesifikasi Modul RME Poliklinik Spesialis Jantung & Pembuluh Darah

## 1. Header Dokumen

| Atribut | Nilai |
|---|---|
| Sumber dokumen | `C:/Users/cubeb/Downloads/Modul_RME_Polispesialis_Jantung_ARIMA_v2.1_Lengkap.docx` |
| Judul internal dokumen | SISTEM INFORMASI MANAJEMEN RUMAH SAKIT & AKREDITASI — ARIMA / MODUL RME POLIKLINIK SPESIALIS JANTUNG & PEMBULUH DARAH / Spesifikasi Fungsional 10 Langkah (Lapis 1 & Lapis 2), Sinkronisasi Dasbor Antrean Poli, Integrasi Penunjang 3-Tingkat, CPPT Multiprofesi, Billing Kasir, serta Pemetaan Otomatis EP STARKES 2024 |
| Versi dokumen | v2.1 — "Final Revisi v2.1 (Tersinkronisasi UI ARIMA)" |
| Metadata berkas | `modified` 2026-11-23 11:26, `revision` 8, 180 paragraf, 21 tabel, 1 gambar |
| Tanggal ekstraksi | 2026-11-24 |
| Unit layanan & kode | Poliklinik Spesialis Jantung & Pembuluh Darah (POLI-JANTUNG) |
| Route & endpoint UI | `/pasien/rajal/?poli=Poli Jantung %26 Pembuluh Darah` |
| Standar akreditasi | STARKES 2024 (ARK, PP, HPK, KE, KPS, PMKP, SKP) |
| Arsitektur RME | Navigasi Kiri 10 Langkah + Form Lapis 1 & 2 + Panel Evaluasi |
| Konsultan utama | Dr. Muh. Basirun Al Ummah, M.Kes. (RS Monsiskami) |
| Cakupan matriks | Langkah 1–10 (Lapis 1 & Lapis 2), Katalog Penunjang 3 Tingkat, Deep-link Dasbor Antrean, RBAC, Pemetaan EP STARKES 2024, aturan waktu kritis/SLA, nilai kritis, ambang alert TTV |
| Di luar cakupan | Kode aplikasi, desain basis data, rencana implementasi |

Konvensi ID: `S<n>-L<lapis>-<urut>` (mis. `S4-L1-01`). Kolom "Tipe Kontrol" memakai istilah dokumen sumber (dropdown, input numerik, multi-select, canvas, otomatis/read-only). Tanda `\|` pada kolom opsi adalah pemisah opsi sebagaimana ditulis dokumen sumber.

---

## 2. Matriks Lapis 1 / Lapis 2 per Langkah

### LANGKAH 1. IDENTITAS PASIEN, VALIDASI KEPESERTAAN & PENJAMIN

Lapis 1 — Data Utama Kunjungan (Otomatis & Dropdown). Lapis 2 — Administrasi Rujukan, Bridging BPJS & Kredensial DPJP.

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S1-L1-01 | L1 | No. Rekam Medis (No. RM) | Otomatis / read-only | `misal: 00-45-82-19` | Otomatis dari master pasien; "untuk menjaga riwayat longitudinal dan mencegah duplikasi berkas". | Master pasien |
| S1-L1-02 | L1 | No. Kunjungan Poli | Otomatis / read-only | `misal: RJ-JTG-20261124-0001` | Otomatis per transaksi kunjungan "dengan validasi otomatis terhadap kunjungan poli yang sama pada hari berjalan". | Transaksi registrasi kunjungan; Langkah 1 poli aktif |
| S1-L1-03 | L1 | Identitas Demografis | Otomatis dari pendaftaran + input | Nama Lengkap Pasien; Tanggal Lahir & Usia (terhitung otomatis); Jenis Kelamin; NIK (16 digit tervalidasi); Nomor Telepon aktif; Alamat lengkap | NIK wajib 16 digit tervalidasi; Usia terhitung otomatis; sumber "data pendaftaran". | Master pasien / pendaftaran |
| S1-L1-04 | L1 | Tanggal & Waktu Pemeriksaan | Timestamp otomatis (editable terbatas) | — | **Auto timestamp** saat registrasi poli dibuka; editable "hanya dengan otorisasi Kepala Unit / Rekam Medis dan tercatat di audit log". | Hak otorisasi Kepala Unit / Rekam Medis; audit log |
| S1-L1-05 | L1 | Jenis Kunjungan | Dropdown | Kunjungan Baru \| Kontrol Rutin \| Konsultasi Antar-Poli \| Kunjungan Pasca-Rawat Inap (Kontrol Post-Op/Cath Lab) | Tidak ada aturan tambahan pada sumber. | — |
| S1-L1-06 | L1 | Poliklinik Tujuan | Dropdown (default terkunci) | POLI-JANTUNG — Poliklinik Spesialis Jantung & Pembuluh Darah | "default terkunci ke unit aktif". | Unit aktif login |
| S1-L1-07 | L1 | Penjamin / Cara Bayar | Dropdown | BPJS Kesehatan / JKN \| Asuransi Swasta \| Umum / Tunai \| Perusahaan / Kerja Sama | **Pemicu percabangan tarif**: menentukan skema tarif INA-CBGs (BPJS) vs tarif master RS (Umum/Asuransi) pada Langkah 7 & 9. | Master penjamin; Langkah 7 & 9 (billing) |
| S1-L2-01 | L2 | Asal Rujukan | Dropdown | FKTP / Puskesmas \| IGD \| Rawat Inap / Antar-Poli \| Rujukan RS Lain \| Datang Sendiri | Tidak ada aturan tambahan pada sumber. | — |
| S1-L2-02 | L2 | Status Rujukan / SEP / Surat Kontrol | Dropdown | Aktif & Terverifikasi (terhubung VClaim BPJS) \| Program Rujuk Balik (PRB) \| Perlu Verifikasi Petugas \| Tidak Berlaku (Umum/Tunai) | Opsi "Aktif & Terverifikasi" **terhubung VClaim BPJS** (bridging). | Bridging VClaim BPJS; opsi S1-L1-07 |
| S1-L2-03 | L2 | DPJP / Dokter Spesialis Jantung | Dropdown tervalidasi | `misal: dr. Bambang, Sp.JP, FIHA / dr. [Nama], Sp.JP(K)` | Tervalidasi dari master SDM kredensial aktif KPS dengan format gelar lengkap; **wajib terisi sebelum status antrean berubah menjadi 'Dilayani'**; kolom DPJP "tidak boleh kosong ('-') saat status sudah 'Dilayani'". | Master SDM / KPS; status antrean Dasbor Poli |

### LANGKAH 2. SKRINING AWAL, CARA DATANG & RED FLAGS KARDIOLOGI

Lapis 1 — Triase Visual, Waktu Kritis & Deteksi Tanda Bahaya. Lapis 2 — Karakteristik Onset & Pencetus.

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S2-L1-01 | L1 | Cara Datang | Dropdown | Jalan Kaki Mandiri \| Kursi Roda \| Brankar / Dibantu Petugas | Tidak ada aturan tambahan pada sumber. | — |
| S2-L1-02 | L1 | Skrining Nyeri Dada / Red Flags Kardiovaskular | Dropdown | Tidak Ada Red Flags \| Nyeri Dada Khas Angina (Suspek SKA) \| Sesak Napas Berat / Orthopnea / Edema Paru \| Sinkop / Presinkop \| Palpitasi dengan Hemodinamik Tidak Stabil | **Side effect**: pemilihan "Nyeri Dada Khas Angina" atau "Sesak Napas Berat" otomatis mencatat stempel waktu skrining dan memicu indikator prioritas door-to-ECG <= 10 menit. | S2-L1-03; SLA §7 |
| S2-L1-03 | L1 | Pencatatan Waktu Kritis (Door-to-ECG) | Otomatis / read-only | — | **Auto timestamp** "Jika dipilih Red Flags nyeri dada atau sesak berat, sistem otomatis mencatat timestamp skrining awal dan memunculkan indikator prioritas perekaman EKG <= 10 menit." | S2-L1-02; Langkah 7 (order EKG) |
| S2-L1-04 | L1 | Keputusan Alur Awal | Dropdown | Lanjut Pemeriksaan Poli Jantung \| Rujuk Segera ke IGD (Cito) | **Side effect**: "Pemilihan red flags berat memicu banner peringatan merah dan tombol pintas transfer langsung ke modul IGD." | S2-L1-02; modul IGD |
| S2-L2-01 | L2 | Waktu Onset Gejala Utama | Dropdown | < 30 Menit \| 30 Menit – 6 Jam \| > 6 – 24 Jam \| > 24 Jam – 7 Hari \| > 7 Hari / Kronis | Tidak ada aturan tambahan pada sumber. | — |
| S2-L2-02 | L2 | Pemicu Gejala | Dropdown | Aktivitas Ringan \| Aktivitas Sedang/Berat \| Saat Istirahat \| Stres Emosional / Suhu Dingin \| Tidak Menentu | Tidak ada aturan tambahan pada sumber. | — |

### LANGKAH 3. ANAMNESIS & RIWAYAT KARDIOVASKULAR

Lapis 1 — Keluhan Utama & Karakteristik Nyeri. Lapis 2 — Riwayat Penyakit, Faktor Risiko, Status Khusus, Obat Rutin & Alergi.

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S3-L1-01 | L1 | Keluhan Utama | Dropdown | Nyeri Dada \| Sesak Napas (Dispnea) \| Berdebar-debar (Palpitasi) \| Cepat Lelah / Penurunan Toleransi Aktivitas \| Bengkak pada Tungkai (Edema) \| Pusing / Hampir Pingsan \| Kontrol Rutin / Evaluasi Hasil | Tidak ada aturan tambahan pada sumber. | — |
| S3-L1-02 | L1 | Karakteristik Nyeri Dada | Dropdown | Tidak Ada Nyeri Dada \| Terasa Ditekan / Ditindih / Terikat (Tipikal) \| Terasa Terbakar / Panas \| Nyeri Tajam / Tertusuk \| Rasa Tidak Nyaman / Pegal | Tidak ada aturan tambahan pada sumber. | — |
| S3-L1-03 | L1 | Penjalaran Nyeri | Dropdown | Tidak Menjalar \| Ke Lengan Kiri \| Ke Kedua Lengan \| Ke Rahang / Leher \| Ke Punggung / Ulu Hati | Tidak ada aturan tambahan pada sumber. | — |
| S3-L2-01 | L2 | Riwayat Penyakit Jantung Sebelumnya | Multi-select Dropdown | Tidak Ada \| Penyakit Jantung Koroner (PJK / CAD) \| Riwayat PCI / Stent / CABG \| Gagal Jantung (HF) \| Aritmia / Fibrilasi Atrium (AF) \| Penyakit Katup Jantung \| Penyakit Jantung Bawaan | Tidak ada aturan tambahan pada sumber. | — |
| S3-L2-02 | L2 | Faktor Risiko Kardiovaskular | Multi-select Dropdown | Hipertensi \| Diabetes Melitus \| Dislipidemia \| Riwayat Keluarga Penyakit Jantung Dini \| Obesitas | Tidak ada aturan tambahan pada sumber. | — |
| S3-L2-03 | L2 | Status Merokok | Dropdown + input numerik | Tidak Pernah Merokok \| Mantan Perokok \| Perokok Aktif | **Auto-komputasi**: input "estimasi batang/hari dan lama merokok untuk kalkulasi Indeks Brinkman". Formula Indeks Brinkman **tidak dituliskan** pada sumber (lihat §10, AMBIGU-03). | S3-L2-02 |
| S3-L2-04 | L2 | Skrining Status Kehamilan & Menyusui (Khusus Pasien Wanita Usia Subur) | Dropdown | Tidak Berlaku \| Tidak Hamil / Tidak Menyusui \| Hamil (Trimester I/II/III) \| Menyusui | **Side effect**: "memicu peringatan interaksi obat kontraindikasi kehamilan (ACEi, ARB, ARNI, Statin, Warfarin)". | Jenis kelamin & usia (S1-L1-03); e-Resep Langkah 8/9 |
| S3-L2-05 | L2 | Riwayat Obat Rutin Kardiovaskular (Rekonsiliasi Obat) | Dropdown + daftar obat | Ada & Patuh \| Ada & Tidak Patuh \| Tidak Ada \| Tidak Tahu | Dilengkapi kolom daftar obat rutin (Antiplatelet, Antikoagulan, Nitrat, Antihipertensi, Obat Gagal Jantung, Statin) dan waktu konsumsi dosis terakhir. | Master formularium; Langkah 8 (e-Resep) |
| S3-L2-06 | L2 | Riwayat Alergi Obat / Zat Kontras | Dropdown + input wajib | Tidak Ada Alergi \| Alergi Obat \| Alergi Zat Kontras \| Alergi Makanan/Lainnya | **Wajib** mengisi nama zat dan jenis reaksi alergi bila memilih 'Alergi'; **side effect**: "memunculkan badge alergi merah permanen di header pasien & baris antrean". | Header pasien; Dasbor Antrean (indikator keselamatan) |

### LANGKAH 4. TANDA-TANDA VITAL (TTV), MAP & ANTROPOMETRI

Lapis 1 — Parameter Hemodinamik Utama & Alert Nilai Ekstrem. Lapis 2 — Antropometri & Skala Nyeri.

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S4-L1-01 | L1 | Tekanan Darah (mmHg) Sistolik & Diastolik | Input numerik | — | **Auto-komputasi MAP**: `MAP = [Sistolik + 2 x Diastolik] / 3`. **Indikator warna otomatis**: rentang normal, hipertensi derajat 1–2, krisis hipertensi (>= 180/120 mmHg), atau hipotensi (Sistolik < 90 mmHg). | §9b ambang klasifikasi |
| S4-L1-02 | L1 | Frekuensi Nadi (bpm) | Input numerik | — | **Alert**: takikardia (> 100 bpm) / bradikardia (< 50 bpm). | §9 |
| S4-L1-03 | L1 | Irama Nadi | Dropdown | Teratur (Reguler) \| Tidak Teratur (Ireguler) \| Sulit Dinilai | Tidak ada aturan tambahan pada sumber. | S4-L1-02 |
| S4-L1-04 | L1 | Frekuensi Napas / RR (x/menit) | Input numerik | — | Tidak ada ambang alert yang ditetapkan pada sumber. | — |
| S4-L1-05 | L1 | Saturasi Oksigen / SpO2 (%) | Input numerik | — | **Alert hipoksia**: < 92%. | §9 |
| S4-L1-06 | L1 | Suhu Tubuh (°C) | Input numerik | — | Tidak ada ambang alert yang ditetapkan pada sumber. | — |
| S4-L2-01 | L2 | Berat Badan (kg) & Tinggi Badan (cm) | Input numerik | — | **Auto-komputasi IMT** + perbandingan selisih berat badan dengan kunjungan sebelumnya "(mendeteksi retensi cairan akut pada pasien gagal jantung)". | Riwayat kunjungan; S4-L2-02 |
| S4-L2-02 | L2 | Kategori IMT (Klasifikasi Asia-Pasifik) | Otomatis (read-only) | Underweight (< 18,5) \| Normal (18,5 – 22,9) \| Overweight / Berisiko (23,0 – 24,9) \| Obesitas I (25,0 – 29,9) \| Obesitas II (>= 30,0) | "Terisi otomatis" dari IMT. | S4-L2-01 |
| S4-L2-03 | L2 | Skala Nyeri (NRS 0–10) | Dropdown | 0 (Tidak Nyeri) \| 1–3 (Nyeri Ringan) \| 4–6 (Nyeri Sedang) \| 7–10 (Nyeri Berat) | **Side effect**: "Skor >= 4 otomatis membuka kolom asesmen nyeri komprehensif (PQRST) dan rencana evaluasi ulang." | §9; form PQRST |

### LANGKAH 5. ASESMEN BIOPSIKOSOSIAL, SPIRITUAL & SKRINING

Lapis 1 — Skrining Keselamatan & Nutrisi. Lapis 2 — Aspek Psikologis, Sosial & Spiritual.

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S5-L1-01 | L1 | Skrining Risiko Jatuh (Get Up & Go / Morse Fall Scale) | Dropdown | Tidak Berisiko (Rendah) \| Risiko Sedang \| Risiko Tinggi | **Side effect**: Risiko Tinggi "otomatis menampilkan instruksi pemasangan penanda/pita kuning risiko jatuh dan edukasi pencegahan jatuh". Skor numerik Morse/Get Up & Go tidak ditetapkan (AMBIGU-08). | — |
| S5-L1-02 | L1 | Status Fungsional / Kemandirian | Dropdown | Mandiri \| Ketergantungan Ringan \| Ketergantungan Sedang/Berat | Tidak ada aturan tambahan pada sumber. | — |
| S5-L1-03 | L1 | Skrining Gizi Awal (MST) | Dropdown | Tidak Berisiko Malnutrisi \| Berisiko Malnutrisi | **Side effect**: "Berisiko Malnutrisi (memicu rekomendasi konsultasi Nutrisionis/Dietisien)". Skor MST tidak ditetapkan (AMBIGU-08). | Peran Gizi/Nutrisionis |
| S5-L2-01 | L2 | Kondisi Psikologis / Kecemasan | Dropdown | Tenang / Kooperatif \| Cemas Ringan–Sedang \| Cemas Berat / Panik \| Depresi / Menarik Diri | Tidak ada aturan tambahan pada sumber. | — |
| S5-L2-02 | L2 | Dukungan Sosial & Keluarga | Dropdown | Dukungan Keluarga Baik \| Dukungan Terbatas \| Tinggal Sendiri / Tanpa Pendamping | Tidak ada aturan tambahan pada sumber. | — |
| S5-L2-03 | L2 | Kebutuhan Spiritual / Nilai Budaya Khusus | Dropdown + kolom keterangan | Tidak Ada Kebutuhan Khusus \| Ada Kebutuhan Khusus | Dilengkapi kolom keterangan pendampingan rohani/budaya — "terhubung langsung ke EP HPK STARKES". | §6 (HPK) |

### LANGKAH 6. PEMERIKSAAN FISIK KARDIOVASKULAR & SISTEMIK

Lapis 1 — Pemeriksaan Inti & Anatomi Visual Jantung. Lapis 2 — Status Volume, Vaskular Perifer & Diagram Ekstremitas.

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S6-L1-01 | L1 | Keadaan Umum & Kesadaran | Dropdown + skor | Compos Mentis — Tampak Baik \| Compos Mentis — Tampak Sakit Ringan \| Tampak Sakit Sedang \| Tampak Sakit Berat | "dilengkapi skor GCS bila diperlukan". | — |
| S6-L1-02 | L1 | Inspeksi & Palpasi Prekordial (Iktus Kordis) | Dropdown | Iktus Kordis Normal (ICS V LMC Sinistra) \| Bergeser ke Lateral/Kaudo-Lateral (Kardiomegali) \| Tidak Teraba / Heaving | Tidak ada aturan tambahan pada sumber. | — |
| S6-L1-03 | L1 | Bunyi Jantung (BJ I & BJ II) & Bunyi Tambahan | Dropdown + sub-input | BJ I–II Reguler, Murmur (-), Gallop (-) \| BJ I–II Reguler dengan Murmur \| BJ I–II Reguler dengan Gallop (S3/S4) \| Irama Ireguler | Opsi Murmur "dilengkapi pilihan derajat 1/6–6/6 & lokasi katup". | S4-L1-03 |
| S6-L1-04 | L1 | Bunyi Napas Paru | Dropdown | Vesikuler Normal Kanan/Kiri \| Ronki Basah Halus Basal (Rales) \| Ronki Basah Luas \| Wheezing / Lainnya | Tidak ada aturan tambahan pada sumber. | — |
| S6-L1-05 | L1 | Diagram Anatomi Jantung Interaktif | Canvas | — | Zoom In/Out, penanda titik/lokasi (iktus kordis, area murmur katup), anotasi teks singkat "yang tersimpan ke RME". | S6-L1-02, S6-L1-03 |
| S6-L2-01 | L2 | Tekanan Vena Jugularis (JVP) | Dropdown | Tidak Meningkat (5 + 0 s.d. 2 cmH2O) \| Meningkat (5 + >= 3 cmH2O) | Nilai baku v2.1 (menggantikan "Meningkat (5 + 2 cmH2O)" pada draf v2.0). | — |
| S6-L2-02 | L2 | Edema Ekstremitas Bawah / Sakral | Dropdown | Tidak Ada Edema \| Edema Pretibial Ringan (+1/+2) \| Edema Tungkai Jelas (+3/+4) / Anasarka | Tidak ada aturan tambahan pada sumber. | — |
| S6-L2-03 | L2 | Diagram Ekstremitas Kanan-Kiri Interaktif | Canvas | — | Zoom In/Out, penanda area edema/pulsasi/iskemia perifer, label teks. | S6-L2-02, S6-L2-04 |
| S6-L2-04 | L2 | Perfusi & Pulsasi Perifer | Dropdown | Akral Hangat, CRT < 2 detik, Pulsasi Kuat \| Akral Dingin / CRT >= 3 detik / Pulsasi Melemah | Tidak ada aturan tambahan pada sumber. | — |

### LANGKAH 7. PEMERIKSAAN PENUNJANG, ORDER 3-TINGKAT & NILAI KRITIS

Lapis 1 — Ringkasan Hasil Penunjang Utama & Alert Nilai Kritis. Lapis 2 — Katalog Master Order Penunjang Kardiovaskular (Hierarki Level 1 -> 2 -> 3).

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S7-L1-01 | L1 | EKG 12-Sadapan — Status Pemeriksaan | Dropdown | Belum Diorder \| Diorder / Menunggu \| Selesai Terbaca \| Dibatalkan | Dipisahkan tegas dari Interpretasi Klinis; timestamp order & terima hasil. | S2-L1-03 (door-to-ECG) |
| S7-L1-02 | L1 | EKG 12-Sadapan — Interpretasi Klinis | Dropdown + kolom kesimpulan + unggah | Sinus Rhythm Normal \| Sinus Takikardia / Bradikardia \| Atrial Fibrilasi (AF) \| Iskemia / Infark (ST-T Changes / Q Patologis) \| Hipertrofi Ventrikel / BBB | Dilengkapi kolom Kesimpulan Hasil dan unggah file/scan EKG; **sinkronisasi tarif otomatis ke tagihan kasir sesuai penjamin (BPJS/Umum/Asuransi)**. | S1-L1-07; billing kasir |
| S7-L1-03 | L1 | Ekokardiografi Transtorakal (TTE) — Status Pemeriksaan | Dropdown | Belum Diorder \| Dijadwalkan / Diproses \| Selesai Terbaca | Tidak ada opsi "Dibatalkan" (berbeda dari EKG) — lihat AMBIGU-04. | — |
| S7-L1-04 | L1 | Ekokardiografi Transtorakal (TTE) — Interpretasi Klinis | Dropdown + input numerik LVEF | Normal / LVEF Baik (>= 50%) \| Disfungsi Sistolik Ringan (HFmrEF 41–49%) \| Disfungsi Sistolik Berat (HFrEF <= 40%) \| Disfungsi Diastolik / Kelainan Katup | Input numerik LVEF (%), Kesimpulan Hasil, unggah laporan/gambar Echo; **sinkronisasi tarif otomatis ke kasir**. | S1-L1-07; §9b |
| S7-L1-05 | L1 | Sistem Alert & Pelaporan Nilai Kritis (SKP 2 / PP) | Otomatis | `misal: hs-Troponin meningkat bermakna, Kalium < 2,8 atau > 6,0 mmol/L, INR > 4,5, atau ST-Elevasi akut` | **Side effect**: badge merah berkedip, notifikasi ke DPJP, serta **wajib** mencatat jam temuan, jam lapor ke DPJP, nama penerima laporan, dan konfirmasi read-back; lapor <= 30 menit. | §8; §7; S7-L1-02, S7-L1-04 |
| S7-L2-01 | L2 | Katalog Master Order Penunjang Kardiovaskular (Level 1 -> 2 -> 3) | Hierarki drill-down | Lihat §3 (9 baris katalog) | Setiap item memiliki kode tarif master, status proses order, timestamp order & terima hasil; biaya masuk otomatis ke tagihan kasir sesuai skema penjamin. | §3; S1-L1-07 |
| S7-L2-02 | L2 | Quick Order Bundle | Tombol paket | Paket Nyeri Dada Akut \| Paket Evaluasi Gagal Jantung \| Paket Kontrol Hipertensi/Dislipidemia | Dapat diakses langsung dari tombol 'Penunjang' pada Dasbor Antrean Poli. | §5 (deep-link 'Penunjang') |

### LANGKAH 8. PENETAPAN DIAGNOSIS & RENCANA TATA LAKSANA

Toolbar metode input berlaku seragam untuk Langkah 8 & 9.

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S8-L1-01 | L1 | Toolbar Metode Input (Langkah 8 & 9) | Toolbar | Manual \| Master (Dropdown) \| Bantuan AI (Clinical Decision Support) | Manual: "Pengisian langsung oleh DPJP/PPA dengan validasi format klinis"; Master: katalog ICD-10/ICD-9-CM Kardiologi, Formularium Obat RS, Paket Edukasi; AI: menyusun draf usulan diagnosis, evaluasi kesesuaian terapi GDMT, materi edukasi, ringkasan SOAP "berdasarkan data terverifikasi dari Langkah 1–7". | Langkah 1–7 |
| S8-L1-02 | L1 | Diagnosis Kerja Utama (ICD-10 Kardiologi) | Dropdown + Pencarian ICD-10 | Hipertensi Esensial (I10) \| Penyakit Jantung Koroner / Angina Pektoris (I20/I25) \| Gagal Jantung / CHF (I50) \| Aritmia Jantung / Atrial Fibrilasi (I48/I49) \| Penyakit Katup Jantung (I34–I38) \| Diagnosis Lainnya | "dilengkapi Diagnosis Sekunder/Komorbid". | Master ICD-10 |
| S8-L1-03 | L1 | Diagnosis Keperawatan / Gizi / Farmasi (Pendamping) | Tab khusus | SDKI (keperawatan) \| IDNT (gizi) \| DRP (masalah terkait obat) | "Tersedia tab khusus untuk penetapan diagnosis ... secara terintegrasi". | Peran PPA (Perawat, Gizi, Farmasi) |
| S8-L1-04 | L1 | Klasifikasi Fungsional / Stratifikasi Risiko | Dropdown | NYHA Kelas I \| NYHA Kelas II \| NYHA Kelas III \| NYHA Kelas IV \| CCS Kelas I–IV \| Risiko Rendah–Sedang \| Risiko Tinggi | Tidak ada aturan tambahan pada sumber. | S8-L1-02 |
| S8-L1-05 | L1 | Rencana Tindak Lanjut Utama | Dropdown | Rawat Jalan / Kontrol Poli Jantung \| Rawat Inap / ICCU / HCU \| Rujuk ke RS Jejaring / Intervensi Lanjut \| Menunggu Hasil Penunjang Lanjutan | Tidak ada aturan tambahan pada sumber. | Langkah 10 (disposisi) |
| S8-L2-01 | L2 | Terapi Farmakologis / E-Resep — Status | Dropdown | Diberikan Resep Rawat Jalan \| Penyesuaian Dosis Obat Rutin \| Tindakan / Injeksi di Poli \| Belum Diberikan | Pengecekan interaksi obat otomatis, timestamp order, waktu serah terima farmasi, tarif satuan obat, total biaya otomatis masuk ke RME dan tagihan kasir. | Master formularium; S3-L2-04, S3-L2-05; billing |
| S8-L2-02 | L2 | Edukasi Pasien & Keluarga (Standar KE STARKES) | Multi-select Dropdown + ekspor | Pola Hidup Sehat & Berhenti Merokok \| Diet Rendah Garam/Lemak & Pembatasan Cairan \| Kepatuhan Minum Obat GDMT & Pemantauan Efek Samping \| Tanda Bahaya (Red Flags) Kapan Harus ke IGD | **Side effect**: tombol Ekspor PDF dan cetak Bukti Edukasi dengan tanda tangan pasien/keluarga dan edukator yang "otomatis tersimpan ke repositori Dokumen Bukti KE". | §6 (KE) |
| S8-L2-03 | L2 | Jadwal Kontrol Berikutnya | Dropdown | 7 Hari \| 14 Hari \| 30 Hari \| Sesuai Jadwal Tindakan / Hasil Lab | Terhubung otomatis ke pembuatan Surat Kontrol / e-SKDP; informasi dapat langsung masuk WA pasien. | e-SKDP; WA gateway |

### LANGKAH 9. PELAKSANAAN ASUHAN — CPPT MULTIPROFESI & BILLING

Lapis 1 — CPPT (Format SOAP / ADIME). Lapis 2 — Tindakan Poliklinik, Sinkronisasi Billing & Panel Pendukung Kanan.

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S9-L1-01 | L1 | Hari/tanggal/bulan/tahun & waktu | Otomatis (editable) | format `DD/MM/YYYY` dan `HH:mm` | **Auto timestamp** saat form dibuka atau disimpan; "opsi edit jika menginput catatan susulan" / penyesuaian waktu disertai alasan singkat. | Sesi CPPT |
| S9-L1-02 | L1 | Nama Petugas & TTE | Otomatis + tombol aksi | Tombol "Tanda Tangani & Simpan" | Terisi otomatis dari akun login (nama, peran/profesi, unit); konfirmasi PIN/sandi atau biometric/passkey singkat. | Akun PPA aktif; kredensial |
| S9-L1-03 | L1 | Deteksi Perangkat & Tata Letak Adaptif | Otomatis | Desktop / Laptop (dua kolom) \| Tablet & Ponsel Android (satu kolom) | Desktop: panel SOAP kiri, konteks pasien kanan; Tablet/Ponsel: tombol aksi besar, tab cepat (Header, S, O, A, P), **auto-save lokal** saat jaringan tidak stabil. | — |
| S9-L1-04 | L1 | Kanvas Tulisan Tangan Stylus (Handwriting-to-Text) | Canvas + OCR | — | Tersedia di kolom S, O, A, P dan area TTE; palm rejection aktif; konversi bertahap dengan inline preview + skor keyakinan/sorotan kata untuk dikoreksi sebelum dikunci. | — |
| S9-L1-05 | L1 | TTE PPA | Canvas tanda tangan | — | Menangkap goresan, timestamp, identitas akun PPA, dan status tanda tangan terverifikasi saat catatan difinalisasi. | S9-L1-08 |
| S9-L1-06 | L1 | Header Catatan & Metadata Otomatis | Otomatis | `DD/MM/YYYY` dan `HH:mm` | Terisi otomatis saat sesi dimulai; opsi penyesuaian waktu catatan susulan disertai alasan singkat. | — |
| S9-L1-07 | L1 | Nama Petugas & Peran PPA | Otomatis | — | Terisi otomatis dari sesi aktif (nama lengkap, profesi/PPA, unit/ruangan). | Akun PPA aktif |
| S9-L1-08 | L1 | Tanda Tangan Elektronik (TTE) | Canvas / tanda tangan tersimpan | — | Konfirmasi kredensial singkat **sebelum status berubah dari Draf menjadi Terverifikasi/Terkunci**. | Verifikasi DPJP <= 24 jam (§7) |
| S9-L1-09 | L1 | S — Keluhan (quick-chips) | Quick-chips + teks bebas + stylus | sesak napas, nyeri dada, ortopnea, PND, berdebar, edema tungkai, pusing/presinkop | Kombinasi quick-chips sekali klik, kanvas tulisan tangan stylus, dan kotak teks bebas. | S3-L1-01 |
| S9-L1-10 | L1 | S — Kepatuhan Terapi | Pilihan status + penandaan obat | Patuh penuh \| Sebagian terlewat \| Menghentikan sendiri \| Belum memulai | Terhubung langsung dengan daftar obat aktif pasien; petugas menandai obat tertentu bila ada ketidaksesuaian dosis atau penghentian. | S3-L2-05; S8-L2-01 |
| S9-L1-11 | L1 | O — TTV & MAP Otomatis | Otomatis + input manual | TD Sistolik, TD Diastolik, Nadi, RR, Suhu, SpO₂, BB | Menarik data TTV terbaru dari rekam medis/monitor atau input manual; **MAP dihitung otomatis** dan ditampilkan bersama indikator status rentang. | S4-L1-01 … S4-L2-01 |
| S9-L1-12 | L1 | O — Fisik Kardiopulmonal | Checklist toggle + catatan | bunyi jantung I–II, murmur, gallop, JVP, suara napas/ronki, edema ekstremitas | Toggle normal/abnormal dengan catatan stylus/teks. | Langkah 6 |
| S9-L1-13 | L1 | O — Ringkasan Penunjang (Otomatis) | Otomatis | `misalnya elektrolit, fungsi ginjal, penanda jantung/natriuretik, EKG, ekokardiografi` | Kartu ringkas otomatis untuk hasil laboratorium dan diagnostik terbaru, dengan tautan cepat ke laporan penuh. | Langkah 7 |
| S9-L1-14 | L1 | O — Viewer Gambar Jantung & Ekstremitas Bertanda | Canvas + marker | `misalnya area katup/prekordial dan tungkai/pergelangan kaki` | Pin/marker bawaan; ketuk marker, pilih status/temuan, atau beri anotasi stylus langsung pada gambar. | S6-L1-05; S6-L2-03 |
| S9-L1-15 | L1 | A — Diagnosis Utama | Pencarian kode / manual / stylus | — | Pencarian kode/diagnosis klinis atau input manual/stylus. | S8-L1-02 |
| S9-L1-16 | L1 | A — Komorbid | Daftar | — | Daftar kondisi penyerta aktif/riwayat yang relevan dengan tata laksana. | S3-L2-01 |
| S9-L1-17 | L1 | A — Evaluasi Respons Terapi | Pilihan status + uraian | Membaik \| Membaik sebagian \| Stagnan/Belum membaik \| Memburuk | Disertai uraian singkat. | — |
| S9-L1-18 | L1 | A/P — Mode Bantuan AI ("Susun Draf AI") | Tombol + editor | — | Draf AI dapat diedit bebas (teks maupun stylus), menautkan rujukan data sumber, dan **memerlukan tinjauan/persetujuan petugas** sebelum dikirim ke e-Resep/kasir. | S8-L1-01; data S & O |
| S9-L1-19 | L1 | P — Pintasan Regimen GDMT & Penyesuaian Dosis | Dropdown/quick-pick + catatan | mulai dosis rendah \| titrasi naik \| tahan/turunkan dosis \| lanjutkan dosis saat ini | Konteks klinis S/O/A tampil di atas pilihan; "Satu sumber kebenaran": memilih pintasan mengisi/memperbarui baris draf resep yang sama, bukan menambah baris ganda. | S9-L1-15…S9-L1-17; S9-L1-11 |
| S9-L1-20 | L1 | P — E-Resep Manual via Touchscreen | Canvas/stylus + preview | — | Sistem membaca tulisan tangan menjadi field obat terstruktur dan menyorot bagian dengan keyakinan rendah/belum cocok katalog; dokter mengonfirmasi sebelum item diteruskan ke antrean e-Resep/Farmasi. | Master formularium; Farmasi |
| S9-L1-21 | L1 | P — Status Item Obat | Badge status | Perlu tinjauan \| Tersinkronisasi e-Resep \| Tersinkronisasi Kasir | "Perlu tinjauan": item **ditahan dari pengiriman otomatis** hingga diperbaiki/disetujui. | Farmasi; billing kasir |
| S9-L1-22 | L1 | P — Edukasi Non-Farmakologis | Checklist + catatan + PDF | `misalnya pembatasan cairan, pembatasan natrium, timbang berat badan rutin, aktivitas bertahap, dan tanda bahaya` | Brosur sesuai materi edukasi (bantuan AI dapat diedit) pdf, cetak; **tarif mengikuti master billing tagihan pasien masuk kasir**. | S8-L2-02; billing |
| S9-L1-23 | L1 | P — Rencana Kontrol | Pilihan jadwal / tanggal spesifik | jadwal kontrol cepat \| tanggal spesifik | Menyertakan unit/poli tujuan serta instruksi sebelum kunjungan berikutnya. | S8-L2-03 |
| S9-L2-01 | L2 | Tindakan Poliklinik & Kode ICD-9-CM | Dropdown pelaksana + master tindakan | Pelaksana: Dokter \| Perawat \| Nakes Lain. Tindakan: Rekam EKG 12-Lead \| Ekokardiografi Transtorakal \| Pemasangan Holter / ABPM \| Konseling & Edukasi Kardiologi \| Pemberian Oksigen / Obat Injeksi \| Tidak Ada Tindakan Tambahan | Dapat dipilih manual (mengisi) atau dari Master Tindakan Poli, beserta kode ICD-9-CM. | Master tindakan; billing |
| S9-L2-02 | L2 | Sinkronisasi Tarif & Billing Kasir | Otomatis | INA-CBGs (BPJS Kesehatan) \| tarif master rumah sakit (Umum/Asuransi Swasta) | Otomatis menyesuaikan skema tarif berdasarkan penjamin; seluruh rincian tindakan, penunjang, dan e-Resep terakumulasi real-time ke sistem kasir/billing. | S1-L1-07; Langkah 7; S8-L2-01 |
| S9-L2-03 | L2 | Panel Pendukung Sisi Kanan (Regulasi, Informed Consent & Multi-Upload) | Panel kontekstual | (1) Menu regulasi (Panduan Praktik Klinis & SOP) PDF + hover preview; (2) Formulir Informed Consent siap cetak; (3) Brosur edukasi & informasi tindakan siap cetak; (4) Menu unggah dokumen pendukung multi-file | Informed Consent "otomatis terisi identitas pasien dan jenis tindakan"; nama file unggahan otomatis menjadi judul dokumen dan dapat dilihat, dicetak, diekspor ke PDF. | Jenis tindakan (S9-L2-01); §6 (HPK) |

Catatan struktur CPPT (Lampiran dokumen, "Ringkasan Struktur Modul & Alur Data"): Header & TTE = Otomatis + verifikasi tanda tangan → "Mengunci & mengesahkan catatan CPPT"; S = "Konteks gejala & kepatuhan untuk A dan P"; O = "Bukti objektif untuk A dan P"; A = "Dasar penentuan Plan & riwayat klinis"; P = "Sinkronisasi e-Resep, Kasir, & jadwal kontrol".

### LANGKAH 10. EVALUASI AKHIR KUNJUNGAN, DISPOSISI & MUTU STARKES

Lapis 1 — Kondisi Akhir, TTV Pulang & Alur Disposisi. Lapis 2 — Pelaporan Risiko Mutu Unit (STARKES) & Penguncian Rekam Medis.

| ID | Lapis | Field / Kontrol | Tipe Kontrol | Opsi / Nilai (verbatim) | Validasi / Auto-komputasi / Aturan | Ketergantungan |
|---|---|---|---|---|---|---|
| S10-L1-01 | L1 | Versi & Waktu Update | Otomatis (read-only) | `misal: Versi 1 · 24 Nov 2026 09:45 WIB` | Tercatat otomatis pada panel kanan. | Audit/versioning RME |
| S10-L1-02 | L1 | Kondisi Akhir | Dropdown | Stabil / Membaik \| Tetap / Perlu Pemantauan Ketat \| Memburuk / Dirujuk ke IGD | Tidak ada aturan tambahan pada sumber. | — |
| S10-L1-03 | L1 | Respons Terapi | Dropdown | Baik — Keluhan Berkurang & Hemodinamik Stabil \| Cukup Baik — Perlu Evaluasi Lanjutan \| Kurang Optimal — Perlu Eskalasi Terapi | Tidak ada aturan tambahan pada sumber. | S10-L1-02 |
| S10-L1-04 | L1 | Tanda Vital Akhir Kunjungan | Input numerik | Tekanan Darah Sistolik (mmHg), Tekanan Darah Diastolik (mmHg), Nadi (bpm) | Diukur "sebelum pasien meninggalkan poliklinik"; hanya 3 parameter (lihat AMBIGU-06). | S4-L1-01, S4-L1-02 |
| S10-L1-05 | L1 | Disposisi Pasien | Dropdown + percabangan | Pulang (Selesai) \| Rawat Inap \| Rujuk Antar-Poli \| Rujuk Keluar RS | **Side effect per cabang** — Pulang: menu cetak/unduh Berkas Pulang (Resume Rawat Jalan, E-Resep, Surat Kontrol, brosur edukasi, masuk dalam ERM). Admisi Rawat Inap: Surat Pengantar Rawat Inap, persetujuan rawat inap, modul Manajemen Bed real-time (Kelas Perawatan, Bangsal/Ruang ICCU/HCU/Bangsal Jantung, indikator Nomor Bed tersedia [hijau] vs penuh [merah], booking kamar + tarif kamar otomatis dari master tarif bed). Rujuk Antar-Poli: pilihan Poliklinik Tujuan internal, alasan konsultasi, ringkasan klinis siap cetak/kirim. Rujuk Keluar RS: Surat Rujukan Eksternal (RS tujuan, alasan rujukan, kondisi stabilisasi, resume klinis). | Master tarif bed; poli internal; §5 (deep-link Disposisi) |
| S10-L2-01 | L2 | Catatan Insiden Keselamatan / Risiko Mutu Unit | Dropdown | Tidak Ada Insiden / Risiko Terkendali \| Kejadian Nyaris Cedera (KNC) Tercatat \| Kejadian Tidak Diharapkan (KTD) / Sentinel \| Risiko Kepatuhan / Alur Pelayanan Tercatat | **Side effect**: terhubung otomatis ke Matriks PDCA unit dan tombol Ekspor PDF Bukti Pelaksanaan EP. | §6 (PMKP & SKP); Matriks PDCA |
| S10-L2-02 | L2 | Status Finalisasi & Audit Trail Rekam Medis | Dropdown | Final Terkunci (Read-Only setelah verifikasi DPJP) \| Mode Addendum | Mode Addendum: perubahan pasca-finalisasi **wajib mengisi alasan klinis**, tidak menimpa catatan asli, mencatat identitas pengguna dan timestamp dalam log audit versi. | Verifikasi DPJP; RBAC |

---

## 3. Katalog Penunjang 3 Tingkat (Level 1 -> 2 -> 3)

Sumber: tabel "Katalog Master Order Penunjang Kardiovaskular (Hierarki Level 1 -> 2 -> 3)", dapat diakses dari tombol 'Penunjang' pada Dasbor Antrean Poli. Setiap item memiliki kode tarif master, status proses order, timestamp order & terima hasil.

| Level 1: Kategori Order | Level 2: Kelompok Pemeriksaan | Level 3: Jenis Item Pemeriksaan | Usulan kode |
|---|---|---|---|
| 1. Laboratorium (Routing ke LIS) | Biomarker Jantung (Prioritas Teratas) | • hs-Troponin I / Troponin T<br>• CK-MB<br>• NT-proBNP / BNP | TODO |
| 1. Laboratorium (Routing ke LIS) | Hematologi & Koagulasi | • Darah Lengkap (CBC)<br>• PT & INR (pemantauan Warfarin)<br>• APTT & D-Dimer | TODO |
| 1. Laboratorium (Routing ke LIS) | Profil Lipid | • Kolesterol Total, LDL, HDL, Trigliserida<br>• ApoB & Lipoprotein(a) | TODO |
| 1. Laboratorium (Routing ke LIS) | Metabolik, Ginjal & Elektrolit | • GDP, GD 2 Jam PP, HbA1c, Asam Urat<br>• Ureum, Kreatinin (eGFR)<br>• Elektrolit Lengkap (Na, K, Cl, Mg, Ca) | TODO |
| 1. Laboratorium (Routing ke LIS) | Fungsi Hati, Tiroid & Inflamasi | • SGOT (AST) & SGPT (ALT)<br>• TSH & Free T4<br>• hs-CRP | TODO |
| 2. Radiologi & Pencitraan (RIS/PACS) | Radiologi Konvensional & CT/MRI Jantung | • Rontgen Thorax (AP/PA)<br>• CT Calcium Score Koroner & CT Coronary Angiography<br>• Cardiac MRI (CMR) | TODO |
| 2. Radiologi & Pencitraan (RIS/PACS) | USG Vaskular | • USG Doppler Karotis<br>• USG Doppler Ekstremitas (Arteri/Vena) & Ginjal | TODO |
| 3. Penunjang Kardiologi (Unit Diagnostik) | Elektrofisiologi & Uji Latih Non-Invasif | • EKG 12-Lead, Holter Monitoring (24–72 Jam), ABPM 24 Jam<br>• Ekokardiografi (TTE & TEE), Treadmill Test, Stress Echo, ABI | TODO |
| 4. Tindakan Invasif (Rujukan Cath Lab) | Kateterisasi & Elektrofisiologi Invasif | • Angiografi Koroner (Kateterisasi Jantung) / PCI<br>• Studi Elektrofisiologi (EPS) & Pemasangan Pacu Jantung | TODO |

Jumlah baris data: 9. Kolom "Usulan kode" tidak ada pada dokumen sumber — diisi `TODO` sesuai instruksi (lihat AMBIGU-01).

---

## 4. Matriks RBAC

Dasar verbatim dokumen sumber:
- Bagian F: "Hak akses verifikasi akhir otomatis menyesuaikan profil login (Kepala Unit Kerja / DPJP Sp.JP / Perawat Poli Jantung)."
- Bagian F, butir 4 (RBAC): "Perawat Poli (isi Langkah 1–6, CPPT Keperawatan, order penunjang sesuai delegasi), DPJP Sp.JP (akses penuh Langkah 1–10, verifikasi CPPT, finalisasi/kunci RME), Farmasi/Gizi/Fisioterapi (akses baca RME & tulis CPPT sesuai profesi), Kasir/Rekam Medis (akses rincian billing & ekspor dokumen klaim/audit)."
- Langkah 1: "editable hanya dengan otorisasi Kepala Unit / Rekam Medis".
- Tabel Profesi PPA: Dokter "melakukan verifikasi instruksi/asuhan PPA lain maksimal 24 jam"; Perawat "Mencatat sesuai kewenangan klinis keperawatan (SPK/RKK)"; Apoteker "Memastikan keamanan pengobatan"; Nutrisionis "format ADIME atau SOAP"; Fisioterapis "Hak akses CPPT diberikan sesuai Surat Penugasan Klinis (SPK) dan Rincian Kewenangan Klinis (RKK)".

Sel akses: `isi` / `baca` / `verifikasi` / `finalisasi`; gabungan ditulis dengan `+`; `tidak diatur` bila dokumen sumber tidak menyebutkan peran tersebut untuk langkah itu.

| Peran | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9 | L10 | Dasar (verbatim) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Perawat Poli | isi | isi | isi | isi | isi | isi | isi (order penunjang sesuai delegasi) | tidak diatur | isi (CPPT Keperawatan) | tidak diatur (AMBIGU-05) | "Perawat Poli (isi Langkah 1–6, CPPT Keperawatan, order penunjang sesuai delegasi)" |
| DPJP Sp.JP | isi + verifikasi | isi + verifikasi | isi + verifikasi | isi + verifikasi | isi + verifikasi | isi + verifikasi | isi + verifikasi | isi + verifikasi | isi + verifikasi | isi + verifikasi + finalisasi | "DPJP Sp.JP (akses penuh Langkah 1–10, verifikasi CPPT, finalisasi/kunci RME)" |
| Farmasi | baca | baca | baca | baca | baca | baca | baca | baca | baca + isi (CPPT sesuai profesi) | baca | "Farmasi/Gizi/Fisioterapi (akses baca RME & tulis CPPT sesuai profesi)" |
| Gizi | baca | baca | baca | baca | baca | baca | baca | baca | baca + isi (CPPT sesuai profesi) | baca | idem |
| Fisioterapi | baca | baca | baca | baca | baca | baca | baca | baca | baca + isi (CPPT sesuai profesi) | baca | idem; "Hak akses CPPT diberikan sesuai SPK dan RKK" |
| Kasir / Rekam Medis | isi (otorisasi edit Tanggal & Waktu Pemeriksaan) + baca | tidak diatur | tidak diatur | tidak diatur | tidak diatur | tidak diatur | baca (rincian tarif/billing) | tidak diatur | baca (rincian billing) + ekspor dokumen klaim/audit | tidak diatur | "Kasir/Rekam Medis (akses rincian billing & ekspor dokumen klaim/audit)"; L1 "otorisasi Kepala Unit / Rekam Medis" |
| Kepala Unit | isi (otorisasi edit Tanggal & Waktu Pemeriksaan) | tidak diatur | tidak diatur | tidak diatur | tidak diatur | tidak diatur | tidak diatur | tidak diatur | tidak diatur | verifikasi (verifikasi akhir) | "Hak akses verifikasi akhir otomatis menyesuaikan profil login (Kepala Unit Kerja / DPJP Sp.JP / Perawat Poli Jantung)"; L1 "otorisasi Kepala Unit" |

Catatan RBAC:
- Dokumen sumber tidak merinci hak per langkah untuk Farmasi, Gizi, Fisioterapi, Kasir/Rekam Medis, dan Kepala Unit; sel "baca"/"tidak diatur" di atas adalah pembacaan harfiah atas kalimat RBAC, bukan perluasan.
- Perawat Poli disebut pada kalimat "verifikasi akhir" (Bagian F) tetapi butir RBAC hanya memberi isi Langkah 1–6 + CPPT; sel L10 ditandai AMBIGU-05.

---

## 5. Matriks Deep-Link Dasbor Antrean

Sumber: Bagian F, tabel "Aksi / Tombol di Dasbor Antrean | Target Deep-Link pada Modul RME | Aturan Validasi & Perubahan Status Sistem".

| Tombol / Aksi di Dasbor Antrean | Target langkah | Aturan validasi & perubahan status (verbatim) |
|---|---|---|
| Tombol '+ Pendaftaran Baru' | Langkah 1 (Identitas & Penjamin) | "Membuka modal registrasi kunjungan, mengisi otomatis No. RM/Kunjungan, mewajibkan pemilihan DPJP, dan menetapkan status antrean 'Menunggu'." |
| Tombol 'SOAP' | Langkah 2 (Skrining) atau Langkah 8–9 (Diagnosis & CPPT) | "Jika asesmen awal perawat (Langkah 1–6) belum terisi, membuka Langkah 2; jika sudah terisi, langsung membuka Langkah 8–9. Status antrean otomatis berubah menjadi 'Dilayani'." |
| Tombol 'Penunjang' | Langkah 7 (Penunjang & Order 3-Tingkat) | "Membuka drawer atau melompat langsung ke Langkah 7 untuk order cepat EKG/TTE/Biomarker tanpa harus menggulir form dari Langkah 1." |
| Tombol Disposisi (Dropdown Disposisi) | Langkah 10 (Evaluasi Akhir Kunjungan) | "Membuka Langkah 10 dengan pilihan percabangan disposisi sesuai header dasbor: Pulang (Selesai), Rujuk Antar-Poli, Admisi Rawat Inap, atau Rujuk Keluar." |
| Ikon 'Detail' (Kanan Tabel) | Panel Pratinjau Longitudinal RME | "Menampilkan ringkasan riwayat kunjungan sebelumnya, grafik tren TTV/LVEF, badge alergi, dan daftar obat GDMT aktif." |

Aturan tambahan Dasbor Antrean (Bagian F, "Rekomendasi Perbaikan UI Tabel Antrean"):
1. Sticky Column: kolom identitas pasien (No. RM & Nama Lengkap) wajib `position: sticky; left: 0`.
2. Validasi DPJP: kolom DPJP "tidak boleh kosong ('-') saat status sudah 'Dilayani'"; validasi sejak pendaftaran atau saat klik tombol SOAP.
3. Indikator Keselamatan: ikon peringatan di samping nama pasien bila ada Alergi Obat/Kontras atau hasil Nilai Kritis Penunjang yang belum dibaca.

---

## 6. Matriks Pemetaan EP STARKES 2024

Sumber: Bagian G. Pada dokumen sumber, PMKP dan SKP digabung dalam satu baris ("PMKP & SKP"); matriks ini memecahnya menjadi dua baris dengan isi identik (AMBIGU-07).

| Bab STARKES | Sumber data langkah | Dokumen bukti PDF | Indikator mutu PDCA |
|---|---|---|---|
| ARK (Akses & Kontinuitas Pelayanan) | "Langkah 1, 2, & 10: Triase Red Flags kardiologi, alur transfer IGD (Cito), surat kontrol, dan disposisi rawat inap / rujukan eksternal." | "PDF Resume Rawat Jalan, Surat Pengantar Rawat Inap, & Surat Rujukan otomatis terindeks ke Dokumen Bukti ARK." | "Waktu tunggu pelayanan rawat jalan <= 60 menit; ketepatan alur rujukan Cito ke IGD." |
| PP (Pelayanan & Asuhan Pasien) | "Langkah 3–7 & 9: Asesmen awal terstandar, CPPT multiprofesi (SOAP/ADIME), rekonsiliasi/PTO obat, dan alert Nilai Kritis." | "Log timestamp pelaporan Nilai Kritis ke DPJP dan kelengkapan pengisian CPPT terverifikasi sebagai bukti EP PP." | "Kelengkapan asesmen awal medis & keperawatan <= 24 jam (100%); verifikasi CPPT DPJP." |
| HPK (Hak Pasien & Keterlibatan Keluarga) | "Langkah 5 & 8–9: Skrining nilai budaya/kebutuhan spiritual, persetujuan tindakan invasif/diagnostik (e-Consent), serta privasi akses RME." | "Menyimpan e-Consent tindakan diagnostik jantung (Treadmill Test / kateterisasi) dan unggahan dokumen ke Dokumen Bukti HPK (cetak PDF)." | "Kepatuhan kelengkapan Informed Consent sebelum tindakan diagnostik invasif/berisiko (100%)." |
| KE (Komunikasi & Edukasi) | "Langkah 8 (Lapis 2): Checklist edukasi terstruktur (diet rendah garam, pembatasan cairan, kepatuhan GDMT, tanda bahaya ke IGD)." | "Tombol Ekspor PDF Bukti Edukasi dengan tanda tangan elektronik pasien/keluarga dan edukator otomatis tersimpan ke Dokumen Bukti KE." | "Cakupan pemberian edukasi terstruktur pada pasien gagal jantung & PJK." |
| KPS (Kualifikasi & Pendidikan Staf) | "Langkah 1, 9, & 10: Validasi master kredensial DPJP (Sp.JP / Sp.JP(K), FIHA), Perawat, Apoteker, dan Dietisien sesuai SPK/RKK." | "Sistem membatasi hak verifikasi akhir (Langkah 10) dan tanda tangan CPPT medis hanya untuk DPJP dengan kredensial aktif di master SDM." | "Kepatuhan pelayanan klinis oleh PPA sesuai SPK dan RKK aktif (100%)." |
| PMKP (Mutu & Keselamatan Pasien) | "Langkah 3, 4, 5, 7, & 10: Identifikasi pasien (No. RM + NIK), badge alergi obat/kontras, skrining risiko jatuh, nilai kritis, & pelaporan KNC/KTD." | "Data ditarik otomatis ke Matriks PDCA unit Poli Jantung dan laporan insiden keselamatan pasien unit (ekspor PDF)." | "Kepatuhan peresepan GDMT pada HFrEF; waktu lapor hasil nilai kritis <= 30 menit; kepatuhan identifikasi & risiko jatuh." |
| SKP (Sasaran Keselamatan Pasien) | idem (digabung dengan PMKP pada sumber) | idem | idem |

---

## 7. Aturan Waktu Kritis & SLA

| Aturan | Nilai | Pemicu | Konsekuensi sistem |
|---|---|---|---|
| Door-to-ECG | <= 10 menit | Red flags "Nyeri Dada Khas Angina (Suspek SKA)" atau "Sesak Napas Berat / Orthopnea / Edema Paru" dipilih pada Langkah 2 | Auto timestamp skrining awal + indikator prioritas perekaman EKG; banner peringatan merah dan tombol pintas transfer ke IGD bila red flags berat |
| Verifikasi DPJP (CPPT / instruksi asuhan PPA lain) | <= 24 jam | Catatan CPPT PPA masuk (Langkah 9) | Status catatan Draf → Terverifikasi/Terkunci; verifikasi CPPT DPJP menjadi indikator mutu PP |
| Lapor nilai kritis ke DPJP | <= 30 menit | Nilai kritis ditemukan (Langkah 7): hs-Troponin meningkat bermakna, Kalium < 2,8 atau > 6,0 mmol/L, INR > 4,5, ST-Elevasi akut | Badge merah berkedip, notifikasi DPJP, kewajiban isi jam temuan, jam lapor, nama penerima laporan, konfirmasi read-back; log timestamp menjadi bukti EP PP |
| Waktu tunggu pelayanan rawat jalan | <= 60 menit | Kunjungan poli berjalan (Langkah 1 → Langkah 10) | Indikator mutu PDCA ARK (mekanisme pengukuran tidak dirinci — AMBIGU-09) |
| Kelengkapan asesmen awal medis & keperawatan | <= 24 jam (target 100%) | Kunjungan baru (Langkah 3–7) | Indikator mutu PDCA PP |
| Waktu serah terima farmasi | tidak ditetapkan (hanya timestamp) | Item e-Resep terkirim ke Farmasi (Langkah 8/9) | Timestamp "waktu serah terima farmasi" tercatat pada e-Resep |
| Finalisasi/penguncian RME | tidak ditetapkan | Verifikasi DPJP selesai (Langkah 10) | Status "Final Terkunci (Read-Only)"; perubahan hanya via Mode Addendum + alasan klinis + audit log |

---

## 8. Daftar Nilai Kritis

Sumber: Langkah 7 Lapis 1, butir "Sistem Alert & Pelaporan Nilai Kritis (SKP 2 / PP)".

| Parameter | Ambang | Sumber |
|---|---|---|
| hs-Troponin (I / T) | "meningkat bermakna" — **tanpa angka** (AMBIGU-02) | Langkah 7 Lapis 1 |
| Kalium | < 2,8 atau > 6,0 mmol/L | Langkah 7 Lapis 1 |
| INR | > 4,5 | Langkah 7 Lapis 1 |
| ST-Elevasi | "ST-Elevasi akut" — **tanpa kriteria millimeter/sadapan** (AMBIGU-02) | Langkah 7 Lapis 1 |
| CK-MB | tidak ditetapkan sebagai nilai kritis | Katalog §3 (Biomarker Jantung) |
| NT-proBNP / BNP | tidak ditetapkan sebagai nilai kritis | Katalog §3 (Biomarker Jantung) |
| LVEF | tidak ditetapkan sebagai nilai kritis; <= 40% = "Disfungsi Sistolik Berat (HFrEF)" | Langkah 7 Lapis 1 (TTE) |

Efek sistem untuk setiap nilai kritis: badge merah berkedip, notifikasi ke DPJP, kewajiban mencatat jam temuan, jam lapor ke DPJP, nama penerima laporan, dan konfirmasi read-back.

---

## 9. Ambang Alert TTV & Parameter Klinis

### 9a. Ambang alert (memicu peringatan/badge)

| Parameter | Ambang | Sumber |
|---|---|---|
| Takikardia | Nadi > 100 bpm | Langkah 4 Lapis 1 |
| Bradikardia | Nadi < 50 bpm | Langkah 4 Lapis 1 |
| Hipoksia | SpO2 < 92% | Langkah 4 Lapis 1 |
| Krisis hipertensi | >= 180/120 mmHg | Langkah 4 Lapis 1 |
| Hipotensi | Sistolik < 90 mmHg | Langkah 4 Lapis 1 |
| Nyeri | NRS >= 4 (membuka asesmen PQRST + rencana evaluasi ulang) | Langkah 4 Lapis 2 |
| Kenaikan berat badan | >= 2 kg dalam 2–3 hari (lapor) | Lampiran D (CPPT contoh, Plan) |
| Hipertensi derajat 1–2 | **tanpa angka** pada sumber (AMBIGU-01) | Langkah 4 Lapis 1 |
| Risiko jatuh | kategori "Risiko Tinggi" (skor Morse/Get Up & Go tidak ditetapkan — AMBIGU-08) | Langkah 5 Lapis 1 |
| Risiko malnutrisi | kategori "Berisiko Malnutrisi" (skor MST tidak ditetapkan — AMBIGU-08) | Langkah 5 Lapis 1 |
| Interaksi obat kehamilan | Status "Hamil (Trimester I/II/III)" atau "Menyusui" → peringatan kontraindikasi (ACEi, ARB, ARNI, Statin, Warfarin) | Langkah 3 Lapis 2 |
| Alergi | Pilihan "Alergi Obat" / "Alergi Zat Kontras" → badge alergi merah permanen di header & baris antrean | Langkah 3 Lapis 2 |

### 9b. Ambang klasifikasi & auto-komputasi (bukan alert)

| Parameter | Nilai / Klasifikasi | Sumber |
|---|---|---|
| MAP | `MAP = [Sistolik + 2 x Diastolik] / 3` | Langkah 4 Lapis 1 |
| MAP — kategori | rentang normal \| hipertensi derajat 1–2 \| krisis hipertensi (>= 180/120 mmHg) \| hipotensi (Sistolik < 90 mmHg) — batas angka kategori normal & derajat 1–2 tidak dituliskan (AMBIGU-01) | Langkah 4 Lapis 1 |
| IMT (Asia-Pasifik) | Underweight (< 18,5) \| Normal (18,5 – 22,9) \| Overweight / Berisiko (23,0 – 24,9) \| Obesitas I (25,0 – 29,9) \| Obesitas II (>= 30,0) | Langkah 4 Lapis 2 |
| LVEF | Normal / LVEF Baik (>= 50%) \| Disfungsi Sistolik Ringan (HFmrEF 41–49%) \| Disfungsi Sistolik Berat (HFrEF <= 40%) \| Disfungsi Diastolik / Kelainan Katup | Langkah 7 Lapis 1 |
| JVP | Tidak Meningkat (5 + 0 s.d. 2 cmH2O) \| Meningkat (5 + >= 3 cmH2O) | Langkah 6 Lapis 2 |
| Indeks Brinkman | dihitung dari "estimasi batang/hari dan lama merokok" — formula tidak dituliskan (AMBIGU-03) | Langkah 3 Lapis 2 |
| Selisih BB antar kunjungan | perbandingan otomatis dengan kunjungan sebelumnya (deteksi retensi cairan akut) | Langkah 4 Lapis 2 |

---

## 10. Daftar Ambiguitas

| Kode | Lokasi | Teks sumber (kutipan) | Ambiguitas |
|---|---|---|---|
| AMBIGU-01 | Langkah 4 Lapis 1; §9b | "indikator warna otomatis rentang normal, hipertensi derajat 1–2, krisis hipertensi (>= 180/120 mmHg), atau hipotensi (Sistolik < 90 mmHg)" | Batas numerik "rentang normal" dan "hipertensi derajat 1–2" tidak dituliskan; hanya krisis (>= 180/120) dan hipotensi (Sistolik < 90) yang berangka. |
| AMBIGU-02 | Langkah 7 Lapis 1 | "Nilai Kritis (misal: hs-Troponin meningkat bermakna, Kalium < 2,8 atau > 6,0 mmol/L, INR > 4,5, atau ST-Elevasi akut)" | "meningkat bermakna" dan "ST-Elevasi akut" tanpa ambang angka/kriteria sadapan. |
| AMBIGU-03 | Langkah 3 Lapis 2 | "dengan input estimasi batang/hari dan lama merokok untuk kalkulasi Indeks Brinkman" | Rumus Indeks Brinkman tidak dinyatakan (hanya komponen input). |
| AMBIGU-04 | Langkah 7 Lapis 1 | EKG: "Belum Diorder \| Diorder / Menunggu \| Selesai Terbaca \| Dibatalkan"; TTE: "Belum Diorder \| Dijadwalkan / Diproses \| Selesai Terbaca" | Set status TTE tidak memiliki opsi pembatalan dan label statusnya tidak sejajar dengan EKG. |
| AMBIGU-05 | Bagian F; butir RBAC 4 | "Hak akses verifikasi akhir otomatis menyesuaikan profil login (Kepala Unit Kerja / DPJP Sp.JP / Perawat Poli Jantung)" vs "Perawat Poli (isi Langkah 1–6, CPPT Keperawatan, order penunjang sesuai delegasi)" | Perawat Poli disebut pada kalimat verifikasi akhir, tetapi butir RBAC tidak memberinya hak verifikasi/finalisasi; cakupan per langkah untuk Farmasi/Gizi/Fisioterapi/Kasir/Kepala Unit tidak dirinci. |
| AMBIGU-06 | Langkah 10 Lapis 1 | "Input numerik Tekanan Darah Sistolik (mmHg), Tekanan Darah Diastolik (mmHg), dan Nadi (bpm) sebelum pasien meninggalkan poliklinik." | TTV akhir hanya 3 parameter (tanpa RR, SpO2, suhu, MAP) sehingga tidak sebanding dengan TTV masuk. |
| AMBIGU-07 | Bagian G | Baris "PMKP & SKP / (Mutu & Keselamatan Pasien)" | Dua bab STARKES digabung dalam satu baris; pemetaan per bab tidak dipisahkan pada sumber. |
| AMBIGU-08 | Langkah 5 Lapis 1 | "Skrining Risiko Jatuh (Get Up & Go / Morse Fall Scale)" dan "Skrining Gizi Awal (MST)" | Tidak ada skor/batas kategori numerik untuk Morse, Get Up & Go, maupun MST. |
| AMBIGU-09 | Bagian G (ARK) | "Waktu tunggu pelayanan rawat jalan <= 60 menit" | Titik awal/akhir pengukuran waktu tunggu tidak didefinisikan (registrasi vs mulai dilayani vs selesai). |
| AMBIGU-10 | Langkah 2 Lapis 1 | "sistem otomatis mencatat timestamp skrining awal dan memunculkan indikator prioritas perekaman EKG <= 10 menit" | Titik akhir hitungan door-to-ECG tidak ditetapkan (timestamp order EKG vs hasil EKG "Selesai Terbaca"). |
| AMBIGU-11 | Langkah 9 | Penomoran butir: "3. Header Catatan & Metadata Otomatis" lalu "3. Komponen SOAP Terintegrasi"; paragraf "P — Plan (GDMT Tersinkronisasi e-Resep & Kasir, Edukasi, Kontrol)" diikuti paragraf kosong sebelum sub-butir "1. Spesifikasi Perbaikan Bagian Terapi Farmakologis GDMT" | Cacat penomoran/paragraf kosong pada struktur CPPT; tidak ada field yang hilang, tetapi hierarki butir tidak konsisten. |
| AMBIGU-12 | Langkah 10 Lapis 1 | Dropdown: "Pulang (Selesai) \| Rawat Inap \| Rujuk Antar-Poli \| Rujuk Keluar RS"; rincian cabang: "Admisi Rawat Inap" | Label opsi ("Rawat Inap") berbeda dengan label rincian cabang ("Admisi Rawat Inap"). |
| AMBIGU-13 | Langkah 8 header & Langkah 9 | "Standar Toolbar Metode Input Langkah 8 & 9 (Seragam)" ditempatkan pada blok judul Langkah 8 | Toolbar berlaku untuk dua langkah tetapi hanya didefinisikan sekali pada Langkah 8. |
| AMBIGU-14 | Langkah 1 Lapis 1 | "No. Rekam Medis (No. RM): Otomatis dari master pasien" dan "NIK (16 digit tervalidasi)" | Tidak dijelaskan apakah NIK wajib (mandatory) atau opsional untuk pasien tanpa NIK. |
| AMBIGU-15 | Bagian C (judul langkah) vs Bagian E (wireframe) | Navigasi: "8. Diagnosis & Rencana (AI)"; judul resmi: "LANGKAH 8. PENETAPAN DIAGNOSIS & RENCANA TATA LAKSANA" | Label menu pada wireframe berbeda dari judul langkah pada spesifikasi. |
| AMBIGU-16 | Bagian F, tombol 'SOAP' | "Langkah 2 (Skrining) atau Langkah 8–9 (Diagnosis & CPPT)" | Satu tombol memetakan ke dua target berbeda; aturan penentunya bergantung pada kelengkapan Langkah 1–6 tanpa definisi "terisi" (field wajib mana). |
