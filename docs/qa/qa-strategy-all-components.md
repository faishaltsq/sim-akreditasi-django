# Dokumen Strategi QA Multi-Quarter (Q4 2026 - Q2 2027)
## Aplikasi Terpadu Manajemen Risiko & Tata Kelola Dokumen Akreditasi (ARIMA / SIK AP)

**Pemilik Dokumen:** Tim QA & Lead Engineering  
**Versi:** 2.0  
**Tanggal Efektif:** 04 Oktober 2026  
**Status:** Disetujui  

---

### 1. Executive Summary

Dokumen strategi ini menetapkan arah jaminan mutu teknis untuk aplikasi ARIMA (SIK AP RS). Meliputi 33 model data dan 250 rute URL pada modul Manajemen Pasien (Pendaftaran, IGD, Rajal, Ranap, Farmasi), Akreditasi STARKES (PDCA, EP, Dokumen, Scoring), Akun & Kontrol Akses (Hierarki, RBAC, Survey Freeze), Manajemen Risiko & Mutu (Risk Register, Insiden, Indikator), dan Integrasi AI (DeepSeek). Strategi ini mentransformasi pengujian dari dominasi manual menjadi piramida uji terautomasi dengan target rasio 70% Unit, 20% Integrasi, dan 10% E2E, menekan tingkat defek produksi di bawah 3% serta menjaga durasi CI di bawah 10 menit.

---

### 2. Scope & Objectives

#### Cakupan (In-Scope):
1. **Modul Pasien:** Manajemen data induk pasien, validasi NIK/RM, reservasi tempat tidur (`BookingKamar`), General Consent ranap (`GeneralConsentRawatInap`), alur Triage & EMR IGD (GCS, Nyeri, Critical Value), Poliklinik Rawat Jalan (Antrean DPJP, SOAP ke CPPT, Rujukan), Resep Elektronik & Farmasi, serta Billing/Kasir.
2. **Modul Akreditasi:** 16 Bab Standar STARKES, Matriks PDCA 7-kolom, Elemen Penilaian (EP) CRUD, pengunggahan & penautan berkas bukti dokumen hub, profil RS & Renstra 2026-2030, serta kalkulasi scoring otomatis kelulusan.
3. **Modul Akun & Kontrol:** RBAC 10 peran nakes/staf, pemetaan hierarki unit kerja 4-level, *survey freeze mode* (pembekuan edit saat survei akreditasi), serta audit log.
4. **Modul Risiko & Mutu:** Risk register (inherent & residual risk matrix), pelaporan insiden keselamatan pasien (IKP), pemantauan indikator mutu nasional/unit, dan evaluasi berkala.
5. **Modul AI:** Analisis mitigasi risiko otomatis, formulasi rencana aksi PDCA, grading keparahan insiden otomatis, dan telaah regulasi RDWOS via DeepSeek API backend.

#### Di Luar Cakupan (Out-of-Scope):
- Integrasi perangkat keras printer thermal fisik (diverifikasi pada tingkat format payload ESC/POS / PDF).
- Infrastruktur cloud provider backend Supabase/Railway tingkat kernel OS (dicakup oleh SLA vendor).

#### Sasaran Terukur (Objectives):
1. Menurunkan *Defect Escape Rate* ke lingkungan produksi hingga < 3% pada akhir Q1 2027.
2. Meningkatkan cakupan kode otomatis (*code coverage*) inti dari 15 test saat ini menjadi minimum 80% pada logika bisnis kritis.
3. Memastikan tingkat kegagalan non-deterministik (*flakiness rate*) < 1.5% di CI pipeline.
4. Memangkas waktu regresi rilis dari 3 hari kerja manual menjadi < 15 menit otomatis di CI.

---

### 3. Test Levels & Types

| Level Pengujian | Ruang Lingkup Validasi | Pemilik | Framework & Alat | Target Rasio | Frekuensi Eksekusi |
|---|---|---|---|---|---|
| **Unit Test** | Validasi model Django, metode `save()`, kalkulasi skor akreditasi, kalkulasi BOR/LOS, aturan bisnis triage | Software Engineer | `pytest-django`, Django TestCase | 70% (~140 tes) | Setiap commit / pre-push |
| **Integration Test** | Aliran transaksi multi-model (Booking ke Checkin Ranap, Order Penunjang ke Billing, Transisi Status Kunjungan) | SE + QA Engineer | Django Test Client, SQLite Memory | 20% (~40 tes) | Setiap Pull Request |
| **End-to-End (E2E)** | Alur kritis pengguna menyeluruh (Pendaftaran -> IGD -> Admisi Ranap -> Pulang) | QA Automation | Playwright TS (Headless) | 10% (~20 skenario) | Pre-deploy & Nightly |
| **API Contract Test** | Endpoint JSON internal (Cek NIK, Bed Tersedia, ICD-10 autocomplete) | SE | Schemathesis, Django Client | Per endpoint aktif | Setiap Pull Request |
| **Security & RBAC** | Verifikasi pencegahan privilege escalation, audit logging, penegakan unit scoping | QA Security | Custom Test Runner & Bandit | Modul akun & audit | Setiap build rilis |
| **Performance Test** | Ketahanan akses bersamaan pada Matriks PDCA & Dashboard Antrean Pasien | SDET / DevOps | k6 CLI | Endpoint terpadat | Pra-survei & bulanan |

---

### 4. Test Pyramid Analysis

#### Kondisi Saat Ini (Current State - Q4 2026):
- Unit Tests: 7 kasus uji (47%)
- Integration Tests: 8 kasus uji (53%)
- E2E Tests: 0 kasus uji formal CI (hanya smoke script ad-hoc)
- Total Kasus Uji: 15 kasus uji
- Bentuk Piramida: **Hourglass Terbalik / Cincang** (volume sangat minim, disparitas tinggi dibanding 250 rute rujukan).

#### Target Kondisi Ideal (Target State - Akhir Q1 2027):
- **Unit Tests:** 140+ kasus uji (70%) — fokus kalkulasi rumus, sanitasi input, method model.
- **Integration Tests:** 40+ kasus uji (20%) — fokus interaksi DB multi-tabel, transaksional atomik, penegakan izin RBAC per view.
- **E2E Tests:** 20 skenario terfokus (10%) — jalur kritis penerimaan pasien, pengisian matriks, pelaporan insiden.
- Total Volume: ~200 kasus uji otomatis.
- Target Durasi CI: < 4 menit untuk Unit/Integrasi, < 6 menit untuk E2E.

#### Rencana Transisi:
1. Menghindari pembengkakan E2E dengan melarang pengujian aturan validasi field di level browser (dialihkan ke Unit Test form/model).
2. Membangun fondasi fixture data bersama (`conftest.py` / factory fixtures) untuk meniadakan perulangan kode setup.

---

### 5. Risk Assessment Matrix (5x5)

| Komponen / Fitur | Dampak (1-5) | Peluang (1-5) | Skor Risiko | Tingkat Risiko | Strategi Pengujian |
|---|---|---|---|---|---|
| **Alur Billing & Kasir Pasien** | 5 (Katastropik) | 3 (Mungkin) | **15** | **CRITICAL** | Unit test kalkulasi tarif, integrasi atomik, audit concurrency |
| **Pemesanan Kamar & Check-in Ranap** | 5 (Katastropik) | 3 (Mungkin) | **15** | **CRITICAL** | Concurrency race condition test, validasi status bed |
| **Kontrol Akses Hierarki & Survey Freeze** | 5 (Katastropik) | 2 (Jarang) | **10** | **HIGH** | Matrix testing hak akses tiap role, boundary unit-scoping |
| **Triage & Nilai Kritis IGD** | 4 (Besar) | 3 (Mungkin) | **12** | **HIGH** | Automasi integrasi alert dokter, pengujian batas skor EWS/GCS |
| **Scoring Otomatis STARKES & Rekap** | 4 (Besar) | 2 (Jarang) | **8** | **MEDIUM** | Pengujian regresi matematis skor kelulusan, pembulatan |
| **Integrasi Sanitasi AI DeepSeek** | 4 (Besar) | 2 (Jarang) | **8** | **MEDIUM** | Contract test mocking, uji regex redaksi data privat pasien |
| **Pencarian Autocomplete ICD-10** | 2 (Kecil) | 3 (Mungkin) | **6** | **MEDIUM** | Unit test response limit, sanitasi karakter simbol |
| **Profil Rumah Sakit & Master Kamar** | 2 (Kecil) | 1 (Sangat Jarang) | **2** | **LOW** | Smoke test form CRUD dasar |

---

### 6. Environment Strategy

1. **Local Dev (SQLite / Docker Postgres):**
   - Fokus: Loop umpan balik cepat pengembang (TDD), eksekusi unit test < 30 detik.
   - Data: Seed fixtures standar (`seed_data`, `seed_nakes`, `seed_hospital_type_b`).
2. **CI Pipeline (GitHub Actions - Ephemeral Container):**
   - Fokus: Linting, validasi migrasi skema DB, unit & integration tests, audit keamanan statis.
   - Isolasi: Database Postgres in-memory ephemeral (dibuat dan dihapus tiap run).
3. **Staging (Railway Staging / Vercel Preview):**
   - Fokus: E2E Playwright, pengujian otentikasi nyata dengan DB Supabase Staging, audit performa k6.
   - Pemicu: Otomatis pada setiap Pull Request ke branch `master`.
4. **Production (Railway / Vercel Live):**
   - Fokus: Health check sintetis pasca-deploy, audit uptime URL, pemantauan error log Sentry.

---

### 7. Tool Selection Rationale

| Kriteria Evaluasi (Bobot) | pytest-django | Django Native TestCase | Playwright | Cypress | Selenium |
|---|---|---|---|---|---|
| Keselarasan Ekosistem (25%) | 5 (1.25) | 5 (1.25) | 4 (1.00) | 3 (0.75) | 3 (0.75) |
| Kecepatan Eksekusi (20%) | 5 (1.00) | 4 (0.80) | 5 (1.00) | 3 (0.60) | 2 (0.40) |
| Kemudahan Pemeliharaan (20%) | 4 (0.80) | 3 (0.60) | 5 (1.00) | 4 (0.80) | 2 (0.40) |
| Dukungan Komunitas & CI (15%) | 5 (0.75) | 5 (0.75) | 5 (0.75) | 5 (0.75) | 4 (0.60) |
| Ketahanan Locator/Flake (10%) | N/A | N/A | 5 (0.50) | 3 (0.30) | 2 (0.20) |
| Biaya Lisensi (10%) | 5 (0.50) | 5 (0.50) | 5 (0.50) | 4 (0.40) | 5 (0.50) |
| **Total Skor Terbobot** | **4.30** | **3.90** | **4.75** | **3.60** | **2.85** |

*Keputusan Stack:*
- **Backend Test Framework:** `pytest-django` + `pytest-xdist` untuk paralelisasi.
- **Frontend / E2E Engine:** `Playwright` (TypeScript) dengan locator semantik berbasis aksesibilitas (`getByRole`, `getByLabel`).

---

### 8. CI Scaling Levers

1. **Paralelisasi DB Worker:** Menjalankan unit test dengan opsi multi-thread Django (`manage.py test --parallel auto`).
2. **Test Impact Analysis (TIA):** Menjalankan subset pengujian yang hanya berkaitan langsung dengan file yang diubah pada PR (menggunakan git diff file mapping).
3. **Artifact Caching:** Caching wheel direktori `.venv` dan browser binary Playwright pada GitHub Actions Runner untuk menghemat 2.5 menit proses setup per build.
4. **Selective Gating:** E2E visual dan load test hanya dieksekusi terjadwal (nightly build) atau pada PR dengan label `release`.

---

### 9. Entry & Exit Criteria

#### Kriteria Masuk (Entry Criteria):
- [ ] Kode sumber berhasil dikompilasi / lolos pemeriksaan sintaks `manage.py check`.
- [ ] Migrasi database lokal dan staging bersih (`makemigrations --check` exit 0).
- [ ] Tidak ada dependensi usang atau kerentanan kritis CVE (`pip-audit` bersih).
- [ ] Data seed pengujian tersedia dan tervalidasi.

#### Kriteria Keluar (Exit Criteria):
- [ ] 100% kasus uji level Unit dan Integrasi lolos hijau.
- [ ] Seluruh skenario E2E alur kritis pasien dan matriks akreditasi berhasil tanpa kegagalan.
- [ ] Nol (0) temuan bug keparahan P0 (Critical - Crash/Data Loss) dan P1 (High - Fitur Utama Macet).
- [ ] Waktu respon rata-rata 25 endpoint utama di bawah 800ms.
- [ ] Log audit memverifikasi tidak ada kebocoran kunci otentikasi atau data pasien polos.

---

### 10. Quality Gates & Definition of Done (DoD)

1. **PR Quality Gate (Bloker Penggabungan Kode):**
   - Lolos seluruh test suite Unit & Integrasi.
   - Penambahan kode baru wajib disertai unit test (Coverage tidak boleh turun).
   - Zero linter warning pada Ruff / Flake8.
   - Minimum 1 persetujuan review dari Tech Lead / QA.
2. **Merge Gate (Menuju Branch Master):**
   - E2E smoke test pada 25 rute utama lolos 100%.
   - Migrasi database teruji sukses *forward* dan *reverse*.
3. **Release Gate (Staging ke Produksi):**
   - Seluruh kriteria keluar terpenuhi.
   - Backup database otomatis Supabase terverifikasi aktif.
   - Dokumen *release notes* dan panduan pembaruan fitur telah disahkan.

---

### 11. Metrics & KPIs

| Metrik Kualitas | Definisi | Target Operasional | Frekuensi Evaluasi |
|---|---|---|---|
| **Code Coverage** | Persentase baris kode ter-cover pengujian otomatis | >= 80% (Modul Kritis), >= 65% (Total) | Setiap PR |
| **Rasio Piramida Uji** | Proporsi Unit : Integrasi : E2E | 70% : 20% : 10% (Toleransi ±5%) | Bulanan |
| **Flakiness Rate** | Persentase tes yang gagal lalu lolos pada rerun | < 1.5% dari seluruh eksekusi | Mingguan |
| **Defect Escape Rate** | Persentase defek yang baru ditemukan di Produksi | < 3% dari total temuan defek | Per Rilis |
| **CI Wall-Clock Time** | Durasi pipeline dari push hingga status final | < 8 menit (PR), < 15 menit (Full) | Mingguan |
| **MTTR (Mean Time to Repair)**| Rata-rata waktu deteksi hingga perbaikan P0/P1 live | < 3 jam (P0), < 12 jam (P1) | Per Insiden |

---

### 12. Timeline & Milestones

- **Fase 1: Fondasi & Stabilisasi (Bulan 1 / Okt 2026):**
  - Implementasi fixture pabrik data bersama (`factory_boy` / seed Django).
  - Pemasangan CI pipeline GitHub Actions dengan gate Unit Test terisolasi.
  - Baseline otomatisasi 25 rute kritis (mencegah error 500 berulang).
- **Fase 2: Perluasan Integrasi & Modul Kritis (Bulan 2-3 / Nov-Des 2026):**
  - Penulisan 40 tes integrasi transaksi Billing, Booking Bed, dan Matriks PDCA.
  - Implementasi RBAC security test suite menyeluruh.
- **Fase 3: E2E Playwright & Automasi Karantina (Bulan 4-5 / Jan-Feb 2027):**
  - Pembentukan 20 skenario E2E Playwright dengan selector stabil.
  - Implementasi sistem karantina tes flakiness otomatis.
- **Fase 4: Optimasi & Continuous Audit (Bulan 6 / Mar 2027):**
  - Pemasangan uji performa k6 terotomasi berkala.
  - Tinjauan efektivitas strategi semesteran pertama.

---

### 13. Revision History

| Versi | Tanggal | Penulis | Perubahan Utama |
|---|---|---|---|
| 1.0 | 2026-09-24 | QA Lead | Dokumen inisiasi awal SIK AP akreditasi |
| 2.0 | 2026-10-04 | Lead Engineering & QA | Ekspansi menyeluruh ke seluruh modul (Pasien, STARKES, RBAC, AI, KPS), definisi piramida uji 70/20/10, dan integrasi penjaminan mutu pasca-investigasi error 500. |
