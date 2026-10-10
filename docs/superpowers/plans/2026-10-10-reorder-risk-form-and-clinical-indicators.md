# Implementation Plan: ARIMA v2.6 Risk Form Reordering & Clinical Indicators Expansion

## Context & Objectives
Based on two specification documents provided by the hospital quality & risk committee:
1. `Tolong lakukan perubahan urutan di arima.docx`:
   Reorganize the risk input flow in ARIMA v2.6 into a standardized, logical 7-step sequence (A to G):
   - **A. Identifikasi Risiko**: Unit Kerja, Masalah & Data Pendukung, Kategori Risiko, Jenis Risiko, Deskripsi Risiko.
   - **B. Penilaian Risiko Awal**: Dampak / Severity (1-5), Peluang / Likelihood (1-5), **Pengendalian yang Sudah Ada (Existing Control)**, Realtime Grading Score ($S \times O$).
   - **C. Pilihan Metode Evaluasi / Hiliran (Moved from Section E)**:
     - Choice pills: `[ Standar PDCA ]` | `[ 🗂️ FMEA Proaktif ]` | `[ 🔍 RCA Reaktif ]`.
     - When FMEA is chosen, expose **Detection ($D$)** input (1-5) and compute **RPN = $S \times O \times D$** dynamically.
     - Multidisciplinary team, failure modes & causes (+ AI FMEA assistant).
     - When RCA is chosen: investigation team, 5-Whys root cause (+ AI RCA assistant), corrective action plan (CAP).
   - **D. Indikator Mutu**: Indicator selection filtered by unit, categorized into 🟢 **INM** (Nasional), 🔵 **Indikator RS** (IMP-RS), 🔴 **Indikator Unit** (IMP-Unit), Target Capaian (%), and preset mitigation chips.
   - **E. Rencana Aksi & Mitigasi**: Strategi mitigasi, PJ mitigasi, Estimasi biaya, Rencana aksi (+ AI DeepSeek assistant), Target selesai.
   - **F. Penilaian Risiko Sisa (Residu Pasca Mitigasi)**: Dampak residu (1-5), Peluang residu (1-5), Deteksi residu (1-5 jika FMEA), RPN residu, Δ penurunan skor risiko.
   - **G. Evaluasi dan RTL**: Evaluasi capaian indikator mutu, RCA ulang (jika risiko berulang/menetap), Rencana Tindak Lanjut (RTL), PJ RTL.

2. `BAB  INDIKATOR RESIKO KLINIS.docx`:
   Implement and seed specific clinical quality indicators and risk profiles for 11 clinical service units:
   - Kamar Operasi (OK)
   - Perawatan Rawat Inap Bedah
   - Kamar Persalinan (VK)
   - Rawat Inap Pasca Persalinan (Nifas)
   - Kamar Hemodialisa (HD)
   - Rawat Inap Orthopedi
   - Perawatan Mata (Eye Care)
   - Rawat Inap Persyarafan (Neurologi)
   - Rawat Inap Jantung (Kardiologi)
   - Rawat Inap Penyakit Dalam (Interna)
   - Rawat Inap THT (Telinga Hidung Tenggorok)
   Each unit includes:
   - Evidence-based background (`Masalah & Data Pendukung` from real hospital operational sources).
   - 5 unit-specific clinical risks (total 55 clinical risks).
   - Structured quality indicators per category:
     - 🟢 **INM**: Indikator Nasional Mutu (2 indicators per unit with targets).
     - 🔵 **Indikator RS**: Indikator Mutu Prioritas Rumah Sakit (5 indicators per unit with targets).
     - 🔴 **Indikator Unit**: Indikator Mutu Spesifik Unit Kerja (5 indicators per unit with targets).
     (Total ~132 clinical quality indicators).

---

## Architecture & Database Changes

### 1. Data Model (`akreditasi/risiko_models.py`)
Add the following fields to `RisikoUnit`:
- `pengendalian_ada` (`models.TextField`, blank=True, default=''): Existing controls/SPO before mitigation (Section B).
- `deteksi_fmea` (`models.IntegerField`, null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]): Detection variable $D$ for FMEA (Section C).
- `deteksi_residual` (`models.IntegerField`, null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]): Residual detection $D_{res}$ for post-mitigation FMEA (Section F).
- `rpn_residual` (`models.IntegerField`, null=True, blank=True): Residual RPN ($S_{res} \times O_{res} \times D_{res}$) (Section F).
- `evaluasi_capaian` (`models.TextField`, blank=True, default=''): Evaluation text and indicator achievement review (Section G).
- `rca_ulang` (`models.TextField`, blank=True, default=''): Re-assessment root-cause analysis for persisting or recurrent risks (Section G).
- `rencana_tindak_lanjut` (`models.TextField`, blank=True, default=''): Follow-up action plan / RTL (Section G).
- `pj_rtl` (`models.CharField`, max_length=150, blank=True, default=''): Person in charge of follow-up / RTL (Section G).

Model Helper Properties:
- `rpn_calc`: Calculate $S \times O \times D$ dynamically if $D$ is present, fallback to `rpn_fmea` or $S \times O$.
- `rpn_residual_calc`: Calculate $S_{res} \times O_{res} \times D_{res}$.
- `skor_residual_label` & `skor_residual_color`: Consistent visual grading for residual scores.

### 2. Form Layout & Realtime JS (`templates/akreditasi/risiko_form.html`)
- Reorganize sections into sequential order A $\rightarrow$ B $\rightarrow$ C $\rightarrow$ D $\rightarrow$ E $\rightarrow$ F $\rightarrow$ G.
- In Section B: Add `pengendalian_ada` field with placeholder explaining existing SPO/controls.
- In Section C:
  - Place method toggle pills `[ Standar PDCA ] | [ 🗂️ FMEA Proaktif ] | [ 🔍 RCA Reaktif ]`.
  - When FMEA is active: render Detection $D$ slider (1 to 5) with descriptive ticks (1 = Sangat Mudah Terdeteksi, 5 = Hampir Mustahil Terdeteksi).
  - Calculate RPN in real time: `RPN = Dampak (S) × Probabilitas (O) × Deteksi (D)`. Update RPN badge and priority indicator.
  - Tim FMEA, Mode Kegagalan & Efek + AI FMEA generator.
  - When RCA is active: Tim RCA, 5-Whys Root Cause (+ AI RCA generator), Corrective Action Plan.
- In Section D:
  - Indikator Mutu selection with colored category badges: 🟢 `[INM]`, 🔵 `[Indikator RS]`, 🔴 `[Indikator Unit]`.
  - Target Capaian (%) field.
  - Preset quick mitigation action chips.
- In Section E:
  - Strategi Mitigasi, PJ Mitigasi, Estimasi Biaya, Rencana Aksi (+ AI DeepSeek button), Target Selesai.
- In Section F:
  - Residual Risk Assessment (Dampak Residu, Probabilitas Residu, Deteksi Residu if FMEA).
  - Realtime visual comparison: Inherent Risk Score vs Residual Risk Score (showing reduction).
- In Section G:
  - Evaluasi capaian indikator mutu.
  - RCA ulang field.
  - Rencana Tindak Lanjut (RTL) & PJ RTL.

### 3. Views & Controller Updates (`akreditasi/risiko_views.py`)
- Update `risiko_input`:
  - Handle saving of `pengendalian_ada`, `deteksi_fmea`, `deteksi_residual`, `rpn_residual`, `evaluasi_capaian`, `rca_ulang`, `rencana_tindak_lanjut`, and `pj_rtl`.
  - Calculate and validate RPN ($S \times O \times D$) if FMEA is selected.
- Update `risiko_evaluasi`:
  - Add fields for Section F (Residual S, O, D) and Section G (Evaluasi, RCA Ulang, RTL, PJ RTL) to complete the PDCA cycle.
- Update `risiko_detail`:
  - Render sections A to G cleanly in card format, displaying existing controls, FMEA Detection and RPN, linked indicators, residual scores, and RTL.
- Update `risiko_laporan`:
  - Reflect existing controls, FMEA RPN & SOD, and RTL in Section 5 monitoring table.

### 4. Database Seeding (`akreditasi/management/commands/seed_bab_clinical_indicators.py`)
- Implement a comprehensive seeding command for the 11 clinical units in `BAB  INDIKATOR RESIKO KLINIS.docx`:
  1. Map / auto-create 11 units in local SQLite and Supabase production:
     - `IBS` (Kamar Operasi / OK)
     - `BANGSAL-BEDAH` (Perawatan Rawat Inap Bedah)
     - `VK` / `RUANG-BERSALIN-VK` (Kamar Persalinan VK)
     - `RUANG-NIFAS` (Rawat Inap Pasca Persalinan Nifas)
     - `HD` (Kamar Hemodialisa)
     - `BANGSAL-ORTHOPEDI` (Rawat Inap Orthopedi)
     - `BANGSAL-MATA` / `EYE-CARE` (Perawatan Mata)
     - `BANGSAL-SARAF` / `NEUROLOGI` (Rawat Inap Neurologi)
     - `BANGSAL-JANTUNG` / `KARDIOLOGI` (Rawat Inap Kardiologi)
     - `BANGSAL-INTERNA` / `PENYAKIT-DALAM` (Rawat Inap Penyakit Dalam)
     - `BANGSAL-THT` (Rawat Inap THT)
  2. Seed all 132 indicators:
     - Categorized with `jenis='NASIONAL'` (🟢 INM), `jenis='IMP_RS'` (🔵 Indikator RS), `jenis='IMP_UNIT'` (🔴 Indikator Unit).
     - Standard target values, numerators, denominators, and dimension of quality.
  3. Seed all 55 clinical risks:
     - Unit-specific `masalah` and `data_pendukung` directly from hospital source data.
     - 5 distinct clinical risks per unit.
     - Automatically link each risk to the corresponding primary unit indicator.

---

## Step-by-Step Task Breakdown

### Task 1: Update Model & Create Migration
- Modify `akreditasi/risiko_models.py` to add new fields (`pengendalian_ada`, `deteksi_fmea`, `deteksi_residual`, `rpn_residual`, `evaluasi_capaian`, `rca_ulang`, `rencana_tindak_lanjut`, `pj_rtl`).
- Add helper methods and properties for RPN calculation and residual evaluation.
- Run `makemigrations` to generate migration `0032_reorder_risk_fields_and_controls.py`.
- Run `migrate` on local SQLite database.

### Task 2: Create Seeding Script for 11 Clinical Units (55 Risks, 132 Indicators)
- Extract full dataset from `BAB  INDIKATOR RESIKO KLINIS.docx`.
- Write `akreditasi/management/commands/seed_bab_clinical_indicators.py` with idempotent `get_or_create` logic.
- Include candidate unit code resolution for both local and Supabase production environments.
- Execute seed script locally and verify database counts.

### Task 3: Restructure `risiko_form.html` to A-G Sequential Layout
- Reorder template blocks into sections:
  - `A. Identifikasi Risiko` (Unit, Masalah, Data, Banner, Kategori, Jenis, Deskripsi)
  - `B. Penilaian Risiko Awal` (Dampak, Probabilitas, Pengendalian yang Sudah Ada, Skor Matriks)
  - `C. Pilihan Metode Evaluasi / Hiliran` (Standar PDCA / FMEA Proaktif / RCA Reaktif with Detection slider & dynamic RPN calculation)
  - `D. Indikator Mutu` (Grouped dropdown by INM / RS / Unit, Target Capaian, Preset Action Chips)
  - `E. Rencana Aksi & Mitigasi` (Strategi, PJ, Biaya, Rencana Aksi + AI, Target Selesai)
  - `F. Penilaian Risiko Sisa` (Dampak Residu, Probabilitas Residu, Deteksi Residu, Realtime Residu Score)
  - `G. Evaluasi dan RTL` (Evaluasi capaian, RCA Ulang, RTL, PJ RTL)
- Update JavaScript event listeners for real-time RPN calculation ($S \times O \times D$), Detection slider sync, and residual comparison.

### Task 4: Update Views (`risiko_input`, `risiko_evaluasi`, `risiko_detail`, `risiko_laporan`)
- Update `risiko_input` in `akreditasi/risiko_views.py` to parse and store all new fields from sections B, C, F, and G.
- Update `risiko_evaluasi` view and template to support full post-mitigation evaluation (residual scoring and RTL).
- Update `risiko_detail.html` to display the newly ordered sections, existing controls, detection scores, and RTL cards.
- Update `risiko_laporan.html` to show existing controls and RTL columns in Section 5.

### Task 5: Testing & Automated Verification
- Write new unit tests in `akreditasi/tests_reorder_risk_flow.py` covering:
  - Model field validation and default values.
  - Form submission with sections A through G.
  - FMEA Detection slider and RPN computation ($S \times O \times D$).
  - Seeding command execution and linkage integrity for all 11 units.
- Run entire test suite (`tests_manajemen_risiko_515`, `tests_fmea_rca`, `tests_reorder_risk_flow`) and confirm 100% pass rate.

### Task 6: Deploy to Supabase Production & Vercel
- Apply migration `0032` to Supabase PostgreSQL database.
- Execute `seed_bab_clinical_indicators` against Supabase production database.
- Commit all changes and push to GitHub `master` branch.
- Verify live deployment on Vercel (`https://sim-akreditasi-django.vercel.app/`).

---

## Acceptance Criteria
1. `/risiko/baru/` reflects the exact 7-step sequence (A to G) specified in `Tolong lakukan perubahan urutan di arima.docx`.
2. Section B includes `Pengendalian yang Sudah Ada (Existing Control)`.
3. Section C includes FMEA Detection ($D$) input (1-5) and auto-computes $RPN = S \times O \times D$.
4. Section D groups indicators by category (🟢 INM, 🔵 Indikator RS, 🔴 Indikator Unit) with target percentage.
5. Sections F and G are properly integrated for residual risk and follow-up (RTL).
6. 11 clinical units from `BAB  INDIKATOR RESIKO KLINIS.docx` are fully seeded with 55 risks and 132 indicators.
7. All automated tests pass with 0 regressions.
8. Deployed and verified on production Supabase & Vercel.
