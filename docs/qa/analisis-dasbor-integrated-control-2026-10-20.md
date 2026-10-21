# Analisis — Dasbor Utama "ARIMA HOSPITAL INTEGRATED CONTROL"

Tanggal: 2026-10-20
Sumber: `judul Dasbor Utama terbaik yang profesional.docx`
Status: analisis + usulan, belum ada implementasi

---

## 1. Apa yang diminta dokumen

Dokumen hanya berisi **judul dan kerangka**, bukan spesifikasi lengkap:

| Elemen | Isi dari dokumen |
|---|---|
| Judul utama | `ARIMA HOSPITAL INTEGRATED CONTROL` |
| Subjudul | `Executive Dashboard for Quality, Risk & EHR Integration` |
| Latar | "Untuk background ada gambar RS" |
| Sub-dasbor 1 | `Integrated Risk & Patient Safety Control + AI` — pusat kendali risiko klinis/operasional, profil indikator mutu, budaya safety |
| Sub-dasbor 2 | `Smart EMR & Clinical Quality STARKES + AI` — RME terintegrasi standar pelayanan & kepatuhan PPA |
| Sub-dasbor 3 | `Electronic Accreditation Document & Automation Hub + AI` — pusat otomasi & evidence digital STARKES, terkoneksi RME & manajemen risiko |
| Perilaku | "Untuk setiap Unit Contoh; dasbor tanpa tulisan Side, selanjutnya masuk ke yang sudah ada" — berlaku juga untuk sub-dasbor 2 dan 3 |

Pola yang terbaca: **satu pintu masuk eksekutif → tiga portal → masuk ke modul yang sudah ada.** Bukan aplikasi baru, tapi lapisan presentasi di atas data yang sudah tersimpan.

## 2. Isi gambar di dalam docx — bukan aset

`word/media/image1.png` (391 KB) **bukan foto rumah sakit**. Itu tangkapan layar aplikasi yang sedang berjalan: `sim-akreditasi-django.vercel.app`, halaman unit IGD, judul "ARIMA v2.6 Command Center", banner teal besar "INSTALASI GAWAT DARURAT (IGD)", tombol Matriks PDCA Unit / Input Risiko / Lapor Insiden, dan 4 kartu KPI.

Konsekuensi:

- Gambar itu **referensi tampilan sekarang**, bukan bahan latar. Tidak bisa dipakai sebagai background — di dalamnya sudah ada teks dan navigasi.
- Aset foto RS **belum ada**. Repo juga tidak punya folder `static/img/` (hanya `static/css` dan `static/js`).
- Jadi "background gambar RS" harus disediakan operator (foto fasad/gedung), atau diganti latar yang dibuat sendiri (gradien + siluet SVG) supaya tidak pernah muncul gambar rusak.

## 3. Gap: aplikasi sekarang vs yang diminta

| Aspek | Sekarang | Diminta |
|---|---|---|
| Titik masuk | `dashboard` — berorientasi PDCA/EP, sidebar penuh, konten per peran | Control room eksekutif, tiga portal, tanpa sidebar |
| Cakupan | Per unit, dengan sidebar | Lintas unit sebagai pintu masuk, per unit sebagai isi |
| Bahasa visual | Kartu putih, header teal, KPI kecil | "Profesional & futuristik", hero besar + latar RS |
| Narasi | Angka mentah | Angka + "+AI" (ringkasan/interpretasi) |
| Navigasi | Sidebar pohon pokja/standar | Kartu portal + tombol Link ke modul lama |

Artinya pekerjaan ini **tidak menyentuh model data** — hanya penambahan view, template, dan satu endpoint AI. Tidak ada migration baru.

## 4. Pemetaan tiga sub-dasbor ke data yang benar-benar ada

Semua angka di bawah ini bisa dihitung dari tabel yang sudah ada. Tidak ada angka karangan.

### Sub-dasbor 1 — Integrated Risk & Patient Safety Control + AI

| Metrik | Sumber |
|---|---|
| Jumlah risiko per level (Ekstrem/Tinggi/Sedang/Rendah) | `RisikoUnit` |
| Risiko tanpa RTL / RTL lewat tenggat | `RisikoUnit` + `TindakLanjutRisiko` |
| Insiden per jenis & per gradasi (Biru/Hijau/Kuning/Merah) | `InsidenKeselamatan` |
| Insiden dalam masa investigasi / belum tuntas | `InsidenKeselamatan` (status) |
| Capaian indikator mutu (%) vs target | `IndikatorMutu`, `CatatanIndikator` |
| Indikator di bawah target bulan berjalan | `CatatanIndikator` |
| Laporan mutu menunggu verifikasi | `LaporanMutu` (status DRAF/DIVERIFIKASI) |
| Budaya safety (proxy) | rasio pelaporan insiden per unit + ketuntasan RTL |

### Sub-dasbor 2 — Smart EMR & Clinical Quality STARKES + AI

| Metrik | Sumber |
|---|---|
| Kunjungan aktif (RI/RJ/IGD) | `pasien.KunjunganPasien` |
| BOR / keterisian bed | `pasien.Bed`, `pasien.BookingKamar` |
| Kelengkapan CPPT per kunjungan | `pasien.CPPT` |
| Asesmen risiko klinis (jatuh, dekubitus, gizi) | `pasien.AsesmenRisikoKlinis` |
| Resep elektronik & antrean farmasi | `pasien.ResepElektronik`, `pasien.ResepDetail` |
| Discharge planning / resume | `pasien.DischargeRecord` |
| Kepatuhan PPA (kredensial & STR) | `accounts.NakesCredential` via `rekap_kps_unit` |
| Klaim/ billing belum tutup | `pasien.BillingItem` |

### Sub-dasbor 3 — Electronic Accreditation Document & Automation Hub + AI

| Metrik | Sumber |
|---|---|
| Cakupan EP terisi per standar | `StandardItem`, `QualityRecord` |
| EP tanpa bukti / bukti kadaluarsa | `EvidenceReq`, `EvidenceFile` |
| Dokumen bukti per pokja | `EvidenceFile`, `Category` |
| Kesiapan per bab STARKES | agregat `StandardItem` per `Category` |
| Temuan audit / log aktivitas | `AuditLog` |
| Status laporan mutu terbit | `LaporanMutu` (TERBIT) |

## 5. Tafsir yang perlu dikonfirmasi

**"dasbor tanpa tulisan Side"** — tafsir kerja: halaman hero tidak memakai sidebar navigasi (full-bleed), dan dari situ masuk ke modul lama yang tetap bersidebar. Dua kemungkinan lain: (a) menghapus label/teks tertentu di sidebar, (b) menghapus kata "Side" pada judul kartu. Tafsir (a) dipakai di rencana karena paling masuk akal dengan kalimat "selanjutnya masuk ke yang sudah ada".

**"Unit Contoh"** — tafsir kerja: unit aktif yang sudah punya data (risiko / indikator / EP). Hub menampilkan pemilih unit; setiap unit punya hero sendiri.

**"+ AI"** — bukan chatbot baru. Memakai endpoint DeepSeek yang sudah ada (`/ai/...`), ditambah satu endpoint ringkasan naratif per unit.

## 6. Risiko teknis

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Query meledak (snapshot 3 portal × N unit) | Halaman lambat, Supabase kena limit | Bangun snapshot dalam satu fungsi, batasi ≤12 query/halaman, uji `assertNumQueries`, cache 60 detik |
| Foto RS belum ada | Latar rusak/kosong saat deploy | Lapisan gradien + siluet SVG sebagai dasar; foto hanya penimpa opsional |
| Halaman tanpa sidebar memutus navigasi | User tersesat | Top bar ramping: pemilih unit + tombol "Masuk ARIMA" |
| Angka 0 disalahartikan sebagai "bagus" | Keputusan salah | Status eksplisit "belum ada data" beda dari nilai 0 |
| Scope unit bocor | User unit A melihat unit B | Pakai `profile.is_unit_scoped` seperti dashboard sekarang, diuji |
| Nama "STARKES" dipakai di UI | Salah label bila standar berubah | Ambil label dari `Category`/`Framework`, jangan hardcode |

## 7. Rekomendasi urutan

1. Shell tanpa sidebar + tokens warna (dasar semua halaman).
2. Hub utama (judul besar + 3 kartu portal + pemilih unit).
3. Sub-dasbor 1 (data risiko paling lengkap).
4. Sub-dasbor 3 (data EP paling stabil).
5. Sub-dasbor 2 (butuh agregasi `pasien`, paling banyak query).
6. Endpoint AI ringkasan + poles gerak/print/responsif.

Rencana kerja rinci: `docs/superpowers/plans/2026-10-20-dasbor-integrated-control.md`.
