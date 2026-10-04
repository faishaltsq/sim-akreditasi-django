# Rencana Pengujian Sprint & Rilis Komprehensif (All Components)
## Sistem Informasi Manajemen Akreditasi & Layanan Pasien (ARIMA)

**Dokumen Rencana:** Release Test Plan Q4-2026 / Sprint 12  
**Target Rilis:** Versi 2.4.0 (Pembaruan Alur Klinis & Tata Kelola Terpadu)  
**Kapasitas Terjadwal:** 75% Kerja Terencana | 25% Cadangan (Buffer)  

---

### 1. Dekomposisi Fitur per Komponen

Setiap fitur didekomposisi ke dalam 6 kategori pengujian wajib:

#### Komponen 1: Manajemen Pasien & Layanan Klinis (`pasien`)
- **Happy Path:**
  - Pendaftaran pasien baru -> cetak kartu antrean -> routing triage IGD -> pemeriksaan dokter -> order penunjang -> resep farmasi -> pembayaran kasir.
  - Alur Rawat Jalan: Reservasi bed dari poliklinik -> pembuatan General Consent -> Check-in Rawat Inap (`BookingKamar` status `CHECKIN`).
- **Validasi:**
  - NIK wajib 16 digit angka, tanggal lahir tidak boleh masa depan, pemilihan kelas ruangan harus sesuai penjamin pasien.
- **Error Conditions:**
  - Penanganan graceful saat tabel/kolom migrasi baru belum ter-apply di production (fallback default, bebas error 500).
  - Penanganan saat stok obat farmasi kosong atau kamar tidak memiliki bed berstatus TERSEDIA.
- **Edge Cases:**
  - Nama pasien dengan karakter tanda petik/apostrof (`O'Connor`, `Siti Ma'ruf`), input skala nyeri batas ekstrem (0 dan 10), nilai GCS minimal (E1V1M1 = 3).
- **Concurrency / Race Condition:**
  - Dua staf admin memesan bed yang sama persis dalam waktu bersamaan (`BookingKamar.objects.select_for_update`).
  - Pembatalan booking bersamaan dengan proses check-in ranap.
- **Integration Points:**
  - Sinkronisasi otomatis status kunjungan pasien (`DAFTAR` -> `TRIAGE` -> `ASESMEN` -> `RANAP` -> `PULANG`).
  - Pemotongan status tempat tidur dari `TERSEDIA` menjadi `DIBOOKING` lalu `TERISI`.

#### Komponen 2: Akreditasi STARKES & Matriks PDCA (`akreditasi`)
- **Happy Path:**
  - Pengisian skor EP (0, 5, 10) -> kalkulasi progres Bab STARKES otomatis -> pengunggahan berkas bukti RDWOS -> tautan bukti regulasi antar-unit.
- **Validasi:**
  - Format file bukti hanya PDF, JPG, PNG; ukuran berkas maksimum 10MB.
- **Error Conditions:**
  - Kegagalan upload ke Supabase Storage (koneksi putus) menghasilkan pesan peringatan tanpa merusak record metadata database.
- **Edge Cases:**
  - Standar EP dengan 0 berkas bukti (harus berstatus "Belum Ada Bukti", bukan crash pembagian nol pada persentase).
- **Concurrency / Race Condition:**
  - Dua asesor memasukkan skor cepat (*quick score*) pada EP yang sama secara simultan.
- **Integration Points:**
  - Kalkulasi agregat capaian Rumah Sakit secara instan saat skor tiap EP diperbarui.

#### Komponen 3: Manajemen Risiko & Mutu (`risiko`, `indikator`)
- **Happy Path:**
  - Registrasi risiko baru -> kalkulasi tingkat bahaya (Dampak x Probabilitas) -> penentuan rencana mitigasi -> pemantauan capaian indikator mutu bulanan.
- **Validasi:**
  - Matriks risiko wajib memiliki unit kerja penanggung jawab dan PIC yang valid.
- **Error Conditions:**
  - Penanganan formula indikator dengan penyebut (*denominator*) nol agar tidak memicu `ZeroDivisionError`.
- **Concurrency / Race Condition:**
  - Pembaruan capaian indikator oleh PIC unit bertepatan dengan rekap otomatis komite mutu.
- **Integration Points:**
  - Pemetaan otomatis risiko klinis unit kerja ke dalam dashboard keselamatan pasien.

#### Komponen 4: Kontrol Akses & Hierarki Organisasi (`accounts`)
- **Happy Path:**
  - Login multi-peran (Superadmin, Direktur, Dokter DPJP, Perawat, Asesor Mutu) diarahkan sesuai dashboard masing-masing.
- **Validasi:**
  - Penguncian mode *Survey Freeze*: Saat aktif, seluruh fungsi pengubahan data dokumen dan EP berubah menjadi *Read-Only*.
- **Error Conditions:**
  - Akses URL langsung tanpa izin role tertentu mengembalikan respon `403 Forbidden` terstruktur, bukan error 500.
- **Edge Cases:**
  - User dengan multi-unit kerja dialihkan ke unit kerja primer saat sesi baru dimulai.
- **Concurrency / Race Condition:**
  - Perubahan hak akses peran saat pengguna bersangkutan sedang aktif login.
- **Integration Points:**
  - Penegakan filter data otomatis (*unit scoping*) pada setiap query queryset Django.

#### Komponen 5: Layanan Cerdas AI (`ai`)
- **Happy Path:**
  - Pembuatan draf rencana mitigasi risiko otomatis via LLM backend -> respon terstruktur JSON -> ditampilkan pada modal antarmuka.
- **Validasi:**
  - Seluruh data identitas pasien (NIK, Nama, Tanggal Lahir) wajib disanitasi/diredaksi dengan regex sebelum payload dikirim ke API AI.
- **Error Conditions:**
  - Penanganan timeout API AI eksternal atau rate-limit (fallback pesan informatif ke pengguna).

---

### 2. Requirements-to-Test Coverage Mapping (Traceability Matrix)

| ID Kebutuhan | Komponen | Deskripsi Kebutuhan | ID Kasus Uji | Tipe Pengujian | Lokasi File Tes | Status |
|---|---|---|---|---|---|---|
| **REQ-PAS-01** | Pasien | Reservasi bed kamar ranap dengan batas waktu | `TC-BK-001` | Integration | `pasien/tests_booking.py` | **PASS** |
| **REQ-PAS-02** | Pasien | Persetujuan General Consent Ranap 7-Klausul | `TC-GC-001` | Integration | `pasien/tests_consent.py` | **PASS** |
| **REQ-PAS-03** | Pasien | Input TTV lengkap dengan GCS & Skala Nyeri | `TC-IGD-001`| Integration | `pasien/tests_igd_advanced.py` | **PASS** |
| **REQ-PAS-04** | Pasien | Alert otomatis jika order penunjang berstatus kritis | `TC-CV-001` | Integration | `pasien/tests_igd_advanced.py` | **PASS** |
| **REQ-PAS-05** | Pasien | SOAP rawat jalan tersinkronisasi ke CPPT | `TC-RJ-001` | Integration | `pasien/tests_rajal_advanced.py`| **PASS** |
| **REQ-AKR-01** | Akreditasi | Matriks PDCA 7-kolom render tanpa error | `TC-PDCA-01` | Integration | `akreditasi/tests.py` | **PASS** |
| **REQ-AKR-02** | Akreditasi | Scoring otomatis Bab STARKES matematis tepat | `TC-SCOR-01` | Unit | `akreditasi/tests.py` | **PASS** |
| **REQ-ACC-01** | Accounts | Enforce survey freeze mode (read-only locks) | `TC-SEC-01` | Integration | `accounts/tests.py` | **PASS** |
| **REQ-ACC-02** | Accounts | Pembatasan unit-scoping pada user berstatus unit | `TC-SEC-02` | Integration | `accounts/tests.py` | **PASS** |
| **REQ-RIS-01** | Risiko | Kalkulasi risk grading matrix (Dampak x Peluang) | `TC-RIS-01` | Unit | `akreditasi/tests.py` | **PASS** |
| **REQ-AI-01**  | AI | Sanitasi NIK & nama sebelum kirim ke LLM | `TC-AI-01` | Unit | `akreditasi/tests.py` | **PASS** |
| **REQ-E2E-01** | Pasien | Smoke E2E 25 rute utama pasca-migrasi | `TC-SMK-25` | E2E Smoke | Inline CI Harness | **PASS** |

---

### 3. Lembar Kerja Estimasi Usaha (Effort Estimation Worksheet)

| Kategori Aktivitas Pengujian | Volume Item | Jam per Item | Total Jam Terencana |
|---|---|---|---|
| Penulisan Unit Test Baru (Model & Logika) | 12 tes | 0.75 jam | 9.0 jam |
| Penulisan Integration Test (Transaksi Multi-Model) | 8 tes | 1.50 jam | 12.0 jam |
| Pembuatan Skenario E2E Smoke (Playwright) | 4 skenario | 2.50 jam | 10.0 jam |
| Pengujian Sesi Eksploratori Fitur Baru (Klinis & IGD) | 2 sesi | 2.00 jam | 4.0 jam |
| Penyiapan Lingkungan & Fixture Data Bersama | 1 paket | 5.00 jam | 5.0 jam |
| **Subtotal Jam Terencana (Planned Work)** | | | **40.0 jam** |
| **Alokasi Cadangan (Buffer untuk Bug Fixing & Verifikasi 25%)** | | | **13.3 jam** |
| **Total Kapasitas Dibutuhkan** | | | **53.3 jam** |

---

### 4. Matriks Prioritas Pengujian (Risk x Effort)

Berdasarkan perpaduan skor risiko dan estimasi usaha:

```
Tinggi │ [DO SECOND]                    │ [DO THIRD]
       │ • Triage & Nilai Kritis IGD    │ • Alur Kasir & Billing Otomatis
       │ • Kontrol Akses Survey Freeze  │ • Concurrency Booking Bed Ranap
R      ├────────────────────────────────┼─────────────────────────────────
I      │ [DO FIRST]                     │ [DEFER / JADWALKAN NANTI]
S      │ • Defense Guarding Kolom/Model │ • Uji Beban Lonjakan 1000 User
I      │ • Traceability 25 Rute Kritis  │ • Otomatisasi Visual Regression
K      │ • Validasi NIK/RM Pasien       │ • Export Laporan Format Kustom
O      │                                │
Rendah └────────────────────────────────┴─────────────────────────────────
       Rendah                        Usaha                        Tinggi
```

**Aturan Keputusan:**
1. **DO FIRST:** Perbaikan bug 500 & pengujian smoke 25 rute utama diselesaikan sebelum pekerjaan lain.
2. **DO SECOND:** Uji kontrol akses peran dan validasi klinis kritis IGD.
3. **DO THIRD:** Uji konkurensi booking bed dan transaksi kasir.
4. **DEFER:** Pengujian visual layout kosmetik ditunda ke sprint pemeliharaan.

---

### 5. Alokasi Sumber Daya

| Peran Pelaksana | Nama / Tim | Kapasitas Tersedia | Alokasi Terencana (75%) | Cadangan / Buffer (25%) |
|---|---|---|---|---|
| **Lead QA / SDET** | SDET Lead | 30 Jam | 22.5 Jam (Otomasi & E2E) | 7.5 Jam (Investigasi Flake) |
| **Backend Engineer** | Backend Lead | 25 Jam | 18.7 Jam (Unit & Model Test) | 6.3 Jam (Bug Triage & Hotfix) |
| **Total Tim** | | **55 Jam** | **41.2 Jam** | **13.8 Jam** |

*Prinsip: Tidak ada anggota tim yang dijadwalkan 100% dari jam kerjanya; buffer 25% melekat pada masing-masing personil.*

---

### 6. Jadwal 2 Minggu (Sprint Schedule) dengan Buffer

- **Hari 1 - 2 (Senin - Selasa, Minggu I):**
  - Setup fixture data dan lingkungan test lokal.
  - Eksekusi audit 25 rute kritis pasca-migrasi skema.
- **Hari 3 - 5 (Rabu - Jumat, Minggu I):**
  - Implementasi unit test model `BookingKamar` dan `GeneralConsentRawatInap`.
  - Penulisan tes integrasi alert nilai kritis IGD dan alur SOAP rawat jalan.
- **Hari 6 - 7 (Senin - Selasa, Minggu II):**
  - Pengujian integrasi Kontrol Akses Hierarki & Survey Freeze Mode.
  - Sesi pengujian eksploratori alur pendaftaran hingga kasir.
- **Hari 8 - 9 (Rabu - Kamis, Minggu II):**
  - **Aktivasi Jam Cadangan (Buffer):** Verifikasi perbaikan defek yang ditemukan, regresi ulang PR.
- **Hari 10 (Jumat, Minggu II):**
  - Konfirmasi akhir kriteria keluar (*Exit Criteria*).
  - Eksekusi pipeline CI lengkap dan pengesahan rilis ke produksi.

---

### 7. Checklist Kriteria Masuk & Keluar (Entry & Exit Checklists)

#### Kriteria Masuk (Sprint Ready):
- [x] Spesifikasi revisi alur klinis dan PDCA tersedia.
- [x] Migrasi database `0005` dan `0006` lulus pengujian lokal.
- [x] Server dev lokal dapat merender form login tanpa error.

#### Kriteria Keluar (Ship / Release Ready):
- [x] Seluruh 15 kasus uji unit/integrasi lulus 100%.
- [x] 25/25 rute URL aplikasi mengembalikan status HTTP 200 (Zero HTTP 500).
- [x] Tidak ada data pasien riil yang terekspos tanpa sanitasi.
- [x] Skrip deployment `build_vercel.sh` dan `config/wsgi.py` terpasang auto-migrate.
- [x] Branch `master` bersih dan tersinkronisasi ke remote repository.
