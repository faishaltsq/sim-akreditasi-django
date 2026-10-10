# Implementation Plan: Clinical Risk Indicators Seeding & FMEA / RCA Deep Evaluation System

**Date:** 2026-10-09  
**Source Documents:**
1. `Downloads/Tolong ini diinputkan indicator resiko klinis.docx`
2. `Downloads/Buatkan tambahan menu di identifikasi resiko fmea dan RCA.docx`

---

## Executive Summary & Architecture

This plan delivers two tightly integrated capabilities for the hospital risk management & accreditation module (STARKES PMKP 7 & 8 / Standar 5.15):

1. **Clinical Risk & Quality Indicators Seeding for 9 Service Units**:
   - Seed authentic hospital operational data, issues, 45 clinical quality indicators (categorized into INM, IMP-RS, and IMP-Unit), and 45 specific clinical risks across 9 core service units:
     1. IGD (Emergency Room)
     2. ICU (Intensive Care Unit)
     3. ICCU (Intensive Coronary Care Unit)
     4. Rawat Jalan (Outpatient Clinic)
     5. Rawat Inap (Inpatient Ward)
     6. HD (Hemodialysis Unit)
     7. Laboratorium (Clinical Pathology & Blood Bank)
     8. VK (Delivery Room / PONEK)
     9. OK (Operating Theater / Central Surgery)
   - Stored in `IndikatorMutu` and `RisikoUnit` tables with automatic linkage.

2. **In-depth Evaluation Framework: FMEA & RCA (Section E & Navigation Hub)**:
   - **Form Extension (`risiko_form.html`)**: Add **Section E. HILIRAN METODE EVALUASI MENDALAM (FMEA & RCA)** below Section D:
     - **FMEA (Proactive Approach / Risk Management)**: For proactive prevention on high-priority processes (RPN calculation, failure modes, potential effects, FMEA team, target review).
     - **RCA (Reactive Approach / Incident Investigation)**: For reactive investigation of sentinel events, severe incidents (KTD), or persistent red/high risks (5-Whys / Fishbone analysis, RCA investigative team, corrective action plan).
     - **AI DeepSeek Assistance**: Integrated AI helpers for both FMEA failure mode generation and RCA 5-Whys root cause analysis.
   - **Navigation & Hub (`sidebar.html` & `/risiko/fmea-rca/`)**:
     - Dedicated navigation link in the sidebar under `Manajemen Risiko`.
     - FMEA & RCA Command Center / Register page listing proactive FMEA processes and reactive RCA incident investigations.
   - **Database Enhancements (`RisikoUnit`)**:
     - Add fields for `metode_evaluasi` (`STANDAR`, `FMEA`, `RCA`), `tim_evaluasi`, `akar_masalah_rca`, `failure_mode_fmea`, and `tindakan_korektif_rca`.
   - **Reporting & Detail Displays**:
     - Update `risiko_detail.html` and `risiko_laporan.html` to highlight FMEA / RCA findings and corrective workflows.

---

## User Review Required

> [!IMPORTANT]
> **Database Schema Migration**:
> We will add 5 nullable/defaulted fields to `RisikoUnit` for storing FMEA & RCA evaluation data:
> - `metode_evaluasi`: CharField with choices `STANDAR` (default), `FMEA`, `RCA`.
> - `tim_evaluasi`: CharField(255, blank=True).
> - `akar_masalah_rca`: TextField(blank=True).
> - `failure_mode_fmea`: TextField(blank=True).
> - `tindakan_korektif_rca`: TextField(blank=True).
>
> All fields have safe defaults or are optional, ensuring 100% backward compatibility with all existing risk records.

---

## Detailed Task Breakdown

### Task 1: Clinical Risk & Quality Indicators Seeding (9 Units)
**Objective**: Populate 45 clinical indicators and 45 clinical risks with operational issues and baseline data for the 9 specified hospital units.

- **Files affected**:
  - `akreditasi/management/commands/seed_clinical_risk_indicators.py` (New command)
  - `akreditasi/models.py` (Reference existing `IndikatorMutu`, `UnitKerja`)
  - `akreditasi/risiko_models.py` (Reference existing `RisikoUnit`)
- **Implementation steps**:
  1. Map the 9 operational unit names to existing `UnitKerja` IDs in the database:
     - `IGD` -> UnitKerja ID 13 (`IGD`)
     - `ICU` -> UnitKerja ID 21 (`ICU`)
     - `ICCU` -> UnitKerja ID 120 (`ICCU`)
     - `Rawat Jalan` -> UnitKerja ID 11 (`RAJAL`)
     - `Rawat Inap` -> UnitKerja ID 4 (`RANAP`)
     - `HD` -> UnitKerja ID 23 (`HD`)
     - `Laboratorium` -> UnitKerja ID 12 (`LAB`)
     - `VK` -> UnitKerja ID 19 (`VK`)
     - `OK` -> UnitKerja ID 20 (`IBS`)
  2. Create `seed_clinical_risk_indicators.py` management command with idempotent `get_or_create`:
     - **For each unit**:
       - Seed indicators into `IndikatorMutu`:
         - 🟢 INM (`jenis='NASIONAL'`)
         - 🔵 IMP-RS (`jenis='IMP_RS'`)
         - 🔴 IMP-Unit (`jenis='IMP_UNIT'`)
       - Seed 5 clinical risks into `RisikoUnit`:
         - `unit`: target UnitKerja
         - `tahun`: 2026, `periode`: `'TAHUNAN'`
         - `kategori_risiko`: `'KLINIS'`
         - `masalah`: Unit's authentic problem statement from docx
         - `data_pendukung`: Unit's baseline data / evidence
         - `jenis_risiko`: Specific clinical risk description
         - `deskripsi_risiko`: Detailed operational context
         - `dampak` & `probabilitas`: Clinical scoring (e.g., 4x4, 5x3)
         - `strategi_mitigasi`: `'HINDARI'` / `'KURANGI'`
         - `pj_mitigasi`: Head of unit / clinical coordinator
         - `indikator_mutu_terkait`: Foreign key to corresponding seeded indicator
         - `target_capaian_indikator`: Standard target (e.g. 100.00, 85.00)
  3. Run the command and verify records created in Supabase PostgreSQL database.

---

### Task 2: Data Model Migration for FMEA & RCA
**Objective**: Support deep evaluation tracking directly on `RisikoUnit`.

- **Files affected**:
  - `akreditasi/risiko_models.py`
  - `akreditasi/migrations/0031_add_fmea_rca_to_risikounit.py`
- **Implementation steps**:
  1. Add evaluation fields to `RisikoUnit`:
     ```python
     METODE_EVALUASI_CHOICES = [
         ('STANDAR', 'Standar Pemantauan PDCA'),
         ('FMEA', 'FMEA — Failure Mode and Effects Analysis (Proaktif)'),
         ('RCA', 'RCA — Root Cause Analysis (Reaktif)'),
     ]
     metode_evaluasi       = models.CharField('Metode Evaluasi Mendalam', max_length=10, choices=METODE_EVALUASI_CHOICES, default='STANDAR')
     tim_evaluasi          = models.CharField('Tim Evaluasi / Investigasi', max_length=255, blank=True)
     akar_masalah_rca      = models.TextField('Analisis Akar Masalah (RCA 5-Whys / Fishbone)', blank=True)
     failure_mode_fmea     = models.TextField('Mode Kegagalan & Efek Potensial (FMEA)', blank=True)
     tindakan_korektif_rca = models.TextField('Rencana Tindakan Korektif & Solusi Permanen', blank=True)
     ```
  2. Generate migration via `python manage.py makemigrations akreditasi --name add_fmea_rca_to_risikounit`.
  3. Execute `python manage.py migrate akreditasi` against production DB.

---

### Task 3: UI Enhancement: Section E in `risiko_form.html`
**Objective**: Add Section E. HILIRAN METODE EVALUASI MENDALAM (FMEA & RCA) to the risk input form with interactive selection and AI assistance.

- **Files affected**:
  - `templates/akreditasi/risiko_form.html`
  - `akreditasi/risiko_views.py` (Form save handler)
- **Implementation steps**:
  1. Add Section E container after Section D in `risiko_form.html`:
     - Title: `E. Hiliran Metode Evaluasi Mendalam (FMEA & RCA)`
     - Subtitle helper: Explaining proactive FMEA vs reactive RCA based on hospital risk severity.
     - Radio / Pill buttons to toggle evaluation mode:
       - `[Standar PDCA]` (Default)
       - `[FMEA Proaktif]` (Failure Mode and Effects Analysis)
       - `[RCA Reaktif]` (Root Cause Analysis - Kejadian Sentinel / KTD)
  2. Interactive conditional panels:
     - **When FMEA selected**:
       - Input for `tim_evaluasi` (Tim FMEA Multidisiplin)
       - Textarea for `failure_mode_fmea` (Identifikasi Mode Kegagalan & Potensi Dampak)
       - Quick AI Helper button: `✨ Rekomendasi Failure Mode FMEA (DeepSeek AI)`
     - **When RCA selected**:
       - Input for `tim_evaluasi` (Tim Investigasi RCA)
       - Textarea for `akar_masalah_rca` (Analisis 5-Whys / Diagram Fishbone)
       - Textarea for `tindakan_korektif_rca` (Rencana Tindakan Korektif & SPO Baru)
       - Quick AI Helper button: `✨ Analisis 5-Whys & Solusi RCA (DeepSeek AI)`
  3. Update `risiko_input` view in `risiko_views.py` to persist `metode_evaluasi`, `tim_evaluasi`, `failure_mode_fmea`, `akar_masalah_rca`, and `tindakan_korektif_rca`.

---

### Task 4: AI Endpoints for FMEA & RCA Generation
**Objective**: Provide automated AI assistance for FMEA failure mode brainstorming and RCA 5-Whys analysis.

- **Files affected**:
  - `akreditasi/ai_prompts.py`
  - `akreditasi/ai_views.py`
  - `akreditasi/urls.py`
  - `static/js/ai-assist.js` (or inline script in `risiko_form.html`)
- **Implementation steps**:
  1. Define prompt templates:
     - `PROMPT_FMEA_SUGGESTION`: Based on clinical risk and unit, suggest Failure Modes, Potential Causes, and Prevention Barriers.
     - `PROMPT_RCA_5WHYS`: Based on incident/problem and baseline data, suggest 5-Whys root cause progression and corrective actions.
  2. Add endpoints:
     - `POST /ai/risiko-fmea-saran/`
     - `POST /ai/risiko-rca-saran/`
  3. Wire frontend buttons to fetch and auto-fill the respective textareas.

---

### Task 5: Dedicated FMEA & RCA Hub & Sidebar Navigation
**Objective**: Provide a centralized management view for tracking FMEA proactive studies and RCA investigations across units.

- **Files affected**:
  - `templates/includes/sidebar.html`
  - `templates/akreditasi/risiko_fmea_rca.html` (New template)
  - `akreditasi/risiko_views.py` (New view: `risiko_fmea_rca`)
  - `akreditasi/urls.py`
- **Implementation steps**:
  1. Add sidebar menu item under `Manajemen Risiko`:
     - Title: `Metode FMEA & RCA`
     - Subtitle: `Evaluasi Proaktif & Reaktif`
     - Icon: `bi-diagram-3-fill`
  2. Create view `risiko_fmea_rca(request)`:
     - Displays two organized tabs:
       - **Tab 1: Kajian FMEA Proaktif** (Risiko-risiko prioritas tinggi dengan status FMEA).
       - **Tab 2: Investigasi RCA Reaktif** (Insiden sentinel / risiko kronis dengan investigasi 5-Whys).
     - Filter by Unit, Tahun, and Status.
     - Summary KPI cards: Total FMEA Aktif, Total RCA Selesai, Tindakan Korektif Berjalan.
     - Direct links to detail view, edit, and RDWOS evidence upload.

---

### Task 6: Update Risk Detail (`risiko_detail.html`) & Report (`risiko_laporan.html`)
**Objective**: Display Section E evaluation information in the comprehensive report and detail pages.

- **Files affected**:
  - `templates/akreditasi/risiko_detail.html`
  - `templates/akreditasi/risiko_laporan.html`
- **Implementation steps**:
  1. In `risiko_detail.html`:
     - If `risiko.metode_evaluasi != 'STANDAR'`, render a dedicated card:
       - Badge FMEA / RCA with color accent.
       - Tim Evaluasi, Mode Kegagalan / Akar Masalah 5-Whys, and Tindakan Korektif.
  2. In `risiko_laporan.html`:
     - Enhance Section 5 sub-section C/E to display a summary table of risks undergoing FMEA / RCA.

---

## Verification & Deployment Plan

### Automated Test Suite
- Write test case in `akreditasi/tests_fmea_rca.py`:
  1. Verify seeding command runs cleanly and populates 45 indicators + 45 risks without duplicates.
  2. Verify creating a risk with FMEA / RCA fields saves correctly.
  3. Verify FMEA & RCA hub view returns HTTP 200.
  4. Verify report page displays Section E data accurately.

### Manual / Browser Verification
- Login with `monsiskami`.
- Check `/risiko/baru/`:
  - Choose unit `IGD`: confirm seeded indicators appear in dropdown.
  - Verify Section E toggles (FMEA, RCA, Standar).
  - Test AI assistant button for FMEA and RCA.
- Check sidebar: click `Metode FMEA & RCA`.
- Check `/risiko/laporan/`: confirm 5-seksi report reflects unit indicators and evaluation status.
- Deploy to Vercel and verify live production endpoints.
