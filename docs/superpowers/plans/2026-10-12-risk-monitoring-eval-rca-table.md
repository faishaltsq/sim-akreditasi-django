# Implementation Plan: Comprehensive Risk Monitoring & Evaluation Table with Structured RCA (Fishbone) & Evidence Uploads

**Document Reference:** User attached Word document: `Berikut adalah kelengkapan tabel monitoring dan evaluasi beserta analisis RCA.docx`  
**Target Application:** ARIMA v2.6 (Hospital Accreditation & Clinical Risk Management System)  
**Author:** Apex (All-Role Engineering Operator)  
**Date:** October 12, 2026  
**Status:** READY FOR IMPLEMENTATION  

---

## 1. Executive Summary & Problem Context

The user uploaded an operational requirements document (`Berikut adalah kelengkapan tabel monitoring dan evaluasi beserta analisis RCA.docx`) from hospital quality and safety practitioners. It defines the exact standard for **Monitoring and Evaluation of Quality & Clinical Risks** along with **Root Cause Analysis (RCA)** required by accreditation surveyors (STARKES PMKP 7, PMKP 8, PMKP 12, and ISO 31000).

### Gap Analysis: Current State vs. Document Specification

| Element in Word Document | Current ARIMA State | Gap / Required Enhancement |
| :--- | :--- | :--- |
| **1. Dedicated Monitoring & Evaluation Table** | Mixed inside `risiko_laporan.html` (text report) & single risk view | Needs dedicated menu & interactive dashboard table with unit/period filters. |
| **2. Column: Quality Indicator & Target** | Linked via `indikator_mutu_terkait` FK | Display formatted: Indicator name + Target (%) + Unit. |
| **3. Column: Indicator Achievement (Capaian)** | `evaluasi_capaian` (unstructured TextField) | Add dedicated `capaian_nilai` (%), `bukti_capaian` (FileField for PDF/Img), and visual progress vs target. |
| **4. Column: Action Execution (Pelaksanaan)** | Section F table (`TindakLanjutRisiko`) | Aggregate status (*Dilakukan* / *Tidak Dilakukan*), display summary of actions taken, and link to uploaded evidence. |
| **5. Column: Structured RCA** | Plain text `akar_masalah_rca` / `rca_ulang` | Add structured Fishbone categories (*Manpower, Process/Method, Material, Machine, Environment/Behavior, System*) with UI badges and guided inputs. |
| **6. Column: Follow-up Plan (RTL)** | `rencana_tindak_lanjut` (plain text) | Add structured subfields: RTL description, PIC (`pj_rtl`), Deadline (`deadline_rtl`), Tracking Status (*BELUM / PROSES / SELESAI*), and `bukti_rtl` (FileField). |
| **7. Evidence Uploads Across All Columns** | Only exists in `TindakLanjutRisiko.bukti_upload` | Enable file upload (PDF, JPG, PNG, DOCX, video max 10MB) for: (1) Capaian Indikator, (2) Pelaksanaan, (3) RTL. |
| **8. Visual Risk Matrix Comparison** | Pre-mitigation matrix exists | Side-by-side Inherent vs Residual risk score badges with ISO 31000 colors (Red, Orange, Yellow, Green). |
| **9. Navigation & Sidebar** | Only "Laporan Manajemen Risiko" | Add explicit sidebar entry: **"Monitoring & Evaluasi Risiko"** under Manajemen Risiko group. |
| **10. Export Capability** | Print CSS only | Add one-click **Excel (.xlsx/CSV)** export and **Print / PDF report view**. |

---

## 2. Technical Architecture & Database Schema

### 2.1 Model Changes in `akreditasi/risiko_models.py` (`RisikoUnit`)

Add additive, backward-compatible fields to `RisikoUnit`:

```python
# In akreditasi/risiko_models.py -> class RisikoUnit

# ── Monitoring & Evaluasi Capaian Indikator ──
capaian_nilai = models.DecimalField(
    'Nilai Capaian Indikator (%)',
    max_digits=5, decimal_places=2, null=True, blank=True,
    help_text='Nilai realisasi capaian indikator mutu terkait saat evaluasi'
)
bukti_capaian = models.FileField(
    'Bukti Dokumen Capaian',
    upload_to='risiko/bukti_capaian/', null=True, blank=True,
    help_text='Dokumen pendukung capaian (laporan sensus harian, rekapitulasi, foto logbook)'
)

# ── Status Pelaksanaan Tindakan Rencana (Do) ──
STATUS_PELAKSANAAN_CHOICES = [
    ('DILAKUKAN', 'Dilakukan Seluruhnya'),
    ('SEBAGIAN', 'Dilakukan Sebagian'),
    ('TIDAK_DILAKUKAN', 'Tidak Dilakukan'),
]
status_pelaksanaan = models.CharField(
    'Status Pelaksanaan Tindakan',
    max_length=20, choices=STATUS_PELAKSANAAN_CHOICES, default='DILAKUKAN'
)

# ── Structured Fishbone RCA Categories ──
# Stored as JSON or structured text for backward-compatibility with existing SQLite / Postgres
rca_fishbone = models.JSONField(
    'Analisis Fishbone Terstruktur',
    default=dict, blank=True,
    help_text='Dict format: {"manpower": "...", "process": "...", "material": "...", "machine": "...", "environment": "...", "system": "..."}'
)

# ── RTL Structured Subfields ──
STATUS_RTL_CHOICES = [
    ('BELUM', 'Belum Dimulai'),
    ('PROSES', 'Dalam Proses'),
    ('SELESAI', 'Selesai'),
]
status_rtl = models.CharField(
    'Status RTL',
    max_length=15, choices=STATUS_RTL_CHOICES, default='BELUM'
)
deadline_rtl = models.DateField(
    'Target Waktu / Tenggat RTL',
    null=True, blank=True
)
bukti_rtl = models.FileField(
    'Bukti Dokumen Pelaksanaan RTL',
    upload_to='risiko/bukti_rtl/', null=True, blank=True,
    help_text='Bukti dokumen penyelesaian RTL (SPO revisi, sertifikat diklat, Berita Acara, dll)'
)
```

### 2.2 Helper Properties on `RisikoUnit`
- `capaian_status_badge`: Compares `capaian_nilai` against `indikator_mutu_terkait.target` or default 100%. Returns `tercapai` (green) or `tidak_tercapai` (danger/warning).
- `fishbone_display`: Returns formatted bullet list or dictionary of non-empty fishbone dimensions.
- `inherent_vs_residual_delta`: Computes score reduction ($S_{inherent} - S_{residual}$) to visually demonstrate risk mitigation effectiveness.

---

## 3. Detailed Component Plan

### Task 1: Database Migration (Schema Update)
1. Patch `akreditasi/risiko_models.py` with the new fields:
   - `capaian_nilai`, `bukti_capaian`
   - `status_pelaksanaan`
   - `rca_fishbone`
   - `status_rtl`, `deadline_rtl`, `bukti_rtl`
2. Run `.venv/Scripts/python manage.py makemigrations akreditasi`
3. Run `.venv/Scripts/python manage.py migrate akreditasi`
4. Verify migration backwards-compatibility with existing database rows.

### Task 2: Update Evaluation Form View (`Section G`) in `risiko_views.py` & `risiko_evaluasi.html`
1. Update `risiko_evaluasi` view to receive and save:
   - `capaian_nilai`, file `bukti_capaian`
   - `status_pelaksanaan`
   - Fishbone fields from POST: `rca_manpower`, `rca_process`, `rca_material`, `rca_machine`, `rca_environment`, `rca_system`
   - RTL fields: `rencana_tindak_lanjut`, `pj_rtl`, `deadline_rtl`, `status_rtl`, file `bukti_rtl`
2. Update `templates/akreditasi/risiko_evaluasi.html`:
   - Add **Sub-section G.0: Capaian Indikator Mutu** (Number input % + File upload `bukti_capaian` + Target reminder).
   - Add **Sub-section G.1: Status Pelaksanaan Tindakan (Do)** (Radio cards: *Dilakukan*, *Sebagian*, *Tidak Dilakukan*).
   - Add **Sub-section G.2: Structured Fishbone RCA** (6 categorized text boxes with placeholders matching hospital standards: Manpower, Process/Method, Material, Machine, Environment/Behavior, System + Quick AI Assist button).
   - Add **Sub-section G.3: Rencana Tindak Lanjut (RTL)** (Description + PIC + Target Deadline Datepicker + Status Badge Radio + File upload `bukti_rtl`).
   - Add `enctype="multipart/form-data"` to evaluation `<form>`.

### Task 3: Build Dedicated "Tabel Monitoring & Evaluasi Risiko" View & Template
1. Create new view `risiko_monitoring_evaluasi` in `akreditasi/risiko_views.py`:
   - URL: `/risiko/monitoring-evaluasi/` (and `/risiko/monitoring-evaluasi/<int:unit_id>/`)
   - Filtering: by `unit` (RBAC-scoped for unit heads/staff), `tahun` (2025/2026/2027), `status_rtl`, and `search`.
   - Aggregate calculation:
     - Total risks evaluated
     - % RTL Completed vs In-progress
     - Average risk reduction score
2. Create new template `templates/akreditasi/risiko_monitoring_evaluasi.html`:
   - **Header Card:** Summary KPIs (Total Risiko Dimonitor, Capaian Rata-rata, RTL Selesai, Risiko Terkendali).
   - **Filter Toolbar:** Unit dropdown, Tahun, Status RTL, Search, Tombol Cetak / Export.
   - **Main Table (Exact 6-column match to user's Word doc):**
     1. **No**
     2. **Indikator Mutu dan Target** (Nama Indikator, Target %, Kategori INM/IMP-RS/Unit, Unit Kerja)
     3. **Capaian Indikator Mutu** (Nilai %, Badge status vs Target, Link/Button "Lihat Bukti Capaian")
     4. **Pelaksanaan Tindakan setiap rencana** (Badge *Dilakukan*/*Tidak*, Ringkasan Rencana Aksi/Do, Link/Button "Lihat Bukti Pelaksanaan")
     5. **RCA (Root Cause Analysis)** (Structured Fishbone pills: Manpower, Process, Material, Machine, Environment, System, atau Analisis 5-Whys)
     6. **RTL (Rencana Tindak Lanjut)** (Uraian RTL, PIC, Deadline, Status Badge: Belum/Proses/Selesai, Link/Button "Lihat Bukti RTL", Tombol Quick Update / Edit Evaluasi)
     7. **Matriks Skor (Sebelum vs Sesudah)**: Visual badge skor inherent vs residual ($D \times P$).

### Task 4: Export to Excel / CSV & Print-Ready View
1. Add endpoint `/risiko/monitoring-evaluasi/export-csv/`:
   - Generates CSV/Excel compatible file with UTF-8 BOM encoding for seamless Microsoft Excel opening.
   - Formats all 6 columns cleanly with human-readable text and URLs to bukti files.
2. Add `@media print` CSS styling for crisp landscape A4 printout for Akreditasi surveyor packets.

### Task 5: Sidebar Navigation Integration
1. Update `templates/includes/sidebar.html`:
   - Under `Manajemen Risiko` section, add:
     - `Daftar Risiko PDCA` (`risiko_daftar`)
     - `Input Risiko Baru` (`risiko_input`)
     - **`Monitoring & Evaluasi (MONEV)`** (`risiko_monitoring_evaluasi`) — with icon `bi bi-clipboard2-data-fill`
     - `Laporan Manajemen Risiko` (`risiko_laporan`)
     - `Kajian FMEA & RCA Proaktif` (`risiko_fmea_rca`)

### Task 6: Seed Demonstration Data from User's Word Document
1. Seed the 3 real-world clinical risk examples from the Word document into the database if not present or as high-fidelity demo samples:
   - **Case 1 (IGD):** Waktu tanggap pelayanan gawat darurat $\le$ 5 menit (Target: 100%, Capaian: 82%, Dilakukan, RCA: Manpower/Process/Material, RTL: Audit kepatuhan 2 mingguan & evaluasi rasio beban kerja).
   - **Case 2 (Rawat Inap/Bangsal):** Kepatuhan identifikasi pasien sebelum tindakan medis (Target: 100%, Capaian: 88%, Dilakukan, RCA: Behavior/Environment, RTL: Monitoring Champion KPRS & reward/punishment).
   - **Case 3 (Rekam Medis / DPJP):** Kelengkapan pengisian Asesmen Awal Medis dalam 24 jam (Target: $\ge$ 95%, Capaian: 76%, Dilakukan, RCA: System/Behavior, RTL: Auto-lock resume & laporan mingguan Komite Medis).

---

## 4. Quality Gates & Verification Checklist

- [ ] **Data Integrity Gate:** Migrations run cleanly on local SQLite and Supabase PostgreSQL without data loss.
- [ ] **File Upload Gate:** Uploading PDF, JPG, PNG, and DOCX files for Capaian, Pelaksanaan, and RTL works up to 10MB; empty files do not break `full_clean()`.
- [ ] **Fishbone RCA Validation:** Structured RCA saves valid JSON / dictionary structure and gracefully handles empty categories.
- [ ] **RBAC Gate:** Unit-scoped users (`KEPALA_UNIT`, `STAF_NAKES`) only see their unit's monitoring data; `SUPER_ADMIN`, `KOMITE_MUTU`, and `DIREKTUR` see all units.
- [ ] **Regression Tests:** `tests_insiden` and `tests_security` continue to pass (11/11 tests).
- [ ] **Browser Verification:** Real Chromium execution verifies table rendering, interactive filters, modal/detail views, and export features on Vercel production.

---

## 5. Execution Order

1. **Step 1:** Apply Model Changes (`RisikoUnit` new fields) & create/apply Django migration.
2. **Step 2:** Update `akreditasi/risiko_views.py` (`risiko_evaluasi` and new `risiko_monitoring_evaluasi` view).
3. **Step 3:** Update URL routing in `akreditasi/urls.py`.
4. **Step 4:** Build `templates/akreditasi/risiko_monitoring_evaluasi.html` and update `risiko_evaluasi.html`.
5. **Step 5:** Add sidebar link in `templates/includes/sidebar.html`.
6. **Step 6:** Run tests & commit/push to master (Vercel deployment).
7. **Step 7:** Verify production on browser.
